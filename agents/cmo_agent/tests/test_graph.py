"""
tests/test_graph.py
====================
O grafo do time de marketing: gates, durabilidade e retomada.

A propriedade central testada aqui é a que nenhum saver de prateleira do
LangGraph entrega neste ambiente: o grafo pausa num gate, o PROCESSO MORRE,
e outro processo retoma exatamente do mesmo ponto lendo o Firestore. É isso
que permite a aprovação acontecer horas ou dias depois — que é o tempo real
de alguém ler um artigo e assistir a um vídeo.
"""

import pytest

from fake_firestore import FakeFirestore
from graph.state import novo_estado, tem_erro_fatal


@pytest.fixture
def db():
    return FakeFirestore()


@pytest.fixture
def grafo(db, monkeypatch):
    """Grafo com os nós de IA trocados por versões determinísticas."""
    import graph.nodes as nodes

    async def briefing(s):
        # Uma rodada só, já completa: o foco destes testes são os gates e a
        # durabilidade, não a negociação do recorte.
        return {"briefing": {"angulo": "como usar na IDE",
                             "ferramentas": ["Cursor"],
                             "o_que_aparece_na_tela": ["o arquivo aberto", "o agente lendo"],
                             "resumo_da_proposta": "proposta"},
                "conversa_briefing": [{"papel": "cmo", "texto": "proposta"}],
                "fase": "aguardando_briefing", "trilha": ["briefing"]}

    async def plan(s):
        return {"pauta": {"titulo": "Testes A/B", "angulo_video": "o algoritmo"},
                "fase": "artigo", "trilha": ["planejamento"]}

    async def artigo(s):
        # O comentário do gate tem que chegar ao agente que refaz a peça.
        nota = (s.get("aprovacao_artigo") or {}).get("comentario", "")
        return {"artigo_markdown": "# a\n" + "x" * 600 + nota,
                "artigo_titulo": "Testes A/B",
                "fase": "aguardando_aprovacao_artigo", "trilha": [f"artigo({nota or 'v1'})"]}

    async def video(s):
        return {"manifesto": {"title": "T", "youtube": {"segments": [{"script": "f"}]}},
                "video_titulo": "T", "fase": "aguardando_aprovacao_video",
                "trilha": ["video"]}

    async def social(s):
        return {"plano_social": {"pecas": 9}, "fase": "concluido", "trilha": ["social"]}

    monkeypatch.setattr(nodes, "no_briefing", briefing)
    monkeypatch.setattr(nodes, "no_planejamento", plan)
    monkeypatch.setattr(nodes, "no_artigo", artigo)
    monkeypatch.setattr(nodes, "no_video", video)
    monkeypatch.setattr(nodes, "no_social", social)

    from graph.build import construir_grafo
    return construir_grafo(db, tenant_id=None)


def cfg(sessao="s1"):
    from graph.build import config_thread
    return config_thread("default", sessao)


async def ate_o_artigo(grafo, sessao="s1", tema="Testes A/B"):
    """
    Roda do início até o gate do artigo, aprovando o briefing no caminho.

    O briefing é o primeiro gate desde que o recorte passou a ser negociado
    antes de escrever. Para os testes cujo assunto é o gate do artigo ou o do
    vídeo, ele é preâmbulo — quem o exercita são os testes logo abaixo.
    """
    await grafo.ainvoke(novo_estado("default", sessao, tema), cfg(sessao))
    await grafo.aupdate_state(cfg(sessao), {"aprovacao_briefing": {"decisao": "aprovado"}})
    await grafo.ainvoke(None, cfg(sessao))


# ── O gate do briefing ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_para_no_briefing_antes_de_escrever(grafo):
    """
    O primeiro contato humano é o RECORTE, não o artigo pronto.

    Antes, o grafo ia direto de tema a artigo e só parava depois de escrever.
    Quando o ângulo saía errado — o vídeo de SDD que ensinou a implementação
    quando o pedido era o uso na IDE — não havia onde corrigir sem refazer a
    pesquisa e o texto inteiros.
    """
    await grafo.ainvoke(novo_estado("default", "s1", "Testes A/B"), cfg())
    snap = await grafo.aget_state(cfg())

    assert snap.next == ("gate_briefing",)
    assert snap.values["fase"] == "aguardando_briefing"
    # Nada foi escrito nem pesquisado ainda: é esse o ponto do gate.
    assert not snap.values.get("artigo_markdown")
    assert not snap.values.get("pauta")


@pytest.mark.asyncio
async def test_ajustar_briefing_refaz_o_recorte(grafo):
    await grafo.ainvoke(novo_estado("default", "s1", "Testes A/B"), cfg())
    await grafo.aupdate_state(cfg(), {
        "aprovacao_briefing": {"decisao": "ajustar", "comentario": "quero o uso na IDE"}
    })
    await grafo.ainvoke(None, cfg())

    snap = await grafo.aget_state(cfg())
    assert snap.next == ("gate_briefing",)
    assert not snap.values.get("artigo_markdown")


@pytest.mark.asyncio
async def test_briefing_aprovado_libera_a_escrita(grafo):
    await ate_o_artigo(grafo)
    snap = await grafo.aget_state(cfg())

    assert snap.next == ("gate_artigo",)
    assert snap.values["briefing"]["angulo"]
    # O recorte aprovado chega ao estado que o artigo consome.
    assert snap.values["pauta"]


@pytest.mark.asyncio
async def test_rejeitar_briefing_encerra_sem_gastar_nada(grafo):
    await grafo.ainvoke(novo_estado("default", "s1", "Testes A/B"), cfg())
    await grafo.aupdate_state(cfg(), {"aprovacao_briefing": {"decisao": "rejeitado"}})
    await grafo.ainvoke(None, cfg())

    snap = await grafo.aget_state(cfg())
    assert snap.next == ()
    assert not snap.values.get("artigo_markdown")


@pytest.mark.asyncio
async def test_para_no_primeiro_gate_sem_avancar(grafo):
    await ate_o_artigo(grafo)
    snap = await grafo.aget_state(cfg())

    assert snap.next == ("gate_artigo",)
    assert snap.values["fase"] == "aguardando_aprovacao_artigo"
    # O vídeo NÃO pode ter sido produzido antes da aprovação do artigo:
    # é o que impede gastar HeyGen num artigo que será rejeitado.
    assert not snap.values.get("manifesto")


@pytest.mark.asyncio
async def test_estado_sobrevive_a_morte_do_processo(db, grafo):
    """
    O caso real: o gate espera dias, o Cloud Run recicla a instância várias
    vezes no meio. Um saver em memória perderia o pacote inteiro.
    """
    await ate_o_artigo(grafo)

    # Descarta o grafo e monta outro do zero, só com o Firestore.
    from graph.build import construir_grafo
    outro = construir_grafo(db, tenant_id=None)
    snap = await outro.aget_state(cfg())

    assert snap.next == ("gate_artigo",)
    assert len(snap.values["artigo_markdown"]) > 500


@pytest.mark.asyncio
async def test_aprovar_artigo_libera_o_video(grafo):
    await ate_o_artigo(grafo)
    await grafo.aupdate_state(cfg(), {"aprovacao_artigo": {"decisao": "aprovado"}})
    await grafo.ainvoke(None, cfg())

    snap = await grafo.aget_state(cfg())
    assert snap.next == ("gate_video",)
    assert snap.values["manifesto"]


@pytest.mark.asyncio
async def test_ajustar_refaz_a_peca_com_o_comentario(grafo):
    await ate_o_artigo(grafo)
    await grafo.aupdate_state(cfg(), {
        "aprovacao_artigo": {"decisao": "ajustar", "comentario": "raso demais"}
    })
    await grafo.ainvoke(None, cfg())

    snap = await grafo.aget_state(cfg())
    # Voltou para o gate depois de refazer, não avançou para o vídeo.
    assert snap.next == ("gate_artigo",)
    assert "raso demais" in snap.values["artigo_markdown"]
    assert any("raso demais" in t for t in snap.values["trilha"])


@pytest.mark.asyncio
async def test_rejeitar_encerra_sem_produzir_video(grafo):
    await ate_o_artigo(grafo)
    await grafo.aupdate_state(cfg(), {"aprovacao_artigo": {"decisao": "rejeitado"}})
    await grafo.ainvoke(None, cfg())

    snap = await grafo.aget_state(cfg())
    assert snap.next == ()
    assert not snap.values.get("manifesto")


@pytest.mark.asyncio
async def test_funil_completo_ate_o_plano_social(grafo):
    await ate_o_artigo(grafo)
    await grafo.aupdate_state(cfg(), {"aprovacao_artigo": {"decisao": "aprovado"}})
    await grafo.ainvoke(None, cfg())
    await grafo.aupdate_state(cfg(), {"aprovacao_video": {"decisao": "aprovado"}})
    final = await grafo.ainvoke(None, cfg())

    assert final["fase"] == "concluido"
    assert final["plano_social"]["pecas"] == 9
    assert not tem_erro_fatal(final)


@pytest.mark.asyncio
async def test_sessoes_diferentes_nao_compartilham_estado(grafo):
    await grafo.ainvoke(novo_estado("default", "s1", "Tema um"), cfg("s1"))
    await grafo.ainvoke(novo_estado("default", "s2", "Tema dois"), cfg("s2"))

    a = await grafo.aget_state(cfg("s1"))
    b = await grafo.aget_state(cfg("s2"))
    assert a.values["tema"] == "Tema um"
    assert b.values["tema"] == "Tema dois"


@pytest.mark.asyncio
async def test_tenants_diferentes_ficam_em_arvores_separadas(db, grafo):
    """Isolamento multi-tenant no nível do checkpoint, não só do caminho."""
    from graph.build import construir_grafo, config_thread

    outro_tenant = construir_grafo(db, tenant_id="acme")
    await outro_tenant.ainvoke(
        novo_estado("acme", "s1", "Tema da Acme"), config_thread("acme", "s1")
    )
    caminhos = [k for k in db.store if "/checkpoints/" in k]
    assert any(k.startswith("tenants/acme/") for k in caminhos)
    # O tenant default grava na raiz, sem prefixo de tenant.
    assert not any(k.startswith("tenants/default/") for k in caminhos)
