import { NextResponse } from 'next/server';
import type { ArticleCategory } from '@/types/article';

type OutputFormat = 'blog' | 'youtube' | 'linkedin';

interface ExportRequest {
  content: string;
  title: string;
  format: OutputFormat;
  category: ArticleCategory;
  language: 'pt-BR' | 'en';
}

function formatBlogJson(content: string, title: string, category: ArticleCategory, language: 'pt-BR' | 'en'): string {
  const payload = {
    title,
    slug: '[PREENCHER]',
    content,
    category,
    language,
    publishedAt: new Date().toISOString(),
    readTime: Math.max(1, Math.round(content.split(/\s+/).length / 200)),
    coverImage: 'https://storage.googleapis.com/eozore-assets/covers/default.jpg',
  };
  return JSON.stringify(payload, null, 2);
}

function formatYoutubeScript(content: string, title: string): string {
  return [
    '='.repeat(60),
    `ROTEIRO: ${title}`,
    `Gerado por: éozoré Content Studio`,
    `Data: ${new Date().toLocaleDateString('pt-BR')}`,
    '='.repeat(60),
    '',
    content,
    '',
    '='.repeat(60),
    'FIM DO ROTEIRO',
  ].join('\n');
}

function formatLinkedinPost(content: string, title: string): string {
  // Strip markdown formatting for LinkedIn plain text
  const clean = content
    .replace(/#{1,6}\s+/g, '')          // remove headings
    .replace(/\*\*(.+?)\*\*/g, '$1')    // remove bold
    .replace(/\*(.+?)\*/g, '$1')        // remove italic
    .replace(/`(.+?)`/g, '$1')          // remove inline code
    .replace(/```[\s\S]*?```/g, '')      // remove code blocks
    .replace(/\$\$[\s\S]*?\$\$/g, '')   // remove LaTeX blocks
    .replace(/\$[^$]+\$/g, '')          // remove LaTeX inline
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // links → text
    .replace(/^[-*]\s+/gm, '• ')        // normalize bullets
    .replace(/^\d+\.\s+/gm, '• ')       // normalize numbered lists
    .replace(/^>\s+/gm, '')             // remove blockquote markers
    .replace(/---+/g, '')               // remove HR
    .replace(/\n{3,}/g, '\n\n')         // collapse excess newlines
    .trim();

  const lines = clean.split('\n\n').filter(Boolean);

  // Trim to ~1300 chars (LinkedIn limit)
  let result = '';
  for (const line of lines) {
    if ((result + '\n\n' + line).length > 1250) break;
    result += (result ? '\n\n' : '') + line;
  }

  return [
    `[POST LINKEDIN — ${new Date().toLocaleDateString('pt-BR')}]`,
    `Tópico: ${title}`,
    '',
    '-'.repeat(50),
    '',
    result,
    '',
    '-'.repeat(50),
    `Caracteres: ${result.length}/1300`,
  ].join('\n');
}

/**
 * POST /api/csm/export
 * Formats the generated content for different channels and returns as downloadable text.
 */
export async function POST(request: Request): Promise<Response> {
  let body: ExportRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { content, title, format, category, language } = body;

  if (!content || !title || !format) {
    return NextResponse.json({ error: 'Missing required fields: content, title, format' }, { status: 400 });
  }

  let output: string;

  switch (format) {
    case 'blog':
      output = formatBlogJson(content, title, category, language);
      break;
    case 'youtube':
      output = formatYoutubeScript(content, title);
      break;
    case 'linkedin':
      output = formatLinkedinPost(content, title);
      break;
    default:
      return NextResponse.json({ error: 'Invalid format' }, { status: 400 });
  }

  return NextResponse.json({ output, format });
}
