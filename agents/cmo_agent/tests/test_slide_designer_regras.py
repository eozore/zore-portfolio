"""
tests/test_slide_designer_regras.py
====================================
O slide não pode exibir a própria narração.

Regressão do vídeo de 27/08/2026: o slide `yt-02` trazia a locução inteira
entre aspas num elemento `.footer-script`. O espectador lia e ouvia a mesma
frase ao mesmo tempo — atenção dividida sem ganho nenhum.

O prompt passou a proibir explicitamente, mas regra em prompt é sugestão: o
modelo pode ignorar e nada acusa. Esta checagem é o que barra de fato, e faz o
designer tentar de novo em vez de gravar o slide errado.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slide_designer_agent import _narracao_vazou_para_a_tela  # noqa: E402

FALA = (
    "Hoje nós vamos destrinchar um dos conceitos mais críticos da engenharia "
    "de IA moderna: o harness. Vamos ver como essa camada de infraestrutura "
    "transforma a estocasticidade dos modelos em código determinístico."
)


def test_narracao_inteira_no_rodape_e_barrada():
    """A forma exata em que o defeito foi a produção."""
    html = f'<div class="slide-container"><div class="footer-script">"{FALA}"</div></div>'
    assert _narracao_vazou_para_a_tela(html, FALA)


def test_trecho_longo_da_fala_tambem_e_barrado():
    html = "<div>engenharia de IA moderna: o harness. Vamos ver como essa camada</div>"
    assert _narracao_vazou_para_a_tela(html, FALA)


def test_slide_legitimo_passa():
    """Diagrama e remate curto: diz o que a fala não diz."""
    html = (
        '<div class="badge-tag">Arquitetura de harness</div>'
        '<div class="col-text">Estocástico vira determinístico</div>'
        '<div class="footer-note">cada chamada deixa de ser aposta</div>'
    )
    assert not _narracao_vazou_para_a_tela(html, FALA)


def test_termo_tecnico_repetido_nao_e_vazamento():
    """
    Repetir "harness" ou "estocasticidade" na tela é esperado e legítimo — o
    slide fala do mesmo assunto. O que não pode é a FRASE inteira.
    """
    html = '<div class="titulo">harness</div><div class="sub">estocasticidade</div>'
    assert not _narracao_vazou_para_a_tela(html, FALA)


def test_texto_dentro_de_style_nao_conta():
    """CSS não é visível — não pode gerar falso positivo."""
    html = f"<style>/* {FALA} */</style><div>Diagrama</div>"
    assert not _narracao_vazou_para_a_tela(html, FALA)


def test_script_curto_nao_dispara():
    """Fala curta demais não dá para distinguir de conteúdo legítimo."""
    assert not _narracao_vazou_para_a_tela("<div>ok</div>", "ok")


def test_quebra_de_linha_e_tag_no_meio_nao_escondem_o_vazamento():
    """Partir a frase em spans não deveria driblar a checagem."""
    meio = len(FALA) // 2
    html = f"<p>{FALA[:meio]}<span>{FALA[meio:]}</span></p>"
    assert _narracao_vazou_para_a_tela(html, FALA)
