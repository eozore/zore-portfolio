# Team-Level Rules

> This team's affirmed practices and corrections. Overrides aidlc-org.md.
> Populated by practices-discovery affirmation gate. Edit at the gate,
> not directly.

## Way of Working

Trunk-based development com a branch `main` como único trunk. Todo o trabalho de feature é feito em Bolts AIDLC com branches de curta duração (`bolt/<slug>`), squash-merged para `main` ao completar cada Bolt. Conventional Commits são o padrão de mensagem de commit (`feat:`, `fix:`, `ci:`, `refactor:`, `security:`). Commits diretos em `main` são permitidos apenas para hotfixes triviais.

## Walking Skeleton

Os Bolts da pipeline autônoma rodam sequencialmente sem gates de aprovação entre eles — o sistema executa de Bolt 1 a Bolt 5 sem interrupção, exceto em caso de falha. Quando uma falha ocorre, o workflow para e apresenta opções (retry/skip/abort) antes de prosseguir. Esta postura reflete a confiança do operador solo no sistema e a preferência por velocidade de entrega sobre cerimônia de aprovação inter-Bolt.

## Testing Posture

Os novos microserviços Python (TTS Job, Avatar Job, Video Editor Job, Publisher Service) adotam a estratégia **Minimal (Nyquist)**: um teste por requisito funcional crítico, cobrindo o happy path de cada job. Foco em testes de integração que validam o contrato real com as APIs externas (ElevenLabs, HeyGen, Pub/Sub) mais do que testes unitários com mocks excessivos. O frontend Next.js (novos componentes do CSM Studio) mantém o Vitest já configurado com `@testing-library/react` para testes de componentes críticos. Testes não bloqueiam CI atualmente — esta postura será reavaliada quando o volume de testes crescer.

## Deployment

Dois domínios de deployment com pipelines separados:
1. **`cloudbuild.yaml`** — produto web (Next.js + CMO Agent FastAPI). Deploy automático em push para `main`. Cloud Run Services (sempre online).
2. **`cloudbuild-pipeline.yaml`** (novo) — microserviços da content pipeline (TTS Job, Avatar Job, Video Editor Job, Publisher Service). Deploy separado do ciclo de vida do produto web. Cloud Run Jobs (assíncronos, disparados por Pub/Sub). O trigger de deploy pode ser manual ou em tag dedicada, separado do deploy do web app.

Ambas as pipelines usam GCR com tags `$COMMIT_SHA` + `latest`, secrets via Cloud Run `--set-secrets` apontando para Secret Manager.

## Code Style

**TypeScript (Next.js):** `strict: true`, CSS Modules exclusivo para componentes CSM, named exports, camelCase. ESLint com `next/core-web-vitals`. Glassmorphism como padrão visual para novos componentes de painel.
**Python (microserviços):** FastAPI + Pydantic v2, snake_case, type hints obrigatórios em funções públicas, async/await para todas as chamadas de I/O. Imports absolutos a partir da raiz do serviço.
## Forbidden

<!-- Team-specific forbidden patterns -->

## Mandated

<!-- Team-specific mandates -->

## Corrections

<!-- Self-learning loop appends here. -->
