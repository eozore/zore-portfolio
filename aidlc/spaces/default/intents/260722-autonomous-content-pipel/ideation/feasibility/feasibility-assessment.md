# Feasibility Assessment
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [intent-statement.md](../intent-capture/intent-statement.md) | [competitive-analysis.md](../market-research/competitive-analysis.md) | [market-trends.md](../market-research/market-trends.md) | [build-vs-buy.md](../market-research/build-vs-buy.md)

**Veredicto geral:** ✅ **VIÁVEL** — todas as integrações críticas têm APIs estáveis e documentadas. Os maiores riscos são de integração (HeyGen v2→v3 migration) e de conformidade (AI disclosure obrigatório), ambos mitigáveis com design cuidadoso.

---

## 1. Viabilidade Técnica por Componente

### 1.1 ElevenLabs TTS → Áudio por Segmento

**Viabilidade: Alta**

- API REST bem documentada, SDKs para Python e Node.js
- Clone de voz (`POST /v1/voice-clone`) disponível no plano Creator ($22/mês) — Instant Voice Clone
- TTS por texto (`POST /v1/text-to-speech/{voice_id}`) retorna áudio MP3/WAV
- Rate limits: 2 req/s no plano Creator; para batch de 15 segmentos por vídeo, latência total estimada ~30-45s — aceitável para processamento assíncrono
- **Risco identificado:** ElevenLabs Instant Voice Clone (plano Creator) vs Professional Voice Clone (plano Scale $330/mês). A diferença de qualidade para pt-BR precisa ser testada antes de decidir o plano. Custo: Creator $22/mês vs Scale $330/mês — diferença significativa.
- **Mitigação:** Testar clone instantâneo no plano Creator com amostras de voz do Victor antes de commitar ao plano. Se qualidade inadequada, subir para Creator Pro ($99/mês) que inclui Professional Voice Clone com mais amostras.

### 1.2 HeyGen Lipsync API → Vídeo Avatar Sincronizado

**Viabilidade: Alta — com migração necessária**

O fluxo técnico confirmado via documentação HeyGen v3:

```
1. Upload avatar base (foto ou vídeo loop)
   POST /v3/assets  →  retorna asset_id (avatar)

2. Upload áudio ElevenLabs
   POST /v3/assets  →  retorna asset_id (audio)

3. Criar lipsync job
   POST /v3/lipsyncs
   {
     "video": { "type": "asset_id", "url": "<avatar_asset_id>" },
     "audio": { "type": "asset_id", "url": "<audio_asset_id>" },
     "mode": "precision",          // frame-accurate para conteúdo longo
     "enable_dynamic_duration": true
   }
   →  retorna lipsync_id

4. Polling status
   GET /v3/lipsyncs/{lipsync_id}
   →  quando status = "completed", retorna video_url para download
```

- **Migração crítica:** código atual usa `/v2/video/generate` (descontinuado em outubro/2026). Deve migrar para v3 Lipsync API.
- **Modo `precision` obrigatório** para vídeos de 10-20 min — frame-accurate lip sync é o que garante naturalidade.
- **Latência de renderização HeyGen:** tipicamente 1-3x a duração do vídeo. Para vídeo de 15 min → estimativa 15-45 min de renderização. Pub/Sub com polling periódico é o padrão correto (não aguardar sincronamente).
- **Assets têm TTL no HeyGen:** assets sobem temporariamente; o vídeo final deve ser baixado e armazenado no GCS assim que disponível.

### 1.3 Pipeline de Edição (Composição Slides + Avatar)

**Viabilidade: Alta — simplificação significativa vs. atual**

O manifesto v2 já contém `slide_index` e `start_time`/`end_time` por segmento. Com o áudio de duração determinística (ElevenLabs retorna duração exata do áudio gerado), o pipeline de edição fica completamente determinístico:

```python
# Pseudo-código do novo editor (sem Gemini alignment)
for segment in manifest["youtube"]["segments"]:
    audio_duration = elevenlabs_audio_durations[segment["id"]]
    slide_clip = render_slide_html(
        deck=manifest["youtube"]["deck"],
        slide_index=segment["slide"],
        duration=audio_duration + segment.get("pause_after_s", 0)
    )
    # compor sobre o vídeo do avatar no timestamp acumulado
    timeline.add(slide_clip, start=cumulative_time)
    cumulative_time += audio_duration + segment.get("pause_after_s", 0)
```

O `tool-videoyoutube` existente tem toda a estrutura FFmpeg necessária. A refatoração principal é:
1. Remover a dependência do Gemini para alignment (substituir por leitura direta do manifesto + duração do áudio)
2. Empacotar como Cloud Run Job consumindo mensagens Pub/Sub
3. Manter Playwright para renderização dos slides HTML em vídeo

### 1.4 Publisher Service → Publicação nas Redes Sociais

**Viabilidade: Alta para Meta/LinkedIn, Média para YouTube**

| Plataforma | API | Status Victor | Risco |
|---|---|---|---|
| Instagram | Meta Graph API v21+ (`POST /{ig-user-id}/media`) | Operacional | Baixo — já funciona |
| Threads | Meta Graph API (`POST /{user-id}/threads`) | Operacional | Baixo — já funciona |
| Facebook | Meta Graph API | Operacional | Baixo |
| LinkedIn | LinkedIn API v2 (`POST /ugcPosts`) | Operacional | Baixo |
| YouTube | YouTube Data API v3 (`POST /youtube/v3/videos`) | A confirmar | Médio — requer OAuth com escopo `youtube.upload` |

**YouTube especificamente:** Como o projeto já está no GCP, a YouTube Data API v3 está disponível no mesmo console. A autenticação requer OAuth 2.0 com conta Google do canal (service account não suporta upload em nome de canal pessoal — requer OAuth do usuário). O token refresh deve ser gerenciado pelo painel de configuração.

**AI Disclosure obrigatório no YouTube:** O payload de upload deve incluir o campo `selfDeclaredMadeForKids: false` e, para conteúdo com AI disclosure, o `VideoStatus.madeForKids` e os novos campos de AI content declaration. O Publisher Service deve preencher isso automaticamente para todo conteúdo da pipeline.

### 1.5 Infraestrutura GCP (Perspectiva AWS Platform Agent — adaptada para GCP)

**Viabilidade: Alta — ecossistema já estabelecido**

```
Serviços GCP necessários:
+--------------------------------------------+
| JA ATIVOS                                  |
|  Cloud Run (Services) - cmo_agent          |
|  Firestore - banco principal               |
|  Cloud Storage - midia e assets            |
|  Secret Manager - chaves e tokens          |
+--------------------------------------------+
| PRECISAM SER ATIVADOS/CONFIGURADOS         |
|  Cloud Pub/Sub - mensageria entre servicos |
|  Cloud Run Jobs - processamento async longo|
|  Cloud Scheduler - publicacao agendada     |
|  Cloud Tasks - retry de jobs com backoff   |
+--------------------------------------------+
| OPCIONAIS (fase 2)                         |
|  Cloud Workflows - orquestracao complexa   |
|  Artifact Registry - imagens Docker        |
+--------------------------------------------+
```

**Topologia dos microserviços no Cloud Run:**

```
cloud-run-services/
  cmo-agent           (existente - interativo, FastAPI)
  publisher-service   (novo - publica nas redes sociais)
  config-service      (novo - painel de configuração)

cloud-run-jobs/
  tts-job             (ElevenLabs TTS por segmento)
  avatar-job          (HeyGen Lipsync - polling longo)
  video-editor-job    (FFmpeg composição de slides)
  
cloud-scheduler/
  daily-publisher     (verifica fila e publica 1 pacote/dia)
```

**Estimativa de custo de infra GCP por semana (1 pacote/semana):**
- Cloud Run Jobs (3 jobs × ~$0.00002/vCPU-sec × ~300s): ~$0.02
- Cloud Storage (armazenamento de vídeos ~2GB/semana): ~$0.05/semana
- Pub/Sub (~20 mensagens/semana): ~$0.00 (free tier)
- Cloud Scheduler (1 job/dia): ~$0.00 (free tier 3 jobs)
- **Total infra GCP: ~$0.07/semana** — insignificante no orçamento

---

## 2. Riscos Técnicos Classificados

| ID | Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|
| R01 | HeyGen muda pricing/API antes da entrega | Média | Alto | Encapsular em `AvatarService` interface; manter Synthesia como backup |
| R02 | ElevenLabs Instant Clone inadequado para pt-BR | Média | Médio | Testar antes de implementar; fallback para Creator Pro |
| R03 | HeyGen renderização demora >30 min para vídeo longo | Baixa | Médio | Pub/Sub com polling; timeout de 60 min com alertas |
| R04 | Meta suspende conta por volume de publicação | Baixa | Alto | Throttler com rate limits conservadores; nunca postar mais de 1x/dia por rede |
| R05 | YouTube rejeita upload por AI disclosure ausente | Alta | Alto | Preencher campo automaticamente; checklist obrigatório no gate |
| R06 | Vídeo horizontal de 15 min excede limite de créditos HeyGen | Média | Médio | Monitorar créditos; segmentar em múltiplos clips se necessário |
| R07 | Slides HTML com Playwright quebram em Cloud Run | Média | Alto | Playwright precisa de Chromium headless — verificar compatibilidade com Cloud Run Jobs Alpine |

---

## 3. Dependências Externas Críticas

| Dependência | Tipo | Estabilidade | SLA Estimado |
|---|---|---|---|
| ElevenLabs API | Parceiro TTS | Alta — API madura, empresa bem capitalizada | 99.9% |
| HeyGen API v3 | Parceiro Avatar | Alta — API v3 é a versão atual; v2 descontinua out/2026 | 99.5% |
| Meta Graph API | Publicação | Alta — API oficial Meta, muito estável | 99.9% |
| LinkedIn API v2 | Publicação | Alta — API oficial LinkedIn | 99.5% |
| YouTube Data API v3 | Publicação | Alta — Google, mesma infra do projeto | 99.99% |
| GCP Pub/Sub | Infra | Altíssima — serviço gerenciado Google | 99.95% |
| Playwright/Chromium | Renderização slides | Média — dependência de browser headless em container | N/A |

---

## 4. Veredicto por Objetivo do Intent

| Objetivo | Viabilidade | Nota |
|---|---|---|
| Sessão CMO semanal → aprovação de pacote | ✅ Alta | CSM Studio já existe; adicionar kanban de projetos |
| ElevenLabs gera áudio por segmento | ✅ Alta | API estável; testar qualidade de clone pt-BR primeiro |
| HeyGen gera avatar com áudio externo | ✅ Alta | Lipsync API v3 confirmada; migrar v2→v3 |
| Editor compõe slides + avatar deterministicamente | ✅ Alta | Manifesto v2 elimina necessidade de inferência |
| Publicação automática em 6+ canais | ✅ Alta | APIs operacionais; YouTube requer OAuth setup |
| Painel de configuração com keys seguras | ✅ Alta | Secret Manager já ativo; UI nova no CSM Studio |
| Kanban de projetos no CSM Studio | ✅ Alta | Nova coleção Firestore `content_projects`; nova aba no web |
| Teto de custo R$100/vídeo | ✅ Alta | Estimativa R$67 — margem de 33% |
| Zero ban nas plataformas | ⚠️ Média | Requer implementação cuidadosa: APIs oficiais + AI disclosure + throttler |
