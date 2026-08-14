#!/usr/bin/env bash
# ==============================================================================
# check-credentials.sh — valida TODAS as credenciais externas da CSM.
#
# Por que existe: tokens OAuth (YouTube, LinkedIn, Threads) expiram sozinhos e
# a pipeline só descobre na hora de publicar — depois de já ter gasto créditos
# de ElevenLabs e HeyGen gerando o vídeo. Rode isto ANTES de aprovar um pacote.
#
#   ./scripts/check-credentials.sh
#
# Nenhum valor de segredo é impresso. Nada é publicado.
# Saída 0 = tudo válido; 1 = alguma credencial precisa ser renovada.
# ==============================================================================
set -uo pipefail

PROJECT="${GCP_PROJECT:-vazfy-417019}"
FAIL=0

green() { printf "  \033[32m✓\033[0m %-14s %s\n" "$1" "$2"; }
red()   { printf "  \033[31m✗\033[0m %-14s %s\n" "$1" "$2"; FAIL=1; }
info()  { printf "\n\033[1m%s\033[0m\n" "$1"; }

sec() { gcloud secrets versions access latest --secret="$1" --project="$PROJECT" 2>/dev/null; }

# ── Vertex AI ─────────────────────────────────────────────────────────────────
info "Geração de conteúdo"
MODEL="${VERTEX_MODEL:-gemini-3.5-flash-lite}"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token 2>/dev/null)" \
  -H "Content-Type: application/json" -d '{"contents":[{"role":"user","parts":[{"text":"ok"}]}]}' \
  "https://aiplatform.googleapis.com/v1/projects/$PROJECT/locations/us-central1/publishers/google/models/$MODEL:generateContent")
[ "$code" = "200" ] && green "Vertex AI" "$MODEL responde" || red "Vertex AI" "HTTP $code em $MODEL"

# ── ElevenLabs ────────────────────────────────────────────────────────────────
info "Produção de vídeo"
EL=$(sec elevenlabs-api-key | tr -d '\n'); VOICE=$(sec elevenlabs-voice-id | tr -d '\n')
# /v1/user e /v1/voices exigem escopos que a chave pode não ter; o que importa
# é a síntese em si, então testamos o endpoint que a pipeline realmente usa.
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://api.elevenlabs.io/v1/text-to-speech/$VOICE" \
  -H "xi-api-key: $EL" -H "Content-Type: application/json" \
  -d '{"text":"ok","model_id":"eleven_multilingual_v2"}')
[ "$code" = "200" ] && green "ElevenLabs" "síntese OK" || red "ElevenLabs" "HTTP $code na síntese"

# ── HeyGen (chave vive no Firestore, não no Secret Manager) ───────────────────
# Lida via REST do Firestore: `gcloud firestore documents describe` não existe
# como subcomando, e silenciosamente devolvia vazio — gerando alarme falso.
HG=$(curl -s -H "Authorization: Bearer $(gcloud auth print-access-token 2>/dev/null)" \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents/agent_configurations/api_keys" \
  | python3 -c "import sys,json;print(json.load(sys.stdin).get('fields',{}).get('HEYGEN_API_KEY',{}).get('stringValue',''))" 2>/dev/null | tr -d '\n')
if [ -n "$HG" ]; then
  q=$(curl -s -H "X-Api-Key: $HG" https://api.heygen.com/v2/user/remaining_quota)
  credits=$(echo "$q" | python3 -c "import sys,json;print(json.load(sys.stdin).get('data',{}).get('remaining_quota','?'))" 2>/dev/null)
  [ "$credits" != "?" ] && [ -n "$credits" ] && green "HeyGen" "$credits créditos" || red "HeyGen" "resposta inesperada"
else
  red "HeyGen" "HEYGEN_API_KEY ausente em agent_configurations/api_keys"
fi

# ── YouTube ───────────────────────────────────────────────────────────────────
info "Publicação"
CID=$(sec youtube-oauth-client-id | tr -d '\n')
CSEC=$(sec youtube-oauth-client-secret | tr -d '\n')
RTOK=$(sec youtube-oauth-refresh-token | tr -d '\n')
AT=$(curl -s -X POST https://oauth2.googleapis.com/token \
  -d "client_id=$CID" -d "client_secret=$CSEC" -d "refresh_token=$RTOK" -d "grant_type=refresh_token" \
  | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -n "$AT" ]; then
  ch=$(curl -s -H "Authorization: Bearer $AT" \
    "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['items'][0]['snippet']['title'] if d.get('items') else '')" 2>/dev/null)
  [ -n "$ch" ] && green "YouTube" "canal: $ch" || red "YouTube" "token ok mas nenhum canal — escopo errado?"
else
  red "YouTube" "refresh token inválido — renove o consentimento OAuth"
fi

# ── LinkedIn ──────────────────────────────────────────────────────────────────
LITOK=$(sec linkedin-tokens | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $LITOK" https://api.linkedin.com/v2/userinfo)
[ "$code" = "200" ] && green "LinkedIn" "token válido" || red "LinkedIn" "HTTP $code — token expirado (validade de 60 dias)"

# ── Meta: Instagram + Threads ─────────────────────────────────────────────────
M=$(sec meta-credentials)
for pair in "instagram:graph.facebook.com/v21.0:instagram_user_id:instagram_token" \
            "threads:graph.threads.net/v1.0:threads_user_id:threads_token"; do
  name="${pair%%:*}"; rest="${pair#*:}"; host="${rest%%:*}"; rest="${rest#*:}"
  uid_k="${rest%%:*}"; tok_k="${rest#*:}"
  uid=$(echo "$M" | python3 -c "import sys,json;print(json.load(sys.stdin).get('$uid_k',''))" 2>/dev/null)
  tok=$(echo "$M" | python3 -c "import sys,json;print(json.load(sys.stdin).get('$tok_k',''))" 2>/dev/null)
  resp=$(curl -s "https://$host/$uid?fields=username&access_token=$tok")
  user=$(echo "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin).get('username',''))" 2>/dev/null)
  [ -n "$user" ] && green "$name" "@$user" \
    || red "$name" "$(echo "$resp" | python3 -c "import sys,json;print(json.load(sys.stdin).get('error',{}).get('message','erro')[:70])" 2>/dev/null)"
done

echo
[ "$FAIL" = "0" ] && echo "Todas as credenciais válidas — seguro aprovar um pacote." \
                  || echo "Renove as credenciais marcadas com ✗ ANTES de aprovar (senão o vídeo é gerado, gasta créditos, e falha só na publicação)."
exit $FAIL
