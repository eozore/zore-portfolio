"""
agents/pipeline/shared/captions.py
===================================
Legendas queimadas para a peça vertical (Reel / Short).

Por que existe: a maior parte do público de Reels e Shorts assiste SEM SOM.
Uma peça vertical sem legenda perde o espectador nos primeiros segundos, por
melhor que seja o áudio. Até aqui o corte vertical do CSM saía sem legenda
nenhuma.

━━━ De onde vêm os tempos ━━━

Do próprio ElevenLabs. O endpoint `/with-timestamps` devolve, junto com o
áudio, o instante de início e fim de CADA CARACTERE sintetizado — pelo mesmo
preço da chamada normal.

A referência desta feature (MoneyPrinterTurbo) roda Whisper por cima do áudio
já gerado para descobrir os tempos. Isso é ASR: custa CPU, adiciona uma
dependência pesada ao job, e ainda erra — é um modelo *adivinhando* o que foi
dito a partir da forma de onda. Aqui o motor que produziu a fala já sabe
exatamente quando disse cada letra, então a legenda encaixa no frame certo sem
inferência nenhuma.

━━━ Por que ASS e não SRT ━━━

SRT não tem posicionamento, contorno nem destaque por palavra. ASS tem:
  - contorno grosso, que mantém o texto legível sobre qualquer fundo;
  - margem inferior generosa, para o texto não cair atrás da UI do
    Instagram/TikTok (botões, legenda do autor, barra de progresso);
  - karaokê `\\k`, o destaque palavra-a-palavra que segura a atenção.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# ── Grafia falada → grafia escrita ────────────────────────────────────────────
#
# O roteirista escreve o script em português fonético para o ElevenLabs
# pronunciar termos em inglês corretamente (REGRA 2 do scriptwriter_agent). É
# certo para o ÁUDIO e errado para a TELA: a legenda vem do mesmo texto, então
# o vídeo saía com "no primeiro prómpti", "quantidade de tóquens" e "enviado
# para a ê-pê-í" queimados na imagem. Num canal técnico isso lê como erro de
# português, e apareceu nos dois Shorts de 31/08.
#
# A tabela é o inverso EXATO da do scriptwriter, que é declarada lá como
# exaustiva — por isso a reversão é segura. Se um termo entrar lá, entra aqui.
PRONUNCIA_PARA_ESCRITA: dict[str, str] = {
    "lóra": "LoRA", "qiu-lóra": "QLoRA", "tiny-lóra": "TinyLoRA",
    "fain-tiúning": "fine-tuning", "tóquens": "tokens", "tóquen": "token",
    "freim-uórc": "framework", "éli-éli-êmi": "LLM", "ê-pê-í": "API",
    "êmbeding": "embedding", "bátch": "batch", "rênqui": "rank",
    "prómpti": "prompt", "prómptis": "prompts", "ínsait": "insight",
    "deplói": "deploy", "déshbord": "dashboard", "deitasséti": "dataset",
    "paip-lain": "pipeline", "mochin lérning": "machine learning",
    "cláud": "cloud", "tésti": "test", "cômit": "commit",
    "rilís": "release", "rôl-béqui": "rollback", "quéxi": "cache",
    "endi-point": "endpoint", "fítcher": "feature", "lógui": "log",
    "esse-qiu-éle": "SQL", "guê-cê-pê": "GCP", "á-dábliu-ésse": "AWS",
    "eme-éle-ops": "MLOps", "guê-pê-u": "GPU", "pê-valor": "p-valor",
    # Termos de duas palavras entram também partidos: a reversão acontece
    # palavra a palavra (é assim que o alinhamento do ElevenLabs chega), e
    # "mochin lérning" nunca casaria inteiro.
    "mochin": "machine", "lérning": "learning",
    "fain": "fine", "tiúning": "tuning",
}

# Ordenado por tamanho decrescente: "prómptis" tem que casar antes de
# "prómpti", senão sobra um "s" solto na tela.
_PRONUNCIA_RE = re.compile(
    r"(?<!\w)(" + "|".join(
        re.escape(k) for k in sorted(PRONUNCIA_PARA_ESCRITA, key=len, reverse=True)
    ) + r")(?!\w)",
    re.IGNORECASE,
)


def desfonetizar(texto: str) -> str:
    """
    Devolve a grafia REAL dos termos que o script escreveu por pronúncia.

    Só a legenda passa por aqui. O áudio continua sendo gerado a partir do
    texto fonético — trocar lá quebraria a pronúncia, que é o motivo de a
    grafia existir.
    """
    def troca(m: re.Match) -> str:
        certo = PRONUNCIA_PARA_ESCRITA[m.group(1).lower()]
        # "Prómpti" no começo da frase vira "Prompt", não "prompt".
        return certo.capitalize() if m.group(1)[:1].isupper() and certo.islower() else certo

    return _PRONUNCIA_RE.sub(troca, texto)


# ── Legibilidade das cues ─────────────────────────────────────────────────────
# Números pensados para 9:16 em tela de celular: uma cue curta o suficiente
# para ser lida de relance, longa o suficiente para não piscar.
MAX_CUE_CHARS     = 30
MAX_CUE_SECONDS   = 2.6
MAX_CUE_WORDS     = 5
# Pausa na fala acima disto quebra a cue, mesmo sem atingir os limites acima:
# é onde o apresentador respira, e a legenda deve acompanhar a frase.
CUE_BREAK_GAP_S   = 0.45

# ── Estilo ────────────────────────────────────────────────────────────────────
# Cores ASS são &HAABBGGRR — alpha, BLUE, GREEN, RED (BGR invertido, não RGB).
# Errar a ordem é o engano clássico: #e8873a vira azul se escrito como RRGGBB.
#
# No karaokê do ASS, SecondaryColour é a cor ANTES da sílaba ser alcançada e
# PrimaryColour é a cor DEPOIS. Por isso o estilo usa laranja como Primary e
# branco como Secondary: a palavra entra branca e ACENDE em laranja quando é
# falada. Invertido (Primary branco), a palavra já nasceria destacada e
# apagaria ao ser dita — o olho seguiria o texto ainda não falado.
ASS_WHITE        = "&H00FFFFFF"
ASS_BLACK        = "&H00000000"
ASS_BRAND_ORANGE = "&H003A87E8"   # #e8873a (R=232 G=135 B=58) invertido
ASS_TRANSPARENT  = "&HFF000000"


@dataclass
class WordTiming:
    text:    str
    start_s: float
    end_s:   float

    def shifted(self, offset_s: float) -> "WordTiming":
        return WordTiming(self.text, self.start_s + offset_s, self.end_s + offset_s)


@dataclass
class Cue:
    words: list[WordTiming] = field(default_factory=list)

    @property
    def start_s(self) -> float:
        return self.words[0].start_s

    @property
    def end_s(self) -> float:
        return self.words[-1].end_s

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


# ── Alinhamento do ElevenLabs → palavras ──────────────────────────────────────


def words_from_alignment(alignment: dict) -> list[WordTiming]:
    """
    Converte o alinhamento por CARACTERE do ElevenLabs em palavras.

    Formato de entrada (resposta de /with-timestamps):
        {"characters": ["O", " ", "t", "e", ...],
         "character_start_times_seconds": [0.0, 0.05, ...],
         "character_end_times_seconds":   [0.05, 0.11, ...]}

    Uma palavra começa no primeiro caractere não-espaço e termina no último.
    Pontuação fica colada na palavra anterior — quebrar "decisão." em
    "decisão" + "." produziria uma cue com um ponto solto piscando na tela.
    """
    chars   = alignment.get("characters") or []
    starts  = alignment.get("character_start_times_seconds") or []
    ends    = alignment.get("character_end_times_seconds") or []

    if not chars or len(chars) != len(starts) or len(chars) != len(ends):
        logger.warning(
            "[captions] Alinhamento inconsistente: %d chars, %d starts, %d ends",
            len(chars), len(starts), len(ends),
        )
        return []

    words: list[WordTiming] = []
    buf: list[str] = []
    buf_start: Optional[float] = None
    buf_end = 0.0

    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append(WordTiming("".join(buf), buf_start or 0.0, buf_end))
                buf, buf_start = [], None
            continue
        if buf_start is None:
            buf_start = float(s)
        buf.append(ch)
        buf_end = float(e)

    if buf:
        words.append(WordTiming("".join(buf), buf_start or 0.0, buf_end))

    # A grafia fonética morre AQUI, na fronteira entre áudio e tela. O
    # alinhamento vem do texto que foi falado, então carrega "prómpti" e
    # "ê-pê-í"; a partir deste ponto tudo que existe é legenda.
    return [
        WordTiming(desfonetizar(w.text), w.start_s, w.end_s) for w in words
    ]


# ── Palavras → cues ───────────────────────────────────────────────────────────

# Palavras que não podem FECHAR uma cue: preposições, artigos, conjunções e
# pronomes relativos. Terminar nelas deixa a frase pendurada — o leitor
# entende que vem um complemento e a legenda troca antes de ele aparecer.
FUNCIONAIS = frozenset("""
a o as os um uma uns umas de do da dos das em no na nos nas por pelo pela
para pra com sem sob sobre entre até desde após ante e ou mas que se como
quando onde qual quais cujo cuja ao aos à às num numa dum duma
""".split())

# Quanto a cue pode passar do limite para não fechar numa palavra funcional.
# Pequeno de propósito: é um ajuste de leitura, não uma licença para cue longa.
FOLGA_CHARS    = 8
FOLGA_SEGUNDOS = 0.4


def _limpa(palavra: str) -> str:
    return "".join(c for c in palavra.lower() if c.isalnum() or c == "-")


def _funcional(palavra: str) -> bool:
    return _limpa(palavra) in FUNCIONAIS


def _termina_frase(palavra: str) -> bool:
    return palavra.rstrip().endswith((".", "?", "!", ":", ";"))



def group_into_cues(
    words: Iterable[WordTiming],
    max_chars: int = MAX_CUE_CHARS,
    max_seconds: float = MAX_CUE_SECONDS,
    max_words: int = MAX_CUE_WORDS,
) -> list[Cue]:
    """
    Agrupa palavras em blocos legíveis.

    Quebra quando qualquer um dos limites é atingido, OU quando há uma pausa
    real na fala — respeitar a respiração do apresentador faz a legenda
    parecer editada à mão em vez de fatiada por contador de caracteres.
    """
    cues: list[Cue] = []
    current = Cue()
    lista = list(words)

    for i, word in enumerate(lista):
        if current.words:
            anterior   = current.words[-1]
            gap        = word.start_s - anterior.end_s
            would_be   = len(current.text) + 1 + len(word.text)
            duration   = word.end_s - current.start_s
            estourou   = (
                gap >= CUE_BREAK_GAP_S
                or would_be > max_chars
                or duration > max_seconds
                or len(current.words) >= max_words
            )

            # Fim de frase quebra SEMPRE, mesmo sem estourar limite.
            #
            # Sem isto, a cue juntava o fim de uma frase com o começo da
            # seguinte — "atrás? O vibe coding parece" — e o leitor recebia
            # duas ideias no mesmo piscar.
            if _termina_frase(anterior.text):
                estourou = True

            # E nunca termina numa palavra funcional. O olho para em "no",
            # "a", "que", fica esperando o complemento, e a cue troca antes
            # de ele chegar. Adiar uma palavra é mais barato que quebrar a
            # leitura — desde que ainda caiba.
            elif estourou and _funcional(anterior.text) and len(current.words) > 1:
                if (
                    would_be <= max_chars + FOLGA_CHARS
                    and duration <= max_seconds + FOLGA_SEGUNDOS
                    and gap < CUE_BREAK_GAP_S
                ):
                    estourou = False

            if estourou:
                cues.append(current)
                current = Cue()
        current.words.append(word)

    if current.words:
        cues.append(current)
    return cues


# ── Cues → ASS ────────────────────────────────────────────────────────────────


def _ass_time(seconds: float) -> str:
    """ASS usa H:MM:SS.cc — centésimos, não milésimos."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape(text: str) -> str:
    """
    Neutraliza o que o parser do ASS interpretaria como marcação.

    `{` e `}` delimitam tags de override — um script que contenha chaves
    (JSON falado, código) apagaria o resto da linha silenciosamente.
    """
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", " ")
    )


def build_ass(
    cues: list[Cue],
    width: int,
    height: int,
    *,
    highlight: bool = True,
    uppercase: bool = False,
    font: str = "DejaVu Sans",
) -> str:
    """
    Monta o arquivo ASS completo.

    Args:
        highlight: destaque palavra-a-palavra (karaokê). Desligue para uma
                   legenda estática, mais sóbria.
        uppercase: caixa alta. Comum em Reels, mas prejudica a leitura em
                   português, onde os acentos ficam apertados — default off.
        font:      precisa existir NO CONTAINER. "DejaVu Sans" vem no
                   python:slim-bookworm; uma fonte ausente faz o libass cair
                   num fallback silencioso e a legenda sai com outro desenho.
    """
    # Escala com a altura do vídeo: o mesmo número absoluto ficaria minúsculo
    # em 1920 de altura e gigante numa prévia de 720.
    font_size    = max(16, round(height * 0.045))
    outline      = max(2, round(height * 0.0035))
    shadow       = max(1, round(height * 0.0012))
    # Margem inferior alta de propósito: Instagram e TikTok desenham a própria
    # UI sobre os ~15% de baixo. Legenda ali fica atrás dos botões.
    margin_v     = round(height * 0.16)
    margin_h     = round(width * 0.07)

    header = f"""[Script Info]
; Legendas geradas pelo CSM éozoré a partir do alinhamento do ElevenLabs.
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,{font},{font_size},{ASS_BRAND_ORANGE},{ASS_WHITE},{ASS_BLACK},{ASS_TRANSPARENT},-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines: list[str] = []
    for cue in cues:
        if highlight:
            parts: list[str] = []
            for i, word in enumerate(cue.words):
                # A duração do \k vai até o INÍCIO da próxima palavra, não até
                # o fim desta: senão o destaque apaga durante a pausa entre
                # palavras e o efeito pisca.
                next_start = (
                    cue.words[i + 1].start_s if i + 1 < len(cue.words) else word.end_s
                )
                centis = max(1, round((next_start - word.start_s) * 100))
                text   = word.text.upper() if uppercase else word.text
                parts.append(f"{{\\k{centis}}}{_escape(text)}")
            body = " ".join(parts)
        else:
            body = _escape(cue.text.upper() if uppercase else cue.text)

        lines.append(
            f"Dialogue: 0,{_ass_time(cue.start_s)},{_ass_time(cue.end_s)},"
            f"Legenda,,0,0,0,,{body}"
        )

    return header + "\n".join(lines) + "\n"


def write_ass(
    cues: list[Cue],
    dest: str | Path,
    width: int,
    height: int,
    **kwargs,
) -> Path:
    dest = Path(dest)
    dest.write_text(build_ass(cues, width, height, **kwargs), encoding="utf-8")
    logger.info("[captions] %d cues → %s", len(cues), dest.name)
    return dest


# ── Fallback: sem alinhamento, estima pelo texto ──────────────────────────────


def words_from_text_estimated(text: str, duration_s: float) -> list[WordTiming]:
    """
    Distribui as palavras proporcionalmente ao seu tamanho ao longo da duração.

    Usado só quando o alinhamento não existe — áudio gerado por uma versão
    anterior do tts_job, ou uma resposta do ElevenLabs sem o campo. A sincronia
    é aproximada, mas uma legenda levemente adiantada continua muito melhor do
    que peça vertical nenhuma.
    """
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    if not tokens or duration_s <= 0:
        return []

    total_chars = sum(len(t) for t in tokens)
    words: list[WordTiming] = []
    cursor = 0.0
    for token in tokens:
        share = (len(token) / total_chars) * duration_s
        # Mesma fronteira do caminho com alinhamento: daqui para frente é
        # legenda, e legenda não mostra grafia de pronúncia.
        words.append(WordTiming(desfonetizar(token), cursor, cursor + share))
        cursor += share
    return words
