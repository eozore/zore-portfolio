# Business Rules — U-01: firestore-schema

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## Regras de Segmento (Manifesto)

| Regra | Condição | Consequência |
|---|---|---|
| BR-01 | `segment.script == ""` | TTSJob ignora o segmento; AvatarJob ignora; VideoEditorJob renderiza via Playwright pelo tempo `min_duration_s` |
| BR-02 | `segment.script != ""` | TTSJob gera MP3; AvatarJob inclui no áudio concatenado para HeyGen |
| BR-03 | `segment.script != "" AND segment.slide != null` | Avatar fala; slide aparece como overlay no mesmo clipe |
| BR-04 | `segment.script == "" AND segment.slide == null` | **Inválido** — todo segmento deve ter pelo menos um dos dois |
| BR-05 | `segment.min_duration_s` obrigatório quando `script == ""` | É a única fonte de duração do clipe de slide puro |

## Regras de Status do Projeto

| Regra | Transição | Gatilho |
|---|---|---|
| BR-06 | `creating → awaiting_approval` | CMO Agent gera o pacote HTML e cria o doc no Firestore |
| BR-07 | `awaiting_approval → generating_media` | Victor clica "Aprovar" e custo estimado ≤ cost_limit |
| BR-08 | `awaiting_approval → awaiting_approval` (bloqueado) | Custo estimado > cost_limit — gate recusado |
| BR-09 | `generating_media → awaiting_publication` | Todos os stages (tts, avatar, editor) com `status: completed` |
| BR-10 | `generating_media → error` | Qualquer stage com `status: error` após 3 retries |
| BR-11 | `awaiting_publication → publishing` | Victor aprova publicação (gate 2) |
| BR-12 | `publishing → published` | Publisher registra resultado em pelo menos 1 canal |
| BR-13 | `* → error` | CostTrackerService detecta que custo acumulado + próxima etapa > cost_limit |

## Regras de Stage

| Regra | Detalhe |
|---|---|
| BR-14 | `retry_count` incrementa antes de cada tentativa automática (1, 2, 3) |
| BR-15 | Quando `retry_count == max_retries` e ainda falha: `status = error` |
| BR-16 | HTTP 4xx (exceto 429) → `error_type = "permanent"`, sem retry |
| BR-17 | HTTP 429/503/timeout → `error_type = "transient"`, retry com backoff |
| BR-18 | `status = "retrying"` enquanto retry automático em andamento — CTAs manuais não aparecem |
| BR-19 | `status = "error"` somente após esgotar retries — CTAs manuais aparecem |

## Regras de Custo

| Regra | Detalhe |
|---|---|
| BR-20 | `cost_breakdown.total_real` = soma de tts + heygen + gemini + gcp (em BRL) |
| BR-21 | Conversão USD→BRL usa `pipeline_config.exchange_rate_usd_brl` (não hardcoded) |
| BR-22 | Alert quando `total_real >= cost_limit * alert_threshold / 100` |
| BR-23 | Gate bloqueado quando `total_real + estimated_next > cost_limit` |
| BR-24 | Custo do Lipsync só registrado em `heygen` quando `avatar_completed` callback recebido |

## Regras de Publicação

| Regra | Detalhe |
|---|---|
| BR-25 | Publisher verifica `status == "awaiting_publication"` antes de qualquer ação |
| BR-26 | Falha em um canal não bloqueia os outros (isolamento garantido) |
| BR-27 | `publications.blog.status = "skipped_duplicate"` quando slug já existe na coleção `articles` |
| BR-28 | `publications.{channel}.status = "throttled"` quando canal atingiu `max_per_day` |
| BR-29 | YouTube upload sempre inclui `selfDeclaredAiGeneratedContent: true` (obrigatório) |
| BR-30 | Projeto permanece em `awaiting_publication` se canais throttled existem — re-tentado no próximo disparo do Scheduler |

## Regras de Lipsync (HeyGen Callback)

| Regra | Detalhe |
|---|---|
| BR-31 | `stages.avatar.lipsync_jobs.horizontal` e `.vertical` são independentes |
| BR-32 | `avatar_completed` publicado no Pub/Sub **somente** quando ambos horizontal E vertical estão `completed` |
| BR-33 | Se um dos dois falha: `stages.avatar.status = "error"` imediatamente |
