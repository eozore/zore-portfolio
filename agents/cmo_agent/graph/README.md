# Time de marketing — grafo de agentes

```
planejamento → artigo → [GATE artigo] → video → [GATE video] → social → fim
                  ↑         │                     ↑        │
                  └─ajustar─┘                     └─ajustar┘
```

## O que cada nó é

| Nó | Agente que envolve | Produz |
|---|---|---|
| `planejamento` | saída estruturada direta | pauta + **ângulo do vídeo** (a promessa do funil) |
| `artigo` | `research_agent` + `writing_agent` | artigo em Markdown |
| `video` | `scriptwriter_agent` + `slide_designer_agent` | manifesto v2 (80/20) + slides HTML |
| `social` | saída estruturada (`PlanoSocial`) | LinkedIn, Threads, carrossel, stories |

O grafo **não reescreve** nenhum agente. Ele dá ordem, estado tipado,
tratamento de falha e rastro ao que já existia solto.

## Os gates param de verdade

`interrupt_before` faz o LangGraph persistir o checkpoint e **encerrar a
execução**. Não há thread parada, não há espera ativa, não há instância de
Cloud Run segurada por horas.

Isso obriga o checkpointer a ser durável e compartilhado — entre a pausa e a
retomada, o container que rodou o grafo já morreu. Os savers que vêm no
LangGraph (memória, SQLite, Postgres) não servem: memória some na reciclagem,
e subir um Postgres seria infra nova para guardar o que o Firestore já guarda.
Daí `graph/checkpointer.py`.

## Por que o vídeo só nasce depois do artigo aprovado

Ordem deliberada. O `scriptwriter` e o `slide_designer` custam token, e o
manifesto é a entrada da pipeline que gasta HeyGen. Produzir o vídeo antes de
o artigo ser aprovado é pagar por uma peça que pode ser descartada inteira.

## Memória

Três camadas, em `graph/knowledge.py`:

- **Marca** — voz, público, o que evitar. Impede cada geração de reinventar
  o tom.
- **Base de conhecimento** — o que já foi publicado. Evita propor pela
  terceira vez o mesmo tema.
- **Episódica** — o que o humano aprovou/rejeitou nos gates, **com o motivo**.
  Três artigos rejeitados por "raso demais" entram no prompt do quarto.

Sem banco vetorial: o volume é de dezenas de artigos, não milhões. Busca por
campo resolve, e um índice vetorial seria infra nova sem ganho nessa escala.

## Observabilidade

`observability.py` — cada nó vira um span no Cloud Trace, com tenant, custo e
contagens. Degrada para no-op se o exporter não estiver disponível:
observabilidade que derruba produção é pior que observabilidade nenhuma.

## Saída estruturada

Nenhum agente do grafo parseia JSON com regex. `structured.py` converte o
modelo Pydantic no `responseSchema` do Vertex, e o decoder é obrigado a emitir
JSON válido. O que existia antes era um parser de JSON escrito em expressão
regular (`re.sub(r",\s*([}\]])", ...)`) — e foi uma falha dessa classe que
deixou um manifesto quebrado virar um vídeo de 163 segundos de avatar puro.

Detalhe medido: com `responseSchema` ativo o modelo tende a devolver português
**sem acento**. Por isso `PT_BR_ORTOGRAFIA` é prefixado em toda geração.

## Endpoints

| Método | Rota | Para quê |
|---|---|---|
| POST | `/graph/start` | conversa vira tema; roda até o primeiro gate |
| GET | `/graph/state` | tudo que já existe — a tela de revisão |
| POST | `/graph/approve` | decisão do gate; retoma o grafo |
