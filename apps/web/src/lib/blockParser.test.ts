import { describe, it, expect } from 'vitest';
import { parseMarkdownToBlocks, parseBlocksToMarkdown } from './blockParser';

describe('blockParser', () => {
  it('should parse simple text and headings correctly', () => {
    const md = `## Introdução
Este é um parágrafo normal.

### Subtópico
Outro parágrafo.`;
    const blocks = parseMarkdownToBlocks(md);
    
    expect(blocks.length).toBe(4);
    expect(blocks[0].type).toBe('heading');
    expect(blocks[0].content).toBe('Introdução');
    expect(blocks[0].metadata?.level).toBe(2);
    
    expect(blocks[1].type).toBe('text');
    expect(blocks[1].content).toBe('Este é um parágrafo normal.');
    
    expect(blocks[2].type).toBe('heading');
    expect(blocks[2].content).toBe('Subtópico');
    expect(blocks[2].metadata?.level).toBe(3);
    
    expect(blocks[3].type).toBe('text');
    expect(blocks[3].content).toBe('Outro parágrafo.');
  });

  it('should parse equations, code and plots', () => {
    const md = `## Fundamentação Matemática
$$
y = f(x)
$$

Eis um código:
\`\`\`python
def train():
    pass
\`\`\`

E um gráfico executável:
\`\`\`python-plot
plt.plot([1, 2], [3, 4])
\`\`\``;

    const blocks = parseMarkdownToBlocks(md);
    
    expect(blocks[0].type).toBe('heading');
    expect(blocks[1].type).toBe('latex');
    expect(blocks[1].content).toBe('y = f(x)');
    
    expect(blocks[2].type).toBe('text');
    
    expect(blocks[3].type).toBe('code');
    expect(blocks[3].content).toBe('def train():\n    pass');
    expect(blocks[3].metadata?.language).toBe('python');
    
    expect(blocks[4].type).toBe('text');
    
    expect(blocks[5].type).toBe('matplotlib_plot');
    expect(blocks[5].content).toBe('plt.plot([1, 2], [3, 4])');
  });

  it('should support blockquotes as callout blocks', () => {
    const md = `> **⚠️ Atenção:** Este é um callout.
> Ele pode ter várias linhas.`;
    const blocks = parseMarkdownToBlocks(md);
    
    expect(blocks.length).toBe(1);
    expect(blocks[0].type).toBe('callout');
    expect(blocks[0].content).toBe('**⚠️ Atenção:** Este é um callout.\nEle pode ter várias linhas.');
  });

  it('should convert blocks back to markdown with high fidelity', () => {
    const originalMd = `## Introdução

Este é um parágrafo.

---

> **💡 Dica:** Tente usar LaTeX.

$$
E = mc^2
$$

\`\`\`python-plot
plt.scatter(x, y)
\`\`\``;

    const blocks = parseMarkdownToBlocks(originalMd);
    const rebuiltMd = parseBlocksToMarkdown(blocks);
    
    const reParsedBlocks = parseMarkdownToBlocks(rebuiltMd);
    expect(reParsedBlocks.length).toBe(blocks.length);
    for (let i = 0; i < blocks.length; i++) {
      expect(reParsedBlocks[i].type).toBe(blocks[i].type);
      expect(reParsedBlocks[i].content.trim()).toBe(blocks[i].content.trim());
    }
  });
});
