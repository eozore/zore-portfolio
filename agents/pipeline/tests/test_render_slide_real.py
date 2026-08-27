"""
tests/test_render_slide_real.py
================================
O único teste que RENDERIZA de verdade.

Os demais em test_compose.py inspecionam o texto da função. Isso pegou o que
pegou, mas deixou passar o defeito que mais custou até aqui: o slide 1 do
deck aparecendo no começo do clipe de TODOS os outros slides.

O renderizador antigo (video_editor_job/job.py, antes de 388fed1) abria o
deck — que sempre começa no slide 1 — navegava para o alvo e gravava, mas
chamava `ffmpeg -i src.webm` SEM `-ss`. A cabeça inteira ficava no clipe.
Pior: navegava por `goToSlide(id)`, função que não existe no deck, e o
fallback `goTo(id)` esperava índice — com string, alguns segmentos nunca
saíam do slide 1.

Nenhum teste de inspeção de texto pegaria isso: o código "parecia" navegar.
Só um frame renderizado responde.

Por que importa em dinheiro: o vídeo sai errado, alguém percebe assistindo, e
a correção é reproduzir o pacote inteiro — o que regera TODOS os segmentos de
avatar no HeyGen, porque cada aprovação cria um projectId novo. Um defeito de
renderização que custa zero crédito para acontecer custa um vídeo inteiro
para consertar.

Pulado quando Playwright/Chromium ou FFmpeg não estão disponíveis, para não
quebrar a suíte de quem só mexe em Python.
"""

import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.compose import render_slide_clip  # noqa: E402


def _tem_chromium() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe") or not _tem_chromium(),
    reason="precisa de ffmpeg, ffprobe e chromium do Playwright",
)

# Cores sólidas por slide: o primeiro frame denuncia qual estava no ar. Um
# texto exigiria OCR; a cor média de um frame reduzido a 1x1 é exata.
CORES = {"yt-01": "#ff0000", "yt-02": "#00ff00", "yt-03": "#0000ff"}


def _deck(tmp_path):
    """Réplica mínima do deck do slide_designer — mesma API, mesmo CSS."""
    slides = "".join(
        f'<div class="slide" id="{sid}" data-seg="{sid}"></div>' for sid in CORES
    )
    estilos = "".join(f"#{sid}{{background:{cor}}}" for sid, cor in CORES.items())
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0}}
.slide{{display:none!important;position:absolute;inset:0;background:#0d0f14}}
.slide.active{{display:flex!important}}
{estilos}
</style></head><body>{slides}<script>
var slides=document.querySelectorAll('.slide');var current=0;
function goTo(i){{i=Number(i);if(!Number.isInteger(i)||i<0||i>=slides.length)return false;
for(var k=0;k<slides.length;k++)slides[k].classList.remove('active');
current=i;slides[current].classList.add('active');return true;}}
function indexOfSeg(s){{for(var k=0;k<slides.length;k++){{var e=slides[k];
if((e.id||'')===s||(e.dataset&&e.dataset.seg===s))return k;}}return -1;}}
function goToSeg(s){{var i=indexOfSeg(s);return i>=0?goTo(i):false;}}
function replaySlide(){{var e=slides[current];if(!e)return false;
e.classList.remove('active');void e.offsetWidth;e.classList.add('active');return true;}}
function hideHud(){{document.documentElement.classList.add('recording');}}
window.deckAPI={{goTo:goTo,goToSeg:goToSeg,replay:replaySlide,hideHud:hideHud,
indexOfSeg:indexOfSeg,count:slides.length}};
if(slides.length>0)goTo(0);
</script></body></html>"""
    caminho = tmp_path / "deck.html"
    caminho.write_text(html, encoding="utf-8")
    return caminho


def _rgb_em(video, t, tmp_path):
    """Cor média do frame em `t`, via escala para 1x1."""
    png = tmp_path / f"frame_{t}.png"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video),
         "-frames:v", "1", "-vf", "scale=1:1", str(png)],
        check=True,
    )
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(png), "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return raw[0], raw[1], raw[2]


def test_clipe_comeca_no_slide_alvo_e_nao_no_primeiro_do_deck(tmp_path):
    """
    Regressão do defeito de produção: slide 1 no começo de todo clipe.

    O deck abre no slide 1 e a gravação começa junto. O que separa um clipe
    correto de um contaminado é o `-ss lead_in_s`, que descarta o tempo entre
    abrir a página e disparar a animação do slide alvo.
    """
    deck = _deck(tmp_path)
    dest = tmp_path / "clipe.mp4"

    # yt-03 é azul; yt-01, o que vazava, é vermelho.
    render_slide_clip(deck, "yt-03", dest, 320, 180, 2.0, None)

    assert dest.exists(), "não gerou clipe"

    for t in (0.0, 0.1, 0.4):
        r, g, b = _rgb_em(dest, t, tmp_path)
        assert b > 150 and r < 100, (
            f"em t={t}s o clipe mostra rgb=({r},{g},{b}); esperado azul (slide "
            f"yt-03). A cabeça da gravação voltou ao clipe: vermelho é o slide "
            f"1 do deck, branco é a página antes de renderizar. Nos dois casos "
            f"o `-ss lead_in_s` deixou de cortar."
        )


def test_slide_inexistente_falha_alto_em_vez_de_gravar_tela_preta(tmp_path):
    """
    Um id fora de sincronia com o deck gravava 15s de tela preta, e ninguém
    percebia até assistir. Falhar aqui custa zero; falhar depois custa o
    reprocessamento do pacote — e com ele todo o avatar de novo.
    """
    from shared.compose import ComposeError

    deck = _deck(tmp_path)
    with pytest.raises(ComposeError, match="não encontrado"):
        render_slide_clip(deck, "yt-99", tmp_path / "x.mp4", 320, 180, 1.0, None)
