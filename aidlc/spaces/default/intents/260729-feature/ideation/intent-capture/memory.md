<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.
## Interpretations
2026-07-29T10:00:00Z — Iniciativa é de correção de 6 bugs no Content Studio (eozore.com/admin/csm). Não é uma feature nova: é estabilização de uma pipeline já em produção que tem bugs críticos impedindo a geração correta de vídeos. Tratada como feature pois envolve novo agente (slide_designer_agent) e refatoração de contratos Pub/Sub.
2026-07-29T10:00:01Z — Victor Zore é o único stakeholder + usuário + desenvolvedor. Decisão: não haverá stakeholder-map com múltiplos atores; o mapa será simplificado para o contexto de plataforma individual.
2026-07-29T10:00:02Z — A ordem de execução é determinada pelo NEXT_SESSION.md: BUG3→BUG4→BUG5→BUG6→BUG1→BUG2, onde BUG2 é o último pois muda contratos Pub/Sub que afetam 3 serviços simultaneamente.
## Deviations
2026-07-29T10:00:03Z — Pulando perguntas interativas do intent-capture (etapa 3 do stage): contexto já é completo via NEXT_SESSION.md que documenta causa-raiz, arquivos afetados e solução para cada bug. Resposta às perguntas inferida diretamente do documento.
## Tradeoffs
2026-07-29T10:00:04Z — Optamos por atacar todos os 6 bugs em sequência dentro de um único intent, em vez de criar um intent por bug. Justificativa: os bugs compartilham o mesmo serviço (cmo_agent) e pipeline, e BUG2 depende de BUG1 estar estável.
## Open questions
2026-07-29T10:00:05Z — TAVILY_API_KEY (BUG4): Victor precisa confirmar se já tem uma chave da Tavily ou se usa SerpAPI. A implementação será feita com suporte a ambas via variável de ambiente.
2026-07-29T10:00:06Z — BUG2 (avatar_job por segmento): mudança nos contratos AvatarCompletedMsg afeta 3 serviços em produção simultaneamente. Deploy deve ser coordenado (não rolling update independente).
