# Business Logic Model

## BUG3 — Plot rendering
execute_python_plot(code) → run subprocess → save PNG locally → upload to GCS → return public URL

## BUG4 — Search
search_web(query) → POST tavily.com/search → parse results → return formatted string

## BUG5 — Pydantic
LinkedInPost.post_copy (Field alias="copy") → JSON serialization uses "copy" key → no warning

## BUG6 — Validator
_check_article_deterministic(text, pauta) →
  tipo = pauta.get("tipo_artigo", "tecnico")
  if tipo == "tecnico": check python + mermaid + latex
  if tipo == "conceitual": check mermaid + latex (no python)
  if tipo == "estrategico": check latex only

## BUG1 — Slide designer
run_slide_designer(segment, pauta, target) →
  prompt = build_prompt(beat_type, script, anchors, dimensions)
  html = vertex_generate(prompt)
  validate html (has DOCTYPE, has dimensions)
  return html

## BUG2 — Avatar per segment
for seg_path in audio_paths[target]:
  seg_id = basename(seg_path, ".mp3")
  asset_id = upload_to_heygen(seg_path)
  video_id = generate_avatar_video(asset_id, avatar_id, target)
  save to firestore: segment_videos[target][i] = {seg_id, video_id, "pending"}

on_heygen_callback(video_id):
  seg_entry = firestore.find_by_video_id(video_id)
  seg_entry.video_url = download_and_store(video_url)
  if all_segments_completed(project_id):
    publish AvatarCompletedMsg(paths_list)
