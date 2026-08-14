# RAID Log
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> RAID = Risks · Assumptions · Issues · Dependencies
> Referências: [feasibility-assessment.md](./feasibility-assessment.md) | [constraint-register.md](./constraint-register.md)

---

## Risks (Riscos)

| ID | Risco | Prob | Impacto | Score | Tratamento | Owner |
|---|---|---|---|---|---|---|
| R01 | **HeyGen altera pricing ou descontinua API v3 sem aviso adequado** | Baixa | Alto | 6 | Encapsular em `AvatarService` com interface abstrata. Testar Synthesia como backup anualmente. | Arquiteto |
| R02 | **ElevenLabs Instant Voice Clone tem qualidade insuficiente para pt-BR** | Média | Médio | 6 | Testar clone antes de desenvolver a pipeline completa. Plano B: ElevenLabs Creator Pro ($99/mês) com Professional Clone. | Victor |
| R03 | **YouTube detecta avatar como conteúdo sintético e penaliza sem aviso prévio** | Média | Alto | 8 | Preencher AI disclosure obrigatório (CC-01). Adicionar no descrição do vídeo marcação "Vídeo criado com IA". Monitorar política do YouTube mensalmente. | Publisher Service |
| R04 | **Meta suspende conta por comportamento anômalo de postagem** | Baixa | Catastrófico | 8 | Apenas Graph API oficial. Rate limits conservadores (COP-03). Simular intervalos humanos entre operações (não postar tudo em batch instantâneo). | Publisher Service |
| R05 | **Playwright/Chromium falha em Cloud Run Jobs por falta de memória** | Média | Alto | 8 | Alocar mínimo 2GB de memória para Video Editor Job. Testar renderização HTML de slides complexos em ambiente container antes de implementar. | Video Editor Job |
| R06 | **Custo por pacote excede R$100 por vídeo longo (>20 min)** | Baixa | Médio | 4 | `CostTrackerService` com gate de custo. Definir duração máxima de vídeo como parâmetro configurável no painel (default: 20 min). | CostTrackerService |
| R07 | **HeyGen rendering timeout para vídeos >30 min** | Baixa | Médio | 4 | Polling com timeout de 90 min. Segmentar vídeos muito longos em partes se necessário (HeyGen processa cada parte separadamente). | Avatar Job |
| R08 | **Tokens OAuth das redes sociais expiram sem renovação automática** | Alta | Médio | 8 | Implementar refresh token automático para Meta e LinkedIn. Alertar Victor via painel quando token está próximo de expirar (< 7 dias). | Config Service |
| R09 | **Pub/Sub message ordering não garantido — jobs executam fora de ordem** | Média | Médio | 6 | Pub/Sub FIFO ordering keys por `project_id`. Cada job verifica pré-condições antes de executar (ex: TTS Job só roda se manifesto aprovado existir no Firestore). | Todos os Jobs |

---

## Assumptions (Premissas)

| ID | Premissa | Risco se Falsa | Validar em |
|---|---|---|---|
| A01 | Victor tem uma conta HeyGen com avatar fotorrealista (Avatar IV) já criado e vinculado à API key | Pipeline de avatar não funciona sem avatar configurado | Feasibility → setup de conta |
| A02 | Victor tem conta ElevenLabs com amostras de voz gravadas para clone | Sem amostras, clone de voz não é possível | Feasibility → setup de conta |
| A03 | O canal do YouTube de Victor está associado ao projeto GCP correto no Google Cloud Console | YouTube Data API v3 autenticará com a conta errada | Setup inicial |
| A04 | Os tokens OAuth do Instagram, Threads, Facebook e LinkedIn são tokens de longa duração (not expired) | Publisher Service falhará na primeira execução | Setup inicial → config-service |
| A05 | O pacote HTML com manifesto v2 continua sendo o formato de saída do CMO Agent após a evolução | O editor de vídeo depende do manifesto — quebra se formato mudar | Requirements Analysis |
| A06 | Victor consegue gravar amostras de voz de alta qualidade (>2 min de áudio limpo) para o clone ElevenLabs | Clone com áudio ruim produz voz sintética de baixa qualidade | Antes de implementar TTS Job |
| A07 | GCP Pub/Sub tem latência adequada para o workflow (mensagens entregues em < 1 min) | Jobs podem ficar presos aguardando mensagens | Não crítico — Pub/Sub tem SLA de latência < 100ms normalmente |
| A08 | O custo do HeyGen API PAYG (pay-as-you-go) para vídeo de 15 min é ≤ $12 | O teto de R$100 pode ser insuficiente | Feasibility → testar uma chamada de API de 1-2 min para extrapolar |

---

## Issues (Questões Abertas)

| ID | Issue | Urgência | Status | Ação |
|---|---|---|---|---|
| I01 | **Preço real HeyGen API PAYG não confirmado** — estimativa baseada em plano Creator | Alta | Aberta | Fazer uma chamada de teste (vídeo de 1 min) antes de commitar à arquitetura. Confirmar no feasibility técnico. |
| I02 | **HeyGen v2 → v3 migration obrigatória** — `heygen/route.ts` usa endpoint v2 que para em out/2026 | Alta | Aberta | Incluir migração v2→v3 no escopo de implementação. Prioridade alta. |
| I03 | **Qual o formato de saída do HeyGen Lipsync API?** — O avatar base precisa ser um vídeo loop ou uma foto? | Média | Aberta | Documentação indica suporte a ambos. Testar com foto do avatar do Victor para confirmar qualidade do lip-sync vs. vídeo loop. |
| I04 | **Integração YouTube OAuth** — service account não funciona; requer OAuth com conta pessoal do Google | Média | Aberta | Victor precisa autorizar o app no Google Cloud Console e o refresh token deve ser armazenado no Secret Manager. |
| I05 | **ElevenLabs Professional vs Instant Clone** — diferença de qualidade para pt-BR não testada | Média | Aberta | Victor precisa gravar amostras e testar antes de decidir o plano. |
| I06 | **Playwright em Cloud Run Jobs** — compatibilidade com Alpine Linux e Chromium headless | Média | Aberta | Testar com um vídeo de 1 slide no ambiente Cloud Run antes de desenvolver o job completo. |

---

## Dependencies (Dependências)

| ID | Dependência | Tipo | Disponível? | Bloqueador? |
|---|---|---|---|---|
| D01 | Conta ElevenLabs com voz do Victor clonada | Externa | A criar | Sim — sem isso TTS Job não funciona |
| D02 | Conta HeyGen com Avatar IV do Victor e API key | Externa | Parcial (API key existe, avatar precisa ser confirmado) | Sim — sem avatar, Lipsync Job não funciona |
| D03 | YouTube OAuth refresh token do canal do Victor | Externa | A criar | Sim para publicação no YouTube |
| D04 | Tokens OAuth LinkedIn, Instagram, Threads, Facebook válidos | Externa | Operacionais (Victor confirmou) | Não bloqueante imediato |
| D05 | GCP Pub/Sub API ativada no projeto `eozore-platform` | Interna | A ativar | Sim para arquitetura de microserviços |
| D06 | Cloud Run Jobs configurado no projeto GCP | Interna | A configurar | Sim para TTS/Avatar/Editor jobs assíncronos |
| D07 | Cloud Scheduler configurado para publicação diária | Interna | A configurar | Não bloqueante imediato (após Publisher Service pronto) |
| D08 | `tool-videoyoutube` refatorado como Cloud Run Job | Interna (código existente) | Parcial (código existe, containerização necessária) | Sim para edição automática |
| D09 | Schema Firestore `content_projects` definido | Interna | A criar | Sim para kanban de projetos |
