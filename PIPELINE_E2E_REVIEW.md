# Revisão E2E da pipeline de vídeo — o que precisa ser corrigido

**Contexto:** primeiro ciclo de produção real da CSM (16/08/2026). O ciclo
chegou até o fim, mas o resultado foi errado o suficiente para exigir uma
revisão estrutural antes de gastar mais crédito.

**Restrição ativa:** não criar nada em HeyGen nem em ElevenLabs até que os
itens P0 deste documento estejam corrigidos e validados. Saldo da carteira
HeyGen em 16/08: **US$ 0,28**.

---

## REGRA FIXA DO PRODUTO

> **Todo vídeo DEVE ser um misto de avatar + ilustração.**
>
> Nunca um vídeo inteiro de avatar falando. Nunca só slides sem apresentador.
> O avatar aparece nos momentos de conexão (hook, transições, fechamento) e a
> ilustração carrega o conteúdo técnico (teoria, código, dados, comparativos).

Esta regra é a razão de existir do `slide_designer_agent`, do campo `slide` no
manifesto e do modo `slide-full` do compositor. Hoje ela é violada 100% das
vezes: **o vídeo produzido foi 163 segundos de avatar puro, com zero
ilustração.** A causa está no P0-1 abaixo.

Consequências de violar a regra, nesta ordem de gravidade:
1. O conteúdo técnico fica sem apoio visual — o valor didático despenca.
2. O custo explode: avatar é cobrado por segundo, slide é praticamente grátis.
   No vídeo de teste, 163s de avatar custaram US$ 5,47 quando o correto seria
   ~US$ 0,70 (só os segmentos de conexão).

---

## P0 — Bloqueadores. Nada de produção antes disso.

### P0-1. O manifesto v2 é descartado e o vídeo colapsa em 1 segmento de avatar

**Este é o problema do "vídeo completo" e a causa da ausência total de
ilustração.**

O `scriptwriter_agent` produz um manifesto v2 rico, validado em produção:

```
8 segmentos │ 7 com slide │ 17 âncoras de animação
beats: hook → intro → teoria → teoria → codigo → demo → comparativo → resumo
```

Mas `pipeline-submit` **não envia esse manifesto**. Ele envia o roteiro
achatado em texto puro:

```ts
// apps/web/src/app/api/csm/pipeline-submit/route.ts
const manifestRes = await fetch(`${CMO_AGENT_URL}/build-manifest`, {
  body: JSON.stringify({
    script: youtubeScript,   // ← texto plano, sem estrutura
    title: articleTitle,
    project_id: projectId,
  }),
});
```

O `/build-manifest` chama `_parse_markdown_to_scenes()`, que espera Markdown
com marcadores de seção (`## HOOK`, `## TEORIA`). O `youtubeScript` é a
concatenação dos scripts falados — **sem nenhum marcador**. O parser não acha
seções, cai no default `current_section = "INTRO"` e emite **um único
segmento**.

Resultado real (`manifest.html` do projeto de teste):

| Manifesto v2 gerado | O que chegou na pipeline |
|---|---|
| 8 segmentos | **1 segmento** |
| 7 com `slide` | **0 com slide** |
| beats variados | beat único `"INTRO"` |
| 17 âncoras | **0 âncoras** |
| — | `min_duration_s: 178.3` |

Como `slide: null` significa "avatar em tela cheia", o vídeo inteiro virou
avatar. O `slide_designer_agent`, os slides HTML, as âncoras — nada disso
chega ao vídeo.

**Correção:** parar de reconstruir o manifesto a partir de texto. O manifesto
v2 já existe em `draft.manifestV2` (Firestore, sessão). Opções:

- **(a) Preferida** — `pipeline-submit` envia `draft.manifestV2` direto, e
  `/build-manifest` ganha um caminho que recebe o manifesto pronto e só o
  serializa para HTML + faz upload ao GCS. `manifest_builder.py` já tem
  `wrap_scriptwriter_manifest()` fazendo exatamente isso — é o que o
  `package-job` usa para gerar o `manifestHtml` de preview.
- (b) Manter o parse, mas fazer o `scriptwriter` emitir Markdown com
  marcadores. Pior: reintroduz uma serialização/desserialização frágil no
  meio do caminho.

**Verificação obrigatória após corrigir:** o `manifest.html` no GCS precisa ter
`segment_count == 8` e `slide_segments >= 6`. O endpoint `/build-manifest` já
retorna essas contagens — hoje elas voltam `1` e `0`, e ninguém checa.

**Arquivos:** `apps/web/src/app/api/csm/pipeline-submit/route.ts`,
`agents/cmo_agent/agent.py` (`/build-manifest`),
`agents/cmo_agent/manifest_builder.py`.

---

### P0-2. Guarda contra vídeo sem ilustração

Mesmo depois do P0-1, é preciso uma trava que impeça a regra do produto de ser
violada em silêncio de novo.

**Correção:** validar o manifesto antes de disparar a pipeline, e recusar com
erro claro se:

- `segment_count <= 1`
- `slide_segments == 0`
- proporção de duração de avatar > ~40% do total

O lugar natural é `pipeline-submit`, antes de publicar a `PackageApprovedMsg`
— falhar ali custa zero. Falhar depois custa crédito de HeyGen.

Cobrir com teste, na linha do `tests/test_channel_routing.py` já existente.

---

## P1 — Economia de crédito. Alto impacto, risco baixo.

### P1-1. Reels e Shorts devem ser o MESMO vídeo

Hoje cada Reel e cada Short é um `content_project` independente, com TTS +
avatar + edição próprios. Três Reels = três produções completas.

Decisão do dono do canal: **Reels e Shorts compartilham o mesmo arquivo.** São
a mesma peça vertical distribuída em duas plataformas.

**Correção:** um único projeto vertical por peça, publicado em
`instagram_reel` **e** `youtube_short`. O roteamento por canal já existe
(`channels_approved`, corrigido em `c907a2f`) — basta incluir os dois canais no
mesmo projeto em vez de criar projetos separados.

**Economia:** elimina 1 produção inteira por peça curta.

**Arquivo:** `apps/web/src/app/api/csm/pipeline-submit/route.ts` (bloco de
itens de vídeo).

---

### P1-2. Corte vertical a partir do horizontal, sem nova chamada ao HeyGen

Hoje cada peça gera **duas** chamadas ao HeyGen: uma 1920×1080 e outra
1080×1920, com a **mesma fala**. Isso dobra o custo do avatar.

O HeyGen entrega o avatar centralizado no frame — um recorte central produz um
vertical praticamente idêntico ao gerado nativamente.

**Passos:**

1. **`avatar_job`: gerar apenas horizontal.**
   Em `agents/pipeline/avatar_job/job.py`, o laço
   `for target in ("horizontal", "vertical")` passa a processar só
   `horizontal`. O `vertical` deixa de consumir crédito.

2. **`video_editor_job`: derivar o vertical por crop.**
   Onde hoje o vertical usa `v_heygen_paths`, passar a recortar o clipe
   horizontal. FFmpeg, recorte central 9:16 a partir de 1920×1080:

   ```bash
   ffmpeg -i avatar_h.mp4 \
     -vf "crop=608:1080:656:0,scale=1080:1920:flags=lanczos" \
     -c:a copy avatar_v.mp4
   ```

   `crop=608:1080:656:0` = janela 9:16 (608×1080) centrada horizontalmente
   (offset x = (1920−608)/2 = 656). O `scale` leva à resolução final do Reel.
   `-c:a copy` preserva o áudio sem recodificar.

3. **Enquadramento.** Se o avatar não estiver perfeitamente centralizado,
   ajustar o offset `x`. Vale tornar isso configurável por avatar
   (`HEYGEN_AVATAR_CROP_X`), já que muda por preset de avatar.

4. **Ajustar `AvatarCompletedMsg`.** `vertical_video_paths` passa a ser
   preenchido pelo editor, não pelo HeyGen. Confirmar que
   `heygen_callback` não fica esperando segmentos verticais que nunca virão —
   hoje ele aguarda ambos os targets resolverem.

**Economia:** ~50% do custo de avatar, imediatamente.

**Risco:** enquadramento. Precisa de uma inspeção visual do primeiro corte
antes de adotar em produção — mas o teste não custa crédito, porque parte de um
clipe já gerado.

---

### P1-3. A tarifa do HeyGen no código não bate com a cobrança real

`agents/pipeline/shared/cost_tracker.py`:

```python
HEYGEN_SPEED_RATE_USD_PER_SECOND: float = 0.0335
```

Medição real do ciclo de teste: **276 créditos para ~295s ≈ 0,93 crédito/s** —
não bate com a constante. Além disso a conta é `billing_type: wallet` (saldo em
dólar), e existem dois pools distintos: `api` (o que a pipeline consome) e
`plan_credit` (uso pelo app web). Consumimos o pool `api`, que zerou.

O `cost_limit` da pipeline decide se aborta uma produção cara com base nessa
constante. **Hoje esse gate opera sobre um número não validado.**

**Correção:** medir a cobrança real de uma geração pequena e corrigir a
constante, ou trocar a lógica para consultar o saldo da carteira via
`GET /v3/users/me` antes de disparar.

---

## P2 — Qualidade do que vai a público

### P2-1. Copies sociais saíram pela metade e com o link errado

Os posts publicados no LinkedIn, Instagram e Threads tinham texto incompleto e
apontavam para o **blog**, não para o vídeo. (Já removidos manualmente pelo
dono do canal.)

Duas causas distintas:

- **Texto pela metade:** `publisher_job.job.py` monta `copy_social` como
  `f"{description[:300]}..."`. É um corte cego em 300 caracteres, no meio da
  frase. Precisa de resumo próprio por plataforma, ou pelo menos corte em
  fronteira de sentença.
- **Link errado:** `copy_social` referencia `article_url`. Para a publicação
  que acompanha o **vídeo**, o link deveria ser o do YouTube. A substituição de
  `[LINK_CANAL]` foi implementada em `fafc309`, mas o `copy_social` do
  `publish_video_ready` é montado por f-string e não passa por ela.

**Arquivo:** `agents/pipeline/publisher_job/job.py`, função
`publish_video_ready`.

---

### P2-2. Títulos do YouTube em caixa baixa e com `#` colado

Saíram como `'o fluxo de decisão híbrido'` e
`'#matemática por trás do teste a/b (Short)'`.

- A caixa baixa vem do prompt de capitalização aplicado literalmente demais
  (mesma classe de erro já corrigida no carrossel em `b7209f7` — a correção
  precisa ser estendida aos títulos de vídeo).
- O `#` colado vem de `f"#{title} (Short)"`, hardcoded em `publish_video_ready`.
  Deveria ser uma hashtag de verdade no fim, ou nada.

---

### P2-3. Preview das imagens na revisão nunca foi validado visualmente

A rota `/api/csm/media` e a grade de revisão foram implementadas e deployadas
(`31419d5`), mas **nunca foram abertas num navegador**. Falta confirmar:

- as imagens carregam (a service account do `frontend` é a *default do
  Compute*; se não tiver leitura no bucket da pipeline, todas dão 502);
- o layout do carrossel, stories e posts em tela real.

---

## Estado atual da infraestrutura

Corrigido e deployado em 16/08 — cadeia de bugs que impedia qualquer vídeo de
existir. Todos **pré-existentes**, nunca exercitados porque a pipeline nunca
tinha gerado avatar de verdade:

| Commit | Correção |
|---|---|
| `6db9380` | `heygen-callback` com IAM bloqueando 100% dos webhooks do HeyGen |
| `434a1f8` | `video_editor_job` morria na importação (`anchor_resolver`) |
| `02a94dd` | `gs://` nunca tratado em upload do YouTube, thumbnail e assinatura |
| `c95e34b` | Escopo do token insuficiente para assinar via IAM signBlob |
| `c907a2f` | Cada Reel virava um vídeo longo no canal (`channels_approved` ignorado) |

Credenciais validadas (`./scripts/check-credentials.sh`): Vertex AI,
ElevenLabs, HeyGen, YouTube, LinkedIn, Instagram, Threads — todas válidas.

**Limitação conhecida:** o token do YouTube tem apenas `youtube.upload` e
`youtube.readonly`. **Não permite apagar vídeos.** Para habilitar exclusão via
API é preciso adicionar `youtube.force-ssl` aos escopos em
`scripts/renew_token.py` e refazer o consentimento.

---

## Ordem sugerida para a próxima sessão

1. **P0-1** — manifesto v2 chega íntegro à pipeline. Sem isso nada mais importa:
   todo vídeo sai como avatar puro e caro.
2. **P0-2** — trava que recusa manifesto sem ilustração.
3. **Validar sem gastar crédito:** rodar `pipeline-submit` até a criação do
   `manifest.html` e conferir `segment_count == 8` e `slide_segments >= 6`.
   Este passo **não** chama HeyGen nem ElevenLabs.
4. **P1-2** — crop vertical. Testável sobre os clipes já gerados, custo zero.
5. **P1-1** — unificar Reels e Shorts.
6. Só então, com saldo recarregado, produzir **um** vídeo e inspecionar antes
   de qualquer publicação.

---

## Pendência que exige decisão do dono do canal

- **Dessincronia voz/movimento no avatar.** Relatada ao assistir os vídeos. Não
  foi possível confirmar tecnicamente: o áudio não tem silêncio inicial anormal
  (0,53s, padrão do ElevenLabs) e a boca já se move no primeiro frame. Duas
  hipóteses, na ordem de probabilidade:
  1. `voice.type: "audio"` — enviamos áudio pré-gerado pelo ElevenLabs para o
     HeyGen sincronizar. É lip-sync *guiado por áudio*, tipicamente com
     fidelidade menor do que quando o próprio HeyGen gera a fala a partir de
     texto.
  2. Reamostragem do áudio pelo HeyGen introduzindo offset fixo.

  O teste mais barato é gerar **um** segmento curto e comparar frame a frame —
  mas isso consome crédito, então fica bloqueado pela restrição atual.

- **4 vídeos indevidos no canal** (`VUlO-lVL6XA`, `sR91P5F06TM`,
  `I-w-gHMC6tY`, `CHB0IgOzbKY`). Estão `unlisted`. A exclusão via API falhou
  por falta de escopo; precisam ser removidos pelo YouTube Studio ou após
  renovar o token com `youtube.force-ssl`.
