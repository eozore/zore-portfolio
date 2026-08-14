# Business Logic Model — Video Editor API

> Referência: requirements.md (FR-01 a FR-07), scope: refactor

## Pipeline Overview

```
┌──────────────┐    ┌──────────────┐    ┌───────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Upload     │───▶│  STT Module  │───▶│  Slide Export │───▶│  Alignment   │───▶│  Compose     │───▶│  Jump Cuts   │
│  (MP4+HTML)  │    │  (Transcribe)│    │  (Playwright) │    │  (Gemini LLM)│    │  (FFmpeg)    │    │  (FFmpeg)    │
└──────────────┘    └──────────────┘    └───────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                                        │                    │
                                                                                        ▼                    ▼
                                                                                 ┌─────────────┐    ┌──────────────┐
                                                                                 │ Horizontal  │    │   Vertical   │
                                                                                 │ (1920×1080) │    │ (1080×1920)  │
                                                                                 └─────────────┘    └──────────────┘
```

## Module Breakdown

### 1. Project Manager (Orchestrator)

**Responsabilidade:** Gerencia o ciclo de vida de um "projeto de vídeo" — criação, execução de steps, persistência de estado, retry, e entrega.

**Workflow:**
1. Recebe upload (MP4 + HTML)
2. Cria projeto com ID único + metadata
3. Persiste estado no Firestore (ou JSON local para dev)
4. Executa pipeline step-by-step, atualizando estado a cada transição
5. Emite eventos de progresso via WebSocket
6. No final, registra URLs dos outputs e notifica conclusão

**State Machine do Projeto:**
```
CREATED → UPLOADING → TRANSCRIBING → EXPORTING_SLIDES → ALIGNING → 
COMPOSING_HORIZONTAL → COMPOSING_VERTICAL → CUTTING → UPLOADING_RESULTS → COMPLETED
                                                                              │
                                                         (qualquer step) → FAILED
```

### 2. STT Module (Speech-to-Text)

**Input:** Arquivo MP4 (path local ou GCS URI)
**Output:** `TranscriptResult` — lista de segments com words e timestamps

**Algoritmo:**
1. Extrair áudio do MP4 → WAV (16kHz, mono, PCM s16le) via FFmpeg
2. Upload WAV para GCS (bucket temporário)
3. Chamar GCP Speech-to-Text long_running_recognize (pt-BR, word_time_offsets=true)
4. Aguardar resultado (polling com timeout de 10 min)
5. Parsear response → lista de `{text, start, end, words[]}`
6. Cleanup: deletar WAV do GCS
7. Cache: salvar transcript como JSON no projeto (evita re-transcrição em retry)

**Cache Strategy:** Se `transcript.json` já existe no projeto, skip steps 1-6.

### 3. Slide Export Module

**Input:** Arquivo HTML (deck de slides), resolução alvo (width × height)
**Output:** Lista de clipes MP4 (um por slide)

**Algoritmo:**
1. Abrir HTML no Playwright (Chromium headless)
2. Contar slides (`section.slide`)
3. Para cada slide:
   a. Criar novo browser context com video recording
   b. Navegar para o slide (`goTo(i)`)
   c. Ocultar elementos (CSS injection — opacidade 0)
   d. Aguardar 2s (background limpo para transição suave)
   e. Remover ocultação + `replaySlide()` (dispara animações)
   f. Gravar por SLIDE_DURATION_SECONDS (10s)
   g. Fechar context → salvar WebM
   h. Converter WebM → MP4 (FFmpeg, libx264, crf 18)
4. Retornar lista de paths dos MP4s gerados

**Dual Resolution:**
- Chamar 2x: uma com 1920×1080 (horizontal) e outra com 1080×1920 (vertical)
- Para vertical: o HTML é renderizado com viewport 1080×1920, CSS adapta automaticamente (responsive) ou force-fit via `transform: scale()`

### 4. Alignment Module (LLM)

**Input:** `TranscriptResult` + descrição semântica dos slides
**Output:** `AlignmentResult` — lista de `{slide_index, start_time, end_time}`

**Algoritmo:**
1. Extrair descrição semântica de cada slide (texto do HTML via BeautifulSoup)
2. Construir prompt com system instruction (regras de YouTube editing) + transcript + slides
3. Chamar Gemini 2.5 Flash (temperature 0.2) via Vertex AI
4. Parsear resposta JSON (com fallback regex para markdown blocks)
5. Validar alinhamentos:
   - `slide_index` dentro do range [1, total_slides]
   - `start_time < end_time`
   - Duração mínima de 3s
   - Sem sobreposição temporal
6. Ordenar por `start_time`
7. Retornar resultado validado

**Regras de Pacing (instruções ao LLM):**
- Hook/Intro: apenas avatar (sem slides)
- Desenvolvimento: alternância dinâmica
- Final/CTA: apenas avatar
- Mín 3s por slide, máx 40s contínuos
- Cortes nos limites semânticos da fala

### 5. Compose Module (FFmpeg)

**Input:** Vídeo original (MP4), alignments, slide clips (MP4), resolução alvo
**Output:** Vídeo composto (slides overlayed no avatar)

**Algoritmo:**
1. Deduplicar: agrupar janelas de tempo por slide único
2. Para cada slide: scale + trim (2s de buffer removido) + loop no último frame
3. Construir filter_complex encadeado:
   - `[0:v]` → scale para resolução alvo → `[base_v]`
   - Para cada slide: trim + loop + setpts offset → `[slide_N]`
   - Overlay chain com `enable='between(t,start,end)'`
4. Map áudio original (se existir)
5. Encode: libx264, crf 18, fast preset, yuv420p
6. Executar FFmpeg

**Dual Output:**
- Horizontal: slides de 1920×1080 sobre vídeo 1920×1080
- Vertical: slides de 1080×1920 sobre vídeo cropado/scaled para 1080×1920

### 6. Jump Cuts Module

**Input:** Vídeo composto, TranscriptResult, configurações (min_silence, padding)
**Output:** Vídeo final com silêncios removidos

**Algoritmo:**
1. Extrair todos os words do transcript com timestamps
2. Detectar gaps ≥ `min_silence` (default: 0.5s) entre words
3. Construir segments de "fala ativa" com `padding` (default: 0.2s) nas bordas
4. Guard: se > 25 segments, copiar vídeo sem cortes (evita crash FFmpeg em filtros longos)
5. Construir filter_complex: trim + atrim para cada segment → concat
6. Executar FFmpeg
7. Fallback: se FFmpeg falha, copiar vídeo sem cortes

### 7. Storage Module

**Input:** Vídeos finais (horizontal + vertical)
**Output:** URLs de download (GCS signed URLs ou paths de download da API)

**Algoritmo:**
1. Upload para GCS bucket (`editor-outputs/{project_id}/`)
2. Gerar signed URLs com expiração (24h)
3. Registrar URLs no estado do projeto
4. Cleanup: agendar deleção dos temporários locais após confirmação

## Data Flow Summary

```
MP4 ─────────────────┬──▶ STT ──▶ transcript.json ──▶ Alignment ──▶ alignments.json
                     │                                       │
HTML ──▶ SlideExport ┤                                       │
         (1920×1080) ├──▶ slides_h/*.mp4 ─────────────┬──────┤
         (1080×1920) └──▶ slides_v/*.mp4 ────────┐    │      │
                                                  │    │      │
                              ┌────────────────────┘    │      │
                              ▼                         ▼      ▼
                    Compose(vertical) ──▶ JumpCuts ──▶ final_v.mp4 ──▶ Storage
                              │
                              └── Compose(horizontal) ──▶ JumpCuts ──▶ final_h.mp4 ──▶ Storage
```
