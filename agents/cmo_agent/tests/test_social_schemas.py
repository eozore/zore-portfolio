"""
tests/test_social_schemas.py
=============================
O contrato do plano social — a regra que ele codifica:

    TODO conteúdo social existe para levar a pessoa a assistir ao vídeo.

Os limites aqui não são sugestão de prompt — são validação. O modelo não
"tenta" respeitar; ele é rejeitado se não respeitar. E as regras não são só
de forma (500 caracteres): são de MECÂNICA DE PLATAFORMA, aprendidas em
revisão real — link no corpo do LinkedIn mede pior, Instagram não renderiza
link nenhum, Threads repetindo a própria abertura como primeira resposta.
"""

import pytest
from pydantic import ValidationError

from social_schemas import (
    CTA, Carrossel, CTATipo, FrameStory, PlanoSocial, PostLinkedIn,
    PostThreads, PostYouTubeCommunity, SlideCarrossel, Story,
)


def cta(tipo=CTATipo.ASSISTIR, texto="Veja o código completo no [LINK_CANAL]",
        skill="cta-assistir"):
    return CTA(texto=texto, tipo=tipo, skill_id=skill)


def cta_sem_link(tipo=CTATipo.SALVAR, texto="Salve para consultar depois",
                  skill="cta-salvar"):
    return CTA(texto=texto, tipo=tipo, skill_id=skill)


def li(id="li-01", tipo=CTATipo.SALVAR, copy_skill="copy-aida"):
    # Default sem link: CTA.tipo=ASSISTIR exigiria comentario_fixado, e a
    # maioria dos testes aqui não quer entrar nesse detalhe.
    return PostLinkedIn(
        id=id, copy_skill_id=copy_skill,
        gancho="Um LLM não faz inferência causal.", cta=cta_sem_link(tipo),
        lacuna="O código do teste Z que roda em produção.", dia_offset=1,
        corpo="x" * 400,
    )


def thread(id="th-01", copy_skill="copy-pas",
           gancho="Testes A/B continuam necessários mesmo com IA generativa",
           posts=None):
    posts = posts or [
        "O modelo estima probabilidade de token, não causa efeito real.",
        "Sem contrafactual, não existe inferência causal possível.",
    ]
    return PostThreads(
        id=id, copy_skill_id=copy_skill, gancho=gancho, cta=cta_sem_link(),
        lacuna="l" * 20, dia_offset=2, posts=posts,
    )


def carrossel(id="ca-01", copy_skill="copy-bab"):
    return Carrossel(
        id=id, copy_skill_id=copy_skill, gancho="g" * 20, cta=cta_sem_link(),
        lacuna="l" * 20, dia_offset=3, legenda="legenda sem link nenhum",
        slides=[SlideCarrossel(numero=i, titulo=f"t{i}", corpo="c") for i in range(1, 5)],
    )


def frame(ordem=1, texto="texto do frame", ilustracao="fundo escuro com o título em destaque"):
    return FrameStory(ordem=ordem, texto=texto, ilustracao=ilustracao)


def story(id="st-01", copy_skill="copy-ppp", dia_offset=0, n_frames=3, tipo=CTATipo.SALVAR):
    return Story(
        id=id, copy_skill_id=copy_skill, gancho="g" * 20, cta=cta_sem_link(tipo),
        lacuna="l" * 20, dia_offset=dia_offset,
        frames=[frame(ordem=i) for i in range(1, n_frames + 1)],
    )


def comunidade(id="yc-01", copy_skill="copy-quest"):
    return PostYouTubeCommunity(
        id=id, copy_skill_id=copy_skill, gancho="g" * 20, cta=cta_sem_link(),
        lacuna="l" * 20, dia_offset=0,
        texto="Pergunta para quem já é inscrito: " + "x" * 30,
    )


# ── CTA: o link nunca é literal ───────────────────────────────────────────────

def test_cta_recusa_url_literal():
    with pytest.raises(ValidationError, match="URL literal"):
        CTA(texto="Assista em https://youtu.be/abc123", tipo=CTATipo.ASSISTIR, skill_id="x")


def test_cta_aceita_marcador_de_link():
    assert "[LINK_CANAL]" in cta().texto


def test_cta_exige_declaracao_do_tipo_e_da_skill():
    with pytest.raises(ValidationError):
        CTA(texto="Veja mais no [LINK_CANAL]")


def test_cta_nao_e_so_assistir():
    engajamento = CTA(texto="Salve para a próxima sprint", tipo=CTATipo.SALVAR, skill_id="cta-salvar")
    assert engajamento.tipo not in {CTATipo.ASSISTIR}


# ── LinkedIn: link vai para o comentário, nunca para o post ───────────────────

def test_linkedin_recusa_link_no_corpo():
    with pytest.raises(ValidationError, match="use comentario_fixado"):
        PostLinkedIn(
            id="li-01", copy_skill_id="copy-aida", gancho="g" * 20,
            cta=cta_sem_link(), lacuna="l" * 20, dia_offset=1,
            corpo="Confira mais em [LINK_CANAL]. " + "x" * 300,
        )


def test_linkedin_recusa_link_no_cta_visivel():
    # cta.texto aparece junto do post — mesma regra do corpo.
    with pytest.raises(ValidationError, match="não pode conter link"):
        PostLinkedIn(
            id="li-01", copy_skill_id="copy-aida", gancho="g" * 20,
            cta=cta(texto="Veja mais em [LINK_CANAL]"),
            lacuna="l" * 20, dia_offset=1, corpo="x" * 400,
        )


def test_linkedin_aceita_link_no_comentario_fixado():
    post = PostLinkedIn(
        id="li-01", copy_skill_id="copy-aida", gancho="g" * 20,
        cta=CTA(texto="O link está no comentário", tipo=CTATipo.ASSISTIR, skill_id="cta-assistir"),
        lacuna="l" * 20, dia_offset=1, corpo="x" * 400,
        comentario_fixado="O vídeo completo está aqui: [LINK_CANAL]",
    )
    assert "[LINK_CANAL]" in post.comentario_fixado
    assert "[LINK_CANAL]" not in post.corpo


def test_linkedin_recusa_comentario_fixado_sem_link():
    # O campo existe só para carregar o link — sem marcador, não serve a nada.
    with pytest.raises(ValidationError, match="carregar o link"):
        PostLinkedIn(
            id="li-01", copy_skill_id="copy-aida", gancho="g" * 20,
            cta=cta_sem_link(), lacuna="l" * 20, dia_offset=1, corpo="x" * 400,
            comentario_fixado="Obrigado por ler!",
        )


def test_linkedin_cta_de_engajamento_nao_precisa_de_comentario():
    post = li(tipo=CTATipo.SALVAR)
    assert post.comentario_fixado is None


# ── Instagram (carrossel + stories): sem link em NENHUM campo ────────────────

def test_carrossel_recusa_link_na_legenda():
    with pytest.raises(ValidationError, match="não pode conter link"):
        Carrossel(
            id="ca-01", copy_skill_id="copy-bab", gancho="g" * 20, cta=cta_sem_link(),
            lacuna="l" * 20, dia_offset=3, legenda="Link no [LINK_CANAL]",
            slides=[SlideCarrossel(numero=i, titulo=f"t{i}", corpo="c") for i in range(1, 5)],
        )


def test_carrossel_recusa_link_no_cta():
    with pytest.raises(ValidationError, match="não pode conter link"):
        Carrossel(
            id="ca-01", copy_skill_id="copy-bab", gancho="g" * 20,
            cta=cta(texto="Veja no [LINK_CANAL]"),
            lacuna="l" * 20, dia_offset=3, legenda="legenda limpa",
            slides=[SlideCarrossel(numero=i, titulo=f"t{i}", corpo="c") for i in range(1, 5)],
        )


def test_carrossel_exige_minimo_de_slides():
    with pytest.raises(ValidationError):
        Carrossel(id="ca-01", copy_skill_id="copy-bab", gancho="g" * 20, cta=cta_sem_link(),
                  lacuna="l" * 20, dia_offset=3, legenda="l",
                  slides=[SlideCarrossel(numero=1, titulo="t", corpo="c")])


def test_story_exige_de_3_a_4_frames():
    with pytest.raises(ValidationError):
        Story(id="st-01", copy_skill_id="copy-ppp", gancho="g" * 20, cta=cta_sem_link(),
              lacuna="l" * 20, dia_offset=0, frames=[frame(1), frame(2)])


def test_frame_exige_ilustracao():
    # Sem isto o frame vira só texto sobre fundo liso — não segura atenção.
    with pytest.raises(ValidationError):
        FrameStory(ordem=1, texto="só texto")


def test_story_recusa_link_em_qualquer_frame():
    with pytest.raises(ValidationError, match="não pode conter link"):
        Story(
            id="st-01", copy_skill_id="copy-ppp", gancho="g" * 20, cta=cta_sem_link(),
            lacuna="l" * 20, dia_offset=0,
            frames=[frame(1), frame(2),
                    FrameStory(ordem=3, texto="Vê no [LINK_CANAL]", ilustracao="fundo escuro com destaque")],
        )


def test_story_recusa_link_no_cta():
    with pytest.raises(ValidationError, match="não pode conter link"):
        Story(id="st-01", copy_skill_id="copy-ppp", gancho="g" * 20,
              cta=cta(texto="Vê no [LINK_CANAL]"),
              lacuna="l" * 20, dia_offset=0,
              frames=[frame(1), frame(2), frame(3)])


# ── Threads: post raiz + respostas que avançam, nunca repetem ────────────────

def test_threads_recusa_post_acima_de_500_chars():
    with pytest.raises(ValidationError, match="máx 500"):
        thread(posts=["ok", "x" * 501])


def test_threads_primeira_resposta_nao_pode_repetir_o_gancho():
    # O bug real: posts[0] saía como paráfrase do gancho.
    with pytest.raises(ValidationError, match="repete o gancho"):
        thread(
            gancho="Um LLM não faz inferência causal, apenas estatística de texto",
            posts=["Um LLM não faz inferência causal, só estatística de texto.",
                   "O teste Z resolve isso de verdade."],
        )


def test_threads_recusa_respostas_quase_identicas_entre_si():
    with pytest.raises(ValidationError, match="repete o post"):
        thread(posts=[
            "O modelo estima probabilidade de token, não causa efeito real.",
            "O modelo estima probabilidade de token, não tem efeito causal real.",
        ])


def test_threads_aceita_respostas_que_avancam_a_ideia():
    t = thread()
    assert len(t.posts) == 2


# ── YouTube Community: canal que não existia ──────────────────────────────────

def test_youtube_community_existe_como_canal():
    p = comunidade()
    assert p.texto
    assert p.id == "yc-01"


def test_youtube_community_aceita_enquete():
    p = PostYouTubeCommunity(
        id="yc-01", copy_skill_id="copy-quest", gancho="g" * 20, cta=cta_sem_link(),
        lacuna="l" * 20, dia_offset=0, texto="x" * 30,
        enquete_opcoes=["Sim", "Não"],
    )
    assert p.enquete_opcoes == ["Sim", "Não"]


# ── O plano como funil ────────────────────────────────────────────────────────

def _plano(*, ctas=None, copies=None, stories_convertem=True):
    ctas   = ctas   or [CTATipo.ASSISTIR, CTATipo.SALVAR, CTATipo.COMENTAR,
                        CTATipo.ASSISTIR, CTATipo.MARCAR]
    copies = copies or ["copy-aida", "copy-pas", "copy-bab", "copy-quest", "copy-ppp"]

    li_cta = (CTA(texto="O link está no comentário", tipo=ctas[0], skill_id="cta-assistir")
              if ctas[0] == CTATipo.ASSISTIR else cta_sem_link(ctas[0]))
    linkedin = [PostLinkedIn(
        id="li-01", copy_skill_id=copies[0], gancho="g" * 20, cta=li_cta,
        lacuna="l" * 20, dia_offset=1, corpo="x" * 400,
        comentario_fixado="[LINK_CANAL]" if ctas[0] == CTATipo.ASSISTIR else None,
    )]

    threads_ = [PostThreads(
        id="th-01", copy_skill_id=copies[1], gancho="g" * 20, cta=cta_sem_link(ctas[1]),
        lacuna="l" * 20, dia_offset=2,
        posts=["primeira ideia nova aqui, bem diferente do gancho inicial",
               "segunda ideia, distinta das anteriores por completo"],
    )]

    carrossel_ = [Carrossel(
        id="ca-01", copy_skill_id=copies[2], gancho="g" * 20, cta=cta_sem_link(ctas[2]),
        lacuna="l" * 20, dia_offset=3, legenda="legenda",
        slides=[SlideCarrossel(numero=i, titulo=f"t{i}", corpo="c") for i in range(1, 5)],
    )]

    # 3 das 10 levam direto ao vídeo — stories reais na prática convertem
    # bem, é o formato mais próximo do link-in-bio. O resto trabalha alcance.
    conversoras = {(0, 0), (2, 0), (4, 1)} if stories_convertem else set()
    stories_ = [
        story(id=f"st-{d:02d}-{n}", copy_skill=copies[3], dia_offset=d,
             tipo=CTATipo.ASSISTIR if (d, n) in conversoras else CTATipo.SALVAR)
        for d in range(5) for n in range(2)
    ]

    yt = [PostYouTubeCommunity(
        id="yc-01", copy_skill_id=copies[4], gancho="g" * 20, cta=cta_sem_link(ctas[4]),
        lacuna="l" * 20, dia_offset=0, texto="x" * 30,
    )]

    return PlanoSocial(
        tema="Testes A/B", video_titulo="Testes A/B com GenAI",
        promessa_video="O algoritmo de decisão completo, com o código em Python.",
        linkedin=linkedin, threads=threads_, carrossel=carrossel_,
        stories=stories_, youtube_community=yt,
    )


def test_plano_conta_as_pecas():
    p = _plano()
    assert p.total_pecas() == 1 + 1 + 1 + 10 + 1


def test_plano_equilibrado_nao_gera_aviso():
    assert _plano().diagnostico() == []


def test_plano_sem_nenhuma_peca_levando_ao_video_e_denunciado():
    avisos = _plano(
        ctas=[CTATipo.SALVAR, CTATipo.COMENTAR, CTATipo.MARCAR, CTATipo.SEGUIR, CTATipo.SALVAR],
        stories_convertem=False,
    ).diagnostico()
    assert any("nenhuma peça leva ao vídeo" in a for a in avisos)


def test_plano_com_um_so_metodo_de_copy_e_denunciado():
    avisos = _plano(copies=["copy-pas"] * 5).diagnostico()
    assert any("soar iguais" in a for a in avisos)


def test_plano_denuncia_stories_concentradas_num_dia_so():
    p = _plano()
    # Redistribui as 10 stories padrão para um único dia.
    for s in p.stories:
        s.dia_offset = 0
    avisos = p.diagnostico()
    assert any("concentradas" in a for a in avisos)


def test_plano_exige_pelo_menos_dez_stories():
    # 2 a 3 publicações por dia numa janela de ~7 dias — volume alto de
    # propósito, é o formato mais barato de repetir o convite ao vídeo.
    with pytest.raises(ValidationError):
        PlanoSocial(
            tema="t", video_titulo="v", promessa_video="p" * 25,
            linkedin=[li()], threads=[thread()], carrossel=[carrossel()],
            stories=[story(id="st-01"), story(id="st-02")],
        )


def test_plano_vira_schema_aceito_pelo_vertex():
    import json
    from structured import to_vertex_schema

    schema = json.dumps(to_vertex_schema(PlanoSocial))
    assert "$ref" not in schema
    assert "$defs" not in schema
    assert "anyOf" not in schema
    assert "additionalProperties" not in schema


def test_lotes_por_canal_cabem_no_limite_do_vertex():
    """
    O Vertex recusa responseSchema acima de ~60 nós de estrutura — o
    PlanoSocial inteiro (69 nós) devolvia HTTP 400 enquanto cada peça isolada
    passava. A geração é por canal; cada lote precisa continuar pequeno.
    Volume da LISTA (max_length) não conta pra ESSA contagem — só a forma do
    item conta. (Existe um SEGUNDO teto, de cardinalidade de array aninhado,
    que não aparece na contagem de nós — ver o teste de LoteStories abaixo.)
    """
    import json
    from social_schemas import CANAIS
    from structured import to_vertex_schema

    def nos(o):
        if isinstance(o, dict): return 1 + sum(nos(v) for v in o.values())
        if isinstance(o, list): return sum(nos(v) for v in o)
        return 0

    for canal, (modelo, _) in CANAIS.items():
        n = nos(to_vertex_schema(modelo))
        assert n < 50, f"{canal} com {n} nós, perto do teto do Vertex"


def test_lote_stories_fica_abaixo_do_teto_de_array_aninhado():
    """
    `stories` é o único canal com array-de-array (pecas × frames) e tem um
    teto PRÓPRIO, que a contagem de nós acima não enxerga: bissecção real
    contra o Vertex, usando o `Story` de verdade (que carrega PecaBase — id,
    cta, gancho, lacuna — além de `frames`), mostrou que outer maxItems=9
    passa e =10 já devolve 400. É um teto de cardinalidade de array
    aninhado, com folga desconhecida — não é a contagem de nós de estrutura
    (bem menor aqui) que está em jogo. LoteStories cobre só um terço da
    semana (ver graph/nodes.py, 3 lotes somados em Python) — este teste
    trava se alguém subir o max_length de volta sem lembrar do porquê.
    """
    from social_schemas import LoteStories

    schema = LoteStories.model_json_schema()
    max_pecas = schema["properties"]["pecas"]["maxItems"]
    assert max_pecas <= 7, (
        f"LoteStories.pecas.max_length={max_pecas} — acima de 9 o Vertex "
        "rejeitava com 400 em teste real (medido com o Story de produção, "
        "que é mais pesado que frames sozinho). Mantenha bem abaixo da "
        "margem e gere a semana em lotes (terços), não numa chamada só."
    )
