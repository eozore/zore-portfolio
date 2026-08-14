---
trigger: model_decision
description: Padrão de Rigor Matemático e Didática em Artigos e Tutoriais
---

# Regra Imutável: Rigor Didático — O "Porquê" Antes do "Como"

A plataforma `eozore.com` reflete a autoridade de um Líder Técnico sênior com sólida formação matemática na UFSCar. 

Sempre que redigir artigos técnicos, tutoriais de código ou roteiros de aulas profundas, a IA deve cumprir rigorosamente a seguinte **Hierarquia Didática**:

1. **Intuição Geométrica e Visualização:** Antes de formular equações abstratas ou mostrar código Python, explique a intuição geométrica do problema (ex: *projeção em subespaços*, *deformação de hiperplanos*, *caminho no espaço de pesos*). Utilize blocos ` ```mermaid ` para desenhar fluxos ou grafos computacionais.
2. **Fundamentação Algébrica e Estatística (LaTeX):** Formule o problema matematicamente utilizando blocos de equações `$$...$$` e variáveis inline `$...$`. Explique a função de perda, o gradiente ou a distribuição estatística envolvida.
3. **Implementação Prática Comentada:** Somente após a teoria estar consolidada, apresente o bloco de código Python/TypeScript limpo e comentado passo a passo, conectando as variáveis do código diretamente aos símbolos matemáticos definidos na etapa anterior (ex: `# W_A corresponde à matriz de baixo posto B na equação (2)`).
4. **Análise Crítica de Trade-offs:** Encerre apontando limitações de memória, complexidade assintótica ($O(N)$) e comportamentos em cenários extremos.
