"""
tests/test_thumbnail.py
=======================
A capa do YouTube tem que caber no quadro.

A thumbnail do vídeo de 27/08 saiu com o TÍTULO inteiro — 63 caracteres —
em corpo de 120px, vazando por cima e por baixo dos 720px. Duas causas
somadas:

  1. o publisher passava `title` para o gerador, em vez de uma frase de capa.
     As capas que o canal usa trazem 2 a 5 palavras ("O ERRO MAIS CARO DE
     ML"); o título fica ao lado do vídeo, onde já é lido;
  2. o corpo da fonte era escolhido pelo comprimento da PRIMEIRA palavra.
     Com "O que é harness…", a primeira palavra é "O" — 1 caractere — e a
     tabela devolvia 120px para as outras 58 letras.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from publisher_job.thumbnail_generator import _build_youtube_html, _linhas_da_frase  # noqa: E402


def test_frase_curta_vira_ate_tres_linhas():
    assert _linhas_da_frase("O ERRO MAIS CARO DE ML") == ["O ERRO", "MAIS CARO", "DE ML"]


def test_duas_palavras_ficam_em_uma_linha():
    assert _linhas_da_frase("HARNESS EXPLICADO") == ["HARNESS EXPLICADO"]


def test_linhas_sao_equilibradas_por_caractere():
    """
    Equilibrar por CONTAGEM DE PALAVRAS produzia "SUA IA" ao lado de "VAI
    QUEBRAR" — mesmo número de palavras, larguras muito diferentes. A linha
    larga estourava o bloco e quebrava sozinha, virando quatro linhas.
    """
    linhas = _linhas_da_frase("SUA IA VAI QUEBRAR TUDO")
    assert len(linhas) <= 3
    maior, menor = max(map(len, linhas)), min(map(len, linhas))
    assert maior - menor <= 10


def test_frase_vazia_nao_explode():
    assert _linhas_da_frase("   ") == []


def test_template_trava_a_quebra_de_linha():
    """
    Sem `nowrap` a linha nunca excede a largura do bloco, o ajuste automático
    não vê excesso nenhum e a frase sai empilhada em mais linhas do que o
    previsto — desmontando a composição em vez de encolher a fonte.
    """
    html = _build_youtube_html("", "O ERRO MAIS CARO DE ML", "apoio", "")
    assert "white-space:nowrap" in html


def test_template_ajusta_a_fonte_por_medicao():
    """
    A tabela por faixa de comprimento é o que deixou 120px para um título de
    63 caracteres. O ajuste tem que medir o texto renderizado.
    """
    html = _build_youtube_html("", "O QUE É HARNESS E COMO USAR CORRETAMENTE", "x", "")
    assert "scrollWidth" in html and "clientWidth" in html


def test_titulo_longo_nao_gera_mais_de_tres_linhas():
    """Mesmo no pior caso a composição não vira uma parede de texto."""
    longo = "O que é harness e como usar corretamente no desenvolvimento com IA"
    assert len(_linhas_da_frase(longo)) <= 3
