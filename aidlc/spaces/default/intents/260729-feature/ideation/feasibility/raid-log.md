# RAID Log

## Risks
| ID | Descrição | Prob | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | slide_designer_agent gera HTML malformado (tags não fechadas, CSS inválido) que Playwright não consegue renderizar | Médio | Alto | Validar HTML gerado com BeautifulSoup antes de inserir no manifesto; fallback para slide placeholder se inválido |
| R2 | Tavily API muda endpoint/auth antes do deploy | Baixo | Médio | Abstração em `search_web()` facilita troca; manter DuckDuckGo como fallback comentado |
| R3 | Deploy coordenado BUG2 falha para um dos serviços — estado inconsistente em produção | Baixo | Alto | Testar localmente com docker-compose antes; cloudbuild.yaml roda builds em sequência |
| R4 | HeyGen API rejeita N chamadas rápidas por rate limiting (BUG2) | Baixo | Médio | Adicionar delay de 1s entre chamadas por segmento; retry com backoff já existente |

## Assumptions
| ID | Descrição |
|---|---|
| A1 | `TtsCompletedMsg.audio_paths` já é dict com listas individuais por segmento (confirmado no tts_job/job.py) |
| A2 | Tavily API plano gratuito tem cotas suficientes para o volume de uso do CMO Agent |
| A3 | O Playwright no video_editor_job consegue renderizar HTML com Google Fonts CDN (requer internet no Cloud Run Job) |
| A4 | Victor tem permissão para criar segredos no Secret Manager do projeto vazfy-417019 |

## Issues
| ID | Descrição | Status |
|---|---|---|
| I1 | `tool-videoyoutube/pacote-finetuning-v2.html` (referência visual para BUG1) precisa ser lido antes de implementar slide_designer_agent | Aberto — será lido na fase de code-generation |

## Dependencies
| ID | Descrição | Bloqueante para |
|---|---|---|
| D1 | Criar conta Tavily e obter API key | BUG4 deploy |
| D2 | BUG5 deve estar deployado antes de BUG6 (evitar warnings nos logs durante desenvolvimento) | BUG6 |
| D3 | BUG1 deve estar funcionando localmente antes de iniciar BUG2 | BUG2 |
