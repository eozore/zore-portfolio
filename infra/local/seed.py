# -*- coding: utf-8 -*-
"""
seed.py — Prepara o Firestore e o Pub/Sub emulados para o ambiente local.

Sem isto o Studio abre vazio: as skills padrão só são semeadas na primeira
leitura do agente, e os perfis dos agentes só existem depois de um ciclo.
Rodar este script deixa o ambiente pronto para você abrir e ver.

Cria também os topics do Pub/Sub. O emulador sobe sem topic nenhum, e o gate
do vídeo publica em `content-pipeline.package-approved` — sem o topic ele
falha com `5 NOT_FOUND: Topic not found` e ABORTA a aprovação, que é o
comportamento correto em produção (aprovar sem produzir já gerou um pacote
"concluído" sem vídeo). O efeito colateral era que o gate do vídeo nunca
podia ser exercitado localmente.

    docker compose -f docker-compose.local.yml exec cmo-agent python /app/seed.py
"""

import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "firestore:8080")

from tools import db                                    # noqa: E402
from skills.registry import carregar_skills, semear_agentes  # noqa: E402

# Espelham infra/pipeline/main.tf. Nenhum consumidor roda localmente: o que se
# valida aqui é que o gate publica e devolve um projectId, não a produção do
# vídeo — essa depende dos Cloud Run Jobs e só existe no ambiente real.
TOPICS = (
    "content-pipeline.package-requested",
    "content-pipeline.package-approved",
    "content-pipeline.tts-completed",
    "content-pipeline.avatar-completed",
    "content-pipeline.video-ready",
    "content-pipeline.vertical-cut",
    "content-pipeline.dead-letter",
)


def semear_topics() -> None:
    """
    Cria os topics via REST, e não com `google-cloud-pubsub`.

    O cmo-agent não publica em Pub/Sub — quem publica é o Next.js — então a
    biblioteca não está na imagem, e colocá-la só para este script seria
    carregar uma dependência de produção por causa do ambiente local. O
    emulador aceita `PUT /v1/projects/{p}/topics/{t}`, que resolve com a
    stdlib.
    """
    host = os.environ.get("PUBSUB_EMULATOR_HOST")
    if not host:
        print("PUBSUB_EMULATOR_HOST não definida — pulando topics.")
        return

    import json
    import urllib.error
    import urllib.request

    projeto = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")
    criados = existiam = 0
    for nome in TOPICS:
        url = f"http://{host}/v1/projects/{projeto}/topics/{nome}"
        req = urllib.request.Request(
            url, method="PUT", data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10).read()
            criados += 1
        except urllib.error.HTTPError as exc:
            if exc.code == 409:      # ALREADY_EXISTS
                existiam += 1
            else:
                print(f"  topic {nome}: HTTP {exc.code} {exc.read()[:120]!r}")
        except Exception as exc:
            print(f"  topic {nome}: {exc}")
    print(f"topics: {criados} criado(s), {existiam} já existia(m)")


def main() -> None:
    if db is None:
        print("Firestore indisponível — o emulador subiu?")
        sys.exit(1)

    semear_topics()

    semear_agentes(db, None)
    skills = carregar_skills(db, None)

    agentes = list(db.collection("agents").stream())
    print(f"agentes semeados: {len(agentes)}")
    for a in agentes:
        d = a.to_dict() or {}
        print(f"  {a.id:14} {d.get('nome','')}  (skills: {', '.join(d.get('skills') or []) or '—'})")

    por_categoria: dict[str, int] = {}
    for s in skills:
        por_categoria[s.get("categoria", "?")] = por_categoria.get(s.get("categoria", "?"), 0) + 1
    print(f"\nskills semeadas: {len(skills)}")
    for cat, n in sorted(por_categoria.items()):
        print(f"  {cat:8} {n}")

    print("\nknowledge base: vazia, como esperado — ela ganha conteúdo quando "
          "você subir material ou quando os agentes analistas existirem.")


if __name__ == "__main__":
    main()
