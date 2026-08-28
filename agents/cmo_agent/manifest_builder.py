# -*- coding: utf-8 -*-
"""
manifest_builder.py  (versão 2 — Sprint 2 / G2)
=================================================
Converte um roteiro YouTube (Markdown ou dict do scriptwriter_agent) no
manifesto HTML v2 que o pipeline éozoré consome.

Formato v2 — compatível com pacote-finetuning-v2.html:
{
  "version": 2,
  "video_id": "slug-do-video",
  "series":   "nome-da-serie",
  "title":    "Título completo",
  "language": "pt-BR",
  "audio_naming": "{video_id}__{segment_id}.wav",
  "youtube": {
    "deck": "yt",
    "resolution": {"width": 1920, "height": 1080},
    "overlay": {"mode": "slide-full", "avatar_position": "bottom-right",
                "avatar_scale": 0.28},
    "segments": [
      {
        "id":      "yt-01",
        "slide":   null,          // null ou string id do slide
        "beat":    "hook",
        "script":  "texto falado",
        "anchors": [              // ← NOVO em v2
          {"on_phrase": "frase exacta", "action": "show_slide"},
          {"on_phrase": "outra frase",  "action": "reveal", "element": "fd2"}
        ]
      }
    ]
  },
  "reels": [
    {
      "reel_id": "reel-01",
      "title":   "Título do Reel",
      "deck":    "r1",
      "resolution": {"width": 1080, "height": 1920},
      "overlay": {"mode": "slide-full", "avatar_position": "bottom-center",
                  "avatar_scale": 0.35},
      "segments": [ ... ]
    }
  ]
}

Modos de entrada:
  A) dict do scriptwriter_agent (já no formato v2) → wrap_scriptwriter_manifest()
  B) Markdown de roteiro legado              → build_manifest() (backward-compat)
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


# ── ScriptScene (espelha o tipo TypeScript) ────────────────────────────────────

@dataclass
class ScriptScene:
    id:          str
    section:     str
    visualCue:   str
    spokenText:  str


# ── Âncora v2 ──────────────────────────────────────────────────────────────────

@dataclass
class Anchor:
    on_phrase: str
    action:    str          # "show_slide" | "reveal" | "highlight"
    element:   Optional[str] = None   # id CSS: fd2, fd3, b1-b4 …

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"on_phrase": self.on_phrase, "action": self.action}
        if self.element:
            d["element"] = self.element
        return d


# ── Segmento do manifesto ──────────────────────────────────────────────────────

@dataclass
class ManifestSegment:
    id:             str
    script:         str                    # "" = slide puro
    beat:           str
    slide:          Optional[str] = None   # v2: string id ou null
    anchors:        list = field(default_factory=list)   # list[Anchor]
    # campos legados (mantidos para compatibilidade com video_editor_job v1)
    min_duration_s: float = 5.0
    pause_after_s:  float = 0.4

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":             self.id,
            "kind":           "slide" if self.slide else "avatar",
            "slide":          self.slide,
            "beat":           self.beat,
            "script":         self.script,
            "anchors":        [a.to_dict() if isinstance(a, Anchor) else a
                               for a in self.anchors],
            "min_duration_s": self.min_duration_s,
            "pause_after_s":  self.pause_after_s,
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _estimate_duration(text: str, wpm: float = 140) -> float:
    """Estima duração da fala em segundos dado o texto."""
    words = len(text.split())
    return max(3.0, (words / wpm) * 60)


def _section_to_beat(section: str) -> str:
    """Mapeia o nome da seção para o beat do manifesto."""
    section_upper = section.upper()
    for beat in ("HOOK", "INTRO", "TEORIA", "CODIGO", "CODE", "DEMO", "CTA", "CONCLUSAO"):
        if beat in section_upper:
            return beat.replace("CODE", "CODIGO").replace("CONCLUSAO", "CTA")
    return "TEORIA"


def _is_slide_cue(visual_cue: str) -> bool:
    """Retorna True se o visualCue indica uma tela/slide."""
    cue_upper = visual_cue.upper()
    return any(kw in cue_upper for kw in ["TELA:", "SLIDE:", "DIAGRAMA:", "GRÁFICO:", "GRAFICO:", "CÓDIGO:", "CODIGO:"])


def _parse_anchors_from_script(script: str, slide_id: Optional[str]) -> list[Anchor]:
    """
    Extrai âncoras automaticamente de um segmento de fala para o manifesto v2.

    Heurística determinística (sem LLM) para o path legado (Markdown → manifesto):
      — Primeira frase relevante do segmento → show_slide (se tem slide)
      — Frases com números/percentuais chave → reveal fd2, fd3
      — Frases superlativas ou de conclusão  → reveal fd4

    O scriptwriter_agent já gera anchors[] explícitas — esta função só é usada
    quando o manifesto é construído a partir do roteiro Markdown legado (build_manifest).
    """
    if not slide_id:
        return []

    anchors: list[Anchor] = []
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    if not sentences:
        return [Anchor(on_phrase=script[:40].strip(), action="show_slide")]

    # 1. Âncora show_slide: primeiros ~6 tokens da primeira frase
    first = sentences[0]
    trigger_words = first.split()[:6]
    if trigger_words:
        anchors.append(Anchor(on_phrase=" ".join(trigger_words), action="show_slide"))

    # 2. Revela fd2 na frase com número/percentual chave
    reveal_ids = ["fd2", "fd3", "fd4"]
    reveal_idx = 0
    number_pattern = re.compile(
        r'\b(\d[\d.,]*\s*(?:por cento|%|bilhões?|milhões?|mil|GB|MB|ms|segundos?|minutos?)\b)',
        re.IGNORECASE
    )
    for sent in sentences[1:]:
        if reveal_idx >= len(reveal_ids):
            break
        if number_pattern.search(sent) or any(
            kw in sent.lower()
            for kw in ("resultado", "custo", "memória", "parâmetros", "convergiu", "concluindo", "portanto")
        ):
            words = sent.split()[:6]
            if words:
                anchors.append(Anchor(
                    on_phrase=" ".join(words),
                    action="reveal",
                    element=reveal_ids[reveal_idx],
                ))
                reveal_idx += 1

    return anchors


def _parse_markdown_to_scenes(markdown: str) -> list[ScriptScene]:
    """
    Parseia o Markdown do roteiro YouTube em lista de ScriptScene.
    Espelha exatamente o scriptParser.ts do frontend.
    """
    scenes: list[ScriptScene] = []
    if not markdown or not markdown.strip():
        return scenes

    lines = markdown.split("\n")
    current_section    = "INTRO"
    current_visual_cue = "CENA: Victor falando para a câmera"
    current_spoken: list[str] = []

    def flush():
        text = "\n".join(current_spoken).strip()
        if text or current_visual_cue:
            scenes.append(ScriptScene(
                id=str(uuid.uuid4())[:8],
                section=current_section,
                visualCue=current_visual_cue.strip(),
                spokenText=text,
            ))
            current_spoken.clear()

    for line in lines:
        trimmed = line.strip()

        # Seção (## HOOK / ## [INTRO — 0:30])
        if trimmed.startswith("## ") or trimmed.startswith("# "):
            flush()
            current_section = re.sub(r"^##?\s+", "", trimmed)
            current_section = re.sub(r"[\[\]]", "", current_section).strip()
            # Remove timecode: "[HOOK — 0:00–0:30]" → "HOOK"
            current_section = current_section.split("—")[0].strip()
            continue

        # Blockquote = indicação visual
        if trimmed.startswith(">"):
            brace = re.search(r"\[([^\]]+)\]", trimmed)
            if brace:
                flush()
                current_visual_cue = brace.group(1)
            else:
                clean = re.sub(r"^>\s?", "", trimmed).strip()
                if clean:
                    flush()
                    current_visual_cue = clean
            continue

        # META block — ignora
        if trimmed.startswith("META:"):
            continue

        # Linha vazia
        if not trimmed:
            if current_spoken:
                current_spoken.append("")
            continue

        current_spoken.append(line)

    flush()

    if not scenes and markdown.strip():
        scenes.append(ScriptScene(
            id=str(uuid.uuid4())[:8],
            section="INTRO",
            visualCue="CENA: Victor falando para a câmera",
            spokenText=markdown.strip(),
        ))

    return scenes


# ── Geração de slides HTML ─────────────────────────────────────────────────────

def _build_slide_html(
    slide_index: int,
    visual_cue:  str,
    title:       str,
    is_vertical: bool = False,
) -> str:
    """
    Gera o HTML de um slide Playwright-compatível.
    Design dark premium (fundo #0f172a, laranja #e85d04).
    """
    w, h = (1080, 1920) if is_vertical else (1920, 1080)
    font_size = "2.8rem" if is_vertical else "3.2rem"

    # Extrai o conteúdo limpo do visualCue
    content = visual_cue
    for prefix in ["TELA:", "SLIDE:", "DIAGRAMA:", "GRAFICO:", "CÓDIGO:", "CODIGO:", "GRÁFICO:"]:
        if content.upper().startswith(prefix):
            content = content[len(prefix):].strip()
            break

    # Formata LaTeX para visualização (placeholder — o VideoEditor só precisa do slide HTML)
    content_safe = content.replace("<", "&lt;").replace(">", "&gt;")

    return f"""<section class="slide" data-index="{slide_index}" style="
    width:{w}px;height:{h}px;
    background:#0f172a;
    display:flex;flex-direction:column;
    align-items:flex-start;justify-content:center;
    padding:{80 if is_vertical else 60}px;
    font-family:'Segoe UI',system-ui,sans-serif;
    overflow:hidden;
">
    <div style="
        font-size:0.85rem;font-weight:700;
        color:#e85d04;letter-spacing:3px;
        text-transform:uppercase;margin-bottom:24px;
        border-left:4px solid #e85d04;padding-left:12px;
    ">{title}</div>
    <div style="
        font-size:{font_size};font-weight:800;
        color:#ffffff;line-height:1.2;
        max-width:90%;
    ">{content_safe}</div>
</section>"""


def _build_deck_html(
    slides: list[tuple[int, str, str]],  # (index, visual_cue, title)
    width: int, height: int,
    video_id: str,
) -> str:
    """
    Gera o HTML do deck completo com todos os slides.
    Inclui script JS de controle (goTo, replaySlide, toggleHud).
    Usado pelo VideoEditorJob via Playwright.
    """
    slides_html = "\n".join(
        _build_slide_html(idx, cue, title, is_vertical=(height > width))
        for idx, cue, title in slides
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:{width}px; height:{height}px; overflow:hidden; background:#0f172a; }}
.slide {{ display:none !important; }}
.slide.active {{ display:flex !important; }}
#hud {{ position:fixed; top:12px; right:12px; font-size:11px; color:#64748b; z-index:999; }}
</style>
</head>
<body>
<div id="hud">{video_id}</div>
{slides_html}
<script>
var currentSlide = 0;
var hudVisible = true;
var slides = document.querySelectorAll('.slide');
function goTo(idx) {{
    slides.forEach(function(s) {{ s.classList.remove('active'); }});
    if (slides[idx]) {{ slides[idx].classList.add('active'); currentSlide = idx; }}
}}
function replaySlide() {{
    goTo(currentSlide);
}}
function toggleHud() {{
    var h = document.getElementById('hud');
    if (h) {{ hudVisible = !hudVisible; h.style.display = hudVisible ? '' : 'none'; }}
}}
// Ativa primeiro slide
if (slides.length > 0) goTo(0);
</script>
</body>
</html>"""


# ── Builder principal ──────────────────────────────────────────────────────────

def build_manifest(
    script_markdown: str,
    title:           str,
    language:        str = "pt-BR",
    video_id:        Optional[str] = None,
    series:          Optional[str] = None,
    include_vertical: bool = True,
) -> str:
    """
    Constrói o manifesto HTML v2 a partir do roteiro Markdown do YouTube.
    Path legado — o scriptwriter_agent usa wrap_scriptwriter_manifest().

    Args:
        script_markdown:  Roteiro em Markdown (YoutubeTab ou writing_agent).
        title:            Título do vídeo.
        language:         Idioma (default "pt-BR").
        video_id:         UUID/slug do projeto (gerado automaticamente se None).
        series:           Slug da série no blog (ex: "rag-para-lideres").
        include_vertical: Se True, gera segmentos de reel vertical (reel-01).

    Returns:
        HTML string do manifesto v2, pronto para salvar no GCS.
    """
    if not video_id:
        video_id = str(uuid.uuid4())

    scenes = _parse_markdown_to_scenes(script_markdown)

    # ── Constrói segmentos horizontais ────────────────────────────────────────
    h_segments: list[ManifestSegment] = []
    slide_counter = 0
    slide_cues: list[tuple[int, str, str]] = []  # (idx, cue, title)

    for i, scene in enumerate(scenes):
        seg_id  = f"seg_{i+1:03d}"
        beat    = _section_to_beat(scene.section)
        slide_id = f"yt-{(i+1):02d}" if _is_slide_cue(scene.visualCue) else None

        if scene.spokenText.strip():
            dur     = _estimate_duration(scene.spokenText)
            anchors = _parse_anchors_from_script(scene.spokenText, slide_id)
            h_segments.append(ManifestSegment(
                id             = seg_id,
                script         = scene.spokenText.strip(),
                beat           = beat,
                slide          = slide_id,
                anchors        = anchors,
                min_duration_s = round(dur, 1),
                pause_after_s  = 0.4,
            ))
        elif _is_slide_cue(scene.visualCue):
            slide_cues.append((slide_counter, scene.visualCue, title))
            h_segments.append(ManifestSegment(
                id             = seg_id,
                script         = "",
                beat           = beat,
                slide          = f"yt-{slide_counter+1:02d}",
                anchors        = [],
                min_duration_s = 8.0,
                pause_after_s  = 0.2,
            ))
            slide_counter += 1

    # Se nenhum segmento de avatar, cria um segmento com o texto bruto
    if not any(s.script for s in h_segments):
        full_text = " ".join(
            sc.spokenText for sc in scenes if sc.spokenText.strip()
        ) or script_markdown[:2000]
        dur = _estimate_duration(full_text)
        h_segments = [ManifestSegment(
            id             = "seg_001",
            script         = full_text,
            beat           = "INTRO",
            slide          = None,
            min_duration_s = round(dur, 1),
            pause_after_s  = 0.4,
        )]

    # ── Deck HTML horizontal ──────────────────────────────────────────────────
    deck_h = _build_deck_html(slide_cues, 1920, 1080, video_id) if slide_cues else ""

    # ── Segmentos verticais (reel — mesmo conteúdo, só os de avatar) ──────────
    # Para o reel, usamos apenas segmentos de avatar (script != "")
    # pois os slides verticais precisam de layout próprio (9:16)
    v_segments: list[ManifestSegment] = []
    v_slide_cues: list[tuple[int, str, str]] = []
    v_slide_counter = 0

    if include_vertical:
        for i, seg in enumerate(h_segments):
            if seg.script:
                v_segments.append(ManifestSegment(
                    id             = seg.id + "_v",
                    script         = seg.script,
                    beat           = seg.beat,
                    slide          = None,
                    anchors        = [],
                    min_duration_s = seg.min_duration_s,
                    pause_after_s  = seg.pause_after_s,
                ))
            else:
                v_slide_cues.append((v_slide_counter, scenes[v_slide_counter].visualCue if v_slide_counter < len(scenes) else "", title))
                v_segments.append(ManifestSegment(
                    id             = seg.id + "_v",
                    script         = "",
                    beat           = seg.beat,
                    slide          = f"r1-{v_slide_counter+1:02d}",
                    anchors        = [],
                    min_duration_s = seg.min_duration_s,
                    pause_after_s  = seg.pause_after_s,
                ))
                v_slide_counter += 1

    deck_v = _build_deck_html(v_slide_cues, 1080, 1920, video_id) if v_slide_cues else ""

    # ── JSON do manifesto v2 ──────────────────────────────────────────────────
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().strip())[:60].strip("-")

    manifest_json = {
        "version":       2,
        "video_id":      video_id,
        "series":        series or slug,
        "title":         title,
        "language":      language,
        "audio_naming":  "{video_id}__{segment_id}.wav",
        "youtube": {
            "deck":       "yt",
            "resolution": {"width": 1920, "height": 1080},
            "segments": [s.to_dict() for s in h_segments],
        },
        "reels": [
            {
                "reel_id":    "reel-01",
                "title":      f"Reel 01 — {title[:50]}",
                "deck":       "r1",
                "resolution": {"width": 1080, "height": 1920},
                "segments": [s.to_dict() for s in v_segments],
            }
        ] if include_vertical else [],
    }

    # ── HTML final: JSON + deck horizontal embutido ───────────────────────────
    # O VideoEditorJob abre este HTML via Playwright.
    # O <script type="application/json"> é parseado pelo pipeline.
    # O deck HTML dos slides fica no body para o Playwright renderizar.
    manifest_html = f"""<!DOCTYPE html>
<html lang="{language}">
<head>
<meta charset="UTF-8">
<title>{title} — Manifesto éozoré</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1920px; height:1080px; overflow:hidden; background:#0f172a; }}
.slide {{ display:none !important; }}
.slide.active {{ display:flex !important; }}
#hud {{ position:fixed; top:12px; right:12px; font-size:11px; color:#64748b; z-index:999; }}
</style>
</head>
<body>
<!--
  Manifesto da content pipeline éozoré.
  Processado por: tts_job, avatar_job, video_editor_job.
-->
<script type="application/json">
{json.dumps(manifest_json, ensure_ascii=False, indent=2)}
</script>
<div id="hud">{video_id}</div>
{chr(10).join(_build_slide_html(idx, cue, ttl) for idx, cue, ttl in slide_cues)}
<script>
var currentSlide = 0;
var hudVisible = true;
var slides = document.querySelectorAll('.slide');
function goTo(idx) {{
    slides.forEach(function(s) {{ s.classList.remove('active'); }});
    if (slides[idx]) {{ slides[idx].classList.add('active'); currentSlide = idx; }}
}}
function replaySlide() {{ goTo(currentSlide); }}
function toggleHud() {{
    var h = document.getElementById('hud');
    if (h) {{ hudVisible = !hudVisible; h.style.display = hudVisible ? '' : 'none'; }}
}}
if (slides.length > 0) goTo(0);
</script>
</body>
</html>"""

    return manifest_html


def build_and_upload_manifest(
    script_markdown: str,
    title:           str,
    project_id:      str,
    gcs_bucket:      str,
    language:        str = "pt-BR",
) -> str:
    """
    Constrói o manifesto e salva no GCS.

    Args:
        script_markdown: Roteiro YouTube em Markdown.
        title:           Título do vídeo.
        project_id:      ID do projeto (usado no caminho GCS).
        gcs_bucket:      Nome do bucket GCS (ex: "vazfy-417019-pipeline-media").
        language:        Idioma do conteúdo.

    Returns:
        gs:// URI do manifesto no GCS.
    """
    from google.cloud import storage as gcs_storage

    html = build_manifest(
        script_markdown  = script_markdown,
        title            = title,
        language         = language,
        video_id         = project_id,
        include_vertical = True,
    )

    blob_name = f"projects/{project_id}/manifest.html"
    gcs = gcs_storage.Client()
    bucket = gcs.bucket(gcs_bucket)
    blob   = bucket.blob(blob_name)
    blob.upload_from_string(html, content_type="text/html; charset=utf-8")

    gcs_uri = f"gs://{gcs_bucket}/{blob_name}"
    return gcs_uri


# ── Cache de slides HTML gerados pelo slide_designer_agent ────────────────────
# Preenchido por wrap_scriptwriter_manifest via parâmetro slide_htmls.
_slide_htmls_cache: dict = {}


def wrap_scriptwriter_manifest(
    manifest_dict: dict,
    language: str = "pt-BR",
    slide_htmls: Optional[dict] = None,
) -> str:
    """
    Converte o dict JSON do scriptwriter_agent no HTML de manifesto v2.

    O scriptwriter_agent já produz o JSON no formato correto — esta função
    apenas envolve num HTML com <script type="application/json"> e insere
    os slides HTML gerados pelo slide_designer_agent (BUG1 fix).

    Args:
        manifest_dict: dict retornado por run_scriptwriter()
        language:      Idioma (herdado do manifesto, sobrescrito se passado)
        slide_htmls:   dict mapeando slide_id → HTML completo (de design_all_slides()).
                       Se None ou vazio, usa placeholder mínimo como fallback.

    Returns:
        HTML string do manifesto v2
    """
    global _slide_htmls_cache
    _slide_htmls_cache = slide_htmls or {}
    # Garante versão 2 e audio_naming
    manifest_dict.setdefault("version", 2)
    manifest_dict.setdefault("audio_naming", "{video_id}__{segment_id}.wav")
    manifest_dict["language"] = language or manifest_dict.get("language", "pt-BR")

    title    = manifest_dict.get("title", "Vídeo éozoré")
    video_id = manifest_dict.get("video_id", str(uuid.uuid4())[:12])

    # Coleta slide_ids únicos nos segmentos para gerar slides HTML básicos
    slide_ids: list[str] = []
    for seg in manifest_dict.get("youtube", {}).get("segments", []):
        sid = seg.get("slide")
        if sid and sid not in slide_ids:
            slide_ids.append(sid)
    for item in manifest_dict.get("vertical_cut", {}).get("segments", []):
        sid = item.get("slide")
        if sid and sid not in slide_ids:
            slide_ids.append(sid)
    for reel in manifest_dict.get("reels", []):
        for seg in reel.get("segments", []):
            sid = seg.get("slide")
            if sid and sid not in slide_ids:
                slide_ids.append(sid)

    # Slides HTML — inseridos pelo slide_designer_agent quando disponível,
    # ou placeholder mínimo como fallback (mantém compatibilidade com VideoEditorJob)
    # Os HTMLs do slide_designer são documentos completos — extraímos o <body> e
    # os estilos, mas ESCOPAMOS as regras CSS ao #sid para não vazar para o documento.
    #
    # BUG FIX: sem escopo, as regras "html, body { width:1920px }" e "display:flex"
    # do slide_designer sobrescrevem o CSS principal do manifesto, fazendo todos os
    # slides aparecerem simultaneamente em vez de obedecer ao goTo(i).
    slides_html_parts = []

    for sid in slide_ids:
        designer_html = _slide_htmls_cache.get(sid, "") if _slide_htmls_cache else ""
        if designer_html:
            # Extrai bloco <style> do HTML gerado pelo slide_designer
            style_match = re.search(r'<style[^>]*>([\s\S]*?)</style>', designer_html, re.IGNORECASE)
            body_match  = re.search(r'<body[^>]*>([\s\S]*?)</body>', designer_html, re.IGNORECASE)

            scoped_style = ""
            if style_match:
                # Todo o trabalho está em escopar_css_do_slide: o que havia
                # aqui era uma sequência de regexes que apagava `:root`
                # (levando junto as custom properties do designer) e entrava
                # dentro dos `@keyframes`. Ver o docstring da função.
                css = escopar_css_do_slide(style_match.group(1), sid)
                if css.strip():
                    scoped_style = f'<style id="style-{sid}">\n{css}\n</style>'

            slide_content = body_match.group(1).strip() if body_match else designer_html

            slides_html_parts.append(
                f'{scoped_style}\n'
                # O slide_designer desenha o próprio `.slide-container` de
                # 1920x1080. A regra base `.slide` centraliza e aplica
                # padding:60px, o que reduz a caixa para 1800x960 e faz o
                # conteúdo transbordar por cima e por baixo do quadro.
                #
                # Zera APENAS o padding. A centralização da regra base fica:
                # para um slide que traz o próprio container de 1920x1080 ela
                # é inócua (centralizar um filho do tamanho do pai não move
                # nada), e para um slide que NÃO traz é o que o mantém no meio
                # do quadro em vez de no canto superior esquerdo.
                #
                # `display` não pode ser sobrescrito aqui: `.slide.active` usa
                # `!important` e é ele que controla a navegação.
                f'<section class="slide" id="{sid}" data-seg="{sid}" '
                f'style="position:absolute;inset:0;overflow:hidden;padding:0;'
                f'background:#0d0f14;">'
                f'{slide_content}'
                f'</section>'
            )
        else:
            # Placeholder mínimo — fallback se slide_designer falhar
            slides_html_parts.append(
                f'<section class="slide" id="{sid}" data-seg="{sid}">'
                f'<div class="slide-id">{sid}</div></section>'
            )
    slides_html = "\n".join(slides_html_parts)

    manifest_json_str = json.dumps(manifest_dict, ensure_ascii=False, indent=2)
    n_slides = max(len(slide_ids), 1)

    return f"""<!DOCTYPE html>
<html lang="{manifest_dict['language']}">
<head>
<meta charset="UTF-8">
<!-- Sem esta meta, um viewport estreito (o vertical 1080x1920) faz o Chrome
     assumir a largura padrão de 980px e o deck é diagramado numa caixa que
     não é a do vídeo. -->
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Manifesto v2 éozoré</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
/* Viewport-relativo, não 1920px fixo: o MESMO documento é gravado em 1920x1080
   para o YouTube e em 1080x1920 para a peça vertical. Com largura fixa, os
   slides verticais saíam desenhados em caixa horizontal dentro de um viewport
   9:16 — conteúdo cortado à direita e faixa preta embaixo. */
html,body{{width:100vw;height:100vh;overflow:hidden;background:#0d0f14;color:#eae4dc;font-family:'Space Grotesk',sans-serif}}
.slide{{display:none!important;position:absolute;inset:0;flex-direction:column;justify-content:center;align-items:center;padding:60px;background:#0d0f14}}
.slide.active{{display:flex!important}}
@keyframes pulsa{{0%{{transform:scale(1)}}45%{{transform:scale(1.045)}}100%{{transform:scale(1)}}}}
.pulsa{{animation:pulsa .55s ease-out}}
.slide-id{{font-family:'JetBrains Mono',monospace;font-size:.85rem;letter-spacing:.28em;color:#e8873a;text-transform:uppercase}}
.slide-id::before{{content:'// '}}
#hud{{position:fixed;bottom:14px;right:16px;display:flex;gap:10px;z-index:100;font-family:'JetBrains Mono',monospace;font-size:.7rem;color:#5a5248}}
#progress-bar{{position:fixed;bottom:0;left:0;height:3px;background:#e8873a;transition:width .4s ease;z-index:100}}
/* Gravação: o compositor liga esta classe no <html> antes de gravar. Contador
   e barra de progresso são navegação de preview — apareciam queimados em todos
   os slides do vídeo publicado. */
html.recording #hud,html.recording #progress-bar{{display:none!important}}
</style>
</head>
<body>
<!-- manifesto v2 — éozoré pipeline -->
<script type="application/json" id="content-manifest">
{manifest_json_str}
</script>
<div id="hud"><span id="slide-counter">1 / {n_slides}</span></div>
<div id="progress-bar" style="width:{100 // n_slides}%"></div>
{slides_html}
<script>
var slides=document.querySelectorAll('.slide');var current=0;var hudVisible=true;
// Valida ANTES de mexer em `current`. Na versão anterior um goTo com id de
// string (em vez de índice) escrevia o id em `current`, o slides[current]
// seguinte virava undefined e o deck ficava permanentemente quebrado — a
// gravação inteira saía preta a partir dali.
function goTo(i){{
  i=Number(i);
  if(!Number.isInteger(i)||i<0||i>=slides.length)return false;
  for(var k=0;k<slides.length;k++)slides[k].classList.remove('active');
  current=i;slides[current].classList.add('active');
  var c=document.getElementById('slide-counter');if(c)c.textContent=(current+1)+' / '+slides.length;
  var p=document.getElementById('progress-bar');if(p)p.style.width=(((current+1)/slides.length)*100)+'%';
  return true;
}}
function indexOfSeg(segId){{
  for(var k=0;k<slides.length;k++){{
    var s=slides[k];
    if((s.id||'')===segId||(s.dataset&&s.dataset.seg===segId))return k;
  }}
  return -1;
}}
function goToSeg(segId){{var idx=indexOfSeg(segId);return idx>=0?goTo(idx):false;}}
// Alias histórico: o compositor chamava goToSlide(id) e quebrava porque a
// função não existia neste deck.
function goToSlide(segId){{return goToSeg(segId);}}
// Reinicia as animações CSS do slide no ar: tirar e repor .active força o
// reflow e faz os @keyframes rodarem do zero.
function replaySlide(){{
  var el=slides[current];if(!el)return false;
  el.classList.remove('active');void el.offsetWidth;el.classList.add('active');
  return true;
}}
function toggleHud(){{
  hudVisible=!hudVisible;
  document.documentElement.classList.toggle('recording',!hudVisible);
  return hudVisible;
}}
function hideHud(){{hudVisible=false;document.documentElement.classList.add('recording');}}
// Revela um elemento que nasce escondido (fd2, fd3, fd4, b1-b4).
//
// O manifesto SEMPRE gerou âncoras `reveal` apontando para estes ids, e o
// gravador nunca as executava — não havia sequer esta função. Os elementos
// ficavam em `display:none` o clipe inteiro, então o slide mostrava só o
// primeiro bloco e a ilustração refletia uma fração do que era falado.
function revelar(id){{
  var el=slides[current]?slides[current].querySelector('#'+id):null;
  if(!el)el=document.getElementById(id);
  if(!el)return false;
  el.classList.remove('fd-hidden');
  el.style.removeProperty('display');
  // Reinicia a animação para o elemento ENTRAR, em vez de simplesmente
  // aparecer — é isto que dá movimento ao slide.
  el.classList.remove('fd');void el.offsetWidth;el.classList.add('fd');
  return true;
}}
function destacar(id){{
  var el=document.getElementById(id);if(!el)return false;
  el.classList.remove('pulsa');void el.offsetWidth;el.classList.add('pulsa');
  return true;
}}
window.deckAPI={{goTo:goTo,goToSeg:goToSeg,replay:replaySlide,hideHud:hideHud,
  revelar:revelar,destacar:destacar,indexOfSeg:indexOfSeg,count:slides.length}};
if(slides.length>0)goTo(0);
</script>
</body>
</html>"""


# ── Validação do manifesto (gate do produto) ──────────────────────────────────

# Fora desta faixa o vídeo deixa de ser "avatar + ilustração": abaixo vira
# apresentação sem apresentador, acima vira talking head caro.
AVATAR_SHARE_MIN = 0.10
AVATAR_SHARE_MAX = 0.40

# Duração do vídeo do YouTube, em segundos.
#
# O prompt do scriptwriter já pedia 5–12 minutos, e o vídeo de 27/08 saiu com
# 3min29 — porque NADA validava. `validate_manifest` conferia proporção de
# avatar, contagem de segmentos e fala vazia, e nenhuma duração. O mecanismo
# de 3 tentativas corretivas já existia; faltava o que checar.
#
# A causa concreta: os segmentos de slide saíram com 13,5 a 21,4s contra os
# 25–45s que o prompt manda. Por isso o piso POR SEGMENTO também está aqui —
# só o total deixaria passar um vídeo longo feito de slides atropelados.
DURACAO_MIN_S = 300      # 5 min
DURACAO_MAX_S = 720      # 12 min
SLIDE_MIN_S   = 20       # abaixo disto o slide não é lido, só piscado
AVATAR_MIN_S  = 10


def manifest_stats(manifest_dict: dict) -> dict:
    """
    Contagens do manifesto usadas pelo gate de aprovação e pelos logs.

    Trabalha sobre o dict do manifesto (não sobre o HTML), então serve tanto
    para o caminho do scriptwriter quanto para o Markdown legado.
    """
    segments = manifest_dict.get("youtube", {}).get("segments", []) or []

    def _kind(seg: dict) -> str:
        k = seg.get("kind")
        if k in ("avatar", "slide"):
            return k
        return "slide" if seg.get("slide") else "avatar"

    def _dur(seg: dict) -> float:
        d = seg.get("min_duration_s")
        if isinstance(d, (int, float)) and d > 0:
            return float(d)
        return _estimate_duration(seg.get("script") or "")

    avatar = [s for s in segments if _kind(s) == "avatar"]
    slides = [s for s in segments if _kind(s) == "slide"]
    total  = sum(_dur(s) for s in segments)
    av_dur = sum(_dur(s) for s in avatar)

    cut = manifest_dict.get("vertical_cut", {}).get("segments", []) or []

    return {
        "segment_count":      len(segments),
        "avatar_segments":    len(avatar),
        "slide_segments":     len(slides),
        "total_duration_s":   round(total, 1),
        "avatar_duration_s":  round(av_dur, 1),
        "avatar_share":       round(av_dur / total, 3) if total else 0.0,
        "vertical_cut_count": len(cut),
        "vertical_slides":    len([i for i in cut if i.get("slide")]),
    }


# ── Escopamento do CSS dos slides ─────────────────────────────────────────────

def _blocos_de_topo(css: str) -> list[tuple[str, str]]:
    r"""
    Divide o CSS em blocos de primeiro nível casando chaves de verdade.

    A versão anterior usava a regex `([^{}\n]+)\s*\{([^{}]*)\}`, que não
    enxerga aninhamento: ela entrava DENTRO de um `@keyframes` e tratava os
    passos `from {` e `to {` como se fossem seletores. O manifesto de 27/08
    saiu com regras literais `#yt-02 to { opacity: 1 }`.
    """
    css = re.sub(r"/\*[\s\S]*?\*/", "", css)
    blocos: list[tuple[str, str]] = []
    prof = 0
    ini_prelude = 0
    ini_corpo = 0
    for i, ch in enumerate(css):
        if ch == "{":
            prof += 1
            if prof == 1:
                ini_corpo = i + 1
        elif ch == "}":
            prof -= 1
            if prof == 0:
                blocos.append((css[ini_prelude:ini_corpo - 1].strip(), css[ini_corpo:i]))
                ini_prelude = i + 1
    return blocos


def _escopar_seletor(seletor: str, sid: str) -> str:
    """`.foo, .bar` → `#sid .foo, #sid .bar`; `:root`/`html`/`body` → `#sid`."""
    partes = []
    for bruto in seletor.split(","):
        alvo = bruto.strip()
        if not alvo:
            continue
        # `:root`, `html` e `body` descrevem o documento do slide quando ele é
        # standalone. No deck eles NÃO podem ser apagados: é onde o
        # slide_designer declara as custom properties. Apagá-los foi o que
        # deixou o manifesto de 27/08 com 173 referências `var(--…)` e ZERO
        # definições — todo tamanho, cor e espaçamento caiu no padrão do
        # navegador, e o slide virou texto corrido a 18px.
        #
        # Re-alvejar para `#sid` preserva as variáveis e ainda as mantém
        # herdando só dentro do slide.
        if re.fullmatch(r"(:root|html|body)", alvo, flags=re.IGNORECASE):
            partes.append(f"#{sid}")
        elif re.match(r"(:root|html|body)\b", alvo, flags=re.IGNORECASE):
            resto = re.sub(r"^(:root|html|body)\b", "", alvo, flags=re.IGNORECASE).strip()
            partes.append(f"#{sid} {resto}".strip())
        else:
            partes.append(f"#{sid} {alvo}")
    return ", ".join(partes)


def escopar_css_do_slide(raw_css: str, sid: str) -> str:
    """
    Prende o CSS de um slide ao seu próprio `#sid`, sem perder nada.

    Três coisas que a versão por regex fazia errado, todas verificadas contra
    o manifesto que foi para produção em 27/08:

      1. apagava `:root` e com ele as custom properties — o slide perdia todo
         o design e saía como texto sem estilo;
      2. entrava dentro de `@keyframes` e escopava `from`/`to` como seletor;
      3. só mantinha os `@keyframes` do PRIMEIRO slide (`shared_keyframes_added`),
         então do segundo em diante as animações não existiam.

    Os `@keyframes` agora são renomeados por slide, o que elimina tanto a
    colisão de nomes quanto a necessidade de descartar os repetidos.
    """
    sufixo = sid.replace("-", "_")
    regras: list[str] = []
    nomes_kf: set[str] = set()

    def emitir(prelude: str, corpo: str) -> None:
        nome_at = prelude.split()[0].lower() if prelude.startswith("@") else ""

        if nome_at in ("@keyframes", "@-webkit-keyframes"):
            partes = prelude.split(None, 1)
            nome = partes[1].strip() if len(partes) > 1 else ""
            if nome:
                nomes_kf.add(nome)
                regras.append(f"{partes[0]} {nome}__{sufixo} {{{corpo}}}")
            return

        if nome_at == "@font-face":
            regras.append(f"@font-face {{{corpo}}}")
            return

        if nome_at in ("@media", "@supports", "@layer", "@container"):
            internas = [
                f"{_escopar_seletor(p, sid)} {{{c}}}"
                for p, c in _blocos_de_topo(corpo)
                if p and c.strip() and not p.startswith("@")
            ]
            if internas:
                regras.append(prelude + " {\n" + "\n".join(internas) + "\n}")
            return

        if prelude.startswith("@"):      # @import, @charset e afins: descartar
            return

        if prelude and corpo.strip():
            regras.append(f"{_escopar_seletor(prelude, sid)} {{{corpo}}}")

    for prelude, corpo in _blocos_de_topo(raw_css):
        emitir(prelude, corpo)

    css = "\n".join(regras)

    # Os nomes renomeados precisam ser trocados também em quem os referencia,
    # senão a animação aponta para um `@keyframes` que não existe mais.
    for nome in nomes_kf:
        css = re.sub(
            r"(animation(?:-name)?\s*:[^;}]*?)\b" + re.escape(nome) + r"\b",
            lambda m: m.group(1) + f"{nome}__{sufixo}",
            css,
        )
    return css


def validate_manifest(manifest_dict: dict) -> tuple[list[str], dict]:
    """
    Recusa manifestos que violam a regra do produto ANTES de gastar crédito.

    Falhar aqui custa zero. Falhar depois custa uma geração de HeyGen inteira —
    foi assim que um roteiro achatado em 1 segmento virou 163s de avatar puro.

    Returns:
        (violações, estatísticas). Lista vazia = manifesto aprovado.
    """
    stats = manifest_stats(manifest_dict)
    problems: list[str] = []

    if stats["segment_count"] <= 1:
        problems.append(
            f"manifesto colapsado em {stats['segment_count']} segmento — "
            "o roteiro segmentado não chegou até aqui"
        )
    if stats["slide_segments"] == 0:
        problems.append("nenhum segmento com ilustração — o vídeo sairia 100% avatar")
    if stats["avatar_segments"] == 0:
        problems.append("nenhum segmento de avatar — o vídeo sairia sem apresentador")
    if stats["avatar_share"] > AVATAR_SHARE_MAX:
        problems.append(
            f"avatar ocupa {stats['avatar_share'] * 100:.0f}% do vídeo "
            f"(teto {AVATAR_SHARE_MAX * 100:.0f}%)"
        )
    if stats["avatar_share"] and stats["avatar_share"] < AVATAR_SHARE_MIN:
        problems.append(
            f"avatar ocupa só {stats['avatar_share'] * 100:.0f}% do vídeo "
            f"(piso {AVATAR_SHARE_MIN * 100:.0f}%)"
        )

    total = float(stats.get("total_duration_s") or 0)
    if total and total < DURACAO_MIN_S:
        problems.append(
            f"vídeo de {total / 60:.1f} min — abaixo do piso de "
            f"{DURACAO_MIN_S // 60} min. Alongue os segmentos existentes ou "
            f"acrescente blocos de aplicação; não corte o assunto"
        )
    if total > DURACAO_MAX_S:
        problems.append(
            f"vídeo de {total / 60:.1f} min — acima do teto de "
            f"{DURACAO_MAX_S // 60} min"
        )

    # Um total dentro da faixa pode esconder muitos slides curtos demais.
    curtos = []
    for seg in manifest_dict.get("youtube", {}).get("segments", []):
        d = seg.get("min_duration_s")
        if not isinstance(d, (int, float)):
            continue
        kind = seg.get("kind") or ("slide" if seg.get("slide") else "avatar")
        piso = SLIDE_MIN_S if kind == "slide" else AVATAR_MIN_S
        if d < piso:
            curtos.append(f"{seg.get('id')} ({kind}, {d:.0f}s < {piso}s)")
    if curtos:
        problems.append("segmentos curtos demais: " + ", ".join(curtos[:6]))

    # Os dois CTAs. O roteiro fechava no assunto e nunca convidava a nada —
    # nenhum dos beats disponíveis era CTA, e o roteirista não era instruído a
    # criar um. Regra em prompt sozinha o modelo ignora; esta recusa força a
    # regeração.
    beats = [str(s.get("beat") or "").lower()
             for s in manifest_dict.get("youtube", {}).get("segments", [])]
    if "cta_meio" not in beats:
        problems.append(
            "sem `cta_meio` — falta o convite no meio do vídeo, amarrado ao "
            "assunto"
        )
    if "cta_artigo" not in beats:
        problems.append(
            "sem `cta_artigo` — falta mandar quem quer a versão técnica para "
            "o artigo"
        )
    if beats and beats[-1] in ("cta_meio", "cta_artigo"):
        problems.append(
            "o vídeo termina num pedido; o último segmento tem que ser o resumo"
        )

    missing_script = [
        s.get("id") for s in manifest_dict.get("youtube", {}).get("segments", [])
        if not (s.get("script") or "").strip()
    ]
    if missing_script:
        problems.append(f"segmentos sem fala: {', '.join(map(str, missing_script))}")

    return problems, stats
