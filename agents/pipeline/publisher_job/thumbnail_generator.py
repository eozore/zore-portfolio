# -*- coding: utf-8 -*-
"""
publisher_job/thumbnail_generator.py
======================================
Gera thumbnails para YouTube (1280x720) e Reels/Shorts (1080x1920)
seguindo a identidade visual do canal Victor Zoré:

  - Frame real do vídeo como background (full bleed)
  - Gradiente preto da esquerda para o centro-direita
  - Título em laranja #e85d04, Bold, fonte enorme (left side)
  - Subtítulo em branco/cinza claro, fonte monospace ou sans
  - Ícone SVG opcional embaixo do subtítulo

Fluxo:
  1. FFmpeg extrai o melhor frame do vídeo (segundo configurável)
  2. Playwright renderiza o HTML template com o frame como bg
  3. Retorna bytes PNG prontos para upload
"""

import base64
import logging
import os
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger("publisher_job.thumbnail")

# ── Constantes visuais ────────────────────────────────────────────────────────

ORANGE   = "#e85d04"
WHITE    = "#ffffff"
GRAY     = "#d1d5db"
BLACK    = "#000000"
FONT_URL = "https://fonts.googleapis.com/css2?family=Oswald:wght@700&family=Roboto+Mono:wght@400&display=swap"

# Ícones SVG inline por categoria (simplificados, estilo outline laranja)
ICONS: dict[str, str] = {
    "ia": """<svg viewBox="0 0 64 64" fill="none" stroke="#e85d04" stroke-width="2.5" width="48" height="48">
      <rect x="16" y="12" width="32" height="40" rx="4"/>
      <path d="M24 24h16M24 32h16M24 40h10"/>
      <circle cx="44" cy="14" r="3" fill="#e85d04" stroke="none"/>
    </svg>""",
    "ml": """<svg viewBox="0 0 64 64" fill="none" stroke="#e85d04" stroke-width="2.5" width="48" height="48">
      <circle cx="12" cy="32" r="4"/><circle cx="32" cy="12" r="4"/><circle cx="52" cy="32" r="4"/>
      <circle cx="32" cy="52" r="4"/><circle cx="32" cy="32" r="6"/>
      <path d="M16 32h10M38 32h10M32 16v10M32 38v10"/>
    </svg>""",
    "estatistica": """<svg viewBox="0 0 64 64" fill="none" stroke="#e85d04" stroke-width="2.5" width="48" height="48">
      <path d="M8 56 Q18 20 28 32 Q38 44 48 12"/>
      <rect x="8" y="52" width="48" height="2" fill="#e85d04" stroke="none"/>
      <path d="M40 12 L48 12 L48 20"/>
    </svg>""",
    "default": """<svg viewBox="0 0 64 64" fill="none" stroke="#e85d04" stroke-width="2.5" width="48" height="48">
      <rect x="8" y="8" width="20" height="48" rx="3"/>
      <path d="M28 24 L48 14 L56 48 L28 56"/>
      <circle cx="18" cy="56" r="0"/>
    </svg>""",
}


# ── Extração de frame ─────────────────────────────────────────────────────────

def extract_frame(video_path: str, timestamp_s: float = 3.0) -> bytes:
    """
    Extrai um frame do vídeo no timestamp especificado.

    Args:
        video_path:  Caminho local ou URL do vídeo.
        timestamp_s: Timestamp em segundos para extrair o frame.

    Returns:
        bytes JPEG do frame.
    """
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Baixa o vídeo se for URL ou gs://. Sem o ramo gs://, video_path
        # chegava intacto ao ffmpeg como "gs://bucket/..." — falha sempre,
        # é exatamente o "FFmpeg frame extract failed" visto nos primeiros
        # vídeos reais publicados. Não é fatal (thumbnail é best-effort), mas
        # sem imagem customizada o YouTube usa um frame aleatório do vídeo.
        local_path = video_path
        if video_path.startswith("gs://"):
            from google.cloud import storage
            bucket_name, blob_name = video_path[5:].split("/", 1)
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
                storage.Client().bucket(bucket_name).blob(blob_name).download_to_file(vf)
                local_path = vf.name
        elif video_path.startswith("http"):
            import requests
            r = requests.get(video_path, timeout=120, stream=True)
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    vf.write(chunk)
                local_path = vf.name

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(timestamp_s),
                "-i", local_path,
                "-vframes", "1",
                "-q:v", "2",       # qualidade alta JPEG
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease",
                tmp_path,
            ],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg frame extract failed: {result.stderr.decode()[:200]}")

        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        # Limpa vídeo baixado se for URL
        if video_path != local_path and "local_path" in locals():
            try:
                os.unlink(local_path)
            except Exception:
                pass


def find_best_frame_timestamp(video_path: str) -> float:
    """
    Encontra o melhor timestamp para thumbnail:
    20-25% da duração (geralmente uma boa expressão/pose).

    Não fatal quando falha (cai no default de 3s) — por isso o mesmo bug de
    gs:// nunca travou nada aqui, só produzia thumbnails piores em silêncio.
    ffprobe lê metadados via HTTP Range Request, então uma Signed URL funciona
    sem baixar o arquivo inteiro; gs:// puro não é lido por rede por ele.
    """
    try:
        probe_path = video_path
        if video_path.startswith("gs://"):
            from publisher_job.job import _gcs_to_signed_url
            probe_path = _gcs_to_signed_url(video_path, expiration_minutes=15)
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", probe_path],
            capture_output=True, text=True, timeout=15,
        )
        duration = float(r.stdout.strip())
        # 20% do vídeo costuma ter boa expressão (já passou o setup inicial)
        return max(2.0, duration * 0.20)
    except Exception:
        return 3.0


# ── HTML templates ────────────────────────────────────────────────────────────

RETRATO_GCS = os.environ.get(
    "THUMB_RETRATO_GCS", "gs://vazfy-417019-assets/brand/zore-retrato.png"
)


def _retrato_b64() -> str:
    """
    Retrato do apresentador, em base64. String vazia quando indisponível.

    As thumbnails que o canal usa têm o rosto: a pessoa olhando para a câmera
    é o que separa uma capa de canal de um slide com texto por cima. As
    geradas pela pipeline não tinham nenhum, e ficavam sendo um print do
    vídeo com uma frase — indistinguíveis entre si na lista de recomendados.

    Falha ABERTO: sem o asset, a composição cai para o frame do vídeo. Uma
    thumbnail sem rosto ainda é melhor que nenhuma.
    """
    try:
        from google.cloud import storage as _gcs

        bucket_name, blob_path = RETRATO_GCS.replace("gs://", "").split("/", 1)
        dados = _gcs.Client().bucket(bucket_name).blob(blob_path).download_as_bytes()
        return base64.b64encode(dados).decode()
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("[thumbnail] retrato indisponível (%s) — usando o frame.", exc)
        return ""


def _linhas_da_frase(frase: str) -> list[str]:
    """
    Quebra a frase de impacto em 2 ou 3 linhas curtas.

    O molde é o das capas feitas à mão: "O ERRO / MAIS CARO / DE ML". Linhas
    curtas empilhadas ocupam a coluna esquerda inteira e são legíveis no
    tamanho de miniatura; uma linha longa encolhe a fonte até sumir.
    """
    palavras = frase.strip().split()
    if not palavras:
        return []
    if len(palavras) <= 2:
        return [" ".join(palavras).upper()]

    alvo = 3 if len(palavras) >= 5 else 2
    alvo = min(alvo, len(palavras))

    # Testa TODAS as divisões em `alvo` grupos contíguos e fica com a mais
    # equilibrada. O guloso anterior fechava a linha assim que passava da
    # largura alvo e produzia "O ERRO / MAIS / CARO DE ML" — a linha do meio
    # com um terço da largura das outras. Com no máximo 8 palavras o custo é
    # irrelevante e o resultado é ótimo, não aproximado.
    from itertools import combinations

    n = len(palavras)
    melhor: Optional[list[str]] = None
    melhor_custo = float("inf")
    for cortes in combinations(range(1, n), alvo - 1):
        limites = (0, *cortes, n)
        grupos = [palavras[limites[i]:limites[i + 1]] for i in range(alvo)]
        larguras = [len(" ".join(g)) for g in grupos]
        # Diferença entre a maior e a menor linha: é o que salta aos olhos.
        custo = max(larguras) - min(larguras)
        if custo < melhor_custo:
            melhor_custo, melhor = custo, [" ".join(g).upper() for g in grupos]

    return melhor or [" ".join(palavras).upper()]


def _build_youtube_html(
    frame_b64:   str,
    title:       str,
    subtitle:    str,
    icon_svg:    str,
    title_words: int = 1,
) -> str:
    """
    Thumbnail 1280x720 no padrão do canal.

    Layout: retrato à direita, gradiente escuro cobrindo a esquerda, frase de
    impacto empilhada em 2–3 linhas, régua laranja e apoio em monoespaçada.

    O tamanho da fonte é ajustado por script depois do layout, e não por uma
    tabela de faixas. A versão anterior dimensionava pelo comprimento da
    PRIMEIRA palavra: com "O que é harness e como usar corretamente no
    desenvolvimento com IA", `big_text` era "O", a fonte ia para 120px, e as
    outras 58 letras vazavam por cima e por baixo do quadro.
    """
    linhas = _linhas_da_frase(title)
    if not linhas:
        linhas = ["ÉOZORÉ"]

    # Primeira linha branca, resto laranja — é o contraste das capas do canal.
    html_linhas = "".join(
        f'<span class="l {"br" if i == 0 else "lj"}">{l}</span>' for i, l in enumerate(linhas)
    )

    retrato = _retrato_b64()
    camada_direita = (
        f"background-image:url('data:image/png;base64,{retrato}');"
        if retrato
        else f"background-image:url('data:image/jpeg;base64,{frame_b64}');"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link href="{FONT_URL}" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{
    width:1280px; height:720px; overflow:hidden;
    background:#0d0f14; font-family:'Oswald', Impact, sans-serif;
  }}
  .retrato {{
    position:absolute; top:0; right:0; width:58%; height:100%;
    {camada_direita}
    background-size:cover; background-position:center 18%;
  }}
  /* Cobre a esquerda por inteiro e some sobre o rosto. Sem o trecho opaco a
     tipografia perde contraste em cima de um fundo claro de escritório. */
  .veu {{
    position:absolute; inset:0;
    background:linear-gradient(to right,
      rgba(13,15,20,1) 0%, rgba(13,15,20,0.99) 30%,
      rgba(13,15,20,0.94) 42%, rgba(13,15,20,0.72) 52%,
      rgba(13,15,20,0.34) 64%, rgba(13,15,20,0.08) 76%, rgba(13,15,20,0) 88%);
  }}
  .bloco {{
    position:absolute; left:56px; top:50%; transform:translateY(-50%);
    width:600px; max-height:600px; display:flex; flex-direction:column;
  }}
  .frase {{ display:flex; flex-direction:column; }}
  /* `nowrap` é o que faz o ajuste automático funcionar: com quebra livre a
     linha nunca excede a largura do bloco, o script não vê excesso e a frase
     sai empilhada em mais linhas do que o previsto, desmontando a composição. */
  .l {{
    font-weight:700; line-height:0.94; letter-spacing:-1px;
    text-transform:uppercase; font-size:112px; white-space:nowrap;
  }}
  .br {{ color:{WHITE}; }}
  .lj {{ color:{ORANGE}; }}
  .regua {{ width:132px; height:4px; background:{ORANGE}; margin:22px 0 14px; }}
  .apoio {{
    font-family:'Roboto Mono','Courier New',monospace;
    font-size:24px; color:{GRAY}; letter-spacing:0.3px; line-height:1.35;
  }}
</style>
</head>
<body>
  <div class="retrato"></div>
  <div class="veu"></div>
  <div class="bloco">
    <div class="frase" id="frase">{html_linhas}</div>
    <div class="regua"></div>
    <div class="apoio">{subtitle}</div>
  </div>
<script>
// Encolhe até caber. O ajuste é por MEDIÇÃO e não por faixa de comprimento:
// acento, maiúscula e a própria fonte mudam a largura real, e qualquer tabela
// erra em algum título. Roda antes do screenshot porque é síncrono no parse.
(function () {{
  var bloco = document.querySelector('.bloco');
  var linhas = document.querySelectorAll('.l');
  var tamanho = 112;
  function cabe() {{
    if (bloco.scrollHeight > bloco.clientHeight) return false;
    for (var i = 0; i < linhas.length; i++) {{
      if (linhas[i].scrollWidth > bloco.clientWidth) return false;
    }}
    return true;
  }}
  while (!cabe() && tamanho > 34) {{
    tamanho -= 2;
    for (var i = 0; i < linhas.length; i++) linhas[i].style.fontSize = tamanho + 'px';
  }}
}})();
</script>
</body>
</html>"""


def _build_reel_html(
    frame_b64: str,
    title:     str,
    subtitle:  str,
    icon_svg:  str,
) -> str:
    """
    Gera HTML para thumbnail Reel/Short 1080x1920 (9:16).

    Layout:
    - Frame como background full-bleed (enquadrado para 9:16)
    - Gradiente preto de baixo para cima (texto fica na parte inferior)
    - Título laranja centralizado no terço inferior
    - Subtítulo abaixo
    """
    words     = title.strip().split()
    big_text  = " ".join(words[:2]).upper() if len(words) >= 2 else title.upper()
    rest_text = " ".join(words[2:]).upper() if len(words) > 2 else ""
    font_size = "96px" if len(big_text) <= 10 else "72px"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 1080px; height: 1920px; overflow: hidden; font-family: 'Oswald', Impact, sans-serif; }}

  .bg {{
    position: absolute; inset: 0;
    background-image: url('data:image/jpeg;base64,{frame_b64}');
    background-size: cover;
    background-position: center center;
  }}

  .gradient {{
    position: absolute; inset: 0;
    background: linear-gradient(
      to top,
      rgba(0,0,0,0.97) 0%,
      rgba(0,0,0,0.85) 25%,
      rgba(0,0,0,0.40) 50%,
      rgba(0,0,0,0.05) 75%,
      rgba(0,0,0,0.00) 100%
    );
  }}

  .content {{
    position: absolute;
    bottom: 120px;
    left: 0; right: 0;
    padding: 0 56px;
    text-align: left;
  }}

  .title-big {{
    font-size: {font_size};
    font-weight: 900;
    color: {ORANGE};
    line-height: 0.92;
    letter-spacing: -2px;
    text-shadow: 3px 3px 0px rgba(0,0,0,0.6);
    display: block;
  }}

  .title-rest {{
    font-size: {font_size};
    font-weight: 900;
    color: {WHITE};
    line-height: 0.92;
    letter-spacing: -2px;
    text-shadow: 3px 3px 0px rgba(0,0,0,0.6);
    display: block;
    margin-bottom: 20px;
  }}

  .subtitle {{
    font-family: 'Roboto Mono', 'Courier New', monospace;
    font-size: 28px;
    color: {GRAY};
    border-left: 4px solid {ORANGE};
    padding-left: 16px;
    line-height: 1.4;
    margin-top: 12px;
  }}

  .icon {{
    margin-top: 32px;
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .icon svg {{ width: 56px; height: 56px; }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="gradient"></div>
  <div class="content">
    <span class="title-big">{big_text}</span>
    {'<span class="title-rest">' + rest_text + '</span>' if rest_text else ''}
    <div class="subtitle">{subtitle}</div>
    <div class="icon">{icon_svg}</div>
  </div>
</body>
</html>"""


# ── Função principal ──────────────────────────────────────────────────────────

def generate_thumbnail(
    video_path:       str,
    title:            str,
    subtitle:         str,
    format:           str = "youtube",   # "youtube" | "reel" | "short"
    category:         str = "default",   # "ia" | "ml" | "estatistica" | "default"
    frame_timestamp:  Optional[float] = None,
    output_path:      Optional[str] = None,
) -> bytes:
    """
    Gera thumbnail para YouTube ou Reel/Short.

    Args:
        video_path:      Caminho local ou URL do vídeo.
        title:           Título principal (ex: "LoRA explicado").
        subtitle:        Subtítulo (ex: "como reduzir custo de fine-tuning").
        format:          "youtube" (1280x720) ou "reel"/"short" (1080x1920).
        category:        Categoria para escolher o ícone SVG.
        frame_timestamp: Timestamp do frame (None = automático).
        output_path:     Se informado, salva o PNG neste caminho.

    Returns:
        bytes PNG da thumbnail.
    """
    # 1. Extrai frame
    ts = frame_timestamp if frame_timestamp is not None else find_best_frame_timestamp(video_path)
    logger.info(f"Extraindo frame em t={ts:.1f}s de {video_path}")
    frame_bytes = extract_frame(video_path, ts)
    frame_b64   = base64.b64encode(frame_bytes).decode()

    # 2. Escolhe ícone
    icon_svg = ICONS.get(category, ICONS["default"])

    # 3. Gera HTML
    is_vertical = format in ("reel", "short")
    width  = 1080 if is_vertical else 1280
    height = 1920 if is_vertical else 720

    if is_vertical:
        html = _build_reel_html(frame_b64, title, subtitle, icon_svg)
    else:
        # Heurística: palavras em laranja = primeiro "bloco" do título
        # Ex: "LoRA: Como funciona" → "LORA" laranja + "COMO FUNCIONA" branco
        html = _build_youtube_html(
            frame_b64, title, subtitle, icon_svg,
            title_words=1 if len(title.split()) <= 3 else 2,
        )

    # 4. Renderiza via Playwright
    from publisher_job.html_image_renderer import render_html_image

    logger.info(f"Renderizando thumbnail {width}x{height} via Playwright")
    png_bytes = render_html_image(
        html=html,
        width=width,
        height=height,
        fallback_title=title,
        fallback_body=subtitle,
    )

    # 5. Salva se solicitado
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(png_bytes)
        logger.info(f"Thumbnail salva em: {output_path}")

    return png_bytes
