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
            "overlay":    {
                "mode":             "slide-full",
                "avatar_position":  "bottom-right",
                "avatar_scale":     0.28,
            },
            "segments": [s.to_dict() for s in h_segments],
        },
        "reels": [
            {
                "reel_id":    "reel-01",
                "title":      f"Reel 01 — {title[:50]}",
                "deck":       "r1",
                "resolution": {"width": 1080, "height": 1920},
                "overlay":    {
                    "mode":            "slide-full",
                    "avatar_position": "bottom-center",
                    "avatar_scale":    0.35,
                },
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
    shared_keyframes_added = False  # evita duplicar @keyframes em cada slide

    for sid in slide_ids:
        designer_html = _slide_htmls_cache.get(sid, "") if _slide_htmls_cache else ""
        if designer_html:
            # Extrai bloco <style> do HTML gerado pelo slide_designer
            style_match = re.search(r'<style[^>]*>([\s\S]*?)</style>', designer_html, re.IGNORECASE)
            body_match  = re.search(r'<body[^>]*>([\s\S]*?)</body>', designer_html, re.IGNORECASE)

            scoped_style = ""
            if style_match:
                raw_css = style_match.group(1)

                # 1. Extrair @keyframes separadamente (não precisam de escopo)
                keyframes = re.findall(r'@keyframes\s+\w+\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}', raw_css)

                # 2. Remover @keyframes do CSS principal para reprocessar
                css_no_kf = re.sub(r'@keyframes\s+\w+\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}', '', raw_css)

                # 3. Remover regras que se aplicam ao html/body do documento do slide
                #    (seriam corretas em documento standalone, mas vazam no manifesto)
                css_no_kf = re.sub(
                    r'(?:html\s*,\s*body|html|body|:root)\s*\{[^}]*\}',
                    '',
                    css_no_kf,
                    flags=re.IGNORECASE,
                )

                # 4. Remover regras de .slide e .slide.active que conflitam com o
                #    sistema de navegação do manifesto
                css_no_kf = re.sub(
                    r'\.slide(?:\.active)?\s*\{[^}]*\}',
                    '',
                    css_no_kf,
                    flags=re.IGNORECASE,
                )

                # 5. Escopar todas as regras restantes ao #sid
                #    para que seletores como "div", ".content", etc. não vazem
                scoped_rules = []
                for rule in re.finditer(
                    r'([^{}\n]+)\s*\{([^{}]*)\}',
                    css_no_kf,
                    re.MULTILINE,
                ):
                    selector = rule.group(1).strip()
                    props    = rule.group(2).strip()
                    if not selector or not props:
                        continue
                    # Escopar: ".foo { ... }" → "#sid .foo { ... }"
                    scoped_selectors = ", ".join(
                        f"#{sid} {s.strip()}" for s in selector.split(",") if s.strip()
                    )
                    scoped_rules.append(f"{scoped_selectors} {{ {props} }}")

                kf_css = "\n".join(keyframes) if not shared_keyframes_added and keyframes else ""
                if keyframes:
                    shared_keyframes_added = True

                scoped_style = (
                    f'<style id="style-{sid}">\n'
                    f'{kf_css}\n'
                    f'{chr(10).join(scoped_rules)}\n'
                    f'</style>'
                )

            slide_content = body_match.group(1).strip() if body_match else designer_html

            slides_html_parts.append(
                f'{scoped_style}\n'
                f'<section class="slide" id="{sid}" data-seg="{sid}" '
                f'style="position:absolute;inset:0;overflow:hidden;flex-direction:column;justify-content:center;align-items:flex-start;padding:80px;background:#0d0f14;">'
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
<title>{title} — Manifesto v2 éozoré</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1920px;height:1080px;overflow:hidden;background:#0d0f14;color:#eae4dc;font-family:'Space Grotesk',sans-serif}}
.slide{{display:none!important;position:absolute;inset:0;flex-direction:column;justify-content:center;align-items:center;padding:60px;background:#0d0f14}}
.slide.active{{display:flex!important}}
.slide-id{{font-family:'JetBrains Mono',monospace;font-size:.85rem;letter-spacing:.28em;color:#e8873a;text-transform:uppercase}}
.slide-id::before{{content:'// '}}
#hud{{position:fixed;bottom:14px;right:16px;display:flex;gap:10px;z-index:100;font-family:'JetBrains Mono',monospace;font-size:.7rem;color:#5a5248}}
#progress-bar{{position:fixed;bottom:0;left:0;height:3px;background:#e8873a;transition:width .4s ease;z-index:100}}
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
var slides=document.querySelectorAll('.slide');var current=0;
function goTo(i){{if(i<0||i>=slides.length)return;slides[current].classList.remove('active');current=i;slides[current].classList.add('active');var c=document.getElementById('slide-counter');if(c)c.textContent=(current+1)+' / '+slides.length;var p=document.getElementById('progress-bar');if(p)p.style.width=(((current+1)/slides.length)*100)+'%';}}
function goToSeg(segId){{var idx=[...slides].findIndex(function(s){{return(s.id||'')===segId||(s.dataset&&s.dataset.seg===segId);}});if(idx>=0)goTo(idx);}}
window.deckAPI={{goTo:goTo,goToSeg:goToSeg,count:slides.length}};
if(slides.length>0)goTo(0);
</script>
</body>
</html>"""
