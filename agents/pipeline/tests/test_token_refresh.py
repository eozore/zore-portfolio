# -*- coding: utf-8 -*-
"""
Cobertura do token_refresh_job.

Por que existe: este job grava versões novas de segredo sem ninguém olhando,
e roda uma vez por semana. Um erro aqui só aparece 60 dias depois, na hora de
publicar — que é exatamente a falha que o job foi feito para evitar.

Os casos abaixo vêm do que se apurou em 27/08/2026 ao levantar os tokens:

  - o LinkedIn devolve um refresh token NOVO a cada troca e invalida o
    anterior. Não regravá-lo deixa o segredo com um refresh morto, e a falha
    só aparece na renovação seguinte;
  - o token do Instagram é de PÁGINA e devolve `expires_at: 0`. Tratar 0 como
    "vence agora" geraria alerta toda semana, e alerta que sempre grita deixa
    de ser lido;
  - o refresh token do YouTube não é renovável por código nenhum. O job tem
    que avisar, não tentar.
"""

import json
import time

import pytest

from token_refresh_job.job import TokenRefreshJob, _dias_restantes


# ── Duplos ────────────────────────────────────────────────────────────────────

class Cofre:
    """Secret Manager de mentira: guarda o que foi gravado para inspeção."""

    def __init__(self, inicial: dict[str, str]):
        self.dados = dict(inicial)
        self.gravacoes: list[tuple[str, str]] = []

    def ler(self, nome: str) -> str:
        return self.dados[nome]

    def gravar(self, nome: str, payload: str) -> None:
        self.dados[nome] = payload
        self.gravacoes.append((nome, payload))


def meta_valido(dias_para_vencer: float = 5.0) -> dict:
    return {
        "app_id": "1", "app_secret": "s",
        "instagram_token": "ig", "instagram_user_id": "10",
        "threads_token": "th", "threads_user_id": "20",
        "threads_token_expires_in": 5184000,
        "threads_token_saved_at": int(time.time() - (60 - dias_para_vencer) * 86400),
    }


def linkedin_valido(dias_para_vencer: float = 5.0) -> dict:
    return {
        "access_token": "velho", "refresh_token": "r-velho",
        "client_id": "c", "client_secret": "s",
        "expires_in": 5184000, "refresh_token_expires_in": 31536000,
        "saved_at": int(time.time() - (60 - dias_para_vencer) * 86400),
    }


def job(cofre: Cofre, **kw) -> TokenRefreshJob:
    return TokenRefreshJob(ler_segredo=cofre.ler, gravar_segredo=cofre.gravar, **kw)


# ── Janela de renovação ───────────────────────────────────────────────────────

def test_nao_renova_token_com_folga():
    """Renovar cedo demais queima uma troca à toa — e a Meta recusa < 24h."""
    cofre = Cofre({"meta-credentials": json.dumps(meta_valido(dias_para_vencer=50))})
    r = job(cofre).renovar_threads(meta_valido(dias_para_vencer=50))
    assert r.acao == "ok"
    assert cofre.gravacoes == []


def test_dias_restantes_sem_metadado_devolve_none():
    # Segredo sem saved_at/expires_in não é erro: é ausência de informação, e
    # o job precisa distinguir "não sei" de "vence hoje".
    assert _dias_restantes(None, 100) is None
    assert _dias_restantes(123, None) is None
    assert _dias_restantes("nao-numero", 100) is None


# ── LinkedIn ──────────────────────────────────────────────────────────────────

def test_linkedin_regrava_o_refresh_token_novo(monkeypatch):
    """
    Bug de produção esperando para acontecer: o LinkedIn invalida o refresh
    anterior a cada troca. Guardar só o access deixaria o próximo ciclo sem
    como renovar, 60 dias depois e longe da causa.
    """
    monkeypatch.setattr(
        "token_refresh_job.job._post_form",
        lambda url, dados: {
            "access_token": "novo", "expires_in": 5184000,
            "refresh_token": "r-novo", "refresh_token_expires_in": 31536000,
        },
    )
    cofre = Cofre({"linkedin-tokens": json.dumps(linkedin_valido())})
    r = job(cofre).renovar_linkedin(linkedin_valido())

    assert r.acao == "renovado"
    gravado = json.loads(cofre.gravacoes[0][1])
    assert gravado["access_token"] == "novo"
    assert gravado["refresh_token"] == "r-novo"


def test_linkedin_sem_refresh_token_alerta_em_vez_de_falhar():
    li = linkedin_valido()
    del li["refresh_token"]
    cofre = Cofre({"linkedin-tokens": json.dumps(li)})
    r = job(cofre).renovar_linkedin(li)
    assert r.acao == "alerta"
    assert cofre.gravacoes == []


def test_linkedin_com_refresh_vencido_nao_tenta_trocar():
    li = linkedin_valido()
    li["refresh_token_expires_in"] = 1          # venceu há muito
    cofre = Cofre({"linkedin-tokens": json.dumps(li)})
    r = job(cofre).renovar_linkedin(li)
    assert r.acao == "alerta"
    assert cofre.gravacoes == []


# ── Threads ───────────────────────────────────────────────────────────────────

def test_threads_renova_e_atualiza_o_metadado(monkeypatch):
    monkeypatch.setattr(
        "token_refresh_job.job._get_json",
        lambda url: {"access_token": "th-novo", "expires_in": 5184000},
    )
    cofre = Cofre({"meta-credentials": json.dumps(meta_valido())})
    m = meta_valido()
    antes = m["threads_token_saved_at"]
    r = job(cofre).renovar_threads(m)

    assert r.acao == "renovado"
    gravado = json.loads(cofre.gravacoes[0][1])
    assert gravado["threads_token"] == "th-novo"
    # Sem atualizar saved_at, o job renovaria de novo toda semana.
    assert gravado["threads_token_saved_at"] > antes


def test_threads_ja_vencido_nao_tenta_renovar(monkeypatch):
    """A Meta recusa refresh de token vencido — tentar só produz ruído."""
    monkeypatch.setattr(
        "token_refresh_job.job._get_json",
        lambda url: pytest.fail("não deveria chamar a API com token vencido"),
    )
    cofre = Cofre({"meta-credentials": json.dumps(meta_valido())})
    r = job(cofre).renovar_threads(meta_valido(dias_para_vencer=-3))
    assert r.acao == "alerta"


# ── Instagram ─────────────────────────────────────────────────────────────────

def test_instagram_com_expires_at_zero_e_ok_e_nao_alerta(monkeypatch):
    """
    `expires_at: 0` significa "não expira" para a Meta, não "expirou".
    Tratar como vencido geraria alerta semanal eterno.
    """
    monkeypatch.setattr(
        "token_refresh_job.job._get_json",
        lambda url: {"data": {"is_valid": True, "expires_at": 0, "type": "PAGE"}},
    )
    r = job(Cofre({})).verificar_instagram(meta_valido())
    assert r.acao == "ok"
    assert "não expira" in r.detalhe


def test_instagram_invalido_alerta(monkeypatch):
    monkeypatch.setattr(
        "token_refresh_job.job._get_json",
        lambda url: {"data": {"is_valid": False}},
    )
    r = job(Cofre({})).verificar_instagram(meta_valido())
    assert r.acao == "alerta"


# ── YouTube ───────────────────────────────────────────────────────────────────

def test_youtube_so_verifica_e_nunca_grava(monkeypatch):
    """Trocar o refresh token exige consentimento humano — o job não tenta."""
    monkeypatch.setattr(
        "token_refresh_job.job._post_form",
        lambda url, dados: {"access_token": "at"},
    )
    cofre = Cofre({})
    r = job(cofre).verificar_youtube("c", "s", "r")
    assert r.acao == "ok"
    assert cofre.gravacoes == []


def test_youtube_recusado_vira_alerta_com_o_comando_da_correcao(monkeypatch):
    def explode(url, dados):
        raise RuntimeError("invalid_grant")
    monkeypatch.setattr("token_refresh_job.job._post_form", explode)
    r = job(Cofre({})).verificar_youtube("c", "s", "r")
    assert r.acao == "alerta"
    assert "renew_token.py youtube" in r.detalhe


# ── Orquestração ──────────────────────────────────────────────────────────────

def test_um_provedor_quebrado_nao_impede_os_outros(monkeypatch):
    """
    O LinkedIn vencer não é motivo para o Threads não ser renovado. Antes de
    isolar por provedor, a primeira exceção encerrava a execução inteira.
    """
    monkeypatch.setattr(
        "token_refresh_job.job._get_json",
        lambda url: {"access_token": "th-novo", "expires_in": 5184000}
        if "refresh_access_token" in url
        else {"data": {"is_valid": True, "expires_at": 0}},
    )
    monkeypatch.setattr(
        "token_refresh_job.job._post_form",
        lambda url, dados: {"access_token": "at"},
    )
    cofre = Cofre({
        "meta-credentials": json.dumps(meta_valido()),
        "linkedin-tokens": "isto não é json",
        "youtube-oauth-client-id": "c",
        "youtube-oauth-client-secret": "s",
        "youtube-oauth-refresh-token": "r",
    })
    rel = job(cofre).run()
    acoes = {r.provedor: r.acao for r in rel.resultados}
    assert acoes["threads"] == "renovado"
    assert acoes["linkedin"] == "falha"
    assert acoes["youtube"] == "ok"


def test_alerta_nao_marca_o_job_como_falho(monkeypatch):
    """
    Alerta é o job funcionando: ele achou algo que só um humano resolve.
    Marcar como falha ensinaria a ignorar a execução vermelha.
    """
    monkeypatch.setattr(
        "token_refresh_job.job._get_json",
        lambda url: {"data": {"is_valid": False}},
    )
    monkeypatch.setattr(
        "token_refresh_job.job._post_form",
        lambda url, dados: {"access_token": "at"},
    )
    cofre = Cofre({
        "meta-credentials": json.dumps(meta_valido(dias_para_vencer=50)),
        "linkedin-tokens": json.dumps(linkedin_valido(dias_para_vencer=50)),
        "youtube-oauth-client-id": "c",
        "youtube-oauth-client-secret": "s",
        "youtube-oauth-refresh-token": "r",
    })
    rel = job(cofre).run()
    assert any(r.acao == "alerta" for r in rel.resultados)
    assert not rel.falhou


def test_dry_run_nao_grava_segredo(monkeypatch):
    monkeypatch.setattr(
        "token_refresh_job.job._get_json",
        lambda url: pytest.fail("dry-run não deveria chamar a API de renovação"),
    )
    cofre = Cofre({"meta-credentials": json.dumps(meta_valido())})
    r = job(cofre, dry_run=True).renovar_threads(meta_valido())
    assert r.acao == "renovado"
    assert "dry-run" in r.detalhe
    assert cofre.gravacoes == []
