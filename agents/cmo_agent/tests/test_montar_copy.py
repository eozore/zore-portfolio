"""
tests/test_montar_copy.py
==========================
A copy de cada peça social precisa levar o CTA — e o gancho uma vez só.

Dois defeitos que as 51 peças de 27/08 carregaram, e que só apareceram olhando
o que foi para a fila:

1. **O CTA sumia.** O agente escolhe o tipo peça a peça (assistir, salvar,
   marcar, comentar…), o schema valida a mistura no plano — e `cta.texto`
   nunca entrava na copy. 48 das 51 peças foram publicadas sem pedir nada.
2. **O gancho aparecia duas vezes.** O modelo devolve `corpo` já começando
   pelo gancho, e o código o prefixava de novo: o post do LinkedIn abria
   repetindo a mesma frase palavra por palavra.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from social_publish import montar_copy  # noqa: E402


def test_cta_entra_na_copy():
    saida = montar_copy("Gancho.", "Corpo do post.", {"texto": "Salve para depois."})
    assert "Salve para depois." in saida


def test_gancho_nao_e_repetido_quando_o_corpo_ja_comeca_por_ele():
    """O caso exato do LinkedIn de 27/08."""
    g = "A maior parte dos testes de IA não passa de tentativa e erro."
    saida = montar_copy(g, f"{g} Sem automação, cada atualização quebra o produto.", None)
    assert saida.count("A maior parte dos testes") == 1


def test_gancho_e_corpo_distintos_ficam_os_dois():
    saida = montar_copy("Gancho curto.", "Desenvolvimento diferente.", None)
    assert "Gancho curto." in saida and "Desenvolvimento diferente." in saida


def test_cta_ja_presente_no_corpo_nao_duplica():
    saida = montar_copy(None, "Texto. Salve este post.", {"texto": "Salve este post."})
    assert saida.lower().count("salve este post") == 1


def test_hashtags_ficam_por_ultimo():
    saida = montar_copy("G.", "C.", {"texto": "Comente."}, ["ia", "#mlops"])
    assert saida.strip().endswith("#ia #mlops")


def test_partes_vazias_nao_deixam_linhas_soltas():
    assert montar_copy(None, "Só o corpo.", None) == "Só o corpo."
    assert montar_copy("", "", None) == ""


def test_hashtag_com_e_sem_cerquilha_normaliza():
    saida = montar_copy(None, "C.", None, ["ia", "#ia2"])
    assert "#ia #ia2" in saida
