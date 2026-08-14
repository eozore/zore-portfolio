# Incident Runbooks

## Job com erro (tts-job, avatar-job, video-editor-job)
1. Victor vê badge vermelho no kanban
2. Clica 'Re-tentar etapa' → re-dispara o job
3. Se persistir: 'Pular etapa' ou 'Upload manual .mp4'

## HeyGen timeout (> 90 min)
1. Victor vê estágio avatar em erro
2. Opção 1: Re-tentar (HeyGen pode estar lento)
3. Opção 2: Upload manual do vídeo via side panel

## Custo excedeu teto
1. Projeto entra em estado error com mensagem de custo
2. Victor aumenta o teto no painel Pipeline
3. Clica Re-tentar