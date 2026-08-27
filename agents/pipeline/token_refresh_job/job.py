# -*- coding: utf-8 -*-
"""
token_refresh_job/job.py
========================
Renova os tokens de publicação antes de vencerem, e alerta sobre os que
nenhum código pode renovar.

Por que existe: os tokens expiram sozinhos e a pipeline só descobria na hora
de publicar — depois de já ter gasto ElevenLabs e HeyGen no vídeo inteiro.
`scripts/check-credentials.sh` resolve isso para quem lembra de rodá-lo antes
de aprovar. Este job é a mesma verificação, sem depender de alguém lembrar.

O que dá e o que não dá para automatizar:

  Threads          ✅ `th_refresh_token` estende 60 dias, sem humano.
  LinkedIn         ✅ `refresh_token` troca por novo access de 60 dias.
  Instagram        —  o token é de PÁGINA e não expira. Só se verifica.
  YouTube          ❌ o access token o publisher já renova sozinho
                      (publisher_job/youtube_client.py). O que expira é o
                      REFRESH token, e trocá-lo exige consentimento humano no
                      navegador. Nenhum job resolve isso.

A causa do YouTube expirar em 7 dias é a tela de consentimento estar em
"Testing": autorização de test user vale 7 dias. Publicar o app em
"In production" remove o limite. Enquanto isso não for feito, o melhor que
este job faz é avisar ANTES, e é o que ele faz.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger("token_refresh_job")

# Renova quando faltar menos que isto. 15 dias dá margem para o job falhar
# algumas semanas seguidas (ele roda semanalmente) sem que o token morra.
DIAS_LIMITE_PADRAO = 15

# Abaixo disto, o que não é renovável vira alerta em nível de erro.
DIAS_ALERTA_PADRAO = 10

_TIMEOUT = 30


@dataclass
class Resultado:
    """O que aconteceu com um token. `acao` é o que o log e os testes leem."""
    provedor: str
    acao: str                      # renovado | ok | alerta | falha | ignorado
    dias_restantes: float | None = None
    detalhe: str = ""

    def __str__(self) -> str:
        d = f"{self.dias_restantes:.1f}d" if self.dias_restantes is not None else "—"
        return f"{self.provedor}: {self.acao} ({d}) {self.detalhe}".strip()


@dataclass
class Relatorio:
    resultados: list[Resultado] = field(default_factory=list)

    @property
    def falhou(self) -> bool:
        """Alerta NÃO é falha: o job fez o que podia. Falha é erro de execução."""
        return any(r.acao == "falha" for r in self.resultados)

    def resumo(self) -> str:
        return " | ".join(str(r) for r in self.resultados)


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_form(url: str, dados: dict) -> dict:
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(dados).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _dias_restantes(saved_at, expires_in) -> float | None:
    """Dias até vencer, ou None quando o segredo não guarda o metadado."""
    if saved_at in (None, "") or expires_in in (None, ""):
        return None
    try:
        return (float(saved_at) + float(expires_in) - time.time()) / 86400
    except (TypeError, ValueError):
        return None


class TokenRefreshJob:
    """
    Um método por provedor, cada um devolvendo um Resultado.

    `dry_run` percorre tudo e decide, mas não grava versão de segredo nenhuma
    — é como se confere o que o job FARIA sem consumir uma renovação.
    """

    def __init__(
        self,
        ler_segredo,
        gravar_segredo,
        dias_limite: int = DIAS_LIMITE_PADRAO,
        dias_alerta: int = DIAS_ALERTA_PADRAO,
        dry_run: bool = False,
    ) -> None:
        self.ler = ler_segredo
        self.gravar = gravar_segredo
        self.dias_limite = dias_limite
        self.dias_alerta = dias_alerta
        self.dry_run = dry_run

    # ── Threads ───────────────────────────────────────────────────────────
    def renovar_threads(self, meta: dict) -> Resultado:
        dias = _dias_restantes(
            meta.get("threads_token_saved_at"), meta.get("threads_token_expires_in")
        )
        if dias is not None and dias > self.dias_limite:
            return Resultado("threads", "ok", dias)

        # A janela de renovação da Meta tem PISO: um token com menos de 24h de
        # vida é recusado com "must be at least 24 hours old". Renovar cedo
        # demais é tão inválido quanto tarde demais.
        if dias is not None and dias < 0:
            return Resultado("threads", "alerta", dias,
                             "já vencido — refazer o consentimento")

        if self.dry_run:
            return Resultado("threads", "renovado", dias, "(dry-run)")

        try:
            resp = _get_json(
                "https://graph.threads.net/refresh_access_token?"
                + urllib.parse.urlencode({
                    "grant_type": "th_refresh_token",
                    "access_token": meta["threads_token"],
                })
            )
        except Exception as exc:
            return Resultado("threads", "falha", dias, str(exc)[:120])

        novo = resp.get("access_token")
        if not novo:
            return Resultado("threads", "falha", dias, f"sem access_token: {str(resp)[:100]}")

        meta["threads_token"] = novo
        meta["threads_token_expires_in"] = resp.get("expires_in", 5184000)
        meta["threads_token_saved_at"] = int(time.time())
        self.gravar("meta-credentials", json.dumps(meta))
        return Resultado("threads", "renovado",
                         float(meta["threads_token_expires_in"]) / 86400)

    # ── Instagram ─────────────────────────────────────────────────────────
    def verificar_instagram(self, meta: dict) -> Resultado:
        """
        Não renova: o token é de página e não expira.

        Mas "não expira" não é "não morre" — ele é derivado de um token de
        usuário, e some junto se esse for revogado, se a senha mudar ou se a
        permissão do app for retirada. Por isso se verifica em vez de confiar.
        """
        try:
            d = _get_json(
                "https://graph.facebook.com/debug_token?" + urllib.parse.urlencode({
                    "input_token": meta["instagram_token"],
                    "access_token": f"{meta['app_id']}|{meta['app_secret']}",
                })
            ).get("data", {})
        except Exception as exc:
            return Resultado("instagram", "falha", None, str(exc)[:120])

        if not d.get("is_valid"):
            return Resultado("instagram", "alerta", None,
                             "token inválido — refazer o consentimento da página")

        expira = d.get("expires_at")
        if expira in (0, None):
            return Resultado("instagram", "ok", None, "token de página, não expira")

        dias = (float(expira) - time.time()) / 86400
        if dias <= self.dias_alerta:
            return Resultado("instagram", "alerta", dias, "renovar à mão")
        return Resultado("instagram", "ok", dias)

    # ── LinkedIn ──────────────────────────────────────────────────────────
    def renovar_linkedin(self, li: dict) -> Resultado:
        dias = _dias_restantes(li.get("saved_at"), li.get("expires_in"))
        if dias is not None and dias > self.dias_limite:
            return Resultado("linkedin", "ok", dias)

        dias_refresh = _dias_restantes(li.get("saved_at"), li.get("refresh_token_expires_in"))
        if dias_refresh is not None and dias_refresh <= 0:
            return Resultado("linkedin", "alerta", dias,
                             "refresh token venceu — refazer o consentimento")

        if not li.get("refresh_token"):
            return Resultado("linkedin", "alerta", dias,
                             "sem refresh_token no segredo — refazer o consentimento")

        if self.dry_run:
            return Resultado("linkedin", "renovado", dias, "(dry-run)")

        try:
            resp = _post_form("https://www.linkedin.com/oauth/v2/accessToken", {
                "grant_type": "refresh_token",
                "refresh_token": li["refresh_token"],
                "client_id": li["client_id"],
                "client_secret": li["client_secret"],
            })
        except Exception as exc:
            return Resultado("linkedin", "falha", dias, str(exc)[:120])

        novo = resp.get("access_token")
        if not novo:
            return Resultado("linkedin", "falha", dias, f"sem access_token: {str(resp)[:100]}")

        li["access_token"] = novo
        li["expires_in"] = resp.get("expires_in", 5184000)
        # O LinkedIn devolve um refresh token NOVO a cada troca e invalida o
        # anterior. Não regravar o novo aqui deixaria o segredo com um refresh
        # já morto — a renovação seguinte falharia, 60 dias depois, longe da
        # causa.
        if resp.get("refresh_token"):
            li["refresh_token"] = resp["refresh_token"]
            li["refresh_token_expires_in"] = resp.get(
                "refresh_token_expires_in", li.get("refresh_token_expires_in")
            )
        li["saved_at"] = int(time.time())
        self.gravar("linkedin-tokens", json.dumps(li))
        return Resultado("linkedin", "renovado", float(li["expires_in"]) / 86400)

    # ── YouTube ───────────────────────────────────────────────────────────
    def verificar_youtube(self, client_id: str, client_secret: str,
                          refresh_token: str) -> Resultado:
        """
        Só verifica, porque só dá para verificar.

        Trocar o refresh token exige consentimento no navegador. O que este
        método faz é a única coisa útil possível: usar o refresh token e ver
        se ele ainda responde. Se não responder, o alerta chega antes de um
        vídeo ser produzido — que é o ponto.
        """
        try:
            resp = _post_form("https://oauth2.googleapis.com/token", {
                "client_id": client_id, "client_secret": client_secret,
                "refresh_token": refresh_token, "grant_type": "refresh_token",
            })
        except Exception as exc:
            return Resultado(
                "youtube", "alerta", None,
                f"refresh token recusado ({str(exc)[:60]}) — "
                "rode scripts/renew_token.py youtube",
            )
        if resp.get("access_token"):
            return Resultado("youtube", "ok", None, "refresh token responde")
        return Resultado("youtube", "alerta", None,
                         "sem access_token — rode scripts/renew_token.py youtube")

    # ── Orquestração ──────────────────────────────────────────────────────
    def run(self) -> Relatorio:
        rel = Relatorio()

        # Um provedor que explode não pode levar os outros junto: o LinkedIn
        # vencer não é motivo para o Threads não ser renovado.
        try:
            meta = json.loads(self.ler("meta-credentials"))
            rel.resultados.append(self.renovar_threads(meta))
            rel.resultados.append(self.verificar_instagram(meta))
        except Exception as exc:
            rel.resultados.append(Resultado("meta", "falha", None, str(exc)[:120]))

        try:
            li = json.loads(self.ler("linkedin-tokens"))
            rel.resultados.append(self.renovar_linkedin(li))
        except Exception as exc:
            rel.resultados.append(Resultado("linkedin", "falha", None, str(exc)[:120]))

        try:
            rel.resultados.append(self.verificar_youtube(
                self.ler("youtube-oauth-client-id").strip(),
                self.ler("youtube-oauth-client-secret").strip(),
                self.ler("youtube-oauth-refresh-token").strip(),
            ))
        except Exception as exc:
            rel.resultados.append(Resultado("youtube", "falha", None, str(exc)[:120]))

        for r in rel.resultados:
            nivel = {"alerta": logging.ERROR, "falha": logging.ERROR}.get(r.acao, logging.INFO)
            logger.log(nivel, "[token-refresh] %s", r)
        return rel
