# Security Requirements — Bolt 0 + Bolt 1

> Referências: [requirements.md](../../inception/requirements-analysis/requirements.md) | [discovered-rules.md](../../inception/practices-discovery/discovered-rules.md)

---

## Controles Obrigatórios (da practices-discovery)

| ID | Controle | Implementação | Unidade |
|---|---|---|---|
| SEC-01 | API keys NUNCA em código ou env vars plaintext | GCP Secret Manager: `get_secret()` em `pubsub_client.py` | Todas |
| SEC-02 | Firestore: acesso apenas via Firebase Admin SDK server-side | `firestore.rules`: `allow read, write: if false` para todas as coleções da pipeline | U-01 |
| SEC-03 | HeyGen callback autenticado via token secreto | `X-HeyGen-Token` header validado contra `heygen-callback-token` do Secret Manager | U-10 |
| SEC-04 | Cloud Run Services `--no-allow-unauthenticated` | `heygen-callback` e `publisher-immediate` não são públicos | U-13 |
| SEC-05 | Service account com permissões mínimas | `pipeline-jobs-sa` com apenas roles listados em U-13 | U-13 |
| SEC-06 | YouTube OAuth refresh token no Secret Manager | `youtube-oauth-refresh-token` criado e validado ✅ | U-04 |
| SEC-07 | Nunca logar valores de secrets | `get_secret()` não loga o retorno; CostTracker não loga custo com dados pessoais | Todas |
| SEC-08 | Pub/Sub mensagens não contêm dados sensíveis | Payloads apenas com IDs e metadados, sem conteúdo ou chaves | U-02 |

## Limites de Acesso por Serviço

| Serviço | Acesso externo | Autenticação |
|---|---|---|
| `heygen-callback` | Somente HeyGen (webhook) | Token secreto no header |
| `publisher-immediate` | Somente Next.js `web` (via OIDC token) | GCP IAM (`roles/run.invoker` para service account do `web`) |
| `tts-job`, `avatar-job`, `video-editor-job`, `publisher-scheduled` | Nenhum (Cloud Run Jobs, sem HTTP) | Disparados via gcloud CLI ou Pub/Sub |
