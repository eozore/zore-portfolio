# External Dependency Map
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [unit-of-work.md](../units-generation/unit-of-work.md) | [requirements.md](../requirements-analysis/requirements.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## Dependências Externas por Bolt

### Pré-Bolt 1 (Victor executa manualmente)

| Dependência | Owner | Lead Time | Bloqueia | Mitigação se indisponível |
|---|---|---|---|---|
| Conta ElevenLabs com voz clonada de Victor | Victor | 2-4h | Bolt 1 (U-08 TTSJob) | Usar voz pré-existente do ElevenLabs para testes; adiar clone para depois |
| HeyGen API key + Avatar IV configurado | Victor | 30 min | Bolt 1 (U-09 AvatarJob) | Usar avatar demo do HeyGen para spike de custo |
| Spike de custo HeyGen Lipsync API PAYG (vídeo de 1 min) | Victor | 2h | Bolt 1 Go/No-Go | — (é a própria mitigação do risco de custo) |
| GCP Pub/Sub API ativada no projeto `eozore-platform` | Victor | 15 min | Bolt 0 (U-02) | — |

### Pré-Bolt 3

| Dependência | Owner | Lead Time | Bloqueia | Mitigação se indisponível |
|---|---|---|---|---|
| YouTube Data API v3 habilitada no GCP Console | Victor | 15 min | Bolt 3 (U-12 YouTube channel) | Testar com conta de teste antes do canal principal |
| YouTube OAuth 2.0: token do canal de Victor | Victor | 1-2h | Bolt 3 (U-12 YouTube) | Implementar sem YouTube; adicionar depois |
| Tokens OAuth Meta (Instagram, Threads, Facebook) válidos | Victor | 30 min de verificação | Bolt 3 (U-12 Meta) | Renovar via Meta App Dashboard |
| Token OAuth LinkedIn válido | Victor | 30 min de verificação | Bolt 3 (U-12 LinkedIn) | Renovar via LinkedIn Developer Portal |

---

## APIs Externas com SLAs Relevantes

| API | SLA Publicado | Falha Impacta | Estratégia de Fallback |
|---|---|---|---|
| ElevenLabs TTS | 99.9% | TTS Job (U-08) | Retry automático (backoff 1s/4s/16s); erro persistente → Victor notificado |
| HeyGen Lipsync v3 | 99.5% | Avatar Job (U-09) | Timeout de alerta 60 min, falha 90 min; Victor pode fazer upload manual |
| YouTube Data API v3 | 99.99% | Publisher (U-12 YouTube) | Retry uma vez; falha → canal marcado como `failed`, outros canais prosseguem |
| Meta Graph API | 99.9% | Publisher (U-12 Instagram/Threads/FB) | Retry uma vez; throttler isolado por canal |
| LinkedIn API v2 | 99.5% | Publisher (U-12 LinkedIn) | Retry uma vez; throttler isolado |
| GCP Pub/Sub | 99.95% | Comunicação inter-Jobs | Alta disponibilidade; falha improvável em projeto pessoal |
| GCP Firestore | 99.99% | Toda a pipeline (estado) | Alta disponibilidade; retry automático no SDK |

---

## Decisões Abertas que Bloqueiam Sprints Específicas

| Decisão | Responsável | Bloqueia | Status |
|---|---|---|---|
| Confirmar custo real HeyGen Lipsync PAYG | Victor (spike externo) | Bolt 1 Go/No-Go | Aberta — executar antes do Bolt 1 |
| Confirmar qualidade ElevenLabs Instant Clone pt-BR | Victor (teste de voz) | Bolt 1 Go/No-Go | Aberta — executar antes do Bolt 1 |
| YouTube API: service account ou OAuth pessoal | Victor (teste de upload) | Bolt 3 início | FR-12 condicional — verificar antes de implementar |
| YouTube Community Posts API disponibilidade | Victor (verificar docs) | Bolt 5 | OQ-05 — pode ser descartado se API não disponível |
