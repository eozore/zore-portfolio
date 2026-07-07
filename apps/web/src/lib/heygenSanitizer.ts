/**
 * heygenSanitizer.ts
 *
 * Sanitization logic for HeyGen text-to-speech script input.
 * Strips out visual directions (blockquotes), markdown formatting, URLs, hashtags,
 * and emojis so the synthetic avatar only speaks pure text.
 */

export function sanitizeHeyGenScript(text: string): string {
  if (!text) return '';

  // 1. Remove visual direction blockquotes (lines starting with >)
  let clean = text
    .split('\n')
    .filter((line) => !line.trim().startsWith('>'))
    .join('\n');

  // 2. Remove headings (lines starting with #)
  clean = clean
    .split('\n')
    .filter((line) => !line.trim().startsWith('#'))
    .join('\n');

  // 3. Remove URLs and markdown link wrappers to retain only the anchor text
  clean = clean.replace(/https?:\/\/[^\s]+/g, '');
  clean = clean.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1');

  // 4. Remove inline markdown characters (*, _, `, ~)
  clean = clean.replace(/[\*_`~]/g, '');

  // 5. Remove hashtags symbol but keep the word (e.g. #MachineLearning -> MachineLearning)
  clean = clean.replace(/#(\w+)/g, '$1');

  // 6. Remove common unicode emojis and symbols
  clean = clean.replace(
    /[\u{1F300}-\u{1F9FF}]|[\u{2700}-\u{27BF}]|[\u{1F900}-\u{1F9FF}]|[\u{1F600}-\u{1F64F}]|[\u{1F680}-\u{1F6FF}]|[\u{2600}-\u{26FF}]|[\u{2000}-\u{32FF}]/gu,
    ''
  );

  // 7. Collapse multiple spaces and trim
  clean = clean.replace(/\s+/g, ' ').trim();

  return clean;
}
