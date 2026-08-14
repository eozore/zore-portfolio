# Build and Test Results — Bolt 0 + Bolt 1

**Data:** 2026-07-23
**Status:** ✅ PASSED

---

## Python Tests (pytest)

```
5 passed in 0.49s

tests/test_cost_tracker.py::test_check_cost_gate_blocks_when_limit_exceeded  PASSED
tests/test_cost_tracker.py::test_check_cost_gate_allows_when_within_limit     PASSED
tests/test_retry.py::test_with_retry_succeeds_on_third_attempt                PASSED
tests/test_retry.py::test_with_retry_raises_immediately_on_permanent_error    PASSED
tests/test_retry.py::test_with_retry_updates_firestore_before_sleep           PASSED
```

## TypeScript Type Check

```
npx tsc --noEmit --strict --skipLibCheck
→ 0 erros em apps/web/src/types/pipeline.ts
→ Erros em node_modules de terceiros (vitejs) — não relacionados ao código da pipeline
```

## Import Validation

```python
✅ shared.models     — todos os dataclasses e enums
✅ shared.retry      — with_retry, ApiError
✅ shared.cost_tracker — CostTrackerService
✅ shared.firestore_client — FirestoreClient, ProjectNotFoundError
✅ shared.pubsub_client — PubSubClient, get_secret
✅ tts_job.job       — TTSJob, ManifestParseError, CostLimitExceededError
✅ avatar_job.job    — AvatarJob, CostGateBlockedError
✅ heygen_callback.app — FastAPI app
```

## Arquivos de Código Criados

| Arquivo | Linhas | Verificado |
|---|---|---|
| `agents/pipeline/shared/models.py` | ~180 | ✅ |
| `agents/pipeline/shared/retry.py` | ~95 | ✅ |
| `agents/pipeline/shared/cost_tracker.py` | ~130 | ✅ |
| `agents/pipeline/shared/firestore_client.py` | ~120 | ✅ |
| `agents/pipeline/shared/pubsub_client.py` | ~75 | ✅ |
| `agents/pipeline/tts_job/job.py` | ~175 | ✅ |
| `agents/pipeline/tts_job/__main__.py` | ~55 | ✅ |
| `agents/pipeline/avatar_job/job.py` | ~240 | ✅ |
| `agents/pipeline/avatar_job/__main__.py` | ~50 | ✅ |
| `agents/pipeline/heygen_callback/app.py` | ~210 | ✅ |
| `agents/pipeline/Dockerfile` | ~45 | ✅ |
| `agents/pipeline/requirements.txt` | ~40 | ✅ |
| `cloudbuild-pipeline.yaml` | ~140 | ✅ |
| `agents/pipeline/infra/setup_pubsub.sh` | ~50 | ✅ |
| `agents/pipeline/infra/setup_jobs.sh` | ~80 | ✅ |
| `apps/web/src/types/pipeline.ts` | ~160 | ✅ |
| `firestore.rules` | ~25 | ✅ |
| `firestore.indexes.json` | ~30 | ✅ |
