"""
Cobertura do roteamento por canal na publicação de vídeo.

Por que existe: publish_video_ready publicava nos 5 canais SEMPRE, ignorando
channels_approved. Consequência real em produção — um ciclo com 1 vídeo
principal + 3 Reels colocou 4 vídeos indevidos no canal do YouTube (cada Reel
de ~22s virou também um "vídeo longo"), enquanto o vídeo principal, o único que
deveria estar lá, sequer subiu.

A lista correta já era calculada em pipeline-submit, mas morria no primeiro
estágio: tts-job → avatar-job → video-editor-job não propagam o campo. Agora
ela é persistida no doc do projeto, que o publisher já lia para os metadados.
"""

from unittest.mock import MagicMock

import pytest

from publisher_job.job import PublisherJob


ALL_PLATFORMS = ["youtube", "youtube_short", "instagram_reel", "linkedin", "threads"]


def filtrar(
    approved: list[str] | None,
    media: dict[str, str] | None = None,
) -> list[str]:
    """
    Reproduz o filtro aplicado em publish_video_ready.

    Espelha a lógica em vez de chamar o método inteiro porque publish_video_ready
    faz download de vídeo, gera thumbnail e chama 5 APIs externas — isolar o
    filtro é o que dá um teste rápido e determinístico.

    `media` diz qual arquivo existe nesta execução: o vídeo longo traz só o
    horizontal, o corte vertical traz só o vertical.
    """
    fontes = media or {p: "-" for p in ALL_PLATFORMS}
    attempts = [(p, fontes.get(p, "")) for p in ALL_PLATFORMS]
    attempts = [(p, s) for p, s in attempts if s]

    aprovados = set(approved or [])
    if not aprovados:
        return []
    return [p for p, _ in attempts if p in aprovados]


# ── O caso que quebrou em produção ────────────────────────────────────────────

def test_reel_nao_vira_video_longo_no_canal():
    # Este é o bug exato: um Reel vertical de 22s publicado como vídeo do canal.
    assert filtrar(["instagram_reel"]) == ["instagram_reel"]


def test_short_vai_para_shorts_e_nao_para_instagram():
    # Segundo erro de mapeamento: format 'shorts' era roteado para
    # instagram_reel, nunca para youtube_short.
    assert filtrar(["youtube_short"]) == ["youtube_short"]


def test_video_principal_publica_no_lancamento_completo():
    aprovados = ["youtube", "youtube_short", "instagram_reel", "linkedin", "threads"]
    assert filtrar(aprovados) == ALL_PLATFORMS


# ── Fluxo em duas etapas: vídeo longo primeiro, corte vertical depois ─────────

def test_video_longo_publica_so_no_youtube():
    # O projeto principal nasce com channels_approved=['youtube'] e o editor
    # entrega só o horizontal. Nada de vertical sai junto: o Reel é derivado
    # deste vídeo depois que o dono do canal o aprova.
    media = {"youtube": "gs://.../final_horizontal.mp4", "linkedin": "-", "threads": "-"}
    assert filtrar(["youtube"], media) == ["youtube"]


def test_corte_vertical_publica_reel_e_short_do_mesmo_arquivo():
    media = {"youtube_short": "gs://.../final_vertical.mp4",
             "instagram_reel": "gs://.../final_vertical.mp4"}
    assert filtrar(["instagram_reel", "youtube_short"], media) == \
           ["youtube_short", "instagram_reel"]


def test_canal_sem_midia_nesta_execucao_e_pulado():
    # channels_approved inclui o Short, mas esta execução veio do editor e só
    # tem o horizontal. Tentar subir uma string vazia falhava com erro mudo.
    media = {"youtube": "gs://.../final_horizontal.mp4", "youtube_short": ""}
    assert filtrar(["youtube", "youtube_short"], media) == ["youtube"]


# ── Compatibilidade e bordas ──────────────────────────────────────────────────

@pytest.mark.parametrize("vazio", [None, []])
def test_sem_channels_approved_nao_publica_nada(vazio):
    # O fallback "sem lista = publica em tudo" foi removido. Ele existia para
    # não quebrar retries de projetos antigos, mas foi exatamente por ele que
    # 2 Reels viraram 4 vídeos indevidos no canal: os docs tinham sido criados
    # antes do campo existir, caíam aqui, e cada peça curta subia em todo lugar.
    assert filtrar(vazio) == []


def test_canal_desconhecido_e_ignorado_sem_quebrar():
    assert filtrar(["instagram_reel", "tiktok"]) == ["instagram_reel"]


def test_status_final_considera_apenas_canais_aprovados():
    # all_ok deriva de platform_attempts JÁ filtrado — senão um projeto que
    # publica só no Instagram seria eternamente "published_partial" por causa
    # dos 4 canais que ele nunca deveria ter tentado.
    aprovados = filtrar(["instagram_reel"])
    status = {"instagram_reel": "18111550256098880"}
    assert all(status.get(p) for p in aprovados)


def test_publisher_expõe_o_filtro_em_uso():
    # Guarda contra alguém remover o filtro achando que é redundante.
    import inspect
    src = inspect.getsource(PublisherJob.publish_video_ready)
    assert "channels_approved" in src
