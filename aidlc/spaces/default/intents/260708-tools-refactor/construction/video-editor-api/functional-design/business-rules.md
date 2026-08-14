# Business Rules — Video Editor API

> Referência: requirements.md, business-logic-model.md

## Input Validation Rules

### BR-01: Accepted File Types
- MP4: apenas `.mp4` com codec de vídeo H.264 ou H.265
- HTML: apenas `.html` com pelo menos 1 `<section class="slide">`
- Rejeitar upload se qualquer condição falhar (HTTP 400)

### BR-02: Duration Limits
- Máximo: 2 horas (7200 segundos)
- Validar duração via `ffprobe` antes de iniciar pipeline
- Se exceder: rejeitar com mensagem clara ao usuário

### BR-03: File Size Limits
- MP4: até 2GB (cobre ~2h em 1080p a bitrate razoável)
- HTML: até 10MB (deck com assets inline)
- Configurável via env vars: `MAX_VIDEO_SIZE_MB`, `MAX_HTML_SIZE_MB`

## Pipeline Execution Rules

### BR-04: Idempotência e Cache
- Transcrição é cacheada por projeto: se `transcript.json` existe, skip STT
- Slides exportados são cacheados: se `slides/slide_01.mp4` existe, skip export
- Alignment NÃO é cacheado (depende do contexto do momento)
- Re-run de projeto usa cache dos steps anteriores

### BR-05: Fallback Strategy
| Step | Fallback |
|------|----------|
| STT | Retry 1x com exponential backoff. Se falha 2x → FAILED |
| Slide Export | Skip slide com erro, continuar com restantes. Se 0 slides → FAILED |
| Alignment (Gemini) | Retry 1x. Se JSON inválido 2x → FAILED |
| Compose (FFmpeg) | Se falha com overlay → copiar vídeo original sem slides |
| Jump Cuts | Se > 25 segments OU FFmpeg falha → copiar vídeo sem cortes |
| Storage (GCS) | Retry 2x. Se falha → manter local, retornar path direto |

### BR-06: Timeout por Step
| Step | Timeout |
|------|---------|
| Upload | 5 min |
| STT (GCP) | 10 min |
| Slide Export | 3 min por slide (max 60 min total) |
| Alignment (Gemini) | 2 min |
| Compose | 30 min |
| Jump Cuts | 30 min |
| Storage Upload | 10 min |

### BR-07: Concurrency
- Máximo 3 projetos processando simultaneamente por instância
- Fila FIFO para excedentes
- Configurável via `MAX_CONCURRENT_JOBS`

## Alignment Rules (LLM Instructions)

### BR-08: Slide Timing Constraints
- Duração mínima de um slide na tela: 3 segundos
- Duração máxima contínua: 40 segundos (depois, cortar de volta para avatar)
- Sem sobreposição temporal entre slides
- `start_time < end_time` (invariante)
- `slide_index` deve estar no range [1, total_slides]

### BR-09: Video Structure (YouTube Best Practices)
- Primeiros 15-30s: apenas avatar (hook/intro) — nenhum slide
- Últimos 15-30s: apenas avatar (CTA/encerramento) — nenhum slide
- Meio: alternância dinâmica entre avatar e slides

### BR-10: Semantic Boundaries
- Início/fim de slide deve coincidir com limites de frases (não cortar palavras)
- Usar word-level timestamps do transcript para precisão
- Evitar cortar em filler words ("ééé", "hmm", respirações)

## Output Rules

### BR-11: Video Specifications
| Propriedade | Horizontal | Vertical |
|-------------|-----------|----------|
| Resolução | 1920×1080 | 1080×1920 |
| Codec | H.264 (libx264) | H.264 (libx264) |
| CRF | 18 | 18 |
| Pixel Format | yuv420p | yuv420p |
| Áudio | AAC 192kbps | AAC 192kbps |
| Container | MP4 | MP4 |

### BR-12: Slide Overlay Behavior
- Quando ativo: slide cobre 100% da tela (fullscreen overlay)
- Quando inativo: avatar visível em 100%
- Transição: corte direto (sem fade — mais dinâmico para YouTube)
- Slide loop: congela no último frame se slide clip é mais curto que a janela

### BR-13: Vertical Adaptation
- O HTML é re-renderizado em viewport 1080×1920
- Se CSS não é responsive: aplicar `transform: scale()` para fit
- Slides verticais são clipes independentes dos horizontais

## Project Memory Rules

### BR-14: Project Lifecycle
- Cada upload cria um projeto com UUID
- Estado persistido: Firestore (prod) ou JSON local (dev)
- Projetos mantidos por 7 dias após conclusão
- Projeto pode ser re-executado (re-run) a partir de qualquer step

### BR-15: Project State Fields
```
{
  id: string (UUID),
  status: enum (CREATED|TRANSCRIBING|EXPORTING|ALIGNING|COMPOSING|CUTTING|UPLOADING|COMPLETED|FAILED),
  created_at: timestamp,
  updated_at: timestamp,
  input: { video_path, html_path, video_duration_sec },
  progress: { current_step, percent, message },
  outputs: { horizontal_url, vertical_url, expires_at },
  error: { step, message, stack } | null,
  cache: { transcript_path, slides_h_dir, slides_v_dir }
}
```

### BR-16: WebSocket Events
```
PROJECT_CREATED    → { project_id }
STEP_STARTED       → { project_id, step, message }
STEP_PROGRESS      → { project_id, step, percent, message }
STEP_COMPLETED     → { project_id, step }
PROJECT_COMPLETED  → { project_id, outputs: { horizontal_url, vertical_url } }
PROJECT_FAILED     → { project_id, error: { step, message } }
```

## Security Rules

### BR-17: File Sanitization
- Filenames sanitizados (remove caracteres especiais, espaços → underscore)
- Paths nunca construídos via concatenação com input do usuário (path traversal prevention)
- Temporários isolados por project_id

### BR-18: Resource Cleanup
- Arquivos temporários deletados após conclusão ou falha
- WAV de áudio deletado do GCS imediatamente após transcrição
- Outputs no GCS expiram em 24h (configurable via `OUTPUT_EXPIRY_HOURS`)
