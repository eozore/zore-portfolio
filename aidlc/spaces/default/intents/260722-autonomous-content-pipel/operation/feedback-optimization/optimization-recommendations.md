# Optimization Recommendations

## Imediatas (antes do Bolt 2)
1. Criar GCS bucket `vazfy-417019-pipeline-media`
2. Criar service account `pipeline-jobs-sa` com permissões mínimas
3. Executar `setup_jobs.sh` para criar os Cloud Run Jobs
4. Primeiro deploy via `cloudbuild-pipeline.yaml`

## Após Bolt 1 em produção
1. Validar custo real do HeyGen com vídeo de comprimento real
2. Avaliar se `/lipsync_index` Firestore reduz latência do HeyGenCallback
3. Implementar CloudWatch alert para dead-letter queue

## Bolt 2 (próximo)
- VideoEditorJob: Playwright + FFmpeg composição determinística H+V
- Manifesto com `script=''` → slide puro (zero HeyGen)