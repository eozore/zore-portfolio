# Performance Requirements — Bolt 0 + Bolt 1

> Referências: [requirements.md](../../inception/requirements-analysis/requirements.md) | [functional-design (todas as unidades)](../firestore-schema/functional-design/business-logic-model.md)

---

## NFR-02 (revisado com dados reais do spike)

| Unidade | SLA | Medição | Observação |
|---|---|---|---|
| U-01 `firestore-schema` | Deploy Firestore rules + indexes ≤ 10 min | `firebase deploy` timing | Índice `collection_group` pode levar até 10 min para ficar ativo |
| U-02 `pubsub-infra` | Latência de entrega de mensagem Pub/Sub ≤ 100ms | Cloud Monitoring | SLA do GCP Pub/Sub em projetos pessoais |
| U-07 `pipeline-shared-lib` | `with_retry` total de tempo (3 tentativas + backoff 1+4s) ≤ 25s | Unit test timer | Não inclui o tempo de execução de `fn` |
| U-08 `tts-job` | TTS por segmento ≤ 5s (ElevenLabs Flash v2.5, latência <75ms) | Medido no spike | 237 chars → ~1.2s de latência total |
| U-08 `tts-job` | Processamento total 1h de vídeo (roteiro ~54k chars, ~30 segmentos) ≤ 5 min | Estimativa | 30 × 2s por segmento + GCS upload |
| U-09 `avatar-job` | Concatenação de áudio (pydub, 60 segmentos × 10s) ≤ 30s | Estimativa | pydub em CPU simples |
| U-09 `avatar-job` | Upload áudio para HeyGen Assets ≤ 60s | Depende do tamanho | Arquivo concatenado ~10 MB |
| U-09 `avatar-job` | Criação de 2 jobs Lipsync HeyGen ≤ 10s | API latência | POST /v3/lipsyncs |
| U-09 `avatar-job` | Renderização HeyGen (callback): alerta se > 60 min, falha se > 90 min | NFR-02 da Inception | Timeout do Cloud Run Job = 150 min |
| U-10 `heygen-callback` | Processamento do webhook ≤ 2s | Medição no handler | Download vídeo + GCS upload excluído deste SLA |
| U-10 `heygen-callback` | Download vídeo HeyGen + upload GCS ≤ 120s | Estimativa | Vídeo ~50-200 MB |

## Targets de Cost Efficiency

| Métrica | Target | Fonte |
|---|---|---|
| TTS Flash v2.5 por 1h de vídeo | ≤ R$15 | Medido: $0.00005/char × 54k chars × 5.50 |
| HeyGen Lipsync speed por 1h | ~R$660 | Medido: $0.0335/s × 3600s × 5.50 |
| Overhead de Cloud Run (Bolt 1) | ≤ R$5/mês | GCP pricing para Cold Start jobs |
