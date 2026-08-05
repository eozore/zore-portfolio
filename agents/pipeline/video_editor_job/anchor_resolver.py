# -*- coding: utf-8 -*-
"""
anchor_resolver.py — Sprint 3 / G3
====================================
Converte anchors[] de um segmento do manifesto v2 em SlideTransition objects,
calculando o timestamp (segundos) dentro do clipe de avatar em que cada
âncora deve disparar.

Algoritmo de resolução de timing:
  1. Normaliza as posições de cada on_phrase dentro do script usando a posição
     de caractere da primeira ocorrência (case-insensitive) como proxy para
     tempo de fala (assumindo velocidade de fala linear).
  2. Mapeia posição normalizada [0..1] → timestamp [0..audio_duration].
  3. Para âncoras do tipo show_slide, garante t >= 0 (começo do segmento).
  4. Para âncoras sem on_phrase encontrada (frases não existentes no script),
     distribui linearmente entre 0 e audio_duration.

Módulo puro — sem I/O, sem dependências externas além de stdlib.
Testável isoladamente com python3 -c "from anchor_resolver import ..."
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SlideTransition:
    """
    Representa uma transição de slide num ponto específico do timeline.

    Attributes:
        time_s:      Timestamp (segundos) dentro do clipe de avatar onde a âncora dispara.
        action:      "show_slide" | "reveal" | "highlight"
        element:     ID CSS do elemento a ser revelado/destacado (ex: "fd2", "b3"). Pode ser None.
        on_phrase:   Frase original que disparou este evento (para debug/log).
        seg_id:      ID do segmento origem (para log).
    """
    time_s:     float
    action:     str
    element:    Optional[str] = None
    on_phrase:  str = ""
    seg_id:     str = ""

    def __repr__(self) -> str:
        elem = f" → #{self.element}" if self.element else ""
        return f"SlideTransition(t={self.time_s:.2f}s, {self.action}{elem}, phrase={self.on_phrase!r})"


def _normalise(text: str) -> str:
    """Remove acentuação e lowercase para matching case/accent-insensitive."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _find_phrase_position(script: str, on_phrase: str) -> Optional[float]:
    """
    Retorna a posição normalizada [0..1] da primeira ocorrência de on_phrase
    dentro do script, ou None se não encontrada.

    A posição é calculada pelo centro da match (inicio_char + metade do comprimento)
    dividido pelo comprimento total do script — proxy linear para tempo de fala.
    """
    if not script or not on_phrase:
        return None

    norm_script = _normalise(script)
    norm_phrase = _normalise(on_phrase)

    # Tenta match exato primeiro
    idx = norm_script.find(norm_phrase)
    if idx == -1:
        # Tenta com os primeiros 4 tokens (pode haver variação no script)
        tokens = norm_phrase.split()[:4]
        if tokens:
            pattern = r"\s+".join(re.escape(t) for t in tokens)
            m = re.search(pattern, norm_script)
            if m:
                idx = m.start()

    if idx == -1:
        return None

    center = idx + len(norm_phrase) / 2
    return min(1.0, max(0.0, center / max(len(script), 1)))


def resolve_anchors(
    segment: dict,
    audio_duration_s: float,
    *,
    min_gap_s: float = 0.25,
) -> list[SlideTransition]:
    """
    Converte os anchors[] de um segmento do manifesto v2 em SlideTransitions
    com timestamp absoluto (em segundos dentro do clipe de avatar).

    Args:
        segment:          Dict de segmento do manifesto v2.
                          Campos usados: "id", "script", "anchors".
        audio_duration_s: Duração real do áudio TTS do segmento (segundos).
                          Obtida via ffprobe sobre o .wav do segmento.
        min_gap_s:        Gap mínimo entre transições consecutivas (evita
                          múltiplas transições no mesmo frame).

    Returns:
        Lista de SlideTransition ordenada por time_s, pronta para ser
        consumida por _compose_timeline_v2().
    """
    anchors: list[dict] = segment.get("anchors", []) or []
    if not anchors:
        return []

    script   = segment.get("script", "")
    seg_id   = segment.get("id", "?")
    n        = len(anchors)

    # Posições normalizadas [0..1] para cada âncora
    positions: list[float] = []
    for anchor in anchors:
        on_phrase = anchor.get("on_phrase", "")
        pos = _find_phrase_position(script, on_phrase)
        positions.append(pos)  # pode ser None se não encontrada

    # Âncoras sem posição recebem distribuição linear uniforme como fallback
    none_count = positions.count(None)
    if none_count == n:
        # Nenhuma frase encontrada — distribui uniformemente
        positions = [i / max(n, 1) for i in range(n)]
    else:
        found_positions = [p for p in positions if p is not None]
        avg_step = 1.0 / max(n + 1, 2)
        cursor = avg_step
        for i, p in enumerate(positions):
            if p is None:
                positions[i] = min(1.0, cursor)
                cursor += avg_step

    # Converte posições → timestamps absolutos
    raw: list[SlideTransition] = []
    for anchor, pos in zip(anchors, positions):
        t = round(float(pos) * audio_duration_s, 3)  # type: ignore[arg-type]
        raw.append(SlideTransition(
            time_s    = t,
            action    = anchor.get("action", "show_slide"),
            element   = anchor.get("element"),
            on_phrase = anchor.get("on_phrase", ""),
            seg_id    = seg_id,
        ))

    # Ordena e aplica gap mínimo para evitar transições sobrepostas
    raw.sort(key=lambda tr: tr.time_s)
    result: list[SlideTransition] = []
    last_t = -999.0
    for tr in raw:
        t = max(tr.time_s, last_t + min_gap_s)
        t = min(t, audio_duration_s - 0.05)   # nunca além do final do clipe
        t = max(t, 0.0)
        result.append(SlideTransition(
            time_s    = round(t, 3),
            action    = tr.action,
            element   = tr.element,
            on_phrase = tr.on_phrase,
            seg_id    = tr.seg_id,
        ))
        last_t = t

    return result


def resolve_manifest_anchors(
    segments: list[dict],
    audio_durations: dict[str, float],
) -> dict[str, list[SlideTransition]]:
    """
    Processa todos os segmentos do manifesto de uma vez.

    Args:
        segments:        Lista de segmentos (manifest["youtube"]["segments"]).
        audio_durations: Mapeamento {seg_id: duration_s} obtido via ffprobe
                         sobre os arquivos .wav do TTS job.

    Returns:
        Dict {seg_id: [SlideTransition, ...]} para todos os segmentos
        que possuem anchors[].
    """
    result: dict[str, list[SlideTransition]] = {}
    for seg in segments:
        seg_id = seg.get("id", "")
        anchors = seg.get("anchors", [])
        if not anchors:
            continue
        dur = audio_durations.get(seg_id, seg.get("min_duration_s", 5.0))
        transitions = resolve_anchors(seg, float(dur))
        if transitions:
            result[seg_id] = transitions
    return result
