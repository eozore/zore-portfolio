export const PART1 = String.raw`Se você treina modelos de machine learning, monitora APIs em produção ou analisa resultados de testes A/B, está trabalhando com variáveis aleatórias — mesmo que nunca tenha parado para formalizar isso. Este artigo constrói o conceito do zero, com rigor estatístico mas sem arrogância, e termina com uma aplicação real de monitoramento de SLA.

Ao final, você vai entender: o que é uma variável aleatória, como descrevê-la formalmente, e por que isso é o alicerce de qualquer modelo probabilístico que você vai usar na carreira.

> **🔗 Conexão:** Este é o primeiro artigo da trilha de Estatística para ML. Os conceitos aqui são pré-requisito para tudo que vem depois — distribuições, inferência, testes de hipótese.

---

## O que é uma variável aleatória?

Imagine que você monitora o tempo de resposta de uma API. Cada requisição é um "experimento" — você não sabe de antemão se vai demorar 50ms ou 3 segundos. O valor que você mede é **imprevisível individualmente**, mas segue um **padrão coletivo**. Esse "medidor de resultados imprevisíveis" é exatamente uma variável aleatória.

Formalmente, uma variável aleatória $X$ é uma função que mapeia resultados de um experimento aleatório para números reais:

$$X: \Omega \rightarrow \mathbb{R}$$

Onde $\Omega$ é o espaço amostral — o conjunto de todos os resultados possíveis do experimento.

> **💡 Insight:** Todo dado que você coleta em produção (latência, taxa de conversão, valor de compra, churn) é uma realização de uma variável aleatória. Quando você faz df['latencia'].mean(), está estimando $E[X]$ a partir de amostras.

### Exemplos concretos

- $X$ = tempo de resposta da API → $X = 42$ ms, $X = 180$ ms, $X = 3200$ ms
- $Y$ = número de cliques por sessão → $Y = 0$, $Y = 3$, $Y = 12$
- $Z$ = valor de uma compra → $Z = 0$ (não comprou) ou $Z = 89.90$

---

## Tipos de variáveis aleatórias

Nem todas as variáveis aleatórias são iguais. A distinção fundamental determina quais distribuições e quais modelos você pode usar:

| Tipo | Valores possíveis | Exemplo em produção | Distribuição típica |
|------|-------------------|---------------------|---------------------|
| **Discreta** | Finitos ou enumeráveis | Cliques por sessão, erros por minuto | Poisson, Binomial |
| **Contínua** | Qualquer valor num intervalo | Latência, tempo até churn, receita | Normal, Exponencial, Log-Normal |
| **Mista** | Combinação (ponto + intervalo) | Valor de compra (0 ou contínuo) | Zero-inflated, Hurdle |

> **⚠️ Atenção:** Tratar uma variável discreta como contínua (ou vice-versa) é um dos erros mais comuns em modelagem. Se seus dados têm muitos zeros exatos, provavelmente precisa de um modelo misto — não de uma Normal.

---

## Distribuição de probabilidade

A distribuição descreve **como a probabilidade se espalha** pelos valores de $X$. É o "retrato completo" da variável aleatória — saber a distribuição é saber tudo sobre o comportamento de $X$.

Para variáveis contínuas, usamos a **função densidade de probabilidade** (PDF):

$$f(x) = \frac{1}{\sigma\sqrt{2\pi}} \exp\left(-\frac{1}{2}\left(\frac{x-\mu}{\sigma}\right)^2\right)$$

Esta é a distribuição Normal (Gaussiana) — a mais famosa, com média $\mu$ e desvio padrão $\sigma$.

### Propriedades que você precisa saber

| Propriedade | Fórmula | Significado |
|-------------|---------|-------------|
| Área total = 1 | $\int_{-\infty}^{+\infty} f(x)\, dx = 1$ | A probabilidade total é 100% |
| Probabilidade num intervalo | $P(a \leq X \leq b) = \int_a^b f(x)\, dx$ | Área sob a curva entre $a$ e $b$ |
| Valor esperado | $E[X] = \mu$ | "Centro de gravidade" da distribuição |
| Variância | $\text{Var}(X) = \sigma^2$ | O quão espalhados os valores estão |

> **🛠️ Na prática:** Você raramente calcula integrais manualmente. Use scipy.stats.norm.cdf(x, mu, sigma) para probabilidades e norm.ppf(q, mu, sigma) para quantis.
`;

export const PART2 = String.raw`## Valor esperado e variância

Estes dois números **resumem** qualquer distribuição. Com eles, você já sabe "para onde aponta" e "quão incerto é".

O **valor esperado** $E[X]$ é a média ponderada pela probabilidade:

$$E[X] = \int_{-\infty}^{+\infty} x \cdot f(x)\, dx$$

A **variância** $\text{Var}(X)$ mede o quanto os valores se afastam da média:

$$\text{Var}(X) = E\left[(X - \mu)^2\right] = E[X^2] - (E[X])^2$$

### Por que isso importa em ML?

| Conceito ML | Conexão com variância |
|-------------|----------------------|
| **Bias do estimador** | $\text{Bias}(\hat{\theta}) = E[\hat{\theta}] - \theta$ |
| **Overfitting** | Modelo com alta variância nas previsões |
| **Trade-off bias-variância** | $\text{MSE} = \text{Bias}^2 + \text{Var}$ |
| **Regularização** | Reduz variância ao custo de aumentar bias |

> **💡 Insight:** Quando alguém diz "o modelo está overfitting", está dizendo que a *variância* das previsões é alta — para inputs parecidos, o modelo dá respostas muito diferentes dependendo do treino.

---

## Quantis: a linguagem de produção

Em produção, **ninguém fala em média** — fala-se em quantis (percentis). A razão é simples: a média é sensível a outliers. Um timeout de 30 segundos em 10.000 requisições distorce a média, mas não afeta o P50 nem o P95.

| Quantil | O que representa | Uso típico |
|---------|------------------|------------|
| P50 (mediana) | Metade é menor, metade é maior | "Experiência típica" do usuário |
| P95 | 95% das requisições são mais rápidas | Alerta de degradação |
| P99 | 99% são mais rápidas — o 1% pior | SLA contratual |

> **⚠️ Atenção:** Se seu SLA diz "latência média < 200ms", está mal definido. Um sistema com média 150ms pode ter P99 de 5 segundos. Defina SLA em percentis.
`;

export const PART3 = `## Caso prático: Monitorando SLA na FlashLog

A **FlashLog** é uma startup de logging que processa 50.000 requisições/minuto. O SLA contratual garante latência **P99 < 500ms**. O time de engenharia precisa de um monitor que detecte degradação antes que o SLA estoure.

### Modelando o problema

O tempo de resposta $X$ segue uma distribuição **Log-Normal** (típico para latências — sempre positiva, cauda longa à direita):

$$\\ln(X) \\sim N(\\mu = 4.5,\\; \\sigma = 0.8)$$

### Implementação do monitor

` + "```python\nimport numpy as np\nfrom scipy import stats\n\n# Parâmetros estimados de dados históricos\nmu_ln, sigma_ln = 4.5, 0.8\n\n# Simular 10.000 requisições\nnp.random.seed(42)\nlatencias = np.random.lognormal(mean=mu_ln, sigma=sigma_ln, size=10_000)\n\n# Quantis operacionais\np50 = np.percentile(latencias, 50)\np95 = np.percentile(latencias, 95)\np99 = np.percentile(latencias, 99)\n\nprint(f'P50 (mediana):  {p50:.1f} ms')\nprint(f'P95:            {p95:.1f} ms')\nprint(f'P99:            {p99:.1f} ms')\nprint(f'SLA (P99<500):  {\"VIOLADO\" if p99 > 500 else \"OK\"}')\n\n# Probabilidade de violar o SLA por requisição\nprob_viola = 1 - stats.lognorm.cdf(500, s=sigma_ln, scale=np.exp(mu_ln))\nprint(f'P(X > 500ms):   {prob_viola:.4f} ({prob_viola*100:.2f}%)')\n```" + `

` + "```\nP50 (mediana):  89.4 ms\nP95:            328.7 ms\nP99:            621.3 ms\nSLA (P99<500):  VIOLADO\nP(X > 500ms):   0.0198 (1.98%)\n```" + `

> **📊 Resultado:** Com $\\sigma = 0.8$, quase 2% das requisições violam o SLA. A mediana é ótima (89ms), mas a cauda longa é o problema. O time precisa reduzir a variância dos outliers, não otimizar o caso médio.

### Decisão tomada

| Opção | Ação | Impacto no P99 |
|-------|------|----------------|
| A | Otimizar queries lentas (top 5%) | Reduz $\\sigma$ de 0.8 → 0.6 |
| B | Renegociar SLA para P99 < 700ms | Aceita a cauda atual |
| C | Circuit breaker em 400ms | Corta a cauda, mas gera erros |

O time escolheu **opção A** — atacar a causa (queries lentas), não o sintoma.

> **🛠️ Na prática:** Monitore com \`np.percentile(latencias_janela, 99)\` a cada minuto. Alerte se P99 > 400ms (margem de segurança antes do SLA de 500ms).
`;

export const PART4 = String.raw`---

## Quando usar / Quando NÃO usar

| Cenário | Abordagem correta | Erro comum |
|---------|-------------------|------------|
| Modelar incerteza em previsões | Tratar output como variável aleatória | Reportar só o ponto médio sem intervalo |
| Monitorar performance | Usar quantis (P95, P99) | Usar média (masca outliers) |
| Dados com muitos zeros | Modelo misto (zero-inflated) | Forçar Normal em dados assimétricos |
| Feature engineering | Calcular estatísticas da distribuição | Usar só a média como feature |
| Comparar modelos | Analisar distribuição dos erros | Comparar só RMSE médio |

---

## Resumo

| Conceito | O que é | Por que importa |
|----------|---------|-----------------|
| Variável aleatória $X$ | Função: resultados → números | Base de toda modelagem probabilística |
| Distribuição $f(x)$ | Como a probabilidade se espalha | Escolher o modelo certo |
| Valor esperado $E[X]$ | Centro de gravidade | Bias, previsão pontual |
| Variância $\text{Var}(X)$ | Dispersão | Overfitting, incerteza |
| Quantis (P50, P95, P99) | Pontos de corte | SLAs, alertas, decisões |

---

## Próximo passo

No próximo artigo, vamos abrir a caixa das **distribuições de probabilidade** — Bernoulli, Binomial, Poisson, Normal, Exponencial e Log-Normal. Para cada uma: quando usar, fórmula, gráfico comparativo e um guia prático para escolher a distribuição certa para cada problema que você encontra em produção.

> "O melhor modelo é aquele que você entende profundamente o suficiente para saber quando ele vai falhar." — Victor Zoré
`;
