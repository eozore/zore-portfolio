# Team Allocation
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [unit-of-work.md](../units-generation/unit-of-work.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## Modelo: Victor Zore (Solo) + AIDLC Agent Ensemble

Projeto opera em modelo **Solo Tech Lead + AI Agent Ensemble**. Victor é o único operador humano (~5h/semana de review/gates). Os Bolts são executados pelo Developer Agent com suporte dos agentes especializados.

---

## Alocação por Bolt

| Bolt | Lead de Construção | Agentes de Suporte | Papel de Victor |
|---|---|---|---|
| 0: `foundations` | Developer Agent | Architect Agent | Aprova schema e confirma tópicos Pub/Sub criados |
| 1: `walking-skeleton` | Developer Agent | Architect Agent, Quality Agent, DevSecOps Agent | Executa pré-condições externas (ElevenLabs, HeyGen); aprova Go/No-Go após spike de custo |
| 2: `video-editor` | Developer Agent | Quality Agent | Revisa vídeo gerado (qualidade de composição); testa memory usage |
| 3: `publisher-core` | Developer Agent | Compliance Agent, Quality Agent | Configura YouTube OAuth; verifica tokens Meta/LinkedIn; revisa primeira publicação real |
| 4: `studio-ui` | Developer Agent | Design Agent, Quality Agent | Usa a UI e valida experiência de aprovação/configuração |
| 5: `distribution` | Developer Agent | Quality Agent | Valida sistema completo end-to-end com pacote real |

---

## Tempo Estimado de Victor por Bolt

| Bolt | Estimativa de Envolvimento de Victor |
|---|---|
| 0 | 1h — aprovação de schema, verificação de infra GCP |
| 1 | 4-6h — pré-condições externas (ElevenLabs/HeyGen setup) + revisão de Go/No-Go |
| 2 | 2h — revisão visual do vídeo gerado, teste de memória |
| 3 | 3h — YouTube OAuth setup + revisão de primeira publicação real |
| 4 | 2h — teste de usabilidade da UI |
| 5 | 2h — validação end-to-end completa |

**Total estimado de Victor:** ~15h de envolvimento humano para construir o sistema completo.

---

## Nota sobre Autonomy Mode

Por `team.md § Walking Skeleton`: Bolts rodam **sequencialmente sem gates de aprovação inter-Bolt**. O Developer Agent executa Bolt N, squash-merges para `main`, e inicia Bolt N+1 automaticamente. Falhas param o loop e apresentam `retry/skip/abort` antes de continuar.

`Construction Autonomy Mode: autonomous` (configurado pelo team.md).
