# Discovered Rules
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Regras corretivas derivadas das práticas afirmadas. Formato agente-facing.

---

## Mandated

- ALWAYS usar Cloud Run Jobs (não Services) para TTS Job, Avatar Job, Video Editor Job e Publisher Service — esses processos têm latência variável de 5-45 min e requerem timeout > 60 min.
- ALWAYS armazenar API keys (ElevenLabs, HeyGen) e OAuth tokens (YouTube, Meta, LinkedIn) exclusivamente no GCP Secret Manager — nunca em variáveis de ambiente hardcoded ou no Firestore.
- ALWAYS incluir o campo de AI disclosure (`selfDeclaredAiGeneratedContent: true`) no payload de upload da YouTube Data API v3 para todo conteúdo gerado pela pipeline.
- ALWAYS garantir idempotência nos consumers Pub/Sub — processar a mesma mensagem duas vezes não deve ter efeito colateral duplicado.
- ALWAYS escrever type hints em todas as funções públicas Python dos novos microserviços.
- ALWAYS usar `async/await` para todas as chamadas de I/O nos microserviços Python (ElevenLabs, HeyGen, Pub/Sub, GCS, Firestore).
- ALWAYS usar o `cloudbuild-pipeline.yaml` dedicado (não o `cloudbuild.yaml` do web app) para deploys dos microserviços da content pipeline.
- ALWAYS incluir `approval_status: "approved"` verificado no Firestore antes de qualquer publicação nas redes sociais — o Publisher Service não publica sem esse campo.
- ALWAYS usar a Meta Graph API oficial para publicação no Instagram, Threads e Facebook — nunca browser automation, scrapers ou password-sharing.
- ALWAYS prefixar commits dos Bolts da pipeline com o slug do Bolt (ex: `feat(bolt-1-walking-skeleton): ...`).

---

## Forbidden

- NEVER usar o endpoint `/v2/video/generate` do HeyGen — usar exclusivamente a HeyGen Lipsync API v3 (`POST /v3/lipsyncs`).
- NEVER usar LLMs que não sejam do Google (Gemini via Vertex AI) nos agentes Python da pipeline — OpenAI, Anthropic e outros estão fora do escopo.
- NEVER escrever API keys ou tokens OAuth diretamente em código, `.env` commitado, ou variáveis Cloud Run plaintext — sempre via Secret Manager.
- NEVER usar Gemini para inferir o alinhamento de slides no Video Editor — o manifesto JSON já contém o mapeamento `segmento → slide` explicitamente; leitura direta do manifesto é obrigatória.
- NEVER usar browser automation (Selenium, Playwright para simular postagem) para publicação nas redes sociais — somente APIs oficiais.
- NEVER publicar conteúdo sem AI disclosure preenchido para vídeos no YouTube — viola política do YouTube desde maio/2026.
- NEVER fazer polling ativo de status do HeyGen em loops síncronos — usar o `callback_url` da Lipsync API v3 para notificação assíncrona.
- NEVER usar CSS global ou Tailwind em novos componentes do CSM Studio — CSS Modules exclusivamente.
- NEVER deployar os microserviços da content pipeline via `cloudbuild.yaml` do web app — pipelines separadas por domínio de deployment.
