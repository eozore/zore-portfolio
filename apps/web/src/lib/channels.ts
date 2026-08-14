/**
 * channels.ts — Registro canônico de canais/formatos de conteúdo do CSM Studio.
 *
 * Cada canal representa um "posicionamento" que o usuário pode ligar/desligar
 * na tela de Configurações → Canais & Formatos. O toggle é lido:
 *   1. Ao gerar derivações (/api/csm/package, /api/csm/derivatives) — formatos
 *      desligados são removidos do resultado antes de salvar na sessão.
 *   2. Ao aprovar o pacote (/api/csm/approve-package) — itens de canais
 *      desligados nunca são enfileirados para publicação, mesmo que o
 *      cliente tente enviá-los.
 *   3. Na revisão (ReviewTab) — sub-abas de canais desligados ficam ocultas.
 *
 * `implemented: false` marca formatos ainda sem agente/publisher (aparecem
 * na UI como "Em breve", desligados e não-editáveis) — mantém a lista
 * alinhada com o roadmap sem prometer o que o backend não entrega ainda.
 */

export type ChannelGroup =
  | 'blog'
  | 'youtube'
  | 'instagram'
  | 'linkedin_threads'
  | 'facebook_x'
  | 'newsletter_ads';

export interface ChannelDefinition {
  id: string;
  label: string;
  group: ChannelGroup;
  description: string;
  /** Chave usada nos arrays de repurposedData / specialistCopies retornados pelo cmo-agent. */
  dataKey: string | null;
  implemented: boolean;
}

export const CHANNEL_GROUPS: Record<ChannelGroup, string> = {
  blog: 'Blog',
  youtube: 'YouTube',
  instagram: 'Instagram',
  linkedin_threads: 'LinkedIn & Threads',
  facebook_x: 'Facebook & X',
  newsletter_ads: 'Newsletter & Anúncios',
};

export const CHANNEL_REGISTRY: ChannelDefinition[] = [
  { id: 'blog_article', label: 'Artigo de Blog', group: 'blog', description: 'Artigo técnico publicado em eozore.com/blog.', dataKey: null, implemented: true },

  { id: 'youtube_video', label: 'Vídeo YouTube (avatar)', group: 'youtube', description: 'Roteiro longo + avatar HeyGen + slides animados.', dataKey: null, implemented: true },
  { id: 'youtube_shorts', label: 'YouTube Shorts', group: 'youtube', description: 'Roteiros verticais curtos (30-60s).', dataKey: 'youtubeShorts', implemented: true },
  { id: 'youtube_community', label: 'Post Comunidade YouTube', group: 'youtube', description: 'Post de texto vinculado ao vídeo no YouTube.', dataKey: 'youtubeCommunityPosts', implemented: true },

  { id: 'instagram_reels', label: 'Reels', group: 'instagram', description: 'Vídeo vertical com avatar ou slides animados.', dataKey: 'reelsScripts', implemented: true },
  { id: 'instagram_stories', label: 'Stories', group: 'instagram', description: '10-12 stories sequenciais com interações.', dataKey: 'storiesIdeas', implemented: true },
  { id: 'instagram_feed', label: 'Post de Imagem (Feed)', group: 'instagram', description: 'Post estático com design sugerido.', dataKey: 'imagePosts', implemented: true },
  { id: 'instagram_carousel', label: 'Carrossel', group: 'instagram', description: 'Slides sequenciais de conteúdo educativo.', dataKey: 'carousels', implemented: true },

  { id: 'linkedin_text', label: 'Texto LinkedIn', group: 'linkedin_threads', description: 'Posts editoriais de alto engajamento técnico.', dataKey: 'linkedinPosts', implemented: true },
  { id: 'threads_posts', label: 'Threads (Meta)', group: 'linkedin_threads', description: 'Séries de posts encadeados.', dataKey: 'threads', implemented: true },

  { id: 'facebook_post', label: 'Post Facebook', group: 'facebook_x', description: 'Adaptação do post de LinkedIn para a Página Eozore.', dataKey: null, implemented: false },
  { id: 'x_post', label: 'Post no X (Twitter)', group: 'facebook_x', description: 'Thread curta adaptada para o X.', dataKey: null, implemented: false },

  { id: 'newsletter', label: 'Newsletter / E-mail', group: 'newsletter_ads', description: 'Resumo semanal enviado por e-mail (requer ESP integrado).', dataKey: null, implemented: false },
  { id: 'ads_copy', label: 'Copies para Anúncios', group: 'newsletter_ads', description: 'Variações de copy para campanhas pagas (Meta/Google Ads).', dataKey: null, implemented: false },
];

export type ChannelToggles = Record<string, boolean>;

export function defaultChannelToggles(): ChannelToggles {
  const toggles: ChannelToggles = {};
  for (const channel of CHANNEL_REGISTRY) {
    toggles[channel.id] = channel.implemented; // canais não implementados nascem desligados
  }
  return toggles;
}

/** Mescla toggles salvos com o registro atual, preservando defaults para canais novos. */
export function normalizeChannelToggles(saved: unknown): ChannelToggles {
  const defaults = defaultChannelToggles();
  if (!saved || typeof saved !== 'object') return defaults;
  const savedObj = saved as Record<string, unknown>;
  const merged: ChannelToggles = { ...defaults };
  for (const channel of CHANNEL_REGISTRY) {
    if (!channel.implemented) {
      merged[channel.id] = false; // nunca liga um canal ainda não implementado
      continue;
    }
    if (typeof savedObj[channel.id] === 'boolean') {
      merged[channel.id] = savedObj[channel.id] as boolean;
    }
  }
  return merged;
}

export function isChannelEnabled(toggles: ChannelToggles, channelId: string): boolean {
  const def = CHANNEL_REGISTRY.find((c) => c.id === channelId);
  if (!def) return true; // canal desconhecido (novo, ainda sem registro) — não bloqueia por padrão
  if (!def.implemented) return false;
  return toggles[channelId] !== false;
}

/**
 * Remove do objeto de derivações (repurposedData / specialistCopies) os arrays
 * cujo canal correspondente está desligado. Não muta o objeto original.
 */
export function filterDerivativesByChannels<T extends Record<string, unknown>>(
  data: T,
  toggles: ChannelToggles,
): T {
  const result: Record<string, unknown> = { ...data };
  for (const channel of CHANNEL_REGISTRY) {
    if (!channel.dataKey) continue;
    if (!isChannelEnabled(toggles, channel.id) && channel.dataKey in result) {
      result[channel.dataKey] = [];
    }
  }
  return result as T;
}
