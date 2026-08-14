#!/usr/bin/env bash
# ============================================================
# test-local.sh — Testa o sistema de conteúdo localmente
# sem precisar de deploy.
#
# Uso:
#   ./scripts/test-local.sh           # roda todos os testes
#   ./scripts/test-local.sh syntax    # só sintaxe Python + TS
#   ./scripts/test-local.sh cmo       # sobe cmo-agent local e testa
#   ./scripts/test-local.sh publish   # testa o fluxo de publicação
# ============================================================
set -e
BOLD="\033[1m"; GREEN="\033[32m"; RED="\033[31m"; YELLOW="\033[33m"; RESET="\033[0m"

ok()   { echo -e "${GREEN}✓${RESET} $1"; }
fail() { echo -e "${RED}✗${RESET} $1"; }
info() { echo -e "${YELLOW}→${RESET} $1"; }
sep()  { echo -e "\n${BOLD}── $1 ──────────────────────────────────${RESET}"; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-all}"

# ── 1. SINTAXE PYTHON ────────────────────────────────────────────────────────
run_python_syntax() {
  sep "Python syntax (ast.parse)"
  python3 -c "
import ast, sys, pathlib
files = list(pathlib.Path('agents').rglob('*.py'))
files = [f for f in files if '__pycache__' not in str(f)]
errs = []
for f in sorted(files):
    try:
        ast.parse(f.read_text())
    except SyntaxError as e:
        errs.append((str(f), str(e)))
        print(f'  ✗  {f}: {e}')
if not errs:
    print(f'  ✓  {len(files)} arquivos Python OK')
else:
    sys.exit(1)
" || { fail "Python syntax errors found"; exit 1; }
}

# ── 2. TYPESCRIPT ────────────────────────────────────────────────────────────
run_typescript() {
  sep "TypeScript (tsc --noEmit)"
  cd "$ROOT/apps/web"
  # Ignora erros em node_modules (dependências externas com tipos incompatíveis)
  if npx tsc --noEmit 2>&1 | grep "error TS" | grep -v "node_modules" | grep -q "error TS"; then
    npx tsc --noEmit 2>&1 | grep "error TS" | grep -v "node_modules" | head -10
    fail "TypeScript errors found (in project files)"
    cd "$ROOT"; exit 1
  fi
  ok "TypeScript OK"
  cd "$ROOT"
}

# ── 3. TESTE DO CMO-AGENT LOCAL ──────────────────────────────────────────────
run_cmo_local() {
  sep "cmo-agent — teste local"
  CMO_PID=""

  # Verificar dependências
  info "Verificando dependências Python..."
  cd "$ROOT/agents/cmo_agent"
  if ! python3 -c "import fastapi, pydantic, google.antigravity" 2>/dev/null; then
    info "Instalando dependências (pip install -r requirements.txt)..."
    pip install -r requirements.txt -q
  fi

  # Subir o cmo-agent em background
  info "Subindo cmo-agent na porta 8090..."
  IS_LOCAL=true python3 agent.py &
  CMO_PID=$!
  cd "$ROOT"

  # Aguardar health
  for i in $(seq 1 15); do
    sleep 1
    if curl -s http://localhost:8090/health > /dev/null 2>&1; then
      ok "cmo-agent rodando (PID $CMO_PID)"
      break
    fi
    if [ $i -eq 15 ]; then
      fail "cmo-agent não subiu em 15s"
      kill $CMO_PID 2>/dev/null; exit 1
    fi
  done

  # Health check
  HEALTH=$(curl -s http://localhost:8090/health)
  if echo "$HEALTH" | grep -q '"status":"ok"'; then
    ok "Health: $HEALTH"
  else
    fail "Health retornou: $HEALTH"
    kill $CMO_PID 2>/dev/null; exit 1
  fi

  # Teste do endpoint /package (smoke test)
  sep "cmo-agent /package smoke test"
  info "Chamando /package com pauta mínima..."
  RESP=$(curl -s -X POST http://localhost:8090/package \
    -H "Content-Type: application/json" \
    -d '{
      "pauta": {
        "titulo": "LoRA Fine-Tuning",
        "subtitulo": "teste local",
        "tese": "A",
        "publico": "lideres",
        "objetivo_aprendizado": "entender lora",
        "hardskills": ["lora"],
        "duracao_alvo": "5 min",
        "serie": "ia",
        "tipo_artigo": "tecnico"
      },
      "articleContent": "## Intro\n\n$W = AB$\n\n```python\nA = 1\n```\n\n```mermaid\ngraph LR\nA-->B\n```",
      "category": "ml",
      "language": "pt-BR"
    }' \
    --max-time 120 2>/dev/null)

  if echo "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
keys = list(d.keys())
errors = d.get('partialErrors', [])
mh_len = len(d.get('manifestHtml', ''))
segs = len(d.get('manifest', {}).get('youtube', {}).get('segments', []))
slide_sections = d.get('manifestHtml', '').count('<section')
slide_ids = d.get('manifestHtml', '').count('fd1')
print(f'  Keys: {keys}')
print(f'  partialErrors: {errors}')
print(f'  manifestHtml: {mh_len} chars')
print(f'  segments: {segs}')
print(f'  slide sections: {slide_sections}')
print(f'  fd1 elements: {slide_ids}')
# Verificar que slides têm HTML real (não só placeholder)
import re
placeholders = re.findall(r'<div class=\"slide-id\">', d.get('manifestHtml', ''))
print(f'  placeholder slides: {len(placeholders)}')
if len(placeholders) == slide_sections:
    print('  ⚠ TODOS os slides são placeholders — slide_designer não funcionou')
    sys.exit(1)
if errors:
    print(f'  ⚠ partialErrors: {errors}')
" 2>&1; then
    ok "/package retornou dados válidos"
  else
    fail "/package falhou"
    kill $CMO_PID 2>/dev/null; exit 1
  fi

  # Parar o agente
  kill $CMO_PID 2>/dev/null
  ok "cmo-agent parado"
}

# ── 4. TESTE DO FLUXO DE PUBLICAÇÃO ─────────────────────────────────────────
run_publish_test() {
  sep "approve-package — validação do novo fluxo"
  info "Verificando que approve-package NÃO publica blog (já publicado antes)..."
  python3 << 'PYEOF'
import sys

# Lê o arquivo route.ts e verifica que NÃO tem lógica de publicar blog
with open('apps/web/src/app/api/csm/approve-package/route.ts') as f:
    content = f.read()

checks = {
    'sem publishBlog function': 'async function publishBlog' not in content,
    'sem blog em ApproveResult': "'blog'" not in content and '"blog"' not in content,
    'texto social presente': 'enqueueText' in content,
    'video pipeline presente': 'triggerVideoPipeline' in content,
    'article removido do request': 'article?' not in content,
}

all_ok = True
for name, result in checks.items():
    if result:
        print(f'  ✓  {name}')
    else:
        print(f'  ✗  {name} — FALHOU')
        all_ok = False

if not all_ok:
    sys.exit(1)
PYEOF
  ok "approve-package novo fluxo OK"

  sep "CsmDashboard — ordem das tabs"
  info "Verificando ordem: Idea → Generate → Publish → Package..."
  python3 << 'PYEOF'
import sys

with open('apps/web/src/components/csm/CsmDashboard.tsx') as f:
    content = f.read()

# Encontra a definição de TABS e verifica a ordem
import re
tabs_match = re.search(r"const TABS.*?\[([^\]]+)\]", content, re.DOTALL)
if not tabs_match:
    print('  ✗  TABS não encontrado')
    sys.exit(1)

tabs_content = tabs_match.group(1)
# Extrai os IDs das tabs na ordem
ids = re.findall(r"id:\s*'(\w+)'", tabs_content)

expected_order = ['idea', 'article', 'review', 'tracking']
# Aceita também o formato antigo com MAIN_TABS
tabs_match_main = re.search(r"const MAIN_TABS.*?\[([^\]]+)\]", content, re.DOTALL)
if tabs_match_main:
    ids_main = re.findall(r"id:\s*'(\w+)'", tabs_match_main.group(1))
    if ids_main[:4] == expected_order:
        print(f'  ✓  Ordem correta: {" → ".join(ids_main[:4])}')
    else:
        print(f'  ✗  Ordem incorreta: {" → ".join(ids_main[:4])}')
        print(f'      Esperado: {" → ".join(expected_order)}')
        sys.exit(1)
elif ids[:7] == ['idea', 'generate', 'publish', 'package', 'youtube', 'repurpose', 'calendar']:
    print(f'  ✓  Ordem correta (legado): {" → ".join(ids[:7])}')
elif ids[:4] == expected_order:
    print(f'  ✓  Ordem correta: {" → ".join(ids[:4])}')
else:
    print(f'  ✗  Ordem não reconhecida: {ids[:7]}')
    sys.exit(1)
PYEOF
  ok "Ordem das tabs OK"

  sep "PackageTab — sem lógica de blog"
  info "Verificando que PackageTab não envia articlePayload..."
  python3 << 'PYEOF'
import sys

with open('apps/web/src/components/csm/tabs/PackageTab.tsx') as f:
    content = f.read()

checks = {
    'sem approveStepBlog': 'approveStepBlog' not in content,
    'sem approveDetailBlog': 'approveDetailBlog' not in content,
    'sem articlePayload': 'articlePayload' not in content,
    'sem article: articlePayload': "article:" not in content or "article:      articlePayload" not in content,
}

all_ok = True
for name, result in checks.items():
    if result:
        print(f'  ✓  {name}')
    else:
        print(f'  ✗  {name} — FALHOU')
        all_ok = False

if not all_ok:
    sys.exit(1)
PYEOF
  ok "PackageTab sem lógica de blog OK"
}

# ── 5. CHECAGEM DE CSS SCOPE DOS SLIDES ──────────────────────────────────────
run_slide_css_check() {
  sep "manifest_builder — CSS scope check"
  python3 << 'PYEOF'
with open('agents/cmo_agent/manifest_builder.py') as f:
    content = f.read()
checks = {
    'escopo por #sid':       'scoped_selectors' in content,
    'remove html,body':      'html\\s*,\\s*body' in content or 'html,body' in content,
    'remove .slide rules':   '.slide' in content and 'Remover regras de .slide' in content,
    'remove @keyframes dup': 'shared_keyframes_added' in content,
}
import sys; all_ok = True
for name, result in checks.items():
    sym = '✓' if result else '✗'
    print(f'  {sym}  {name}')
    if not result: all_ok = False
if not all_ok:
    sys.exit(1)
PYEOF
  ok "manifest_builder CSS scope OK"
}

# ── EXECUÇÃO ─────────────────────────────────────────────────────────────────
cd "$ROOT"

case "$MODE" in
  syntax)
    run_python_syntax
    run_typescript
    ;;
  cmo)
    run_python_syntax
    run_cmo_local
    ;;
  publish)
    run_typescript
    run_publish_test
    run_slide_css_check
    ;;
  all|*)
    run_python_syntax
    run_typescript
    run_publish_test
    run_slide_css_check
    echo ""
    echo -e "${GREEN}${BOLD}Todos os testes estáticos passaram.${RESET}"
    echo -e "${YELLOW}Para testar o cmo-agent local: ./scripts/test-local.sh cmo${RESET}"
    echo -e "${YELLOW}Para testar o frontend local: cd apps/web && npm run dev${RESET}"
    ;;
esac

echo ""
ok "DONE"
