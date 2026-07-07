/**
 * arXiv Trending Papers Fetcher
 *
 * Fetches recent papers from arXiv for GenAI / ML / MLOps topics.
 * Used by the CMO agent to inject proactive market intelligence into the
 * first turn of the interview session.
 */

export interface ArxivPaper {
  title: string;
  summary: string;
  authors: string;
  published: string;
  link: string;
}

const ARXIV_QUERIES = [
  'large+language+models+fine-tuning',
  'agentic+AI+multi-agent+systems',
  'RAG+retrieval+augmented+generation',
  'MLOps+model+serving+production',
  'diffusion+models+generative+AI',
];

/**
 * Fetches recent papers from arXiv for a given search query.
 * Uses the arXiv Atom feed API (no API key required).
 */
export async function fetchArxivPapers(
  query: string,
  maxResults = 3
): Promise<ArxivPaper[]> {
  const url = `https://export.arxiv.org/api/query?search_query=all:${query}&start=0&max_results=${maxResults}&sortBy=submittedDate&sortOrder=descending`;

  try {
    const res = await fetch(url, {
      next: { revalidate: 3600 }, // Cache for 1 hour (Next.js fetch cache)
      headers: { 'User-Agent': 'eozore-cmo-agent/1.0' },
    });

    if (!res.ok) return [];

    const xml = await res.text();
    return parseArxivAtom(xml);
  } catch (err) {
    console.warn('[arxiv] Failed to fetch papers:', err);
    return [];
  }
}

/**
 * Fetches trending papers across the main GenAI/ML/MLOps categories.
 * Returns a formatted string ready to be injected into the CMO system prompt.
 */
export async function fetchTrendingPapersForCmo(maxPerQuery = 2): Promise<string> {
  const query = ARXIV_QUERIES[Math.floor(Math.random() * ARXIV_QUERIES.length)];

  try {
    const papers = await fetchArxivPapers(query, maxPerQuery);
    if (papers.length === 0) return '';

    const papersText = papers
      .map(
        (p, i) =>
          `${i + 1}. "${p.title}"\n   Publicado: ${p.published} | Link: ${p.link}\n   Resumo: ${p.summary.slice(0, 200)}...`
      )
      .join('\n\n');

    return `=== PAPERS RECENTES NO arXiv (${query.replace(/\+/g, ' ')}) ===\n\n${papersText}`;
  } catch (err) {
    console.warn('[arxiv] Failed to generate CMO context:', err);
    return '';
  }
}

/**
 * Parses an arXiv Atom XML response and extracts paper metadata.
 */
function parseArxivAtom(xml: string): ArxivPaper[] {
  const papers: ArxivPaper[] = [];

  // Simple regex-based parsing (no DOM required for server-side)
  const entries = xml.split('<entry>').slice(1);

  for (const entry of entries) {
    try {
      const title = extractTag(entry, 'title')?.replace(/\n/g, ' ').trim() ?? '';
      const summary = extractTag(entry, 'summary')?.replace(/\n/g, ' ').trim() ?? '';
      const published = extractTag(entry, 'published')?.slice(0, 10) ?? '';
      const link =
        entry.match(/href="(https:\/\/arxiv\.org\/abs\/[^"]+)"/)?.[1] ?? '';

      // Extract authors
      const authorMatches = [...entry.matchAll(/<name>([^<]+)<\/name>/g)];
      const authors = authorMatches
        .slice(0, 3)
        .map((m) => m[1])
        .join(', ');

      if (title) {
        papers.push({ title, summary, authors, published, link });
      }
    } catch {
      // Skip malformed entries
    }
  }

  return papers;
}

function extractTag(xml: string, tag: string): string | undefined {
  const match = xml.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`));
  return match?.[1];
}
