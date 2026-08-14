# CI Pipeline — Decisões

## CP1. Testes no CI (cloudbuild-pipeline.yaml)

[Answer]: Testes Nyquist são rodados localmente antes do commit (team.md). O cloudbuild não roda pytest atualmente para manter o build rápido. Será adicionado quando o volume de testes crescer.

## CP2. Separação de pipelines

[Answer]: Confirmado — dois arquivos separados: `cloudbuild.yaml` (web app) e `cloudbuild-pipeline.yaml` (microserviços Python). ADR da practices-discovery.
