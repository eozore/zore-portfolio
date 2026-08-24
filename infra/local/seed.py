# -*- coding: utf-8 -*-
"""
seed.py — Popula o Firestore emulado para o ambiente local.

Sem isto o Studio abre vazio: as skills padrão só são semeadas na primeira
leitura do agente, e os perfis dos agentes só existem depois de um ciclo.
Rodar este script deixa o ambiente pronto para você abrir e ver.

    docker compose -f docker-compose.local.yml exec cmo-agent python /app/seed.py
"""

import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("FIRESTORE_EMULATOR_HOST", "firestore:8080")

from tools import db                                    # noqa: E402
from skills.registry import carregar_skills, semear_agentes  # noqa: E402


def main() -> None:
    if db is None:
        print("Firestore indisponível — o emulador subiu?")
        sys.exit(1)

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
