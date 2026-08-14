# Requirements Analysis — Questions

## Q1: Qual é o problema principal na ferramenta de vídeo?

A. O pipeline crasheia em algum passo específico (FFmpeg, GCP STT, Gemini)
B. A duplicação de lógica entre `editor_pipeline.py` (hardcoded) e `process_video.py` (genérico) causa confusão e bugs
C. O `server.js` (Express) não funciona corretamente com o pipeline Python
D. Problemas de performance (demora excessiva, timeout)
E. Tudo acima — a arquitetura inteira precisa ser refeita
X. Other (please specify)

[Answer]: X. O pipeline falha com `ModuleNotFoundError: No module named 'vertexai'` no passo 4 (Orquestração Gemini). O erro é de dependência não instalada, mas o problema maior é a fragilidade arquitetural — dependências, paths, e duplicação de lógica.

## Q2: Qual é o escopo das tools afetadas?

A. Apenas `tool-videoyoutube` (editor de vídeo)
B. `tool-videoyoutube` + `tool-cromex` (ambas as tools)
C. Todas as tools + integração com o CMO agent (`agents/cmo_agent/video_editor.py`)
D. Apenas a lógica Python do pipeline de vídeo (não o server Node.js)
X. Other (please specify)

[Answer]: A

## Q3: O que significa "as pastas tool- não deveriam ser apagadas"?

A. Outro agente/processo está apagando essas pastas indevidamente e isso precisa ser impedido
B. O `.gitignore` exclui `tool-*/` e isso confunde — quero versionar essas pastas no git
C. As pastas são apagadas durante o processo de deploy/build e não deveriam
D. É apenas um lembrete de que, ao refatorar, eu NÃO quero que as pastas sejam deletadas — mantenha a estrutura
X. Other (please specify)

[Answer]: D. Apenas um lembrete. As pastas estão no repo e devem ser mantidas.

## Q4: O `editor_pipeline.py` (versão hardcoded com `RAG2.mp4` fixo) ainda é usado?

A. Não — é código legacy que pode ser removido. O `process_video.py` é a versão correta
B. Sim — ambos são usados para propósitos diferentes
C. Não sei — preciso que o refactor identifique o que pode ser removido
X. Other (please specify)

[Answer]: X. É um teste antigo. O processo precisa funcionar para qualquer MP4 e HTML — não é específico de um arquivo.

## Q5: Qual é o resultado desejado do refactor?

A. Um pipeline unificado, limpo, sem duplicação — mantendo a mesma funcionalidade
B. Reestruturar em módulos independentes (STT, alignment, FFmpeg) com interface clara entre eles
C. Migrar tudo para um microserviço com API REST bem definida (preparar para a plataforma educacional)
D. Apenas corrigir os bugs atuais sem mudar a arquitetura
E. Opções B + C (modularizar E preparar como microserviço)
X. Other (please specify)

[Answer]: X. Quero uma API que recebe MP4 + HTML (até 2h de vídeo) e devolve DOIS vídeos: (1) horizontal e (2) vertical. Ambos simples: vídeo do avatar (MP4 falando) com os vídeos de ilustração (slides do HTML) aparecendo no momento correto. O slide deve cobrir totalmente o avatar quando ativo. O conceito é: "uma pessoa falando + ilustrações da fala aparecendo" (alternando entre avatar e ilustração).

## Q6: Existem dependências externas que devem ser mantidas?

A. GCP Speech-to-Text + Gemini 2.5 Flash + FFmpeg — manter todas
B. Posso trocar o GCP STT por outra solução (Whisper local, etc.)
C. Quero manter GCP STT mas trocar o Gemini por outro modelo
D. Liberdade total — pode propor stack diferente se fizer sentido
X. Other (please specify)

[Answer]: X. Liberdade parcial — aberto a novas stacks, mas priorizo GCP.
