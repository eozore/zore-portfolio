#!/usr/bin/env bash
#
# scripts/deploy.sh — Deploy da plataforma éozoré.
#
# Existe porque o deploy nunca foi um comando só, e a diferença entre os dois
# builds custou caro: o trigger da main roda APENAS o cloudbuild.yaml
# (cmo-agent + frontend). As mudanças em agents/pipeline/** vivem no
# cloudbuild-pipeline.yaml, e por muito tempo nenhum trigger as cobria — toda
# correção da pipeline só chegava em produção se alguém lembrasse do comando
# manual. Foi assim que produção divergiu da main.
#
# Uso:
#   ./scripts/deploy.sh              # tudo: pipeline e depois web
#   ./scripts/deploy.sh pipeline     # só os Cloud Run Jobs
#   ./scripts/deploy.sh web          # só cmo-agent + frontend
#   ./scripts/deploy.sh --check      # não deploya: mostra o que está no ar
#
# A ORDEM importa. A pipeline vai primeiro: se o frontend novo subir antes dos
# jobs, aprovar um vídeo dispara a produção pelo caminho antigo.

set -euo pipefail

PROJECT="${GCP_PROJECT:-vazfy-417019}"
REGION="${GCP_REGION:-us-central1}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$RAIZ"

azul()    { printf '\033[1;34m%s\033[0m\n' "$*"; }
verde()   { printf '\033[1;32m%s\033[0m\n' "$*"; }
amarelo() { printf '\033[1;33m%s\033[0m\n' "$*"; }
vermelho(){ printf '\033[1;31m%s\033[0m\n' "$*" >&2; }

# ── Verificações que evitam um build queimado ────────────────────────────────

pre_voo() {
  azul "▸ Pré-voo"

  local sujo
  sujo="$(git status --porcelain | wc -l | tr -d ' ')"
  if [ "$sujo" != "0" ]; then
    amarelo "  ⚠ $sujo arquivo(s) não commitados — o Cloud Build usa o que está"
    amarelo "    NESTE diretório (builds submit) ou o que está no GitHub (trigger)."
  fi

  azul "  testes python"
  ( cd agents/pipeline  && python3 -m pytest tests -q >/dev/null ) || { vermelho "  ✗ testes da pipeline falharam"; exit 1; }
  ( cd agents/cmo_agent && python3 -m pytest tests -q >/dev/null ) || { vermelho "  ✗ testes do cmo_agent falharam"; exit 1; }

  azul "  build do frontend"
  # O `next build` roda dentro do Cloud Build de qualquer forma; rodar aqui
  # troca 10 minutos de build remoto falhado por 1 minuto local.
  ( cd apps/web && npm run build >/dev/null 2>&1 ) || { vermelho "  ✗ next build falhou"; exit 1; }

  verde "  ✓ pré-voo ok"
}

# ── Deploys ──────────────────────────────────────────────────────────────────

deploy_pipeline() {
  azul "▸ Cloud Run Jobs (tts, avatar, video-editor, vertical-cut, publisher, callbacks)"
  # COMMIT_SHA precisa vir à mão: no envio manual o Cloud Build não o preenche
  # (só o trigger preenche), e as duas configs usam a variável como TAG da
  # imagem. Sem isto o build morre em "invalid image name
  # gcr.io/…/pipeline:" — nome sem tag.
  gcloud builds submit \
    --config=cloudbuild-pipeline.yaml \
    --project="$PROJECT" \
    --region="$REGION" \
    --substitutions="COMMIT_SHA=$(git rev-parse --short HEAD)"
  verde "  ✓ pipeline no ar"
}

deploy_web() {
  azul "▸ cmo-agent + frontend"
  gcloud builds submit \
    --config=cloudbuild.yaml \
    --project="$PROJECT" \
    --region="$REGION" \
    --substitutions="COMMIT_SHA=$(git rev-parse --short HEAD)"
  verde "  ✓ web no ar"
}

# ── Estado atual ─────────────────────────────────────────────────────────────

checar() {
  azul "▸ Revisões no ar"
  gcloud run services list --project="$PROJECT" --region="$REGION" \
    --format='table(SERVICE:label=SERVIÇO,LAST_DEPLOYED_BY:label=POR,LAST_DEPLOYED_AT:label=QUANDO)' 2>/dev/null || true

  azul "▸ Jobs"
  gcloud run jobs list --project="$PROJECT" --region="$REGION" \
    --format='table(JOB,LAST_UPDATED_AT:label=ATUALIZADO)' 2>/dev/null || true

  azul "▸ Últimos builds"
  gcloud builds list --project="$PROJECT" --region="$REGION" --limit=5 \
    --format='table(id.slice(0,8):label=ID,status,createTime.date("%d/%m %H:%M"):label=QUANDO,source.repoSource.branchName:label=BRANCH)' 2>/dev/null || true

  azul "▸ Saúde"
  local cmo
  cmo="$(gcloud run services describe cmo-agent --project="$PROJECT" --region="$REGION" --format='value(status.url)' 2>/dev/null || true)"
  [ -n "$cmo" ] && printf '  cmo-agent  %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$cmo/health")"
  printf '  frontend   %s\n' "$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://eozore.com/admin/studio)"
}

# ── Entrada ──────────────────────────────────────────────────────────────────

case "${1:-tudo}" in
  --check|check)
    checar
    ;;
  pipeline)
    pre_voo && deploy_pipeline
    ;;
  web)
    pre_voo && deploy_web
    ;;
  tudo)
    pre_voo
    deploy_pipeline
    deploy_web
    verde ""
    verde "Deploy completo. Conferindo:"
    checar
    ;;
  *)
    vermelho "uso: $0 [tudo|pipeline|web|--check]"
    exit 1
    ;;
esac
