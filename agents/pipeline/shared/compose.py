"""
agents/pipeline/shared/compose.py
==================================
Primitivas de composição de vídeo compartilhadas pelo compositor horizontal
(video_editor_job) e pelo corte vertical (vertical_cut_job).

Princípio único do produto, e a razão deste módulo existir:

    Cada segmento é UMA tela cheia — ou o avatar falando, ou a ilustração com
    a voz por cima. Nunca avatar reduzido sobreposto ao slide.

Portanto todo clipe, venha do HeyGen ou do Playwright, é normalizado para o
MESMO perfil (resolução, fps, pixel format, taxa de áudio) e só então
concatenado. Sem essa normalização o concat demuxer com `-c copy` falha ou
produz um arquivo com áudio dessincronizado — e como toda produção real até
hoje teve um único clipe, esse caminho nunca chegou a ser exercitado.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Perfil de encode único ────────────────────────────────────────────────────

FPS            = 30
CRF            = 20
PRESET         = "medium"
AUDIO_RATE     = 48_000
AUDIO_BITRATE  = "192k"
PIX_FMT        = "yuv420p"

# Silêncio de borda: o ElevenLabs entrega ~0.5s de silêncio na frente de cada
# faixa. Somado em 15 segmentos, é meia dúzia de segundos de pausa morta.
SILENCE_DB       = -35
SILENCE_MIN_S    = 0.35
SILENCE_KEEP_S   = 0.12   # respiro deixado de propósito nas bordas

FFMPEG_TIMEOUT_S = 900


class ComposeError(RuntimeError):
    """Falha determinística de composição — não adianta reprocessar igual."""


def _run(cmd: list[str], what: str, timeout: int = FFMPEG_TIMEOUT_S) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-1200:]
        raise ComposeError(f"{what} falhou (exit {proc.returncode}):\n{tail}")
    return proc.stderr or ""


# ── Sonda ─────────────────────────────────────────────────────────────────────


def probe_duration(path: str | Path) -> float:
    """Duração em segundos. 0.0 quando o arquivo não é legível."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        logger.warning("[compose] ffprobe não leu a duração de %s", path)
        return 0.0


def probe_size(path: str | Path) -> tuple[int, int]:
    """Resolução do primeiro stream de vídeo, em pixels."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    try:
        w, h = proc.stdout.strip().split("x")[:2]
        return int(w), int(h)
    except ValueError:
        raise ComposeError(f"não foi possível ler a resolução de {path}")


def has_audio_stream(path: str | Path) -> bool:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    return "audio" in proc.stdout


# ── Normalização ──────────────────────────────────────────────────────────────


def _video_chain(width: int, height: int) -> str:
    """
    Encaixa qualquer entrada no frame alvo sem distorcer: escala mantendo
    proporção e completa com barras. `setsar=1` é obrigatório — clipes com
    pixel aspect diferente fazem o concat recusar a mistura.
    """
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps={FPS},format={PIX_FMT}"
    )


def normalize_clip(
    src: str | Path,
    dest: str | Path,
    width: int,
    height: int,
    ensure_audio: bool = True,
) -> Path:
    """
    Reescreve um clipe no perfil canônico. Clipes mudos ganham uma faixa de
    silêncio: o concat exige o mesmo número de streams em todas as entradas, e
    uma cartela sem áudio derrubava a montagem inteira.
    """
    src, dest = Path(src), Path(dest)
    silent = ensure_audio and not has_audio_stream(src)

    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if silent:
        cmd += ["-f", "lavfi", "-i",
                f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_RATE}"]

    cmd += [
        "-vf", _video_chain(width, height),
        "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF),
        "-pix_fmt", PIX_FMT,
        "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
        "-map", "0:v:0", "-map", ("1:a:0" if silent else "0:a:0"),
        "-movflags", "+faststart",
    ]
    if silent:
        cmd += ["-shortest"]
    cmd += [str(dest)]

    _run(cmd, f"normalize({src.name})")
    return dest


def concat_clips(
    clips: list[str | Path],
    dest: str | Path,
    width: int,
    height: int,
) -> Path:
    """
    Junta os clipes na ordem dada com o filtro `concat`, não com o demuxer.

    O demuxer com `-c copy` exige parâmetros de codec idênticos bit a bit e o
    mesmo número de streams; misturar um MP4 do HeyGen com um WebM convertido
    do Playwright quebrava ali. O filtro reencoda uma vez e devolve um arquivo
    com timestamps contínuos — mais lento, mas é o passo que garante que o
    vídeo montado toque do começo ao fim.
    """
    clips = [Path(c) for c in clips]
    if not clips:
        raise ComposeError("concat sem clipes")
    if len(clips) == 1:
        return normalize_clip(clips[0], dest, width, height)

    cmd: list[str] = ["ffmpeg", "-y"]
    for clip in clips:
        cmd += ["-i", str(clip)]

    parts: list[str] = []
    for i in range(len(clips)):
        parts.append(f"[{i}:v]{_video_chain(width, height)}[v{i}]")
        parts.append(
            f"[{i}:a]aresample={AUDIO_RATE},"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]"
        )
    pairs = "".join(f"[v{i}][a{i}]" for i in range(len(clips)))
    parts.append(f"{pairs}concat=n={len(clips)}:v=1:a=1[outv][outa]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF),
        "-pix_fmt", PIX_FMT,
        "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
        "-movflags", "+faststart",
        str(dest),
    ]
    _run(cmd, f"concat({len(clips)} clipes)")
    logger.info("[compose] %d clipes concatenados → %s", len(clips), Path(dest).name)
    return Path(dest)


# ── Silêncio de borda ─────────────────────────────────────────────────────────


def trim_edge_silence(src: str | Path, dest: str | Path) -> Path:
    """
    Corta o silêncio das PONTAS do clipe, nunca do meio.

    A versão anterior rodava `silencedetect` sobre o vídeo já concatenado e
    removia todo silêncio maior que 0.8s. Num vídeo que alterna avatar e
    ilustração isso é destrutivo: uma cartela sem locução é silêncio integral
    e desaparecia inteira do corte final. Aparando só as bordas, cada segmento
    encosta no seguinte sem que nenhum conteúdo seja elegível para remoção.
    """
    src, dest = Path(src), Path(dest)
    total = probe_duration(src)
    if total <= 0:
        raise ComposeError(f"clipe ilegível: {src}")

    log = subprocess.run(
        ["ffmpeg", "-i", str(src), "-af",
         f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN_S}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_S,
    ).stderr

    import re
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", log)]
    ends   = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", log)]

    head = 0.0
    if starts and starts[0] < 0.05 and ends:
        head = max(0.0, ends[0] - SILENCE_KEEP_S)

    tail = total
    if starts and starts[-1] > head and len(starts) > len(ends):
        tail = min(total, starts[-1] + SILENCE_KEEP_S)
    elif starts and ends and starts[-1] > ends[-1]:
        tail = min(total, starts[-1] + SILENCE_KEEP_S)

    if tail - head < 0.5 or (head < 0.05 and tail > total - 0.05):
        # Nada relevante a aparar — evita um reencode inútil.
        import shutil
        shutil.copy2(src, dest)
        return dest

    _run(
        ["ffmpeg", "-y", "-i", str(src), "-ss", f"{head:.3f}", "-to", f"{tail:.3f}",
         "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF), "-pix_fmt", PIX_FMT,
         "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
         str(dest)],
        f"trim_silence({src.name})",
    )
    logger.info(
        "[compose] %s: silêncio de borda aparado (%.2fs → %.2fs)",
        src.name, total, tail - head,
    )
    return dest


# ── Crop vertical ─────────────────────────────────────────────────────────────


def crop_to_vertical(
    src: str | Path,
    dest: str | Path,
    out_width: int = 1080,
    out_height: int = 1920,
    offset_x_ratio: Optional[float] = None,
) -> Path:
    """
    Recorta um clipe horizontal de avatar para 9:16, sem nova geração.

    O HeyGen devolve o apresentador centralizado no frame 16:9, então uma
    janela 9:16 centrada pega o enquadramento certo. Isto substitui a segunda
    chamada ao HeyGen que gerava a MESMA fala em vertical — era metade do
    custo de avatar de cada produção, e foi ela que zerou a carteira.

    offset_x_ratio: 0.5 = centro (padrão). Ajuste por preset de avatar quando
    o enquadramento não estiver centralizado.
    """
    src, dest = Path(src), Path(dest)
    ratio = 0.5 if offset_x_ratio is None else max(0.0, min(1.0, offset_x_ratio))

    # A janela é calculada em Python, com números inteiros, e não por expressão
    # dentro do filtergraph: `min(iw,ih*9/16)` contém uma vírgula, e o parser do
    # FFmpeg lê vírgula como separador de filtro — o comando morria com
    # "No such filter: 'ih*1080/1920):ih:(iw-(min(iw'".
    src_w, src_h = probe_size(src)
    crop_w = min(src_w, int(src_h * out_width / out_height))
    crop_w -= crop_w % 2          # yuv420p exige dimensões pares
    crop_x = int((src_w - crop_w) * ratio)
    crop_x -= crop_x % 2

    vf = (
        f"crop={crop_w}:{src_h}:{crop_x}:0,"
        f"scale={out_width}:{out_height}:flags=lanczos,"
        f"setsar=1,fps={FPS},format={PIX_FMT}"
    )
    logger.info(
        "[compose] crop 9:16 de %s: %dx%d → janela %dx%d em x=%d → %dx%d",
        src.name, src_w, src_h, crop_w, src_h, crop_x, out_width, out_height,
    )

    _run(
        ["ffmpeg", "-y", "-i", str(src), "-vf", vf,
         "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF), "-pix_fmt", PIX_FMT,
         "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
         str(dest)],
        f"crop_vertical({src.name})",
    )
    return dest


# ── Legendas queimadas ────────────────────────────────────────────────────────


def burn_subtitles(
    src: str | Path,
    ass_path: str | Path,
    dest: str | Path,
    width: int,
    height: int,
) -> Path:
    """
    Queima o arquivo ASS no vídeo — passe único, no fim da montagem.

    Roda DEPOIS do concat, não por clipe: os tempos do ASS são absolutos na
    linha do tempo da peça final, então queimar antes de concatenar deslocaria
    toda legenda a partir do segundo clipe.

    O caminho do .ass é passado via `-vf subtitles=`, e não pelo filtro `ass`
    dentro de um filter_complex, porque o `subtitles=` aceita `original_size`
    — sem isso o libass escala a fonte pela resolução de saída e a legenda sai
    com tamanho diferente do que o PlayResX/PlayResY do arquivo pediu.
    """
    src, ass_path, dest = Path(src), Path(ass_path), Path(dest)
    if not ass_path.exists():
        raise ComposeError(f"arquivo de legenda ausente: {ass_path}")

    # `:` e `'` são separadores dentro do argumento do filtro; um caminho
    # temporário com qualquer um deles quebraria o filtergraph.
    escaped = str(ass_path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")

    _run(
        ["ffmpeg", "-y", "-i", str(src),
         "-vf", f"subtitles='{escaped}':original_size={width}x{height}",
         "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF), "-pix_fmt", PIX_FMT,
         "-c:a", "copy",
         "-movflags", "+faststart",
         str(dest)],
        f"burn_subtitles({src.name})",
    )
    logger.info("[compose] legendas queimadas em %s", dest.name)
    return dest


# ── Render de slide via Playwright ────────────────────────────────────────────

# Tempo dado ao deck para carregar fontes e assentar antes de disparar a
# animação. É medido de verdade (não estimado) e descontado do clipe.
SLIDE_SETUP_MS  = 900
# Cauda depois do fim do áudio, para a última animação respirar.
SLIDE_TAIL_S    = 0.6
SLIDE_MIN_S     = 3.0


def tempo_da_frase(alignment: dict | None, frase: str) -> Optional[float]:
    """
    Instante em que `frase` começa a ser falada, em segundos.

    O TTS grava um `.alignment.json` irmão de cada áudio, com tempo por
    CARACTERE. É o que permite disparar a revelação do slide no momento exato
    da frase, em vez de espalhar os reveals por estimativa.

    Devolve None quando a frase não é encontrada — o chamador distribui.
    """
    if not alignment or not frase:
        return None
    chars = alignment.get("characters") or []
    inicios = alignment.get("character_start_times_seconds") or []
    if not chars or len(chars) != len(inicios):
        return None

    def normal(t: str) -> str:
        return re.sub(r"\s+", " ", t).strip().lower()

    texto = normal("".join(chars))
    alvo = normal(frase)
    if not alvo:
        return None
    pos = texto.find(alvo)
    if pos < 0:
        # Casa pelo começo da frase: o roteirista às vezes cita um trecho com
        # pontuação diferente da que o TTS recebeu.
        pos = texto.find(alvo[: max(12, len(alvo) // 2)])
    if pos < 0:
        return None

    # `texto` normalizado pode ter menos caracteres que `chars`; reancora
    # contando caracteres não-espaço, que é o que sobrevive à normalização.
    vistos = 0
    for i, c in enumerate(chars):
        if vistos >= pos:
            return float(inicios[i])
        if not c.isspace() or (vistos and not texto[vistos - 1].isspace()):
            vistos += 1
    return None


def plano_de_reveals(
    anchors: list[dict] | None,
    alignment: dict | None,
    duracao_s: float,
) -> list[tuple[float, str, str]]:
    """
    (segundo, ação, elemento) para cada âncora, na ordem em que devem disparar.

    Âncora sem frase localizável entra por distribuição uniforme: um reveal no
    tempo errado ainda é melhor que um elemento que nunca aparece — que é o
    que acontecia antes, com TODOS eles.
    """
    plano: list[tuple[float, str, str]] = []
    pendentes: list[dict] = []
    for a in anchors or []:
        acao = str(a.get("action") or "")
        elem = str(a.get("element") or "")
        if acao not in ("reveal", "highlight") or not elem:
            continue
        t = tempo_da_frase(alignment, str(a.get("on_phrase") or ""))
        if t is None:
            pendentes.append({"action": acao, "element": elem})
        else:
            plano.append((max(0.0, t), acao, elem))

    if pendentes:
        # Espalha no miolo do segmento: nem no primeiro instante (o slide
        # acabou de entrar) nem no fim (ninguém veria).
        inicio, fim = duracao_s * 0.25, duracao_s * 0.85
        passo = (fim - inicio) / max(1, len(pendentes))
        for i, a in enumerate(pendentes):
            plano.append((inicio + i * passo, a["action"], a["element"]))

    plano.sort(key=lambda x: x[0])
    return plano


# Qual renderizador de slide usar: "playwright" (padrão) ou "hyperframes".
#
# O Playwright GRAVA a página em tempo real; o HyperFrames PERCORRE quadro a
# quadro. O segundo é determinístico, mas troca a etapa mais cara e mais
# frágil da pipeline — então entra por opção, e o padrão continua sendo o
# caminho que já produziu vídeo publicado.
RENDERIZADOR_SLIDE = os.environ.get("RENDERIZADOR_SLIDE", "playwright").strip().lower()


def render_slide_clip(
    html_path: str | Path,
    slide_id: str,
    dest: str | Path,
    width: int,
    height: int,
    duration_s: float,
    audio_path: Optional[str | Path] = None,
    anchors: Optional[list[dict]] = None,
    alignment: Optional[dict] = None,
) -> Path:
    """
    Grava um slide do deck como vídeo, opcionalmente com o áudio TTS colado.

    Três correções em relação à versão anterior, todas confirmadas contra o
    deck real gerado pelo slide_designer:

    1. Navega por `deckAPI.goToSeg(id)`. A chamada antiga era `goToSlide(id)`,
       que não existe no deck, e o fallback `goTo(id)` esperava um índice —
       passar "yt-02" lançava TypeError de dentro do próprio catch, matava o
       page.evaluate e derrubava o job no primeiro slide.
    2. Falha alto se o slide não for encontrado. Antes, um id errado gravava
       15 segundos de tela preta e ninguém percebia até assistir ao vídeo.
    3. Esconde o HUD de verdade (`deckAPI.hideHud`). O contador "4 / 13" e a
       barra de progresso laranja apareciam queimados em todos os slides.
    """
    from playwright.sync_api import sync_playwright

    html_path, dest = Path(html_path), Path(dest)

    # A LOCUÇÃO manda no tempo do slide, não a estimativa do manifesto.
    #
    # `duration_s` chega como `seg.min_duration_s`, que é o chute do roteirista
    # a 140 palavras por minuto. Quando o áudio real sai mais LONGO que o
    # chute, gravar pela estimativa cortava a fala no meio — o espectador
    # perdia o fim da frase. Medir o arquivo elimina o chute do caminho.
    if audio_path:
        measured = probe_duration(audio_path)
        if measured > 0:
            duration_s = measured

    plano_reveals = plano_de_reveals(anchors, alignment, duration_s)

    if RENDERIZADOR_SLIDE == "hyperframes":
        return _render_slide_hyperframes(
            html_path, slide_id, dest, width, height, duration_s,
            audio_path, plano_reveals,
        )

    record_s = max(duration_s + SLIDE_TAIL_S, SLIDE_MIN_S)
    raw_dir  = dest.parent / "_raw_webm"
    raw_dir.mkdir(parents=True, exist_ok=True)

    file_url = html_path.resolve().as_uri()
    lead_in_s = 0.0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu",
                  "--force-color-profile=srgb", "--hide-scrollbars"]
        )
        ctx = browser.new_context(
            viewport={"width": width, "height": height},
            record_video_dir=str(raw_dir),
            record_video_size={"width": width, "height": height},
            device_scale_factor=1,
        )
        t0   = time.monotonic()
        page = ctx.new_page()
        try:
            page.goto(file_url, wait_until="load")
            try:
                page.wait_for_function("() => document.fonts.status === 'loaded'",
                                       timeout=4000)
            except Exception:
                pass  # fonte remota bloqueada não impede a gravação

            found = page.evaluate(
                """(sid) => {
                    if (!window.deckAPI) return 'no-deck';
                    window.deckAPI.hideHud();
                    return window.deckAPI.goToSeg(sid) ? 'ok' : 'not-found';
                }""",
                str(slide_id),
            )
            if found != "ok":
                raise ComposeError(
                    f"slide '{slide_id}' não encontrado no deck ({found}). "
                    "O manifesto e o HTML estão fora de sincronia."
                )

            page.wait_for_timeout(SLIDE_SETUP_MS)

            # Agenda as revelações ANTES de disparar a animação, para que os
            # timers comecem a contar junto com ela.
            #
            # Sem isto os elementos fd2/fd3/fd4 ficam em `display:none` o
            # clipe inteiro: o manifesto sempre gerou as âncoras e nada as
            # executava, então a ilustração mostrava só o primeiro bloco
            # enquanto a locução falava do resto.
            plano = plano_reveals
            if plano:
                page.evaluate(
                    """(plano) => {
                        plano.forEach(([t, acao, el]) => {
                            setTimeout(() => {
                                if (acao === 'reveal') window.deckAPI.revelar(el);
                                else window.deckAPI.destacar(el);
                            }, Math.round(t * 1000));
                        });
                    }""",
                    [[t, a, e] for t, a, e in plano],
                )
            page.evaluate("() => window.deckAPI.replay()")
            lead_in_s = time.monotonic() - t0

            page.wait_for_timeout(int(record_s * 1000))
        finally:
            ctx.close()
            browser.close()

    webms = sorted(raw_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    if not webms:
        raise ComposeError(f"Playwright não gerou vídeo para o slide {slide_id}")
    src_webm = webms[-1]

    # Entradas primeiro, opções de saída depois: no ffmpeg tudo que aparece
    # antes de um `-i` é opção DAQUELE input, então misturar as duas coisas
    # muda silenciosamente o significado do comando.
    #
    # `-ss lead_in` descarta o tempo entre abrir a página e disparar a
    # animação. Sem isso o slide entrava congelado por quase um segundo
    # enquanto a locução já tinha começado.
    inputs: list[str] = ["-ss", f"{lead_in_s:.3f}", "-i", str(src_webm)]
    if audio_path:
        inputs += ["-i", str(audio_path)]
    else:
        inputs += ["-f", "lavfi", "-i",
                   f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_RATE}"]

    outputs: list[str] = [
        "-vf", _video_chain(width, height),
        "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF), "-pix_fmt", PIX_FMT,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
        # `-t` explícito, nunca `-shortest`.
        #
        # `-shortest` NÃO é determinístico entre builds do FFmpeg: com o mesmo
        # áudio de 10,475s, o binário do macOS cortou o vídeo em 10,449s e o
        # do container Debian deixou 11,167s — 0,7s de slide congelado depois
        # da voz terminar, em CADA segmento de ilustração. Num Reel de quatro
        # segmentos isso vira quase 3 segundos de tela morta.
        "-t", f"{duration_s:.3f}",
    ]

    _run(["ffmpeg", "-y", *inputs, *outputs, str(dest)], f"render_slide({slide_id})")
    src_webm.unlink(missing_ok=True)
    logger.info(
        "[compose] slide %s gravado %dx%d (%.1fs, lead-in %.2fs)",
        slide_id, width, height, duration_s, lead_in_s,
    )
    return dest


def _render_slide_hyperframes(
    html_path: Path,
    slide_id: str,
    dest: Path,
    width: int,
    height: int,
    duration_s: float,
    audio_path: Optional[str | Path],
    plano: list[tuple[float, str, str]],
) -> Path:
    """
    Mesmo contrato de `render_slide_clip`, com o quadro vindo do HyperFrames.

    Não há `-ss lead_in` aqui: o lead-in existe no caminho do Playwright para
    descartar o tempo entre abrir a página e disparar a animação, e num
    renderizador que percorre quadros esse intervalo não existe — o quadro 0 é
    o instante 0 por definição.
    """
    from . import hyperframes_slide as hf

    if not hf.disponivel():
        raise ComposeError(
            "RENDERIZADOR_SLIDE=hyperframes, mas o CLI não está nesta imagem. "
            "Instale `hyperframes` no Dockerfile ou volte para playwright."
        )

    composicao = hf.montar_composicao(
        Path(html_path).read_text(encoding="utf-8"),
        slide_id, duration_s, width, height, plano=plano,
    )
    mudo = dest.parent / f"_hf_{slide_id}.mp4"
    hf.renderizar_composicao(composicao, mudo)

    inputs: list[str] = ["-i", str(mudo)]
    if audio_path:
        inputs += ["-i", str(audio_path)]
    else:
        inputs += ["-f", "lavfi", "-i",
                   f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_RATE}"]

    outputs: list[str] = [
        "-vf", _video_chain(width, height),
        "-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF), "-pix_fmt", PIX_FMT,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
        # Explícito pelo mesmo motivo do outro caminho: `-shortest` não é
        # determinístico entre builds do FFmpeg.
        "-t", f"{duration_s:.3f}",
    ]
    _run(["ffmpeg", "-y", *inputs, *outputs, str(dest)], f"render_slide_hf({slide_id})")
    mudo.unlink(missing_ok=True)
    logger.info(
        "[compose] slide %s via hyperframes %dx%d (%.1fs, %d reveals)",
        slide_id, width, height, duration_s, len(plano),
    )
    return dest
