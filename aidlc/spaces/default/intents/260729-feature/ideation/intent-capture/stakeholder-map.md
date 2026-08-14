# Stakeholder Map

## Decision Makers
| Stakeholder | Papel | Interesse Principal |
|---|---|---|
| Victor Zore | Fundador / Único usuário / Desenvolvedor | Pipeline de vídeo funcionando ponta a ponta para criar conteúdo técnico publicável |

## Influencers (sistemas externos)
| Sistema | Papel | Impacto |
|---|---|---|
| HeyGen API | Geração de avatar vídeo | BUG2 depende da HeyGen aceitar N chamadas individuais por segmento em vez de 1 chamada concatenada |
| Tavily API | Busca web para o CMO Agent | BUG4 requer chave de API nova e variável no Secret Manager |
| Google Cloud Run | Hospedagem dos 3 serviços | BUG2 requer deploy coordenado de cmo-agent + heygen-callback + video-editor-job |
| Pub/Sub (GCP) | Barramento de mensagens entre jobs | BUG2 muda schema de AvatarCompletedMsg — consumers devem estar na nova versão antes do producer |

## Communication Requirements
- Todas as mudanças são locais ao repositório `/Users/victorzore/Desktop/zore-portfolio`
- Deploy via `gcloud builds submit --config=cloudbuild.yaml` após aprovação dos artefatos
- Nenhuma aprovação de terceiros necessária
