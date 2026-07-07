/**
 * scriptParser.ts
 *
 * Bidirectional parser for YouTube scripts.
 * Converts between Markdown script strings and ScriptScene[] objects.
 */

export interface ScriptScene {
  id: string;
  section: string;
  visualCue: string;
  spokenText: string;
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 9);
}

/**
 * Parses Markdown script text into ScriptScene[]
 */
export function parseMarkdownToScenes(markdown: string): ScriptScene[] {
  const scenes: ScriptScene[] = [];
  if (!markdown || !markdown.trim()) return scenes;

  const lines = markdown.split('\n');
  let currentSection = 'INTRO';
  let currentVisualCue = 'CENA: Victor falando para a câmera';
  let currentSpokenLines: string[] = [];

  const flushScene = () => {
    const text = currentSpokenLines.join('\n').trim();
    if (text || currentVisualCue) {
      scenes.push({
        id: generateId(),
        section: currentSection,
        visualCue: currentVisualCue.trim(),
        spokenText: text,
      });
      currentSpokenLines = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // 1. Detect section headers (e.g. ## HOOK or ## [GANCHO])
    if (trimmed.startsWith('## ') || trimmed.startsWith('# ')) {
      flushScene();
      currentSection = trimmed.replace(/^##?\s+/, '').replace(/[\[\]]/g, '').trim();
      continue;
    }

    // 2. Detect scene directions/visual cues inside blockquotes, e.g. > [CENA: ...]
    if (trimmed.startsWith('>')) {
      const braceMatch = trimmed.match(/\[([^\]]+)\]/);
      if (braceMatch) {
        flushScene();
        currentVisualCue = braceMatch[1];
      } else {
        // Fallback for general blockquotes
        const cleanQuote = trimmed.replace(/^>\s?/, '').trim();
        if (cleanQuote) {
          flushScene();
          currentVisualCue = cleanQuote;
        }
      }
      continue;
    }

    // 3. Normal narration paragraph
    if (trimmed === '') {
      if (currentSpokenLines.length > 0) {
        // Keep paragraphs separated
        currentSpokenLines.push('');
      }
    } else {
      // Remove double spacing or formatting issues if any
      currentSpokenLines.push(line);
    }
  }

  flushScene();

  // If we ended up with no scenes but have some text, create a default scene
  if (scenes.length === 0 && markdown.trim()) {
    scenes.push({
      id: generateId(),
      section: 'INTRO',
      visualCue: 'CENA: Victor falando para a câmera',
      spokenText: markdown.trim(),
    });
  }

  return scenes;
}

/**
 * Serializes ScriptScene[] back into Markdown script text
 */
export function parseScenesToMarkdown(scenes: ScriptScene[]): string {
  if (!scenes || scenes.length === 0) return '';

  const parts: string[] = [];
  let lastSection = '';

  for (const scene of scenes) {
    // 1. Output section header if it changed
    if (scene.section && scene.section !== lastSection) {
      if (parts.length > 0) parts.push('');
      parts.push(`## ${scene.section}`);
      lastSection = scene.section;
    }

    // 2. Output scene direction/visual cue blockquote
    const cue = scene.visualCue.trim();
    if (cue) {
      if (parts.length > 0 && !parts[parts.length - 1].startsWith('##')) {
        parts.push('');
      }
      parts.push(`> [${cue}]`);
    }

    // 3. Output spoken narration paragraphs
    const spoken = scene.spokenText.trim();
    if (spoken) {
      if (parts.length > 0) parts.push('');
      parts.push(spoken);
    }
  }

  return parts.join('\n');
}
