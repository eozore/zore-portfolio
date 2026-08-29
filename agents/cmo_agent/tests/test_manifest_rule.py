

def test_navegacao_do_deck_e_filho_direto_do_body():
    """
    `.slide{display:none!important}` sem `body>` apaga o container que o
    slide_designer gera DENTRO da seção, quando ele se chama `slide`.

    A <section> ganha `.active` e aparece; o div aninhado homônimo não ganha
    nada e some com o conteúdo inteiro. Quatro dos nove slides de 29/08 saíram
    em branco assim — 115s de tela preta num vídeo de 344, sem erro nenhum.
    """
    import re
    from manifest_builder import wrap_scriptwriter_manifest

    html = wrap_scriptwriter_manifest(
        {
            "video_id": "yt-x", "title": "t", "series": "s", "language": "pt-BR",
            "segments": [{"id": "yt-02", "kind": "slide", "slide": "yt-02",
                          "beat": "intro", "script": "texto", "min_duration_s": 20}],
        },
        slide_htmls={"yt-02": '<div class="slide-container">conteudo</div>'},
    )
    assert re.search(r"body\s*>\s*\.slide\s*\{[^}]*display\s*:\s*none", html), \
        "a regra de navegação precisa ser filho direto do body"

    # E a versão solta não pode voltar. Comentários fora antes de checar: o
    # próprio comentário que documenta o defeito cita o seletor antigo.
    sem_comentario = re.sub(r"/\*.*?\*/", "", html, flags=re.S)
    assert not re.search(r"(?<![>\w-])\.slide\s*\{\s*display\s*:\s*none", sem_comentario)
