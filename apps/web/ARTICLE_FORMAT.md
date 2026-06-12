# Padrão de Artigos — éozoré Blog

> Este documento define o formato que agentes de IA devem usar ao enviar artigos
> para a API do portfólio (`POST /api/articles`). Seguir este padrão garante
> renderização correta de todos os elementos.

---

## Payload da API

```json
POST /api/articles
Authorization: Bearer <API_KEY>
Content-Type: application/json

{
  "title": "Título do Artigo (máx 150 chars)",
  "slug": "titulo-do-artigo (a-z, 0-9, hífens, máx 100 chars)",
  "content": "<markdown completo do artigo>",
  "category": "estatistica | ml | ia",
  "language": "pt-BR | en",
  "publishedAt": "2026-06-11T10:00:00Z",
  "readTime": 12,
  "coverImage": "https://url-da-imagem-de-capa.jpg"
}
```

---

## Formato do Markdown (`content`)

O campo `content` aceita **GitHub Flavored Markdown (GFM)** com extensões para fórmulas LaTeX. Todos os elementos abaixo são renderizados automaticamente como componentes React estilizados.

### Elementos Suportados

| Elemento | Sintaxe | Notas |
|----------|---------|-------|
| Título H2 | `## Título` | Usado para seções. Recebe borda inferior. |
| Título H3 | `### Subtítulo` | Subtítulos de seção. |
| Parágrafo | Texto normal | Fonte 1.075rem, line-height 1.8. |
| Negrito | `**texto**` | Font-weight 600. |
| Itálico | `*texto*` | Font-style italic. |
| Código inline | `` `variável` `` | Fundo rosado, cor primária. |
| Bloco de código | ` ```python ... ``` ` | Fundo escuro, syntax highlight automático. |
| Fórmula inline | `$E[X] = \mu$` | Renderizada com KaTeX. |
| Fórmula em bloco | `$$f(x) = ...$$` | Centralizada em caixa alaranjada. |
| Tabela GFM | `\| Col \| Col \|` | Estilizada com header, hover, bordas. |
| Lista não-ordenada | `- item` | Marker na cor primária. |
| Lista ordenada | `1. item` | Numeração com cor primária. |
| Blockquote | `> citação` | Barra terracota lateral, fundo sutil. |
| Imagem | `![alt](url)` | Arredondada, centralizada, com figcaption. |
| Separador | `---` | Linha sutil horizontal. |
| Link | `[texto](url)` | Cor primária, sublinhado, target _blank se externo. |

---

## Regras de Formatação

### 1. Estrutura obrigatória do artigo

```markdown
Parágrafo de introdução (sem H1 — o título vem do campo `title` da API).

---

## Primeira seção

Conteúdo...

### Subsecão (se necessário)

---

## Segunda seção

...

---

## Conclusão / Resumo

> Citação de fechamento (opcional)
```

**NÃO** incluir H1 (`#`) no `content` — o título é renderizado pelo componente de página a partir do campo `title` da API.

### 2. Fórmulas LaTeX

Use `$...$` para inline e `$$...$$` para bloco:

```markdown
O valor esperado é $E[X] = \mu$ e a variância é $\text{Var}(X) = \sigma^2$.

A distribuição Normal é definida por:

$$f(x) = \frac{1}{\sigma\sqrt{2\pi}} \exp\left(-\frac{1}{2}\left(\frac{x-\mu}{\sigma}\right)^2\right)$$
```

**Regras de LaTeX:**
- Use `\text{...}` para texto dentro de fórmulas: `$\text{Var}(X)$`
- Use `\left(` e `\right)` para parênteses escaláveis
- Use `\exp(...)` em vez de `e^{...}` para legibilidade
- Evite `\\` para quebra de linha em fórmulas — use fórmulas separadas

### 3. Blocos de código

Sempre especifique a linguagem após os backticks:

````markdown
```python
import numpy as np
x = np.array([1, 2, 3])
print(f'Média: {x.mean():.2f}')
```
````

**Linguagens suportadas:** python, javascript, typescript, sql, bash, r, json, yaml, html, css

Para output/resultado, use bloco sem linguagem:

````markdown
```
Média: 2.00
Desvio: 0.82
```
````

### 4. Tabelas

Use formato GFM com pipes e alinhamento:

```markdown
| Conceito | Fórmula | Uso em ML |
|----------|---------|-----------|
| Média | $\bar{x} = \frac{1}{n}\sum x_i$ | Baseline |
| Variância | $s^2 = \frac{1}{n-1}\sum(x_i-\bar{x})^2$ | Spread |
```

**Regras de tabela:**
- Sempre incluir a linha de separação (`|---|---|---|`)
- Manter consistência no número de colunas
- Negrito em headers importantes: `**Conceito**`
- Fórmulas LaTeX funcionam dentro de células

### 5. Gráficos e Visualizações

Para gráficos, use **imagens geradas externamente** (PNG/SVG hospedados):

```markdown
![Distribuição Normal com μ=0 e σ=1](https://storage.googleapis.com/eozore-assets/graficos/normal-dist.png)
```

**NÃO inclua SVG inline no markdown** — o parser de markdown não renderiza SVG complexo corretamente. Gere a imagem, faça upload e use a URL.

Alternativa: para gráficos simples (barras, linhas), use tabelas + descrição textual.

### 6. Callouts / Destaques

Use blockquotes com formatação:

```markdown
> **⚠️ Atenção:** A média é sensível a outliers. Prefira a mediana para dados assimétricos.

> **💡 Dica:** Use `np.percentile(data, 99)` para calcular o P99 diretamente.

> **📊 Resultado:** O modelo atingiu R² = 0.94 no conjunto de teste.
```

### 7. Listas com código

```markdown
O fluxo de ML em produção:

1. **Coleta** — ingestão via Pub/Sub
2. **Feature engineering** — `FeatureStore.get_online_features()`
3. **Inferência** — modelo servido no Vertex AI Endpoint
4. **Monitoramento** — drift detection com Evidently
```

---

## Categorias Permitidas

| Valor | Significado | Tipo de conteúdo |
|-------|-------------|-----------------|
| `estatistica` | Estatística e Probabilidade | Distribuições, testes, inferência |
| `ml` | Machine Learning | Modelos, features, produção |
| `ia` | Inteligência Artificial | LLMs, agentes, aplicações |

---

## Exemplo Completo (payload)

```json
{
  "title": "Regressão Linear: Da Teoria à Produção",
  "slug": "regressao-linear-pratica",
  "category": "ml",
  "language": "pt-BR",
  "publishedAt": "2026-06-11T10:00:00Z",
  "readTime": 12,
  "coverImage": "https://storage.googleapis.com/eozore-assets/covers/regressao-linear.jpg",
  "content": "Regressão linear é o modelo mais subestimado em produção...\n\n---\n\n## Por que ainda usar?\n\nTrês motivos:\n\n1. **Interpretabilidade** — o CEO entende\n2. **Velocidade** — microsegundos\n3. **Baseline** — se não bater, o problema é nos dados\n\n## A fórmula\n\n$$\\hat{y} = \\beta_0 + \\beta_1 x$$\n\n## Implementação\n\n```python\nfrom sklearn.linear_model import LinearRegression\nmodel = LinearRegression().fit(X, y)\nprint(f'R²: {model.score(X, y):.4f}')\n```\n\n---\n\n## Resumo\n\n| Quando usar | Quando evitar |\n|-------------|---------------|\n| Relação linear | Dados não-lineares |\n| Interpretabilidade | Alta dimensionalidade |\n\n> \"All models are wrong, but some are useful.\" — George Box"
}
```

---

## Validações da API

A API rejeita (HTTP 400) se:
- `title` > 150 caracteres
- `slug` não match `/^[a-z0-9-]+$/` ou > 100 chars
- `content` > 100.000 caracteres
- `category` não é `estatistica`, `ml` ou `ia`
- `language` não é `pt-BR` ou `en`
- `publishedAt` não é ISO 8601
- `readTime` não é inteiro entre 1 e 120
- `coverImage` não começa com `https://`
- `slug` já existe (HTTP 409)
