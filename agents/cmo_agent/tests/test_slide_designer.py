

# ── A classe que o deck usa para navegar ──────────────────────────────────────

def test_container_slide_e_renomeado():
    """
    Defeito de 29/08: o modelo escolheu `class="slide"` para o container raiz
    em 4 dos 9 slides. O deck navega com `.slide{display:none!important}` e
    `.slide.active` — a <section> ganha `.active` e aparece, o div interno
    homônimo não ganha nada e some, levando o conteúdo junto.

    Resultado: 115 segundos de tela preta num vídeo de 344, sem erro em lugar
    nenhum — nem no job, nem no upload, nem no YouTube.
    """
    from slide_designer_agent import _renomear_container_slide

    html = '<div class="slide" data-capitulo="X"><div class="kicker">a</div></div>'
    novo = _renomear_container_slide(html)
    assert 'class="slide"' not in novo
    assert 'class="slide-container"' in novo
    assert 'class="kicker"' in novo


def test_renomear_preserva_as_outras_classes():
    from slide_designer_agent import _renomear_container_slide

    novo = _renomear_container_slide('<div class="slide fd destaque">x</div>')
    assert "slide-container" in novo and "fd" in novo and "destaque" in novo


def test_renomear_nao_toca_slide_container_nem_prefixos():
    """`slide-container` e `slide-id` já são nomes distintos — não renomear."""
    from slide_designer_agent import _renomear_container_slide

    original = '<div class="slide-container"><span class="slide-id">1</span></div>'
    assert _renomear_container_slide(original) == original
