# -*- coding: utf-8 -*-
"""
catalog.py — Skills padrão do time.

Uma SKILL é um método que o agente consulta para decidir COMO fazer algo.
Distinta das outras duas coisas que configuram um agente:

    prompt          quem ele é e qual o trabalho
    skill           um método aplicável, com critério de quando usar
    knowledge base  fatos e referências que ele consulta

A diferença que importa: o agente ESCOLHE a skill olhando o conteúdo e a
mídia — não é o código que decide. O que o código exige é que a escolha seja
DECLARADA. Sem declaração não há como auditar por que um post ficou daquele
jeito, nem validar variedade, nem medir depois qual método rendeu mais.

Estas são as sementes. O dono do canal edita, desativa e acrescenta as suas —
elas viram documentos em `tenants/{t}/skills/` na primeira leitura.
"""

from __future__ import annotations

from typing import Any

# ── Frameworks de copy ────────────────────────────────────────────────────────

COPY_SKILLS: list[dict[str, Any]] = [
    {
        "id": "copy-aida",
        "categoria": "copy",
        "nome": "AIDA",
        "quando_usar": (
            "Conteúdo que apresenta algo novo para quem ainda não sabe que tem o "
            "problema. Bom para o primeiro post de um tema, e para LinkedIn."
        ),
        "como_aplicar": (
            "Atenção: uma afirmação que contraria o senso comum da área.\n"
            "Interesse: por que isso é verdade — um dado, um mecanismo.\n"
            "Desejo: o que muda no trabalho de quem entende isso.\n"
            "Ação: o próximo passo concreto."
        ),
        "exemplo": (
            "A maior parte dos testes A/B que você roda não tem poder estatístico. "
            "Com 12 mil sessões por variante e conversão de 12%, a diferença "
            "mínima detectável é de 1,4 ponto. Abaixo disso você está lendo ruído. "
            "Calcule o poder antes de rodar, não depois."
        ),
    },
    {
        "id": "copy-pas",
        "categoria": "copy",
        "nome": "PAS — Problema, Agitação, Solução",
        "quando_usar": (
            "Quando a dor já é conhecida do público e a peça pode ir direto nela. "
            "Funciona bem em Threads e stories, onde o espaço é curto."
        ),
        "como_aplicar": (
            "Problema: nomeie a dor em uma frase, sem rodeio.\n"
            "Agitação: mostre o custo de continuar assim — concreto, não dramático.\n"
            "Solução: o caminho, em uma linha. Não entregue a execução."
        ),
        "exemplo": (
            "Seu time decide cor de botão perguntando para um LLM.\n"
            "O modelo nunca viu a sua base de usuários — ele responde o que é "
            "comum na internet, e você trata isso como evidência.\n"
            "O que resolve é um teste A/B com poder calculado."
        ),
    },
    {
        "id": "copy-bab",
        "categoria": "copy",
        "nome": "BAB — Before, After, Bridge",
        "quando_usar": (
            "Conteúdo de transformação: havia um jeito antigo, existe um novo. "
            "Bom para carrossel, onde o antes e o depois ocupam slides distintos."
        ),
        "como_aplicar": (
            "Before: a situação hoje, reconhecível.\n"
            "After: como fica quando resolvido — específico, mensurável.\n"
            "Bridge: o que liga um ao outro."
        ),
        "exemplo": (
            "Antes: três semanas discutindo qual variante é melhor.\n"
            "Depois: sete dias de teste e uma resposta com intervalo de confiança.\n"
            "A ponte é o cálculo de tamanho de amostra feito ANTES de subir o teste."
        ),
    },
    {
        "id": "copy-quest",
        "categoria": "copy",
        "nome": "QUEST — Qualify, Understand, Educate, Stimulate, Transition",
        "quando_usar": (
            "Público técnico e cético, tema que exige credibilidade antes do "
            "argumento. O mais longo dos frameworks — use no LinkedIn, não em story."
        ),
        "como_aplicar": (
            "Qualify: deixe claro para quem é (e para quem não é).\n"
            "Understand: mostre que você conhece a rotina de quem lê.\n"
            "Educate: entregue UM conceito completo.\n"
            "Stimulate: o que fazer com isso amanhã.\n"
            "Transition: o próximo passo."
        ),
        "exemplo": (
            "Se você roda experimento em produto, isto é para você.\n"
            "Você já viu um teste 'vencer' e o ganho sumir no mês seguinte.\n"
            "Quase sempre é parada antecipada: olhar o resultado todo dia e "
            "encerrar quando fica bonito infla o falso positivo.\n"
            "Fixe o horizonte antes de subir o teste."
        ),
    },
    {
        "id": "copy-ppp",
        "categoria": "copy",
        "nome": "PPP — Picture, Promise, Prove",
        "quando_usar": (
            "Quando existe um número, gráfico ou resultado concreto para mostrar. "
            "A prova é o centro — sem dado real, escolha outro framework."
        ),
        "como_aplicar": (
            "Picture: a cena que o leitor reconhece.\n"
            "Promise: o que muda.\n"
            "Prove: o dado. Sem dado, este framework não se aplica."
        ),
        "exemplo": (
            "Reunião de segunda, dois times defendendo variantes diferentes.\n"
            "Isso acaba quando existe um critério de parada definido antes.\n"
            "No teste que rodamos: 12.450 contra 12.380 sessões, p = 0,003."
        ),
    },
]

# ── Tipos de CTA ──────────────────────────────────────────────────────────────
#
# O objetivo do plano é gerar view no YouTube. Mas mandar TODO post para o
# vídeo cansa o público e desperdiça o que as redes fazem melhor: alcance.
# Um "salve este post" não leva ninguém ao vídeo hoje — ele aumenta a entrega
# do próximo post, que leva. É funil indireto, e compõe.

CTA_SKILLS: list[dict[str, Any]] = [
    {
        "id": "cta-assistir",
        "categoria": "cta",
        "nome": "Assistir ao vídeo",
        "quando_usar": (
            "Quando a peça deixou uma lacuna concreta que só o vídeo fecha "
            "(o código, a demonstração, a conta completa). É o CTA de conversão "
            "direta — mas se TODA peça usar ele, o público para de responder."
        ),
        "como_aplicar": (
            "Nomeie o que está no vídeo, não peça atenção genérica. "
            "'Veja o código completo' converte mais que 'assista ao vídeo'."
        ),
        "exemplo": "O cálculo de amostra passo a passo está no [LINK_CANAL]",
    },
    {
        "id": "cta-salvar",
        "categoria": "cta",
        "nome": "Salvar o post",
        "quando_usar": (
            "Peça de referência — checklist, fórmula, comparativo. Salvamento é "
            "o sinal mais forte para o algoritmo do Instagram e aumenta a "
            "entrega das peças seguintes, inclusive as que levam ao vídeo."
        ),
        "como_aplicar": "Dê um motivo concreto para salvar, ligado a uso futuro.",
        "exemplo": "Salve para a próxima vez que alguém sugerir pular o teste",
    },
    {
        "id": "cta-marcar",
        "categoria": "cta",
        "nome": "Marcar alguém",
        "quando_usar": (
            "Quando o conteúdo tem um destinatário óbvio — o colega que comete "
            "o erro descrito. Marcação traz gente nova ao perfil, que é o "
            "público que vai ver o próximo vídeo."
        ),
        "como_aplicar": "Descreva a PESSOA, não peça a marcação em abstrato.",
        "exemplo": "Marque quem ainda decide roadmap por opinião de LLM",
    },
    {
        "id": "cta-comentar",
        "categoria": "cta",
        "nome": "Provocar comentário",
        "quando_usar": (
            "Tema com divergência real na área. Comentário é o sinal que mais "
            "estende o alcance no LinkedIn."
        ),
        "como_aplicar": (
            "Pergunta específica e respondível em uma linha. "
            "'O que você acha?' não gera comentário — pergunta fechada gera."
        ),
        "exemplo": "Você calcula tamanho de amostra antes ou sobe e observa?",
    },
    {
        "id": "cta-seguir",
        "categoria": "cta",
        "nome": "Seguir para a série",
        "quando_usar": (
            "Quando a peça faz parte de uma sequência. Converte visitante "
            "eventual em audiência recorrente — que é quem assiste vídeo novo."
        ),
        "como_aplicar": "Diga o que vem a seguir, com especificidade.",
        "exemplo": "Semana que vem: por que o teste sequencial muda a conta",
    },
]

# ── Layouts de imagem ─────────────────────────────────────────────────────────

DESIGN_SKILLS: list[dict[str, Any]] = [
    {
        "id": "design-citacao",
        "categoria": "design",
        "nome": "Citação em destaque",
        "quando_usar": "Uma frase forte carrega o slide sozinha.",
        "como_aplicar": "Tipografia grande, muito respiro, sem elemento competindo.",
        "exemplo": "",
    },
    {
        "id": "design-dado",
        "categoria": "design",
        "nome": "Número protagonista",
        "quando_usar": "Existe UM número que resume o argumento.",
        "como_aplicar": "O número ocupa metade do quadro; o rótulo é pequeno abaixo.",
        "exemplo": "",
    },
    {
        "id": "design-comparativo",
        "categoria": "design",
        "nome": "Antes e depois",
        "quando_usar": "Duas abordagens em contraste direto.",
        "como_aplicar": "Divisão vertical, mesma estrutura dos dois lados.",
        "exemplo": "",
    },
    {
        "id": "design-passos",
        "categoria": "design",
        "nome": "Passo a passo",
        "quando_usar": "Processo com 3 a 5 etapas ordenadas.",
        "como_aplicar": "Numeração forte, uma linha por etapa.",
        "exemplo": "",
    },
    {
        "id": "design-codigo",
        "categoria": "design",
        "nome": "Bloco de código",
        "quando_usar": "A implementação é o argumento.",
        "como_aplicar": "Fonte monoespaçada, poucas linhas, destaque na linha-chave.",
        "exemplo": "",
    },
]

TODAS_AS_SKILLS = COPY_SKILLS + CTA_SKILLS + DESIGN_SKILLS


def catalogo_para_prompt(skills: list[dict[str, Any]], categoria: str) -> str:
    """
    Serializa as skills de uma categoria para o agente escolher.

    O formato é deliberadamente legível: o agente precisa COMPARAR critérios
    de "quando usar" para decidir, e uma lista de JSON aninhado atrapalha
    isso mais do que ajuda.
    """
    ativas = [s for s in skills if s.get("categoria") == categoria and s.get("ativo", True)]
    if not ativas:
        return "(nenhuma skill cadastrada nesta categoria)"

    blocos = []
    for s in ativas:
        bloco = [f"[{s['id']}] {s['nome']}", f"  Quando usar: {s['quando_usar']}"]
        if s.get("como_aplicar"):
            passos = s["como_aplicar"].replace("\n", "\n    ")
            bloco.append(f"  Como aplicar:\n    {passos}")
        if s.get("exemplo"):
            bloco.append(f"  Exemplo: {s['exemplo']}")
        blocos.append("\n".join(bloco))
    return "\n\n".join(blocos)
