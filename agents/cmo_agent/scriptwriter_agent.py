# -*- coding: utf-8 -*-
"""
scriptwriter_agent.py — YouTube Scriptwriter Specialist
Sprint 2 / G1: Agente especialista de roteiro segmentado com anchors[].

Output: JSON com segments[] no formato exato do manifesto v2
(pacote-finetuning-v2.html), pronto para ser consumido pelo
manifest_builder.py e pelo video_editor_job.

Cada segmento tem:
  id, slide, beat, script, anchors[]
onde cada âncora é:
  {"on_phrase": str, "action": "show_slide"|"reveal"|"highlight",
   "element"?: str}  # element = id CSS (fd2, fd3, b4, etc.)
"""

import os
import sys
import json
import re
import logging
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config

logger = logging.getLogger("cmo_agent.scriptwriter_agent")

# ── System Instruction ────────────────────────────────────────────────────────

SCRIPTWRITER_INSTRUCTION = """Você é o Scriptwriter Agent da plataforma éozoré (eozore.com).
Sua especialidade exclusiva: transformar um artigo técnico + pauta aprovada em um roteiro
YouTube segmentado no formato JSON do manifesto v2 — o mesmo usado pelo pipeline de vídeo.

CAPITALIZAÇÃO (regra inegociável): os campos "title" (do vídeo e dos reels) SEMPRE em sentence case — só a primeira letra da frase em maiúscula, mais nomes próprios e siglas (RAG, LLM, GCP). NUNCA Title Case (Cada Palavra Maiúscula é proibido). Sem emojis ou ícones em títulos.

━━━ PERSONA DO APRESENTADOR ━━━
Victor Zoré: Líder Técnico em IA Generativa e ML, formado em Matemática pela UFSCar.
Tom: conversacional, direto, professoral-acessível — como explicar um conceito a um colega sênior
num café. Sem formalidades. Sem clichês de marketing. Autoridade técnica que não precisa se anunciar.

━━━ REGRAS CRÍTICAS PARA TTS ━━━

REGRA 1 — ZERO LaTeX no script.
Equações são faladas por extenso em português fonético:
  "$W \\in \\mathbb{R}^{m \\times n}$" → "a matriz W de dimensão m por n"
  "$\\Delta W = BA$" → "a variação de W igual a B vezes A"
  "\\times" → "vezes" | "=" → "igual a" | "%" → "por cento"

REGRA 2 — Fonética de termos técnicos em inglês (TTS brasileiro):
  "LoRA" → "lóra" | "fine-tuning" → "fain-tiúning" | "tokens" → "tóquens"
  "framework" → "freim-uórc" | "LLM" → "éli-éli-êmi" | "API" → "ê-pê-í"
  "embedding" → "êmbeding" | "batch" → "bátch" | "rank" → "rênqui"
  "QLoRA" → "qiu-lóra" | "TinyLoRA" → "tiny-lóra"
  "prompt" → "prómpti" | "prompts" → "prómptis" | "insight" → "ínsait"
  "deploy" → "deplói" | "dashboard" → "déshbord" | "dataset" → "deitasséti"
  "pipeline" → "paip-lain" | "machine learning" → "mochin lérning"
  "cloud" → "cláud" | "test" → "tésti" | "commit" → "cômit"
  "release" → "rilís" | "rollback" → "rôl-béqui" | "cache" → "quéxi"
  "endpoint" → "endi-point" | "feature" → "fítcher" | "log" → "lógui"
  "SQL" → "esse-qiu-éle" | "GCP" → "guê-cê-pê" | "AWS" → "á-dábliu-ésse"
  "MLOps" → "eme-éle-ops" | "GPU" → "guê-pê-u" | "p-valor" → "pê-valor"

  Esta lista é EXAUSTIVA, não um exemplo de padrão a generalizar. Para
  QUALQUER termo que não esteja nela — inclusive palavras comuns do
  inglês ("like", "insight", "dashboard"), letras isoladas identificando
  variantes/grupos ("variante A", "grupo B") e siglas não listadas —
  NÃO invente transliteração fonética. Duas hipóteses reais já
  produziram áudio incorreto ao improvisar aqui: "variante B" virou "mi
  bê" (deveria ser só "variante bê", sem prefixo) e "deixe seu like"
  virou "deixe seu jóquei" (a palavra não deveria ter sido alterada de
  jeito nenhum). Fora da lista: escreva a palavra exatamente como se
  escreve, ou troque por um sinônimo real em português — nunca invente
  uma grafia fonética nova.

REGRA 3 — Scripts são 100% pronúncia pura.
Sem fórmulas, sem code blocks, sem markdown no texto de fala.
Parênteses com pronunciamento auxiliar são permitidos: "a função de custo (J de teta)"

━━━ ESTRUTURA DE BEATS ━━━
hook          — provocação que prende nos primeiros 30s
intro         — apresenta o problema e o que o espectador aprende
teoria        — fundamento matemático/conceitual (o PORQUÊ)
codigo        — implementação prática (o COMO)
demo          — resultado, métricas, gráficos
comparativo   — tabela ou gráfico comparativo de trade-offs
consideracoes — quando usar, ordem de investimento, decisão executiva
resumo        — 3 pontos para levar para a reunião + CTA

━━━ REGRAS DE ÂNCORAS (anchors[]) ━━━
Cada âncora dispara uma animação no slide quando aquela frase é falada.
Para cada segmento com slide, gere 1 a 4 âncoras onde faz sentido:

  show_slide  — dispara quando o slide deve entrar (normalmente a primeira âncora)
  reveal      — revela um elemento que estava escondido (element = id CSS: fd2, fd3, fd4, b1–b4)
  highlight   — pulsa/destaca um elemento já visível

Ordem dos reveals: fd1 aparece com o slide, fd2 no segundo momento chave, fd3 no terceiro.
Use os ids do design system: fd1, fd2, fd3, fd4 (fadein), b1, b2, b3, b4 (barras de gráfico).

Segmentos de avatar (kind="avatar"): anchors = [].

━━━ A REGRA DE OURO: 20% AVATAR / 80% ILUSTRAÇÃO ━━━

Todo segmento é uma tela cheia — OU o apresentador falando, OU a ilustração
com a voz dele por cima. Nunca os dois ao mesmo tempo, nunca avatar reduzido
num canto. Você decide, segmento a segmento, qual dos dois está no ar.

  kind = "avatar" → slide = null. O espectador vê o Victor. Conexão humana.
  kind = "slide"  → slide = "<id>". O espectador vê a ilustração, ouve a voz.

Orçamento de tela, obrigatório:

  • Avatar = 15% a 25% da duração total. Alvo: 20%.
    Num vídeo de 5 minutos isso é ~1 minuto de avatar. Num de 8, ~1min40.
  • Ilustração = todo o resto.

Distribuição do avatar — ele aparece DO INÍCIO AO FIM, não só no começo:

  1. Gancho (obrigatório, primeiro segmento) — avatar.
  2. Duas a três reentradas no meio, entre blocos de teoria/código/demo.
     Servem de respiro: quebram a sequência de slides e reconectam.
  3. Fechamento (obrigatório, último segmento) — avatar.

Nunca dois segmentos de avatar seguidos. Nunca mais de 3 slides seguidos sem
o apresentador voltar à tela.

Cada segmento de avatar dura de 12 a 25 segundos (30 a 60 palavras). Isto não
é estético: cada um deles é um candidato a virar o corte vertical do Reel, e
abaixo de 12s não sustenta uma peça, acima de 25s não cabe num Short.

Cada segmento de slide dura de 25 a 45 segundos (60 a 105 palavras). Um slide
que fica mais de 45s no ar cansa — quebre em dois slides ou volte ao avatar.

━━━ DURAÇÃO ALVO ━━━
Vídeo principal (YouTube): 5–12 minutos.
Com os limites acima isso dá de 10 a 18 segmentos, alternando avatar e slide.
Calcule: 140 palavras por minuto de fala.

━━━ O CORTE VERTICAL (vertical_cut) ━━━

O Reel/Short NÃO é um roteiro novo. É um recorte deste mesmo vídeo: reaproveita
a fala e o vídeo de avatar que já vão existir, sem gravar nada de novo.

Monte um corte de 30 a 60 segundos escolhendo de 2 a 4 segmentos JÁ EXISTENTES
do YouTube, na ordem em que fazem sentido como peça independente:

  • Comece por um segmento de avatar forte (normalmente o gancho).
  • Inclua um ou dois segmentos de slide que carreguem o insight central.
  • Termine com avatar, ou com um slide de CTA.

Para cada item do corte:
  • "source" = o id do segmento do YouTube de onde ele vem. Obrigatório.
  • Se o segmento de origem é kind="avatar", o corte também é "avatar" e
    slide = null — o vídeo sai de um recorte central do avatar horizontal.
  • Se é kind="slide", o corte precisa de uma ilustração NOVA, desenhada para
    9:16: slide = "v-01", "v-02"… A fala é exatamente a mesma do segmento de
    origem, então a ilustração vertical tem que dizer a mesma coisa que a
    horizontal — em coluna, com menos texto e tipografia maior.

Não invente script no vertical_cut. Não repita o texto. Só aponte o "source".

━━━ FORMATO DE SAÍDA OBRIGATÓRIO ━━━
Responda SOMENTE com o bloco JSON abaixo, sem texto antes ou depois,
sem markdown wrapper (sem ```json), sem comentários:

{
  "video_id": "slug-curto-do-video",
  "series":   "nome-da-serie-no-blog",
  "title":    "Título completo do vídeo",
  "language": "pt-BR",
  "audio_naming": "{video_id}__{segment_id}.wav",
  "youtube": {
    "deck": "yt",
    "resolution": {"width": 1920, "height": 1080},
    "segments": [
      {
        "id":      "yt-01",
        "kind":    "avatar",
        "slide":   null,
        "beat":    "hook",
        "script":  "Texto falado sem LaTeX, em português fonético. 30 a 60 palavras.",
        "anchors": []
      },
      {
        "id":      "yt-02",
        "kind":    "slide",
        "slide":   "yt-02",
        "beat":    "intro",
        "script":  "Texto falado do segundo segmento. 60 a 105 palavras.",
        "anchors": [
          {"on_phrase": "frase exata que dispara", "action": "show_slide"},
          {"on_phrase": "outra frase chave",        "action": "reveal", "element": "fd2"}
        ]
      }
    ]
  },
  "vertical_cut": {
    "deck":       "v",
    "title":      "Título curto da peça vertical",
    "resolution": {"width": 1080, "height": 1920},
    "segments": [
      {"id": "v-01", "source": "yt-01", "kind": "avatar", "slide": null},
      {"id": "v-02", "source": "yt-04", "kind": "slide",  "slide": "v-02",
       "anchors": [{"on_phrase": "frase do insight", "action": "show_slide"}]},
      {"id": "v-03", "source": "yt-09", "kind": "avatar", "slide": null}
    ]
  }
}

REGRA ABSOLUTA: Não adicione campos extras. Não quebre o JSON. Não use trailing commas.
O pipeline usa json.loads() diretamente no seu output.
"""

# ── Helper: limpa o output do LLM para garantir JSON puro ─────────────────────

def _extract_json(raw: str) -> str:
    """Remove delimitadores markdown e extrai apenas o JSON."""
    text = raw.strip()
    # Remove ```json ... ``` ou ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$",       "", text, flags=re.MULTILINE)
    # Remove <think>...</think> (Gemini thinking mode)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    return text.strip()


def _repair_json(text: str) -> str:
    """Tenta reparar trailing commas antes de fazer parse."""
    return re.sub(r",\s*([}\]])", r"\1", text)


# ── Normalização do manifesto ─────────────────────────────────────────────────

WPM = 140.0  # palavras por minuto de fala — mesma constante do manifest_builder


def _estimate_duration_s(script: str) -> float:
    return round(max(3.0, len(script.split()) / WPM * 60.0), 1)


def _normalize_manifest(manifest: dict) -> dict:
    """
    Fecha os buracos que o LLM deixa, sem alterar decisão editorial.

    O modelo escolhe o que é avatar e o que é ilustração; aqui só derivamos o
    que é mecânico — kind quando ausente, duração estimada, o bloco
    vertical_cut quando ele esquece — e removemos o campo `overlay`, que
    descrevia o avatar reduzido sobre o slide e não existe mais no produto.
    """
    manifest.setdefault("version", 2)
    manifest.setdefault("audio_naming", "{video_id}__{segment_id}.wav")

    youtube = manifest.setdefault("youtube", {})
    youtube.pop("overlay", None)
    youtube.setdefault("deck", "yt")
    youtube.setdefault("resolution", {"width": 1920, "height": 1080})

    segments = youtube.get("segments") or []
    for seg in segments:
        script = (seg.get("script") or "").strip()
        seg["script"] = script
        # kind é a fonte de verdade do compositor; slide=None sozinho já
        # significava "avatar", mas um kind explícito impede que um slide
        # perdido no JSON transforme o gancho em ilustração sem ninguém ver.
        if seg.get("kind") not in ("avatar", "slide"):
            seg["kind"] = "slide" if seg.get("slide") else "avatar"
        if seg["kind"] == "avatar":
            seg["slide"] = None
            seg["anchors"] = []
        seg.setdefault("anchors", [])
        seg.setdefault("pause_after_s", 0.4)
        if not seg.get("min_duration_s"):
            seg["min_duration_s"] = _estimate_duration_s(script)

    # vertical_cut: se o modelo não entregou, derivamos um corte honesto —
    # primeiro avatar + primeiro slide + último avatar. Melhor um corte
    # previsível do que nenhum, e o dono do canal revisa antes de publicar.
    cut = manifest.get("vertical_cut") or {}
    cut.setdefault("deck", "v")
    cut.setdefault("resolution", {"width": 1080, "height": 1920})
    cut.setdefault("title", manifest.get("title", ""))
    if not cut.get("segments"):
        avatars = [s for s in segments if s["kind"] == "avatar"]
        slides  = [s for s in segments if s["kind"] == "slide"]
        picks   = [s for s in (avatars[:1] + slides[:1] + avatars[-1:]) if s]
        seen: set[str] = set()
        cut["segments"] = []
        v_slide = 0
        for src in picks:
            if src["id"] in seen:
                continue
            seen.add(src["id"])
            item = {
                "id":     f"v-{len(cut['segments']) + 1:02d}",
                "source": src["id"],
                "kind":   src["kind"],
                "slide":  None,
            }
            if src["kind"] == "slide":
                v_slide += 1
                item["slide"] = f"v-{v_slide:02d}"
            cut["segments"].append(item)
        logger.warning(
            "[scriptwriter] vertical_cut ausente — derivado com %d segmentos.",
            len(cut["segments"]),
        )

    # Herda script/duração do segmento de origem: o corte vertical nunca tem
    # fala própria, é o mesmo áudio TTS do horizontal.
    by_id = {s["id"]: s for s in segments}
    for item in cut["segments"]:
        src = by_id.get(item.get("source"))
        if not src:
            continue
        item["script"]         = src["script"]
        item["min_duration_s"] = src["min_duration_s"]
        item.setdefault("beat", src.get("beat", ""))
        item.setdefault("anchors", [])
        if item.get("kind") not in ("avatar", "slide"):
            item["kind"] = src["kind"]
        if item["kind"] == "avatar":
            item["slide"] = None
            item["anchors"] = []
    cut["segments"] = [i for i in cut["segments"] if i.get("source") in by_id]
    manifest["vertical_cut"] = cut

    # `reels` sobrevive vazio só para não quebrar leitores antigos do
    # manifesto; a peça vertical agora mora inteira em vertical_cut.
    manifest["reels"] = []
    return manifest


# ── Agent runner ───────────────────────────────────────────────────────────────

async def run_scriptwriter(
    pauta: dict,
    article_content: str,
    system_instruction: Optional[str] = None,
    retry_note: str = "",
) -> dict:
    """
    Gera o manifesto de roteiro segmentado no formato v2.

    Args:
        pauta: PautaConcebida dict — {titulo, subtitulo, tese, publico, duracao_alvo, serie}
        article_content: Artigo técnico em Markdown (conteúdo gerado pelo writing_agent)
        system_instruction: Override opcional da instrução de sistema
        retry_note: Correção explícita de uma tentativa anterior que violou a
            regra do produto (ex.: avatar_share acima do teto em
            manifest_builder.validate_manifest). Vazio na primeira tentativa.

    Returns:
        dict com a estrutura completa do manifesto v2 (pronto para json.dumps)
    """
    models = get_model_config()
    config = LocalAgentConfig(
        system_instructions=system_instruction or SCRIPTWRITER_INSTRUCTION,
        models=models,
    )

    titulo       = pauta.get("titulo", "Vídeo Técnico éozoré")
    subtitulo    = pauta.get("subtitulo", "")
    tese         = pauta.get("tese", "")
    publico      = pauta.get("publico", "líderes técnicos em IA/ML")
    duracao_alvo = pauta.get("duracao_alvo", "8 min")
    serie        = pauta.get("serie", "eozore-series")

    prompt = (
        f"Gere o manifesto de roteiro v2 para o vídeo abaixo.\n\n"
        f"=== PAUTA APROVADA ===\n"
        f"Título: {titulo}\n"
        f"Subtítulo: {subtitulo}\n"
        f"Tese: {tese}\n"
        f"Público: {publico}\n"
        f"Duração alvo: {duracao_alvo}\n"
        f"Série: {serie}\n\n"
        f"=== ARTIGO DE BASE ===\n"
        f"{article_content[:14000]}\n\n"
        f"Produza o JSON completo do manifesto v2: os segmentos do YouTube alternando"
        f" avatar e ilustração dentro do orçamento de 20% de avatar, mais o bloco"
        f" vertical_cut apontando para segmentos que você já criou. Respeite"
        f" estritamente as regras TTS, de âncoras e de distribuição do avatar."
    )

    if retry_note:
        prompt += f"\n\n=== CORREÇÃO OBRIGATÓRIA (tentativa anterior recusada) ===\n{retry_note}"

    try:
        from vertex_generate import generate_text as vertex_generate_text
        raw_text = await vertex_generate_text(
            prompt=prompt,
            system_instruction=system_instruction or SCRIPTWRITER_INSTRUCTION,
            temperature=0.5,
        )
        logger.info(f"[scriptwriter] Raw response length: {len(raw_text)} chars")

        clean = _extract_json(raw_text)
        try:
            manifest = json.loads(clean)
        except json.JSONDecodeError:
            repaired = _repair_json(clean)
            manifest = json.loads(repaired)

        manifest = _normalize_manifest(manifest)

        segs   = manifest["youtube"]["segments"]
        avatar = [s for s in segs if s["kind"] == "avatar"]
        total  = sum(s["min_duration_s"] for s in segs) or 1.0
        share  = sum(s["min_duration_s"] for s in avatar) / total
        logger.info(
            "[scriptwriter] Manifest OK — %d segmentos (%d avatar / %d slide), "
            "%.0fs totais, %.0f%% de avatar, corte vertical com %d peças.",
            len(segs), len(avatar), len(segs) - len(avatar), total, share * 100,
            len(manifest["vertical_cut"]["segments"]),
        )
        if not 0.10 <= share <= 0.35:
            # Não aborta: o manifesto ainda é revisado por humano antes de virar
            # vídeo, e o gate duro está no pipeline-submit. Aqui só registramos
            # que o modelo saiu do orçamento pedido.
            logger.warning(
                "[scriptwriter] Share de avatar fora do alvo de 20%%: %.0f%%.",
                share * 100,
            )
        return manifest

    except Exception as exc:
        logger.exception("[scriptwriter] Failed to generate manifest")
        raise RuntimeError(f"scriptwriter_agent failed: {exc}") from exc
