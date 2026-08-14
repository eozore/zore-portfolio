# Component Methods
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## C-07: ProjectService (Route Handlers Next.js)

```typescript
// GET /api/csm/projects
async function listProjects(tenantId: string): Promise<ContentProject[]>
// Retorna todos os projetos ordenados por created_at desc

// POST /api/csm/projects
async function createProject(tenantId: string, manifestUrl: string): Promise<{ id: string }>
// Cria projeto em Firestore com status: 'awaiting_approval'

// GET /api/csm/projects/[id]/cost-estimate
async function getCostEstimate(projectId: string): Promise<CostBreakdown>
// Lê manifesto, calcula custo por etapa baseado em config (ElevenLabs rate, HeyGen rate)
// Lança: ProjectNotFoundError, ManifestParseError

// POST /api/csm/projects/[id]/approve
async function approveForProduction(
  projectId: string,
  channelsApproved: string[],
  aiDisclosure: boolean
): Promise<{ ok: true }>
// Escreve approval_data no Firestore; publica package_approved no Pub/Sub
// Lança: CostExceedsLimitError se custo estimado > cost_limit

// GET /api/csm/projects/[id]/publish-preview
async function getPublishPreview(projectId: string): Promise<PublishPreview>
// Gera GCS signed URLs (TTL 1h) para os vídeos finais; retorna cost_breakdown real

// POST /api/csm/projects/[id]/publish
async function approveForPublication(
  projectId: string,
  mode: 'now' | 'scheduled',
  scheduledAt: string | undefined,
  channels: string[]
): Promise<{ ok: true }>
// mode=now: chama publisher-immediate via HTTP; mode=scheduled: salva scheduled_publish_at

// POST /api/csm/projects/[id]/retry-stage
async function retryStage(projectId: string, stage: StageId): Promise<{ ok: true }>
// Publica mensagem Pub/Sub para re-disparar o job; reseta stage.status='running'

// POST /api/csm/projects/[id]/skip-stage
async function skipStage(projectId: string, stage: StageId): Promise<{ ok: true }>
// Atualiza stage.status='skipped'; publica próxima mensagem Pub/Sub na sequência

// POST /api/csm/projects/[id]/stages/[stage]/manual-upload
async function manualUpload(
  projectId: string,
  stage: StageId,
  file: File  // MP4
): Promise<{ ok: true; gcsUrl: string }>
// Upload para GCS; atualiza stage.status='completed', stage.source='manual'
// Publica próxima mensagem na sequência
```

---

## C-08: ConfigService (Route Handlers Next.js)

```typescript
// GET /api/csm/pipeline/config
async function getPipelineConfig(tenantId: string): Promise<PipelineConfig>
// Lê pipeline_config e channel_config do Firestore
// API keys: retorna apenas { masked: "sk-****" } — NUNCA o valor real

// POST /api/csm/pipeline/config
async function savePipelineConfig(
  tenantId: string,
  config: PipelineConfigUpdate
): Promise<{ ok: true }>
// Salva cost_limit, alert_threshold, schedule no Firestore

// POST /api/csm/pipeline/config/keys
async function saveApiKey(
  tenantId: string,
  provider: 'elevenlabs' | 'heygen',
  key: string
): Promise<{ saved: true }>
// Chama GCP Secret Manager para criar/atualizar secret
// NUNCA loga o valor da key; retorna apenas confirmação

// GET /api/csm/pipeline/config/ping
async function pingProvider(
  tenantId: string,
  provider: string
): Promise<{ ok: boolean; latencyMs: number; error?: string }>
// Faz chamada autenticada real ao provider com a key do Secret Manager
// ElevenLabs: GET /v1/models; HeyGen: GET /v3/voices

// POST /api/csm/pipeline/config/youtube-oauth
async function initiateYouTubeOAuth(tenantId: string): Promise<{ authUrl: string }>
// Gera URL de autorização Google OAuth 2.0
// Frontend abre popup com authUrl

// GET /api/csm/pipeline/config/youtube-oauth/callback
async function handleYouTubeOAuthCallback(
  code: string,
  state: string
): Promise<{ ok: true; expiresAt: string }>
// Troca code por tokens; salva refresh_token no Secret Manager
// Retorna data de expiração para o frontend atualizar o UI
```

---

## C-09: TTSJob (Python)

```python
async def run(project_id: str) -> None:
    """Entry point do Cloud Run Job — processa TTS dos segmentos com script != ''.
    Segmentos com script == '' (slide puro) são ignorados completamente."""

async def load_manifest(manifest_gcs_path: str) -> Manifest:
    """Lê e parseia o manifesto HTML do GCS. Lança ManifestParseError se inválido."""

def get_avatar_segments(manifest: Manifest, target: str) -> list[Segment]:
    """Filtra segmentos onde script != '' — apenas esses geram áudio e acionam HeyGen.
    Segmentos com script == '' são slides puros renderizados pelo VideoEditorJob."""

async def generate_segment_audio(
    segment: Segment,
    voice_id: str,
    model: str = "eleven_flash_v2_5"
) -> AudioResult:
    """Chama ElevenLabs API. Retry automático: 3 tentativas, backoff [1,4,16]s.
    Lança PermanentError para 401/403; TransientError esgotado após 3 tentativas."""

async def upload_audio_to_gcs(audio_bytes: bytes, path: str) -> str:
    """Upload MP3 para GCS. Retorna GCS URI."""

async def report_cost(project_id: str, chars: int, rate: float) -> None:
    """Chama CostTrackerService.update(). Lança CostLimitExceededError se bloqueado."""
```

---

## C-10: AvatarJob (Python)

```python
async def run(project_id: str) -> None:
    """Entry point — processa geração de avatar horizontal e vertical."""

async def concatenate_audio(
    audio_paths: list[str],
    target: Literal['horizontal', 'vertical']
) -> str:
    """Concatena MP3s na ordem do manifesto com pause_after_s entre segmentos.
    Retorna path local do arquivo concatenado."""

async def upload_to_heygen_assets(local_path: str) -> str:
    """POST /v3/assets → retorna asset_id."""

async def create_lipsync_job(
    video_asset_id: str,
    audio_asset_id: str,
    resolution: tuple[int, int],
    callback_url: str
) -> str:
    """POST /v3/lipsyncs mode=precision → retorna lipsync_id."""

async def await_lipsync_completion(lipsync_id: str, timeout_minutes: int = 90) -> str:
    """Aguarda callback via Pub/Sub. Timeout → TransientError.
    Retorna video_url quando HeyGen completa."""
```

---

## C-11: VideoEditorJob (Python)

```python
async def run(project_id: str) -> None:
    """Entry point — composição de vídeo horizontal e vertical.
    
    Dois modos de clipe por segmento:
      - script != '' → clipe de avatar (HeyGen output, duração = ffprobe do MP3)
      - script == '' → clipe de slide puro (Playwright, duração = segment.min_duration_s)
    
    O avatar nunca aparece nos segmentos de slide puro — Playwright ocupa 100% da tela.
    """

async def render_avatar_clip(
    avatar_video_path: str,
    segment: Segment,
    audio_path: str,
    resolution: tuple[int, int]
) -> str:
    """Extrai o trecho correspondente do vídeo avatar para o segmento.
    Duração = ffprobe(audio_path) + segment.pause_after_s.
    Retorna path do clipe MP4."""

async def render_slide_clip(
    deck_html: str,
    segment: Segment,
    resolution: tuple[int, int]
) -> str:
    """Playwright: renderiza slide HTML pelo tempo segment.min_duration_s.
    Usado apenas quando segment.script == ''. Zero HeyGen.
    Retorna path do clipe MP4."""

async def build_timeline(
    manifest: Manifest,
    avatar_clips: dict[str, str],
    slide_clips: dict[str, str],
    target: Literal['horizontal', 'vertical']
) -> list[Clip]:
    """Monta timeline intercalando clipes de avatar e de slide na ordem do manifesto.
    avatar_clips: { segment_id → path } para segmentos com script != ''
    slide_clips:  { segment_id → path } para segmentos com script == ''"""

async def compose_video(
    timeline: list[Clip],
    output_resolution: tuple[int, int]
) -> str:
    """FFmpeg concat: concatena todos os clipes na ordem da timeline.
    Retorna path do vídeo composto."""

async def apply_jump_cuts(
    input_path: str,
    transcript: list[Word],
    min_silence_s: float = 0.8,
    padding_s: float = 0.2
) -> str:
    """Remove silêncios usando timestamps da transcrição. Retorna path do vídeo cortado.
    Aplicado apenas nos clipes de avatar — slides puros não têm silêncios."""
```

---

## C-12: PublisherService (Python)

```python
async def publish_project(project_id: str, trigger: Literal['scheduled', 'immediate']) -> dict:
    """Entry point — publica em todos os canais aprovados e habilitados."""

async def publish_youtube(project: ContentProject, video_path: str) -> PublicationResult:
    """YouTube Data API v3 upload. Inclui selfDeclaredAiGeneratedContent: True.
    Suporta OAuth via refresh token (FR-12) ou service account (A-05)."""

async def publish_instagram_reel(project: ContentProject, video_path: str) -> PublicationResult:
    """Meta Graph API Reels endpoint. Falha isolada — não afeta outros canais."""

async def publish_youtube_short(project: ContentProject, video_path: str) -> PublicationResult:
    """YouTube Data API v3 com category: Shorts. Mesmo token OAuth do YouTube principal."""

async def publish_linkedin(project: ContentProject, text_content: str) -> PublicationResult:
    """LinkedIn ugcPosts API. Verifica throttler antes de chamar."""

async def publish_threads(project: ContentProject, text_content: str) -> PublicationResult:
    """Meta Graph API Threads. Falha isolada."""

async def publish_blog(project: ContentProject, article: dict) -> PublicationResult:
    """Chama POST /api/csm/publish (rota Next.js existente). Trata slug duplicado."""

async def record_publication(
    project_id: str,
    channel: str,
    result: PublicationResult
) -> None:
    """Atualiza project.publications.{channel} no Firestore."""
```

---

## C-13: CostTrackerService (Python Module)

```python
def estimate_tts_cost(char_count: int, model: str = "eleven_flash_v2_5") -> float:
    """Estima custo ElevenLabs: char_count * rate (R$/char). Lê rate do config."""

def estimate_heygen_cost(duration_minutes: float) -> float:
    """Estima custo HeyGen: duration * rate (R$/min). Confirmar com spike real."""

def check_cost_gate(project_id: str, additional_cost: float, limit: float) -> bool:
    """Retorna True se custo atual + additional_cost ≤ limit. 
    Se False: atualiza project.cost_blocked no Firestore."""

async def update_actual_cost(
    project_id: str,
    stage: str,
    cost_usd: float
) -> None:
    """Converte USD para BRL (taxa de câmbio config ou fixa R$5.50/USD).
    Atualiza project.cost_breakdown.{stage} no Firestore."""
```
