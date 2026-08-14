# Quality Gates — CI Pipeline

## Gates Atuais

| Gate | Ferramenta | Quando | Status |
|---|---|---|---|
| Testes Nyquist Python | pytest | Antes do push (local) | ✅ 5/5 passando |
| TypeScript type-check | tsc --skipLibCheck | Antes do push (local) | ✅ 0 erros no código da pipeline |
| Import validation | python3 /tmp/check_imports.py | Antes do push | ✅ |
| Docker build | Cloud Build Step 1 | No push para main | Pendente (pós-deploy) |

## Gate de Deploy

Conforme `team.md § Testing Posture`: testes **não bloqueiam CI atualmente** — esta postura será reavaliada quando o volume crescer. O gate atual é:
1. Testes passando localmente antes do commit
2. Docker build bem-sucedido no Cloud Build

## Próximos Gates (Bolt 4 — quando a UI estiver pronta)

- `vitest run` no `apps/web` antes do deploy do web app
- `pytest tests/test_tts_job.py tests/test_avatar_job.py tests/test_heygen_callback.py` no cloudbuild-pipeline.yaml (após Bolt 1 completo com mocks)
