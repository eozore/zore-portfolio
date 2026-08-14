# Stakeholder Map
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

---

## Decisores

| Stakeholder | Papel | Interesse Principal | Critério de Sucesso |
|---|---|---|---|
| **Victor Zore** | CEO, Criador de Conteúdo, Usuário Único | Recuperar tempo de produção sem perder qualidade técnica | Sistema opera sozinho depois da sessão semanal de cocriação |

Victor é simultaneamente o patrocinador, o decisor, o usuário e o operador do sistema. Não há comitê. Decisões são tomadas por ele na cocriação com o CMO Agent e nas gates de aprovação do kanban.

---

## Influenciadores (Plataformas Externas)

Estes stakeholders não têm voz ativa no desenvolvimento mas suas políticas e APIs definem constraints técnicos e de compliance que não podem ser ignorados:

| Plataforma | Tipo de Influência | Risco | Mitigação |
|---|---|---|---|
| **YouTube** | API de upload + políticas de conteúdo IA | Ban de canal por conteúdo 100% gerado por IA | Garantir curadoria humana na aprovação; marcar vídeos como IA-assisted conforme política |
| **Instagram / Meta** | Graph API + políticas de automação | Restrição de conta por publicação automatizada excessiva | Respeitar rate limits; simular comportamento humano nos intervalos de publicação |
| **LinkedIn** | API de posts + políticas de automação | Limitação de API por volume | Usar LinkedIn API oficial; throttling configurável no painel |
| **Threads** | API da Meta (compartilhada com Instagram) | Mesmos riscos do Instagram | Mesma mitigação |
| **HeyGen** | API de geração de avatar | Dependência de fornecedor; mudanças de pricing | Encapsular chamadas em uma camada de abstração; monitorar custos |
| **ElevenLabs** | API de TTS com voz clonada | Dependência de fornecedor; qualidade de voz | Encapsular em camada abstraída; permitir fallback para Google TTS |
| **Google Cloud (GCP)** | Infraestrutura, Pub/Sub, Cloud Run, Secret Manager | Custos de infra | Monitoramento de custos integrado ao dashboard |

---

## Usuários da Audiência Final (indiretos)

Não interagem com o sistema mas são o destinatário de todo o conteúdo produzido. Suas características definem as restrições de qualidade do conteúdo:

| Persona | Descrição | O que esperam do conteúdo éozoré |
|---|---|---|
| **Engenheiro de Dados Sênior** | 5-10 anos de experiência, usa Python/Spark, quer se atualizar em LLMs | Profundidade técnica real; sem simplificações que ignorem a matemática |
| **Cientista de ML em transição para GenAI** | Conhece modelos clássicos, quer entender LLMs e RAG | Ponte entre o que já sabe (gradiente, backprop) e o que está aprendendo (atenção, RLHF) |
| **Tech Lead de IA** | Responsável por decisões arquiteturais de IA na empresa | Conteúdo sobre trade-offs práticos, não teoria pura; casos de uso reais |
| **Estudante de Ciências de Dados** | Graduação ou pós, UFSCar/USP/UNICAMP | Rigor matemático acessível; o "porquê" explicado antes do "como" |

**Implicação para o sistema:** o conteúdo gerado automaticamente precisa respeitar o padrão técnico que essa audiência espera. Conteúdo genérico ou superficial é descartado pela audiência independente de volume de publicação.

---

## Comunicação e Fluxos de Decisão

```
Victor (CEO + Usuário)
    |
    +-- Sessão semanal de cocriação (CMO Agent, CSM Studio)
    |       |
    |       +-- Aprova pacote de conteúdo (gate no kanban)
    |       +-- Aprova peças individuais antes da publicação (gate de publicação)
    |       +-- Configura canais ativos, keys, horários (painel de configuração)
    |
    +-- Monitora kanban de projetos (visibilidade de status em tempo real)
    |
    +-- Aciona fallback manual quando automação falha (operabilidade direta)
```

**Não há aprovação delegada** — Victor é o único aprovador. O sistema não publica nada sem seu `APPROVED` explícito no gate de publicação.

---

## Restrições de Compliance por Stakeholder

| Requisito | Fonte | Implementação |
|---|---|---|
| Divulgação de conteúdo gerado por IA | Políticas YouTube/Meta | Campo obrigatório no metadata de publicação; checklist no gate de aprovação |
| Rate limiting de publicação | APIs das plataformas | Throttler configurável no Publisher Service; alertas quando próximo do limite |
| Segurança de API keys | GCP Security best practices | Todas as keys via GCP Secret Manager; nunca em env vars hardcoded em código deployado |
| Custo máximo por vídeo | Decisão do Victor | Budget tracker integrado ao pipeline; alerta e pausa se estimativa ultrapassar R$100 |
| Conformidade com termos de serviço | Todas as plataformas | Checklist de conformidade por plataforma no painel; documentado e revisável |
