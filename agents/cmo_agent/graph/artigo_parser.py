# -*- coding: utf-8 -*-
"""
artigo_parser.py — Separa metadado de corpo no artigo gerado.

O redator emite frontmatter YAML no topo (`série:`, `título:`, `slug:`,
`descricao:`, `data:`) e, às vezes, um bloco `META: {...}` no fim. Nada disso
é corpo de artigo — mas o nó do grafo guardava o texto inteiro num campo só, e
a tela de revisão renderizava o frontmatter como um parágrafo com os nomes dos
campos embolados no meio da prosa.

A correção não é esconder: é EXTRAIR. Título, slug e descrição são dados que
a plataforma precisa (URL do post, meta description, título do vídeo) e que
hoje eram descartados junto.
"""

from __future__ import annotations

import json
import re
from typing import Any


def _limpa_valor(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v.strip()


def separar(markdown: str) -> tuple[str, dict[str, Any]]:
    """
    Devolve (corpo, metadados).

    Lida com o que o modelo realmente produz, não com o que o prompt pede:
      - frontmatter YAML delimitado por `---`
      - bloco `META: {json}` na última linha
      - H1 repetindo o título logo depois do frontmatter
    """
    texto = (markdown or "").strip()
    meta: dict[str, Any] = {}

    # ── Frontmatter YAML ──────────────────────────────────────────────────────
    if texto.startswith("---"):
        fim = texto.find("\n---", 3)
        if fim != -1:
            bloco = texto[3:fim]
            texto = texto[fim + 4:].lstrip()
            for linha in bloco.splitlines():
                if ":" not in linha:
                    continue
                chave, valor = linha.split(":", 1)
                chave = chave.strip().lower()
                # Normaliza os nomes que o modelo alterna entre acentuado e não.
                chave = {"título": "titulo", "descrição": "descricao",
                         "série": "serie"}.get(chave, chave)
                meta[chave] = _limpa_valor(valor)

    # ── Bloco META no fim ─────────────────────────────────────────────────────
    m = re.search(r"^META:\s*(\{.*\})\s*$", texto, re.M | re.S)
    if m:
        try:
            meta.update(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass
        texto = texto[: m.start()].rstrip()

    # ── H1 duplicado ──────────────────────────────────────────────────────────
    # O primeiro H1 repete o título que já aparece no cabeçalho da tela de
    # revisão. Mostrar duas vezes empurra o conteúdo para baixo e faz o
    # revisor rolar antes de ler qualquer coisa nova.
    linhas = texto.lstrip().splitlines()
    if linhas and linhas[0].startswith("# "):
        h1 = linhas[0][2:].strip()
        meta.setdefault("titulo", h1)
        texto = "\n".join(linhas[1:]).lstrip()

    return texto.strip(), meta
