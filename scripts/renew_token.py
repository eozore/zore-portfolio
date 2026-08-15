#!/usr/bin/env python3
"""
renew_token.py — renova os tokens OAuth que exigem consentimento do dono da conta.

    ./scripts/renew_token.py youtube
    ./scripts/renew_token.py threads

O que o script faz: monta a URL de consentimento correta, sobe um servidor
local para capturar o redirect, troca o código pelo token de longa duração,
grava no Secret Manager e testa contra a API.

O que VOCÊ faz: clicar no link, escolher a conta e aprovar. O login é seu e
acontece só no seu navegador — o script nunca vê sua senha.

Por que existe: tokens de publicação expiram sozinhos (YouTube ~7 dias se a
tela de consentimento estiver em "Testing", Meta 60 dias) e a pipeline só
descobre na hora de publicar, depois de já ter gasto créditos de ElevenLabs e
HeyGen gerando o vídeo inteiro.

PRÉ-REQUISITO — a URI de redirect precisa estar registrada no app:
  YouTube  Google Cloud Console -> APIs & Services -> Credentials -> seu
           OAuth client -> Authorized redirect URIs -> http://localhost:8080/
  Threads  developers.facebook.com -> seu app -> Use cases -> Threads ->
           Settings -> Redirect Callback URLs -> http://localhost:8080/
"""

from __future__ import annotations

import http.server
import json
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

PROJECT = "vazfy-417019"
DEFAULT_PORT = 8080

_captured: dict[str, str] = {}


def redirect_uri_for(port: int) -> str:
    """
    A barra final importa: o Google compara a redirect_uri caractere a
    caractere. "http://localhost:8080" e "http://localhost:8080/" são URIs
    diferentes para ele, e a divergência aparece como redirect_uri_mismatch.
    Registre no console exatamente a string que este script imprime.
    """
    return f"http://localhost:{port}/"


# ── Secret Manager ────────────────────────────────────────────────────────────

def sec_get(name: str) -> str:
    return subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest",
         f"--secret={name}", f"--project={PROJECT}"],
        capture_output=True, text=True, check=True,
    ).stdout


def sec_add(name: str, payload: str) -> None:
    proc = subprocess.run(
        ["gcloud", "secrets", "versions", "add", name,
         f"--project={PROJECT}", "--data-file=-"],
        input=payload, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"falha ao gravar {name}: {proc.stderr.strip()}")
    print(f"  gravado: {proc.stdout.strip() or name}")


# ── Captura do redirect ───────────────────────────────────────────────────────

class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _captured.update({k: v[0] for k, v in qs.items()})
        ok = "code" in _captured
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = ("<h2>Pronto. Pode fechar esta aba e voltar ao terminal.</h2>"
               if ok else
               f"<h2>Nao veio codigo</h2><pre>{json.dumps(_captured, indent=2)}</pre>")
        self.write_safe(f"<html><body style='font-family:sans-serif;padding:40px'>{msg}</body></html>")

    def write_safe(self, html: str) -> None:
        try:
            self.wfile.write(html.encode())
        except BrokenPipeError:
            pass

    def log_message(self, *_):  # silencia o log do servidor
        pass


class _Server(http.server.HTTPServer):
    # Sem isto, o socket em TIME_WAIT de uma execução anterior bloqueia o bind
    # por ~60s e o script falha com "Address already in use".
    allow_reuse_address = True


def _port_owner(port: int) -> str:
    """Quem está segurando a porta — a mensagem de erro precisa dizer isso."""
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().splitlines()
        return out[1] if len(out) > 1 else "(desconhecido)"
    except Exception:
        return "(não consegui identificar)"


def await_code(auth_url: str, redirect_uri: str, port: int, timeout_s: int = 300) -> str:
    try:
        server = _Server(("localhost", port), _Handler)
    except OSError as exc:
        raise SystemExit(
            f"\n  A porta {port} está ocupada e o script precisa dela para receber o\n"
            f"  redirect do consentimento.\n\n"
            f"  Quem está usando:\n    {_port_owner(port)}\n\n"
            f"  Se for uma execução anterior deste script que ficou presa, encerre com:\n"
            f"    lsof -nP -iTCP:{port} -sTCP:LISTEN -t | xargs kill\n\n"
            f"  Ou use outra porta (lembre de registrá-la no app):\n"
            f"    {sys.argv[0]} {sys.argv[1]} --port 8081\n\n"
            f"  (detalhe do SO: {exc})"
        ) from None

    threading.Thread(target=server.serve_forever, daemon=True).start()

    # SIGTERM (kill, timeout, fechar o terminal) não vira KeyboardInterrupt.
    # Sem este handler o processo morria sem passar pelo finally e deixava a
    # porta presa — exatamente o que fazia a execução seguinte falhar com
    # "Address already in use".
    def _on_term(_sig, _frm):
        try:
            server.server_close()
        finally:
            raise SystemExit("\n  Encerrado.")
    signal.signal(signal.SIGTERM, _on_term)

    print(f"\n  Servidor local escutando em {redirect_uri}")
    print("\n  Abra este link, escolha a conta e aprove:\n")
    print(f"    {auth_url}\n")
    try:
        webbrowser.open(auth_url)
        print("  (tentei abrir no seu navegador automaticamente)\n")
    except Exception:
        pass
    print("  Ctrl-C cancela sem deixar a porta presa.\n")

    # try/finally: qualquer saída — sucesso, timeout ou Ctrl-C — libera a porta.
    # Antes, um erro no navegador deixava este processo vivo por 300s segurando
    # a 8080, e a execução seguinte falhava com "Address already in use".
    try:
        deadline = time.time() + timeout_s
        while "code" not in _captured and "error" not in _captured and time.time() < deadline:
            time.sleep(1)
    except KeyboardInterrupt:
        raise SystemExit("\n  Cancelado.") from None
    finally:
        server.shutdown()
        server.server_close()

    if "error" in _captured:
        raise SystemExit(
            f"\n  O provedor recusou: {_captured['error']}\n"
            f"  {_captured.get('error_description', '')}"
        )
    if "code" not in _captured:
        raise SystemExit(
            f"\n  Nenhum código recebido em {timeout_s}s.\n"
            f"  A causa quase sempre é a redirect URI não registrada. Registre\n"
            f"  EXATAMENTE esta string no app (o Google compara caractere a\n"
            f"  caractere, inclusive a barra final):\n\n    {redirect_uri}\n"
        )
    return _captured["code"]


def post_form(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


# ── YouTube ───────────────────────────────────────────────────────────────────

def renew_youtube(port: int) -> None:
    redirect_uri = redirect_uri_for(port)
    client_id = sec_get("youtube-oauth-client-id").strip()
    client_secret = sec_get("youtube-oauth-client-secret").strip()

    print("\n  ANTES DE CONTINUAR — esta URI precisa estar registrada em")
    print("  console.cloud.google.com -> APIs & Services -> Credentials ->")
    print(f"  seu OAuth client -> Authorized redirect URIs:\n\n    {redirect_uri}\n")

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload "
                 "https://www.googleapis.com/auth/youtube.readonly",
        # offline + consent sao obrigatorios para vir refresh_token; sem
        # prompt=consent o Google reaproveita o grant e devolve so o access.
        "access_type": "offline",
        "prompt": "consent",
    })

    code = await_code(auth_url, redirect_uri, port)
    print("  codigo recebido, trocando por tokens...")
    tok = post_form("https://oauth2.googleapis.com/token", {
        "code": code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": redirect_uri, "grant_type": "authorization_code",
    })

    refresh = tok.get("refresh_token")
    if not refresh:
        raise SystemExit("  Google nao devolveu refresh_token. Revogue o acesso em "
                         "myaccount.google.com/permissions e rode de novo.")

    sec_add("youtube-oauth-refresh-token", refresh)

    ch = get_json("https://www.googleapis.com/youtube/v3/channels"
                  f"?part=snippet&mine=true&access_token={tok['access_token']}")
    items = ch.get("items") or []
    print(f"  canal autorizado: {items[0]['snippet']['title'] if items else '(nenhum)'}")


# ── Threads ───────────────────────────────────────────────────────────────────

def renew_threads(port: int) -> None:
    redirect_uri = redirect_uri_for(port)
    creds = json.loads(sec_get("meta-credentials"))
    app_id, app_secret = creds["app_id"], creds["app_secret"]

    print("\n  ANTES DE CONTINUAR — esta URI precisa estar registrada em")
    print("  developers.facebook.com -> seu app -> Use cases -> Threads ->")
    print(f"  Settings -> Redirect Callback URLs:\n\n    {redirect_uri}\n")

    auth_url = "https://threads.net/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": "threads_basic,threads_content_publish",
        "response_type": "code",
    })

    code = await_code(auth_url, redirect_uri, port)
    print("  codigo recebido, trocando por token curto...")
    short = post_form("https://graph.threads.net/oauth/access_token", {
        "client_id": app_id, "client_secret": app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri, "code": code,
    })

    # O token curto vale 1h; a pipeline precisa do longo (60 dias).
    print("  trocando por token longo (60 dias)...")
    long = get_json("https://graph.threads.net/access_token?" + urllib.parse.urlencode({
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": short["access_token"],
    }))

    creds["threads_token"] = long["access_token"]
    if short.get("user_id"):
        creds["threads_user_id"] = str(short["user_id"])
    sec_add("meta-credentials", json.dumps(creds))

    me = get_json(f"https://graph.threads.net/v1.0/{creds['threads_user_id']}"
                  f"?fields=username&access_token={long['access_token']}")
    print(f"  conta autorizada: @{me.get('username','?')}")
    print(f"  validade: ~{round(long.get('expires_in', 0) / 86400)} dias")


# ── Entrada ───────────────────────────────────────────────────────────────────

TARGETS = {"youtube": renew_youtube, "threads": renew_threads}

if __name__ == "__main__":
    args = sys.argv[1:]
    port = DEFAULT_PORT
    if "--port" in args:
        i = args.index("--port")
        try:
            port = int(args[i + 1])
        except (IndexError, ValueError):
            raise SystemExit("  --port precisa de um número. Ex: --port 8081")
        del args[i:i + 2]

    if len(args) != 1 or args[0] not in TARGETS:
        print(__doc__)
        print(f"Uso: {sys.argv[0]} [{'|'.join(TARGETS)}] [--port N]")
        raise SystemExit(1)

    target = args[0]
    print(f"\n=== Renovando token: {target} ===")
    TARGETS[target](port)
    print("\n  Feito. Confirme com: ./scripts/check-credentials.sh\n")
