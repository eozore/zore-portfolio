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
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

PROJECT = "vazfy-417019"
PORT = 8080
REDIRECT_URI = f"http://localhost:{PORT}/"

_captured: dict[str, str] = {}


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


def await_code(auth_url: str, timeout_s: int = 300) -> str:
    server = http.server.HTTPServer(("localhost", PORT), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("\n  Abra este link, escolha a conta e aprove:\n")
    print(f"    {auth_url}\n")
    try:
        webbrowser.open(auth_url)
        print("  (tentei abrir no seu navegador automaticamente)\n")
    except Exception:
        pass

    deadline = time.time() + timeout_s
    while "code" not in _captured and time.time() < deadline:
        time.sleep(1)
    server.shutdown()

    if "code" not in _captured:
        raise SystemExit(f"  Nenhum codigo recebido em {timeout_s}s. "
                         f"Confira se {REDIRECT_URI} esta registrada no app.")
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

def renew_youtube() -> None:
    client_id = sec_get("youtube-oauth-client-id").strip()
    client_secret = sec_get("youtube-oauth-client-secret").strip()

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload "
                 "https://www.googleapis.com/auth/youtube.readonly",
        # offline + consent sao obrigatorios para vir refresh_token; sem
        # prompt=consent o Google reaproveita o grant e devolve so o access.
        "access_type": "offline",
        "prompt": "consent",
    })

    code = await_code(auth_url)
    print("  codigo recebido, trocando por tokens...")
    tok = post_form("https://oauth2.googleapis.com/token", {
        "code": code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code",
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

def renew_threads() -> None:
    creds = json.loads(sec_get("meta-credentials"))
    app_id, app_secret = creds["app_id"], creds["app_secret"]

    auth_url = "https://threads.net/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "scope": "threads_basic,threads_content_publish",
        "response_type": "code",
    })

    code = await_code(auth_url)
    print("  codigo recebido, trocando por token curto...")
    short = post_form("https://graph.threads.net/oauth/access_token", {
        "client_id": app_id, "client_secret": app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI, "code": code,
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
    if len(sys.argv) != 2 or sys.argv[1] not in TARGETS:
        print(__doc__)
        print(f"Uso: {sys.argv[0]} [{'|'.join(TARGETS)}]")
        raise SystemExit(1)

    target = sys.argv[1]
    print(f"\n=== Renovando token: {target} ===")
    TARGETS[target]()
    print("\n  Feito. Confirme com: ./scripts/check-credentials.sh\n")
