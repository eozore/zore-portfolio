# Pipeline de vídeo — arquitetura e estado

**Última revisão:** 16/08/2026, depois da reescrita que alinhou a pipeline ao
fluxo definido pelo dono do canal.

Este documento substitui a revisão anterior, que descrevia correções *dentro*
da arquitetura errada — ela tratava o vídeo vertical como um gêmeo do
horizontal, produzido junto, e as peças curtas como produções independentes.

---

## A REGRA DO PRODUTO

> **Cada segmento é UMA tela cheia: ou o avatar falando, ou a ilustração com a
> voz por cima.** Nunca os dois ao mesmo tempo. Não existe avatar reduzido
> sobreposto ao slide.
>
> **Orçamento de tela: ~20% avatar, ~80% ilustração.** O avatar aparece do
> início ao fim — gancho, duas ou três reentradas de respiro no meio, e o
> fechamento. Nunca só nos primeiros 20 segundos.
>
> **Cada segmento de avatar dura de 12 a 25 segundos.** Não é estética: cada um
> é candidato a virar o corte vertical, e fora dessa faixa não sustenta um Reel
> nem cabe num Short.

Num vídeo de 5 minutos: ~1 minuto de avatar em 3 ou 4 aparições, ~4 minutos de
ilustração. Só os segmentos de avatar consomem crédito de HeyGen.

---

## O FLUXO

```
1. CMO Chat            conversa → pauta fechada
2. Artigo              gerado, editável, publicado no blog
                       (ponto de entrada independente: dá para retomar um
                        artigo antigo e seguir daqui)
3. Roteiro             manifesto v2 com segmentos alternando avatar e
                       ilustração + slides HTML desenhados + plano do corte
                       vertical. Revisado e editável antes de aprovar.
4. Vídeo do YouTube    TTS → HeyGen (só os segmentos de avatar) → composição
                       → upload como PRIVADO
5. Revisão manual      o dono do canal assiste, torna público no Studio
6. Pacote              botão libera o corte vertical: Reel + Short recortados
                       DO MESMO vídeo, sem nova geração de avatar
```

O passo 6 depende do 5 por construção: o corte vertical lê os clipes que o
passo 4 gravou. Sem vídeo longo, não há o que cortar.

---

## COMO O VÍDEO É MONTADO

### Horizontal (`video_editor_job`)

Um clipe de tela cheia por segmento, na ordem do manifesto:

| `kind` | Fonte do clipe | Custo |
|---|---|---|
| `avatar` | vídeo do HeyGen, tela cheia | HeyGen por segundo |
| `slide` | HTML renderizado no Playwright + áudio TTS colado | ~zero |

Todos os clipes são normalizados para o mesmo perfil (1920×1080, 30 fps,
yuv420p, AAC 48 kHz estéreo) antes de concatenar. Clipes mudos ganham faixa de
silêncio — o concat exige o mesmo número de streams em todas as entradas.

Saídas no GCS, por projeto:

```
projects/{id}/final_horizontal.mp4
projects/{id}/clips/{segment_id}.mp4    ← matéria-prima do corte vertical
projects/{id}/timeline.json             ← início/fim de cada segmento
```

Falta de material é **erro nomeado**, não fallback silencioso: se `yt-05` não
tem clipe, o job falha dizendo `yt-05`. A versão anterior pulava o segmento com
um warning e entregava um vídeo incompleto.

### Vertical (`vertical_cut_job`)

Roda sob demanda, depois da aprovação. Para cada item do `vertical_cut`:

- **avatar** → crop central 9:16 do clipe horizontal já gerado.
  Medido: 1920×1080 → janela 606×1080 em x=656 → 1080×1920. Zero HeyGen.
- **ilustração** → slide vertical (HTML próprio, 9:16) com **o mesmo áudio
  TTS** do segmento de origem. Zero ElevenLabs.

`HEYGEN_AVATAR_CROP_X_RATIO` ajusta o enquadramento por preset de avatar
(0.5 = centrado).

---

## O QUE MUDOU, E POR QUÊ

| Antes | Agora |
|---|---|
| `pipeline-submit` mandava a fala concatenada em texto puro; o cmo_agent reparseava Markdown e colapsava 8 segmentos em 1 | manda `draft.manifestV2` + os slides desenhados; `/build-manifest` só serializa e sobe |
| nada checava as contagens antes de gastar crédito | `validate_manifest` recusa manifesto colapsado, sem ilustração, sem apresentador ou com avatar acima de 40% |
| HeyGen gerava horizontal **e** vertical da mesma fala | só horizontal |
| ElevenLabs sintetizava a mesma fala duas vezes, uma por orientação | uma vez |
| o callback só liberava a edição com os dois formatos prontos | um formato só; falha de segmento reavalia o portão em vez de retornar |
| gate de custo estimava 5s por segmento | usa a duração real vinda do manifesto |
| cada Reel/Short era um `content_project` novo, com roteiro, voz, avatar e edição próprios | um recorte do vídeo longo |
| `channels_approved` vazio = publica em tudo | vazio = não publica nada |
| vídeo subia como `unlisted` | sobe como `private` |
| `_compose_timeline_v2` sobrepunha o avatar a 0.28 no canto do slide | removido |

### Bugs que teriam aparecido no primeiro vídeo com ilustração

Nenhum foi exercitado antes porque toda produção teve um clipe só:

- o compositor chamava `goToSlide(id)`, que não existe no deck, e caía em
  `goTo(id)` esperando índice — `TypeError` lançado de dentro do próprio catch,
  matando o job no primeiro slide;
- `goTo` escrevia em `current` antes de validar, então uma chamada ruim
  quebrava o deck em definitivo e o resto da gravação saía preto;
- `toggleHud` também não existia: o contador "4 / 13" e a barra laranja
  ficariam queimados em todos os slides;
- o concat usava `-c copy` misturando MP4 do HeyGen com WebM convertido do
  Playwright, com e sem faixa de áudio;
- os jump cuts removiam todo silêncio acima de 0,8s — uma cartela sem locução
  desapareceria inteira. Agora só as bordas de cada clipe são aparadas;
- o deck fixava `width:1920px` no `body`, então o slide vertical era diagramado
  em caixa horizontal dentro de um viewport 9:16.

---

## VERIFICADO

Contra os artefatos reais do ciclo de 16/08:

- **Gate**: o manifesto aprovado (8 segmentos, 7 com ilustração, 12% de avatar)
  passa; o manifesto achatado que foi para produção é recusado com as três
  violações nomeadas.
- **Deck**: `hideHud()` + `goToSeg('yt-05')` ativa o slide e some com o HUD;
  `replay()` reinicia a animação; `goTo('yt-02')` devolve `false` sem corromper
  o deck; `goToSlide` funciona como alias; slide inexistente devolve `false`.
- **Render**: slide horizontal com áudio → 12,00s / 1920×1080; slide vertical
  mudo → 8,00s / 1080×1920 com faixa de silêncio; slide inexistente falha alto.
- **Concat misto** (avatar HeyGen + slide Playwright + avatar HeyGen) → 56,40s
  contra 56,39s esperados, 1920×1080 @30fps, AAC 48 kHz estéreo, decodificação
  completa sem erros. **Este caminho nunca havia rodado.**
- **Crop vertical** sobre um clipe real do HeyGen: enquadramento correto,
  apresentador centrado, sem corte de cabeça.
- 51 testes passando.

Nada disso consumiu crédito de HeyGen ou ElevenLabs.

---

## PENDÊNCIAS

### Antes de produzir

- **Saldo HeyGen — resolvido.** Os "17 créditos" eram a unidade opaca do
  `/v2/user/remaining_quota`, que a HeyGen **remove em 2026-10-31**. O job
  agora lê `GET /v3/users/me`, que declara `billing_type` e devolve
  `wallet.remaining_balance` **em dólares** — a mesma grandeza que a
  plataforma mostra. Os dois pools continuam independentes: crédito de
  assinatura não paga chamada de API, e o job trata `subscription` como saldo
  zero em vez de liberar uma produção que a HeyGen recusaria.
  A recusa por crédito acontece antes de o HeyGen registrar o `callback_id` —
  ou seja, **sem webhook nenhum**.
- **Tarifa — corrigida.** `0.0335/s` = US$2,01/min era a tarifa de *video
  translation*, não a de avatar. Agora há tabela por motor
  (`USD_POR_MINUTO_POR_MOTOR`): US$1/min no `avatar_iii`, US$4/min no
  `avatar_iv`. O `avatar_v` não tem preço publicado, então o job **mede o
  real** pela variação do saldo antes/depois e loga o desvio contra a
  estimativa.
- **Saldo é o limitante hoje.** Com `avatar_v` a US$4/min, ~60s de avatar
  custam ~US$4 por vídeo. Uma carteira de US$10 dá dois vídeos e meio.

### Do produto

- **Carrossel, stories e copies ainda derivam do artigo**, não das ilustrações
  do vídeo. O corte vertical já vem do vídeo; essas peças não. Fechar isso é
  reescrever o `distribution_agent` para partir do manifesto e dos slides.
- **Nenhum artigo saiu com gráfico.** A pipeline só suporta bloco
  ` ```python-plot ` → matplotlib → **PNG estático**; gráfico interativo
  (Plotly) não existe em lugar nenhum do código. E no artigo do último ciclo o
  modelo não emitiu nem o bloco estático — 0 gráficos, 1 diagrama Mermaid.
- **Publicar artigo dispara o roteiro automaticamente.** Escrever um artigo sem
  gerar conteúdo derivado depende de mudar esse encadeamento.
- **4 vídeos indevidos no canal** (`VUlO-lVL6XA`, `sR91P5F06TM`, `I-w-gHMC6tY`,
  `CHB0IgOzbKY`), todos `unlisted`. A exclusão via API falhou por falta de
  escopo — precisa de `youtube.force-ssl` em `scripts/renew_token.py` e novo
  consentimento, ou remoção manual pelo Studio.
- **Dessincronia voz/movimento no avatar — diagnosticada, falta medir.**
  A hipótese antiga (`voice.type: "audio"` sincroniza pior que o TTS nativo)
  estava **errada como explicação**: o dono do canal também sobe áudio quando
  testa na plataforma web, e lá o resultado é bom. Mesma entrada, resultado
  diferente ⇒ a causa não é o modo de entrada.

  A causa é o **motor de renderização**. O `/v2/video/generate` resolve para
  `avatar_iii`; o v3 tem `avatar_iv` como padrão, e `avatar_v` usa animação
  por referência cruzada, analisando avatar e áudio juntos. O job migrou para
  `POST /v3/videos` com `engine.type` configurável (`HEYGEN_ENGINE`, padrão
  `avatar_v`), checando `supported_api_engines` do look antes de gastar.

  Dois agravantes do lado do áudio também foram corrigidos: o TTS usava
  `eleven_flash_v2_5` (modelo de latência ultrabaixa, inútil num pipeline
  batch) e entregava MP3 128 kbps — um codec com perda antes de o HeyGen
  extrair fonema. Agora é `eleven_multilingual_v2` em PCM/WAV, com fallback
  para 24 kHz e MP3 se o plano da ElevenLabs não liberar PCM a 44,1 kHz.

  **Falta a medida:** um segmento curto nas três configurações para confirmar
  o ganho e o custo real do `avatar_v`.

---

## PRIMEIRO CICLO DEPOIS DA MUDANÇA

1. Gerar o pacote de um tema novo e conferir na revisão: 10 a 18 segmentos,
   avatar entre 15% e 25%, avatar no primeiro e no último segmento.
2. Aprovar. Acompanhar TTS → HeyGen → edição. Custo esperado de avatar: ~60s.
3. Assistir ao vídeo privado no YouTube: os cortes entre avatar e ilustração
   caem em fronteira de frase? O áudio atravessa as emendas sem salto?
4. Tornar público.
5. Clicar em "Gerar pacote de conteúdos" e conferir o enquadramento do crop
   vertical. Se o avatar estiver descentrado, ajustar
   `HEYGEN_AVATAR_CROP_X_RATIO` — não custa crédito.
