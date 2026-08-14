# User Flow — Content Studio (pós-bugfixes)

## Fluxo principal (happy path)

```
Victor acessa eozore.com/admin/csm
  │
  ▼
[IdeaTab] Chat com CMO Agent
  │  Victor descreve o tema (ex: "Fine-tuning com LoRA")
  │  CMO faz perguntas e define: titulo, subtitulo, tese, publico,
  │  objetivo_aprendizado, hardskills, duracao_alvo, serie, tipo_artigo ◄── BUG6 FIX
  │
  ▼
[GenerateTab] Geração do artigo (SSE)
  │  Critic → Research (Tavily API) ◄──────────────────────────────── BUG4 FIX
  │  Writing → Validator (contextual por tipo_artigo) ◄────────────── BUG6 FIX
  │  Gráficos Python: <img src="https://storage.googleapis.com/..."> ◄ BUG3 FIX
  │
  ▼
[PackageTab] Geração do pacote
  │  Scriptwriter → Slide Designer (HTML por beat type) ◄───────────── BUG1 FIX
  │  Thumbnail + Copy + Distribution
  │
  ▼
[CalendarTab] Calendário editorial
  │  Victor edita copy, hashtags, data/hora
  │  Aprova itens
  │
  ▼
[PublishTab] Aprovação e publicação
  │  Blog post + social_queue
  │  Pipeline vídeo disparada:
  │    TTS → Avatar (por segmento) ◄──────────────────────────────── BUG2 FIX
  │              │
  │              ▼ (N callbacks HeyGen, um por segmento)
  │    Video Editor (concatena segmentos na ordem do manifesto)
  │              │
  │              ▼
  │    Publisher (YouTube + Reel)
  │
  ▼
Conteúdo publicado ✅
```

## Fluxo BUG2 (novo — por segmento)

```
TtsCompletedMsg
  audio_paths = {
    "horizontal": ["gs://.../yt-01.mp3", "gs://.../yt-03.mp3", ...],  # N segmentos
    "vertical":   ["gs://.../reel-01.mp3", ...]
  }
    │
    ▼
AvatarJob (NOVO):
  Para cada seg em horizontal:
    upload_to_heygen_assets(seg.mp3) → audio_asset_id
    generate_avatar_video(audio_asset_id) → video_id
    salvar no Firestore: segment_videos.horizontal[i] = {seg_id, video_id, status: "pending"}
  Idem para vertical
    │
    ▼ (N webhooks HeyGen)
HeyGenCallback (NOVO):
  Recebe callback por video_id
  Resolve seg_id via Firestore
  Salva video_url para o seg_id
  Quando TODOS os N seg_ids tiverem video_url → publica AvatarCompletedMsg
    │
    ▼
AvatarCompletedMsg (NOVO):
  horizontal_video_paths: ["gs://.../yt-01.mp4", "gs://.../yt-03.mp4", ...]
  vertical_video_paths:   ["gs://.../reel-01.mp4", ...]
  segment_ids:            ["yt-01", "yt-03", ...]
    │
    ▼
VideoEditorJob (NOVO):
  Para cada segmento com script != "":
    usar horizontal_video_paths[i] como clipe de avatar para esse segmento
  Para segmentos com script == "":
    usar slide HTML (Playwright) — sem mudança
  Concatenar na ordem do manifesto → final_horizontal.mp4
```
