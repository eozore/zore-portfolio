#!/usr/bin/env python3
"""
backfill_sessoes.py — popula o índice de sessões do Studio com o que já existe.

O índice (`studio_sessions`) passou a ser escrito a cada transição do grafo,
mas os ciclos ANTERIORES a ele não têm entrada — e sem entrada não aparecem na
biblioteca, que é justamente a tela criada para alcançá-los.

Reconstrói a partir do que já está gravado: `content_projects` tem
`session_id`, título e data. O que não dá para reconstruir é a `fase` do
grafo, que fica vazia — a biblioteca lida com isso, e abrir o projeto lê o
checkpoint de verdade.

    ./scripts/backfill_sessoes.py            # mostra o que faria
    ./scripts/backfill_sessoes.py --aplicar  # grava
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "cmo_agent"))


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    from google.cloud import firestore
    from sessoes_index import registrar

    db = firestore.Client(project="vazfy-417019")

    # Um projeto por sessão: o mais recente é a produção corrente.
    por_sessao: dict[str, dict] = {}
    for doc in db.collection("content_projects").stream():
        d = doc.to_dict() or {}
        sid = d.get("session_id")
        if not sid:
            continue
        atual = por_sessao.get(sid)
        if not atual or str(d.get("created_at", "")) > str(atual.get("created_at", "")):
            por_sessao[sid] = {**d, "__id": doc.id}

    existentes = {d.id for d in db.collection("studio_sessions").stream()}

    print(f"{len(por_sessao)} sessao(oes) com projeto; {len(existentes)} ja no indice.\n")
    for sid, proj in sorted(por_sessao.items(), key=lambda kv: str(kv[1].get("created_at", ""))):
        marca = "ja existe" if sid in existentes else ("GRAVA" if aplicar else "gravaria")
        print(f"  [{marca:9}] {sid[:14]}  {str(proj.get('title'))[:48]}")
        if sid in existentes or not aplicar:
            continue
        registrar(
            db, None, sid,
            tema             = str(proj.get("title") or ""),
            artigo_slug      = str(proj.get("article_slug") or ""),
            artigo_url       = str(proj.get("article_url") or ""),
            video_project_id = str(proj.get("__id") or ""),
        )

    if not aplicar:
        print("\nNada foi gravado. Rode com --aplicar.")


if __name__ == "__main__":
    main()
