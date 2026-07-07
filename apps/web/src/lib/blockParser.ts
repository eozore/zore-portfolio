export type BlockType =
  | 'text'
  | 'heading'
  | 'code'
  | 'latex'
  | 'matplotlib_plot'
  | 'mermaid'
  | 'callout'
  | 'divider';

export interface ArticleBlock {
  id: string;
  type: BlockType;
  content: string;
  metadata?: Record<string, any>;
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 9);
}

export function parseMarkdownToBlocks(markdown: string): ArticleBlock[] {
  const blocks: ArticleBlock[] = [];
  if (!markdown || !markdown.trim()) return blocks;

  const lines = markdown.split('\n');
  let currentBlockType: BlockType | null = null;
  let currentContentLines: string[] = [];
  let currentMetadata: Record<string, any> = {};

  const flushBlock = () => {
    if (currentContentLines.length > 0 || currentBlockType === 'divider') {
      let content = currentContentLines.join('\n');
      
      if (content.trim() || currentBlockType === 'divider') {
        if (currentBlockType === 'text') {
          content = content.trim();
        }
        
        if (content || currentBlockType === 'divider') {
          blocks.push({
            id: generateId(),
            type: currentBlockType || 'text',
            content,
            metadata: Object.keys(currentMetadata).length > 0 ? { ...currentMetadata } : undefined,
          });
        }
      }
      currentContentLines = [];
      currentMetadata = {};
      currentBlockType = null;
    }
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmedLine = line.trim();

    // 1. Handling Code Blocks (```)
    if (trimmedLine.startsWith('```')) {
      if (currentBlockType === 'code' || currentBlockType === 'matplotlib_plot' || currentBlockType === 'mermaid') {
        flushBlock();
      } else {
        flushBlock();
        
        const lang = trimmedLine.slice(3).trim();
        if (lang === 'python-plot') {
          currentBlockType = 'matplotlib_plot';
        } else if (lang === 'mermaid') {
          currentBlockType = 'mermaid';
        } else {
          currentBlockType = 'code';
          currentMetadata.language = lang || 'text';
        }
      }
      i++;
      continue;
    }

    if (currentBlockType === 'code' || currentBlockType === 'matplotlib_plot' || currentBlockType === 'mermaid') {
      currentContentLines.push(line);
      i++;
      continue;
    }

    // 2. Handling LaTeX Equation Blocks ($$)
    if (trimmedLine === '$$') {
      if (currentBlockType === 'latex') {
        flushBlock();
      } else {
        flushBlock();
        currentBlockType = 'latex';
      }
      i++;
      continue;
    }

    if (currentBlockType === 'latex') {
      currentContentLines.push(line);
      i++;
      continue;
    }

    // 3. Handling Divider (---)
    if (trimmedLine === '---') {
      flushBlock();
      currentBlockType = 'divider';
      currentContentLines = [];
      flushBlock();
      i++;
      continue;
    }

    // 4. Handling Headings (##, ###)
    if (trimmedLine.startsWith('## ') || trimmedLine.startsWith('### ')) {
      flushBlock();
      const level = trimmedLine.startsWith('## ') ? 2 : 3;
      const text = trimmedLine.replace(/^###?\s+/, '');
      blocks.push({
        id: generateId(),
        type: 'heading',
        content: text,
        metadata: { level },
      });
      i++;
      continue;
    }

    // 5. Handling Callout Blockquote (> )
    if (trimmedLine.startsWith('>')) {
      if (currentBlockType !== 'callout') {
        flushBlock();
        currentBlockType = 'callout';
      }
      const cleanLine = line.replace(/^\s*>\s?/, '');
      currentContentLines.push(cleanLine);
      i++;
      continue;
    }

    if (currentBlockType === 'callout') {
      flushBlock();
    }

    // 6. Handling Paragraph / Normal Text
    if (trimmedLine === '') {
      if (currentBlockType === 'text') {
        flushBlock();
      }
    } else {
      if (currentBlockType !== 'text') {
        flushBlock();
        currentBlockType = 'text';
      }
      currentContentLines.push(line);
    }
    
    i++;
  }

  flushBlock();

  return blocks;
}

export function parseBlocksToMarkdown(blocks: ArticleBlock[]): string {
  if (!blocks || blocks.length === 0) return '';
  
  return blocks
    .map((block) => {
      switch (block.type) {
        case 'heading':
          const hashes = '#'.repeat(block.metadata?.level || 2);
          return `${hashes} ${block.content}`;
        case 'code':
          return `\`\`\`${block.metadata?.language || 'text'}\n${block.content}\n\`\`\``;
        case 'matplotlib_plot':
          return `\`\`\`python-plot\n${block.content}\n\`\`\``;
        case 'mermaid':
          return `\`\`\`mermaid\n${block.content}\n\`\`\``;
        case 'latex':
          return `$$\n${block.content}\n$$`;
        case 'callout':
          return block.content
            .split('\n')
            .map((line) => `> ${line}`)
            .join('\n');
        case 'divider':
          return '---';
        case 'text':
        default:
          return block.content;
      }
    })
    .join('\n\n');
}
