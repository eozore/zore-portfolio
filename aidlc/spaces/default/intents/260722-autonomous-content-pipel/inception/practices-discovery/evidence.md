# Practices Discovery — Evidence
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

**Scan Date:** 2026-07-22
**Project Type:** Brownfield (código existente extenso)
**Commit Hash:** 30c4ed8

---

## Pipeline Deploy Agent — Branching & Deployment

**Fontes escaneadas:** `git log --oneline -20`, `git branch -a`, `cloudbuild.yaml`, `agents/cloudbuild-agents.yaml`

**Findings:**
- **Branching:** Trunk-based development confirmado. Branch única `main` no remoto. Nenhuma feature branch ativa ou release branch de longa duração visível. Commits recentes diretamente em `main` com prefixos convencionais (`feat:`, `fix:`, `security:`, `ci:`, `refactor:`, `deploy:`).
- **Commit convention:** Conventional Commits parcialmente aplicado. Prefixos: `feat`, `fix`, `security`, `ci`, `refactor`, `deploy`. Sem `BREAKING CHANGE` observado. Sem enforcer (husky/commitlint) configurado no package.json.
- **Deploy cadence:** Deploy em push para `main` via Cloud Build (`cloudbuild.yaml`). Multi-service: Next.js (`apps/web`) + CMO Agent (Python) + Cromex Pricing Service (Python) deployados em Cloud Run na mesma pipeline. Deploy direto para produção (sem staging intermediário visível no YAML).
- **Ambiente único:** Sem diferenciação dev/staging/prod no `cloudbuild.yaml` atual — única pipeline deploya direto para Cloud Run produção.
- **Container registry:** GCR (`gcr.io/$PROJECT_ID`). Tag dupla: `$COMMIT_SHA` + `latest`.
- **Secrets:** Injetados via `--set-secrets` do Cloud Run apontando para Secret Manager. Padrão correto.

---

## Quality Agent — Testing Posture

**Fontes escaneadas:** `apps/web/vitest.config.ts`, `apps/web/package.json`, `find src/**/*.test.*`

**Findings:**
- **Framework:** Vitest com jsdom. Property-based testing com `fast-check`. `@testing-library/react` configurado.
- **Cobertura:** Sem configuração de coverage floor no `vitest.config.ts` (sem `coverage: { threshold }` visível).
- **Volume de testes atual:** 3 arquivos de teste apenas (`setup.test.ts`, `blockParser.test.ts`, `i18n.test.ts`). Cobertura muito baixa para o tamanho do projeto.
- **CI gate:** Sem `npm test` ou `vitest run` visível no `cloudbuild.yaml` — testes não bloqueiam deploy atualmente.
- **Postura real:** Test-after, esporádico, sem gate no CI. Infra de teste existe (Vitest configurado) mas não está sendo usada sistematicamente.
- **Python side:** Sem framework de teste Python visível em `agents/cmo_agent/`. Sem `pytest`, `requirements-dev.txt`, ou pasta `tests/`.

---

## Developer Agent — Code Style & Architecture

**Fontes escaneadas:** `apps/web/src/` estrutura, `CsmDashboard.tsx`, `agents/cmo_agent/agent.py`, padrões de módulos

**Findings:**
- **TypeScript:** `strict: true` em `tsconfig.json`. Next.js 14 App Router. CSS Modules exclusivo (sem Tailwind no CSM Studio, apesar de `tailwind.config.ts` presente — usado apenas fora do CSM).
- **Python:** FastAPI + Pydantic v2 para os agentes. Imports relativos. Sem tipagem estrita (sem `mypy` ou `pyright` config visível).
- **Naming:** camelCase para TypeScript, snake_case para Python. Named exports predominantes no TS.
- **Camadas:** Next.js usa Route Handlers (`app/api/`) como camada de API. Lógica agêntica em Python separada (`agents/cmo_agent/`). Sem camada de repositório explícita — Firebase Admin chamado diretamente nos Route Handlers.
- **Error handling TS:** Mix de `try/catch` com `NextResponse.json` e throws. Sem padrão `Result<T,E>`.
- **Error handling Python:** Exceptions nativas Python. Sem `Result` monad.
- **Arquitetura CSS:** CSS Modules para escopar estilos. Glassmorphism como padrão visual (`backdrop-filter`, `rgba` translúcidos).

---

## DevSecOps Agent — Security & CI Controls

**Fontes escaneadas:** `.eslintrc.json`, `.gitignore`, `cloudbuild.yaml`, padrões de secret handling

**Findings:**
- **Linting TS:** ESLint com `next/core-web-vitals`. Sem configuração adicional além do preset Next.js. Sem Prettier configurado explicitamente.
- **Linting Python:** Sem `ruff`, `flake8`, ou `black` configurados nos requirements.
- **Secret scanning:** Sem `git-secrets`, `truffleHog`, ou similar configurado no CI.
- **SAST:** Sem SAST tooling (Snyk, CodeQL, Semgrep) configurado.
- **Dependency updates:** Sem Dependabot ou Renovate configurados.
- **Secret management:** Padrão correto — Secret Manager via `--set-secrets` no Cloud Run. `.gitignore` bem configurado para `.env*`, `service-account*.json`, `*-credentials.json`.
- **CI security gate:** Sem step de security scan no `cloudbuild.yaml` atual.
- **Positivo:** `.gitignore` robusto. Sem credenciais hardcoded visíveis no código escaneado.
