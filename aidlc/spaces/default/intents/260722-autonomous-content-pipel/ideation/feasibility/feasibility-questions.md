# Feasibility — Registro de Decisões Técnicas
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Conduzido via análise direta do código existente + pesquisa de APIs. Confirmações de Victor registradas abaixo.

---

### F1. Fluxo ElevenLabs → HeyGen confirmado?

A arquitetura técnica é:
1. ElevenLabs TTS API → gera arquivo WAV/MP3 por segmento
2. HeyGen Assets API (`POST /v3/assets`) → faz upload do áudio, retorna `asset_id`
3. HeyGen Lipsync API (`POST /v3/lipsyncs`) → recebe `video_url` (avatar base) + `audio.type: "asset_id"` → devolve vídeo com lip-sync sincronizado

[Answer]: Confirmado pela documentação HeyGen v3. O Lipsync API aceita áudio externo via asset_id. Fluxo viável.

---

### F2. Migração de HeyGen v2 → v3

O código atual em `apps/web/src/app/api/csm/heygen/route.ts` usa `POST /v2/video/generate`. A documentação HeyGen informa que v1/v2 são descontinuados em outubro/2026. Migração para v3 é obrigatória.

[Answer]: Migração para HeyGen v3 necessária antes de outubro/2026. É parte do escopo de implementação.

---

### F3. Infraestrutura GCP existente é suficiente?

Cloud Run (cmo_agent Python), Firestore, Cloud Storage, Secret Manager já estão ativos. Pub/Sub requer ativação da API no projeto.

[Answer]: Infraestrutura base suficiente. Pub/Sub API precisa ser ativada. Cloud Run Jobs (para processamento assíncrono longo) precisa ser configurado separadamente do Cloud Run Services.

---

### F4. LGPD / dados pessoais na pipeline

A pipeline processa: voz clonada do Victor (dado biométrico do próprio titular), conteúdo técnico público, tokens OAuth de redes sociais. Não processa dados de terceiros.

[Answer]: Risco LGPD baixo — o titular dos dados biométricos é o próprio operador do sistema. Tokens OAuth devem ser armazenados exclusivamente no GCP Secret Manager.
