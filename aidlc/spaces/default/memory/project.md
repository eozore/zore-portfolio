# Project-Level Rules

> Project-specific overrides and corrections. Overrides aidlc-team.md
> and aidlc-org.md. Populated by practices-discovery and the
> self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project deviates from team-wide practice in a
> stable, durable way (e.g., "this monorepo project rebases even though
> our team default is squash"; "this legacy project skips the test
> floor because the existing suite is unsalvageable and we accept
> that").

## Way of Working

<!-- Project-specific override. Example: -->
<!-- This monorepo project rebases instead of squash-merging because -->
<!-- the per-package commit history is the audit trail we depend on -->
<!-- for partial-rollback decisions. Override applies to this project -->
<!-- only. -->

## Walking Skeleton

<!-- Project-specific override. Example: -->
<!-- This project skips the walking skeleton because we're rewriting -->
<!-- an existing service in-place — there's no greenfield bootstrap -->
<!-- to gate. -->

## Testing Posture

<!-- Project-specific override. -->

## Deployment

<!-- Project-specific override. -->

## Code Style

<!-- Project-specific override. -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

## Scope Overrides

<!-- Custom scope rules for this project. -->

## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

- NEVER usar o endpoint `/v2/video/generate` do HeyGen — usar exclusivamente a HeyGen Lipsync API v3 (`POST /v3/lipsyncs`). (affirmed 2026-07-22)
- NEVER usar LLMs que não sejam do Google (Gemini via Vertex AI) nos agentes Python da pipeline — OpenAI, Anthropic e outros estão fora do escopo. (affirmed 2026-07-22)
- NEVER escrever API keys ou tokens OAuth diretamente em código, `.env` commitado, ou variáveis Cloud Run plaintext — sempre via Secret Manager. (affirmed 2026-07-22)
- NEVER usar Gemini para inferir o alinhamento de slides no Video Editor — o manifesto JSON já contém o mapeamento `segmento → slide` explicitamente; leitura direta do manifesto é obrigatória. (affirmed 2026-07-22)
- NEVER usar browser automation (Selenium, Playwright para simular postagem) para publicação nas redes sociais — somente APIs oficiais. (affirmed 2026-07-22)
- NEVER publicar conteúdo sem AI disclosure preenchido para vídeos no YouTube — viola política do YouTube desde maio/2026. (affirmed 2026-07-22)
- NEVER fazer polling ativo de status do HeyGen em loops síncronos — usar o `callback_url` da Lipsync API v3 para notificação assíncrona. (affirmed 2026-07-22)
- NEVER usar CSS global ou Tailwind em novos componentes do CSM Studio — CSS Modules exclusivamente. (affirmed 2026-07-22)
- NEVER deployar os microserviços da content pipeline via `cloudbuild.yaml` do web app — pipelines separadas por domínio de deployment. (affirmed 2026-07-22)
## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

- ALWAYS usar Cloud Run Jobs (não Services) para TTS Job, Avatar Job, Video Editor Job e Publisher Service — esses processos têm latência variável de 5-45 min e requerem timeout > 60 min. (affirmed 2026-07-22)
- ALWAYS armazenar API keys (ElevenLabs, HeyGen) e OAuth tokens (YouTube, Meta, LinkedIn) exclusivamente no GCP Secret Manager — nunca em variáveis de ambiente hardcoded ou no Firestore. (affirmed 2026-07-22)
- ALWAYS incluir o campo de AI disclosure (`selfDeclaredAiGeneratedContent: true`) no payload de upload da YouTube Data API v3 para todo conteúdo gerado pela pipeline. (affirmed 2026-07-22)
- ALWAYS garantir idempotência nos consumers Pub/Sub — processar a mesma mensagem duas vezes não deve ter efeito colateral duplicado. (affirmed 2026-07-22)
- ALWAYS escrever type hints em todas as funções públicas Python dos novos microserviços. (affirmed 2026-07-22)
- ALWAYS usar `async/await` para todas as chamadas de I/O nos microserviços Python (ElevenLabs, HeyGen, Pub/Sub, GCS, Firestore). (affirmed 2026-07-22)
- ALWAYS usar o `cloudbuild-pipeline.yaml` dedicado (não o `cloudbuild.yaml` do web app) para deploys dos microserviços da content pipeline. (affirmed 2026-07-22)
- ALWAYS incluir `approval_status: "approved"` verificado no Firestore antes de qualquer publicação nas redes sociais — o Publisher Service não publica sem esse campo. (affirmed 2026-07-22)
- ALWAYS usar a Meta Graph API oficial para publicação no Instagram, Threads e Facebook — nunca browser automation, scrapers ou password-sharing. (affirmed 2026-07-22)
- ALWAYS prefixar commits dos Bolts da pipeline com o slug do Bolt (ex: `feat(bolt-1-walking-skeleton): ...`). (affirmed 2026-07-22)
--- (affirmed 2026-07-22)
## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
