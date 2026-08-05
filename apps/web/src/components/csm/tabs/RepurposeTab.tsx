'use client';
import { useState, useEffect } from 'react';
import type {
  DraftState, LinkedInDraft, YouTubeDraft, YouTubeShortsDraft,
  ReelDraft, CarouselDraft, ImageDraft, StoryDraft, AttachmentItem,
  ThreadDraft, YouTubeCommunityDraft,
} from '../CsmDashboard';
import EditorialCalendar, { type CalendarItem } from './EditorialCalendar';
import styles from './RepurposeTab.module.css';

interface RepurposeTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  sessionId: string;
  onBack: () => void;
}

// ── Ícones por plataforma ──────────────────────────────────────────────────────
const PLATFORM_ICON: Record<string, string> = {
  linkedin: '💼', youtube: '▶️', youtube_community: '🎬',
  instagram: '📷', threads: '🧵', facebook: '👥',
};
const PLATFORM_LABEL: Record<string, string> = {
  linkedin: 'LinkedIn', youtube: 'YouTube', youtube_community: 'YouTube Community',
  instagram: 'Instagram', threads: 'Threads',
};

// ── Componente de banner de erros da fila ─────────────────────────────────────
interface QueueError { id?: string; platform: string; title: string; errorCode?: string | null; error?: string | null; scheduledAt?: string; }

function QueueErrorBanner({ errors, onDismiss, onRetry }: { errors: QueueError[]; onDismiss: (id: string) => void; onRetry: (id: string) => void }) {
  if (!errors.length) return null;
  return (
    <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '12px', padding: '16px', marginBottom: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <span style={{ fontSize: '1rem' }}>⚠️</span>
        <span style={{ color: '#f87171', fontWeight: 800, fontSize: '0.95rem' }}>{errors.length} publicação(ões) falharam na fila</span>
      </div>
      {errors.map((e, i) => (
        <div key={e.id || i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', marginBottom: '6px', gap: '12px', flexWrap: 'wrap' }}>
          <div>
            <span style={{ color: '#fca5a5', fontWeight: 'bold', fontSize: '0.82rem' }}>{PLATFORM_ICON[e.platform]} {PLATFORM_LABEL[e.platform] || e.platform}</span>
            <span style={{ color: '#94a3b8', fontSize: '0.78rem', marginLeft: '8px' }}>{e.title?.slice(0, 50)}</span>
            {e.errorCode && <span style={{ marginLeft: '8px', background: 'rgba(239,68,68,0.2)', color: '#fca5a5', fontSize: '0.68rem', padding: '2px 6px', borderRadius: '4px', fontFamily: 'monospace' }}>{e.errorCode}</span>}
            {e.error && <div style={{ color: '#94a3b8', fontSize: '0.72rem', marginTop: '2px' }}>{e.error.slice(0, 100)}</div>}
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            {e.id && <button onClick={() => onRetry(e.id!)} style={{ background: '#f59e0b', color: '#000', border: 'none', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 'bold', cursor: 'pointer' }}>Retentar</button>}
            {e.id && <button onClick={() => onDismiss(e.id!)} style={{ background: 'transparent', color: '#94a3b8', border: '1px solid #475569', padding: '4px 10px', borderRadius: '6px', fontSize: '0.72rem', cursor: 'pointer' }}>Cancelar</button>}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function RepurposeTab({ draft, updateDraft, sessionId, onBack }: RepurposeTabProps) {
  const data = draft.repurposedData;
  const [viewMode, setViewMode] = useState<'calendar' | 'list'>('calendar');
  const [attachments, setAttachments] = useState<AttachmentItem[]>(draft.attachments || []);
  const [newAttUrl, setNewAttUrl] = useState('');
  const [newAttName, setNewAttName] = useState('');

  // ── State por tipo de conteúdo ─────────────────────────────────────────────
  const [linkedinPosts, setLinkedinPosts] = useState<LinkedInDraft[]>([]);
  const [ytCommunityPosts, setYtCommunityPosts] = useState<YouTubeCommunityDraft[]>([]);
  const [ytScripts, setYtScripts] = useState<YouTubeDraft[]>([]);
  const [ytShortsScripts, setYtShortsScripts] = useState<YouTubeShortsDraft[]>([]);
  const [reelsScripts, setReelsScripts] = useState<ReelDraft[]>([]);
  const [carousels, setCarousels] = useState<CarouselDraft[]>([]);
  const [imagePosts, setImagePosts] = useState<ImageDraft[]>([]);
  const [storiesIdeas, setStoriesIdeas] = useState<StoryDraft[]>([]);
  const [threads, setThreads] = useState<ThreadDraft[]>([]);

  // ── State de geração (vídeos + imagens) ────────────────────────────────────
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({});
  const [generatingStates, setGeneratingStates] = useState<Record<string, boolean>>({});
  const [generatingProgress, setGeneratingProgress] = useState<Record<string, number>>({});
  const [videoSteps, setVideoSteps] = useState<Record<string, number>>({});
  const [avatarVideoUrls, setAvatarVideoUrls] = useState<Record<string, string>>({});
  const [motionVideoUrls, setMotionVideoUrls] = useState<Record<string, string>>({});
  const [videoErrors, setVideoErrors] = useState<Record<string, string>>({});
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});

  // ── State da fila de publicação ────────────────────────────────────────────
  const [queueErrors, setQueueErrors] = useState<QueueError[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successResult, setSuccessResult] = useState<{ totalApproved: number; videoPipelineTriggered?: number; socialQueueSaved?: number } | null>(null);

  // ── Carrega fila com erros ao montar ───────────────────────────────────────
  useEffect(() => {
    if (!sessionId) return;
    fetch(`/api/csm/publish-queue?sessionId=${sessionId}&status=failed`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.errors) setQueueErrors(d.errors); })
      .catch(() => {});
  }, [sessionId]);

  // ── Inicializa estados a partir dos dados derivados ────────────────────────
  useEffect(() => {
    if (!data) return;
    const now = new Date();
    const getISO = (daysAdd: number, hour: number) => {
      const d = new Date(now);
      d.setDate(d.getDate() + daysAdd);
      d.setHours(hour, 0, 0, 0);
      return d.toISOString();
    };
    const initImgUrls: Record<string, string> = {};
    data.youtubeShorts?.forEach(ys => { if ((ys as any).videoUrl) initImgUrls[`yts_${ys.id}`] = (ys as any).videoUrl; });
    data.reelsScripts?.forEach(r => { if ((r as any).videoUrl) initImgUrls[`re_${r.id}`] = (r as any).videoUrl; });
    data.linkedinPosts?.forEach(p => { if (p.imageUrl) initImgUrls[`li_${p.id}`] = p.imageUrl; });
    data.imagePosts?.forEach(im => { if (im.imageUrl) initImgUrls[`img_${im.id}`] = im.imageUrl; });
    setVideoUrls(initImgUrls);

    setLinkedinPosts(data.linkedinPosts?.map((p, i) => ({ ...p, status: p.status || 'em_revisao', scheduledAt: p.scheduledAt || getISO((i % 5) + 1, 9) })) || []);
    setYtCommunityPosts(data.youtubeCommunityPosts?.map((p, i) => ({ ...p, status: p.status || 'em_revisao', scheduledAt: p.scheduledAt || getISO((i % 5) + 2, 10) })) || []);
    setYtScripts(draft.youtubeScript ? [{ id: 'yt-long-1', title: draft.suggestedTitle || 'Deep Dive YouTube', script: draft.youtubeScript, status: 'aprovado', scheduledAt: getISO(1, 10) }] : []);
    setYtShortsScripts(data.youtubeShorts?.map((ys, i) => ({ ...ys, status: ys.status || 'em_revisao', scheduledAt: ys.scheduledAt || getISO((i % 5) + 1, 15) })) || []);
    setReelsScripts(data.reelsScripts?.map((r, i) => ({ ...r, status: r.status || 'em_revisao', scheduledAt: r.scheduledAt || getISO((i % 5) + 1, 12) })) || []);
    setCarousels(data.carousels?.map((c, i) => ({ ...c, status: c.status || 'em_revisao', scheduledAt: c.scheduledAt || getISO((i % 5) + 1, 14) })) || []);
    setImagePosts(data.imagePosts?.map((im, i) => ({ ...im, status: im.status || 'em_revisao', scheduledAt: im.scheduledAt || getISO((i % 5) + 1, 11) })) || []);
    setStoriesIdeas(data.storiesIdeas?.map((s, i) => ({ ...s, status: s.status || 'em_revisao', scheduledAt: s.scheduledAt || getISO((i % 5) + 1, 8 + (i % 12)) })) || []);
    setThreads(data.threads?.map((t, i) => ({ ...t, status: t.status || 'em_revisao', scheduledAt: (t as any).scheduledAt || getISO((i % 5) + 2, 13) })) || []);
  }, [data, draft.youtubeScript, draft.suggestedTitle]);

  // ── Geração de imagem via HTML + Playwright ────────────────────────────────
  const handleRenderHtmlImage = async (itemId: string, html: string, width: number, height: number, fallbackTitle: string) => {
    if (generatingStates[itemId] || imageUrls[itemId]) return;
    setGeneratingStates(prev => ({ ...prev, [itemId]: true }));
    setGeneratingProgress(prev => ({ ...prev, [itemId]: 20 }));
    try {
      const res = await fetch('/api/csm/render-html-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html, width, height, sessionId, itemId, fallbackTitle }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Erro ao iniciar render HTML');
      const jobId = d.jobId;
      await new Promise<void>((resolve, reject) => {
        let attempts = 0;
        const poll = setInterval(async () => {
          attempts++;
          try {
            const pr = await fetch(`/api/csm/render-html-image?jobId=${jobId}`);
            const pd = await pr.json();
            if (pd.status === 'completed') {
              clearInterval(poll);
              setImageUrls(prev => ({ ...prev, [itemId]: pd.imageUrl }));
              setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 }));
              resolve();
            } else if (pd.status === 'failed') {
              clearInterval(poll);
              reject(new Error(pd.error || 'Render HTML falhou'));
            } else {
              setGeneratingProgress(prev => ({ ...prev, [itemId]: Math.min(90, attempts * 20) }));
            }
          } catch (e) { clearInterval(poll); reject(e); }
        }, 2000);
      });
    } catch (err: any) {
      alert(err.message || 'Falha ao renderizar imagem');
    } finally {
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));
    }
  };

  // ── Geração de vídeo HeyGen (3 passos) ────────────────────────────────────
  const handleGenerateVideo = async (itemId: string, script: string, format: string) => {
    if (generatingStates[itemId] || videoUrls[itemId]) return;
    setGeneratingStates(prev => ({ ...prev, [itemId]: true }));
    setVideoSteps(prev => ({ ...prev, [itemId]: 1 }));
    setGeneratingProgress(prev => ({ ...prev, [itemId]: 10 }));
    setVideoErrors(prev => ({ ...prev, [itemId]: '' }));
    try {
      const res = await fetch('/api/csm/heygen', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script, format, avatarProfile: format === 'shorts' || format === 'reel' ? 'vertical' : 'horizontal', id: itemId }) });
      const rd = await res.json();
      if (!res.ok) throw new Error(rd.error || 'Erro HeyGen');
      const videoId = rd.videoId;
      let avatarVideoUrl = '';
      await new Promise<void>((resolve, reject) => {
        let att = 0;
        const poll = setInterval(async () => {
          att++;
          try {
            const pr = await fetch(`/api/csm/heygen?videoId=${videoId}`);
            const pd = await pr.json();
            if (!pr.ok) { clearInterval(poll); reject(new Error(pd.error)); return; }
            if (pd.status === 'completed') { clearInterval(poll); avatarVideoUrl = pd.videoUrl; setAvatarVideoUrls(prev => ({ ...prev, [itemId]: avatarVideoUrl })); setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 })); resolve(); }
            else if (pd.status === 'failed') { clearInterval(poll); reject(new Error('HeyGen falhou')); }
            else setGeneratingProgress(prev => ({ ...prev, [itemId]: pd.progress || Math.min(95, att * 25) }));
          } catch (e) { clearInterval(poll); reject(e); }
        }, 3000);
      });
      setVideoSteps(prev => ({ ...prev, [itemId]: 2 })); setGeneratingProgress(prev => ({ ...prev, [itemId]: 10 }));
      const mr = await fetch('/api/csm/render-motion', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ itemId, scenes: script, sessionId }) });
      const md = await mr.json();
      if (!mr.ok) throw new Error(md.error || 'Erro render-motion');
      let motionVideoUrl = '';
      await new Promise<void>((resolve, reject) => {
        let att = 0;
        const poll = setInterval(async () => {
          att++;
          try {
            const pr = await fetch(`/api/csm/render-motion?jobId=${md.jobId}`);
            const pd = await pr.json();
            if (pd.status === 'completed') { clearInterval(poll); motionVideoUrl = pd.motionUrl; setMotionVideoUrls(prev => ({ ...prev, [itemId]: motionVideoUrl })); setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 })); resolve(); }
            else if (pd.status === 'failed') { clearInterval(poll); reject(new Error('Motion falhou')); }
            else setGeneratingProgress(prev => ({ ...prev, [itemId]: Math.min(95, att * 25) }));
          } catch (e) { clearInterval(poll); reject(e); }
        }, 3000);
      });
      setVideoSteps(prev => ({ ...prev, [itemId]: 3 })); setGeneratingProgress(prev => ({ ...prev, [itemId]: 10 }));
      const mgr = await fetch('/api/csm/merge-video', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ avatarVideoUrl, motionVideoUrl, sessionId, script }) });
      const mgd = await mgr.json();
      if (!mgr.ok) throw new Error(mgd.error || 'Erro merge-video');
      let finalVideoUrl = '';
      await new Promise<void>((resolve, reject) => {
        let att = 0;
        const poll = setInterval(async () => {
          att++;
          try {
            const pr = await fetch(`/api/csm/merge-video?jobId=${mgd.jobId}`);
            const pd = await pr.json();
            if (pd.status === 'completed') { clearInterval(poll); finalVideoUrl = pd.mergedVideoUrl; setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 })); resolve(); }
            else if (pd.status === 'failed') { clearInterval(poll); reject(new Error('Merge falhou')); }
            else setGeneratingProgress(prev => ({ ...prev, [itemId]: Math.min(95, att * 25) }));
          } catch (e) { clearInterval(poll); reject(e); }
        }, 3000);
      });
      setVideoUrls(prev => ({ ...prev, [itemId]: finalVideoUrl }));
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));
    } catch (err: any) {
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));
      setVideoErrors(prev => ({ ...prev, [itemId]: err.message }));
    }
  };

  const handleRetryMerge = async (itemId: string, script: string, format: string) => {
    const avatarVideoUrl = avatarVideoUrls[itemId];
    const motionVideoUrl = motionVideoUrls[itemId];
    if (!avatarVideoUrl || !motionVideoUrl) { alert('Faltam URLs intermediários para retentar a fusão.'); return; }
    setGeneratingStates(prev => ({ ...prev, [itemId]: true }));
    setVideoSteps(prev => ({ ...prev, [itemId]: 3 }));
    setGeneratingProgress(prev => ({ ...prev, [itemId]: 10 }));
    try {
      const r = await fetch('/api/csm/retry-merge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ avatarVideoUrl, motionVideoUrl, sessionId, script, format }) });
      const rd = await r.json();
      if (!r.ok) throw new Error(rd.error || 'Erro retry-merge');
      let finalVideoUrl = '';
      await new Promise<void>((resolve, reject) => {
        let att = 0;
        const poll = setInterval(async () => {
          att++;
          try {
            const pr = await fetch(`/api/csm/retry-merge?jobId=${rd.jobId}`);
            const pd = await pr.json();
            if (pd.status === 'completed') { clearInterval(poll); finalVideoUrl = pd.mergedVideoUrl; setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 })); resolve(); }
            else if (pd.status === 'failed') { clearInterval(poll); reject(new Error('Retry merge falhou')); }
            else setGeneratingProgress(prev => ({ ...prev, [itemId]: Math.min(95, att * 25) }));
          } catch (e) { clearInterval(poll); reject(e); }
        }, 3000);
      });
      setVideoUrls(prev => ({ ...prev, [itemId]: finalVideoUrl }));
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));
    } catch (err: any) {
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));
      setVideoErrors(prev => ({ ...prev, [itemId]: err.message }));
    }
  };

  // ── Handlers de fila de publicação ────────────────────────────────────────
  const handleDismissQueueError = async (id: string) => {
    try {
      await fetch('/api/csm/publish-queue', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, action: 'cancel' }) });
      setQueueErrors(prev => prev.filter(e => e.id !== id));
    } catch { setQueueErrors(prev => prev.filter(e => e.id !== id)); }
  };

  const handleRetryQueueItem = async (id: string) => {
    try {
      await fetch('/api/csm/publish-queue', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, action: 'retry' }) });
      setQueueErrors(prev => prev.filter(e => e.id !== id));
    } catch { alert('Falha ao retentar item da fila'); }
  };

  // ── Handlers de update de itens ────────────────────────────────────────────
  const handleUpdateUnifiedItem = (unifiedId: string, partial: Partial<CalendarItem>) => {
    const sep = unifiedId.indexOf('_');
    const prefix = unifiedId.slice(0, sep);
    const rawId = unifiedId.slice(sep + 1);
    const st = partial.status; const dt = partial.scheduledAt; const txt = partial.copy; const title = partial.titleOrHook;
    if (prefix === 'li') setLinkedinPosts(prev => prev.map(p => p.id === rawId ? { ...p, ...(st && { status: st }), ...(dt && { scheduledAt: dt }), ...(txt && { copy: txt }), ...(title && { hook: title }) } : p));
    else if (prefix === 'ytc') setYtCommunityPosts(prev => prev.map(p => p.id === rawId ? { ...p, ...(st && { status: st }), ...(dt && { scheduledAt: dt }), ...(txt && { copy: txt }) } : p));
    else if (prefix === 'yt') setYtScripts(prev => prev.map(y => y.id === rawId ? { ...y, ...(st && { status: st }), ...(dt && { scheduledAt: dt }), ...(txt && { script: txt }), ...(title && { title }) } : y));
    else if (prefix === 'yts') setYtShortsScripts(prev => prev.map(ys => ys.id === rawId ? { ...ys, ...(st && { status: st }), ...(dt && { scheduledAt: dt }), ...(txt && { script: txt }), ...(title && { title }) } : ys));
    else if (prefix === 're') setReelsScripts(prev => prev.map(r => r.id === rawId ? { ...r, ...(st && { status: st }), ...(dt && { scheduledAt: dt }), ...(txt && { script: txt }), ...(title && { title }) } : r));
    else if (prefix === 'ca') setCarousels(prev => prev.map(c => c.id === rawId ? { ...c, ...(st && { status: st }), ...(dt && { scheduledAt: dt }), ...(txt && { caption: txt }), ...(title && { title }) } : c));
    else if (prefix === 'img') setImagePosts(prev => prev.map(im => im.id === rawId ? { ...im, ...(st && { status: st }), ...(dt && { scheduledAt: dt }), ...(txt && { copy: txt }), ...(title && { title }) } : im));
    else if (prefix === 'st') setStoriesIdeas(prev => prev.map(s => s.id === rawId ? { ...s, ...(st && { status: st }), ...(dt && { scheduledAt: dt }), ...(txt && { copy: txt }) } : s));
    else if (prefix === 'th') setThreads(prev => prev.map(t => t.id === rawId ? { ...t, ...(st && { status: st }), ...(dt && { scheduledAt: dt }) } : t));
  };

  // ── Handlers de anexos ─────────────────────────────────────────────────────
  const handleAddAttachment = () => {
    if (!newAttUrl.startsWith('https://')) { alert('URL deve começar com https://'); return; }
    const item: AttachmentItem = { id: Math.random().toString(36).slice(2, 9), name: newAttName || 'Anexo', url: newAttUrl, type: newAttUrl.endsWith('.pdf') ? 'pdf' : 'image', tags: ['artigo', 'linkedin'] };
    const next = [...attachments, item];
    setAttachments(next); updateDraft({ attachments: next }); setNewAttUrl(''); setNewAttName('');
  };

  const handleToggleAttTag = (attId: string, tag: 'artigo' | 'linkedin' | 'carrossel' | 'youtube' | 'reels' | 'stories') => {
    const next = attachments.map(a => { if (a.id !== attId) return a; const has = a.tags.includes(tag); return { ...a, tags: has ? a.tags.filter(t => t !== tag) : [...a.tags, tag] }; });
    setAttachments(next); updateDraft({ attachments: next });
  };

  // ── Montagem do CalendarItem[] ─────────────────────────────────────────────
  const allCalendarItems: CalendarItem[] = [
    ...linkedinPosts.map(p => ({
      id: `li_${p.id}`, platform: 'linkedin' as const, format: 'image' as const,
      titleOrHook: p.hook, copy: p.copy, scheduledAt: p.scheduledAt || new Date().toISOString(),
      status: p.status, articleTitle: draft.suggestedTitle,
      imageUrl: imageUrls[`li_${p.id}`] || p.imageUrl,
      imageHtml: p.imageHtml,
      isGenerating: generatingStates[`li_${p.id}`],
      progress: generatingProgress[`li_${p.id}`],
      onRenderHtmlImage: p.imageHtml ? () => handleRenderHtmlImage(`li_${p.id}`, p.imageHtml!, 1200, 628, p.hook) : undefined,
    })),
    ...ytCommunityPosts.map(p => ({
      id: `ytc_${p.id}`, platform: 'youtube_community' as const, format: 'community_post' as const,
      titleOrHook: 'YouTube Community', copy: p.copy, scheduledAt: p.scheduledAt || new Date().toISOString(),
      status: p.status,
    })),
    ...ytScripts.map(y => ({
      id: `yt_${y.id}`, platform: 'youtube' as const, format: 'video' as const,
      titleOrHook: y.title, copy: y.script, scheduledAt: y.scheduledAt || new Date().toISOString(), status: y.status,
    })),
    ...ytShortsScripts.map(ys => ({
      id: `yts_${ys.id}`, platform: 'youtube' as const, format: 'shorts' as const,
      titleOrHook: ys.title, copy: ys.script, scheduledAt: ys.scheduledAt || new Date().toISOString(),
      status: ys.status, hook3s: ys.hook3s,
      videoUrl: videoUrls[`yts_${ys.id}`], isGenerating: generatingStates[`yts_${ys.id}`],
      progress: generatingProgress[`yts_${ys.id}`], avatarVideoUrl: avatarVideoUrls[`yts_${ys.id}`],
      motionVideoUrl: motionVideoUrls[`yts_${ys.id}`], videoError: videoErrors[`yts_${ys.id}`],
      onGenerateVideo: () => handleGenerateVideo(`yts_${ys.id}`, ys.script, 'shorts'),
      onRetryMerge: () => handleRetryMerge(`yts_${ys.id}`, ys.script, 'shorts'),
    })),
    ...reelsScripts.map(r => ({
      id: `re_${r.id}`, platform: 'instagram' as const, format: 'reel' as const,
      titleOrHook: r.title, copy: r.script, scheduledAt: r.scheduledAt || new Date().toISOString(),
      status: r.status, hook3s: r.hook3s, visualCue: r.visualCue,
      videoUrl: videoUrls[`re_${r.id}`], isGenerating: generatingStates[`re_${r.id}`],
      progress: generatingProgress[`re_${r.id}`], avatarVideoUrl: avatarVideoUrls[`re_${r.id}`],
      motionVideoUrl: motionVideoUrls[`re_${r.id}`], videoError: videoErrors[`re_${r.id}`],
      onGenerateVideo: () => handleGenerateVideo(`re_${r.id}`, r.script, 'reel'),
      onRetryMerge: () => handleRetryMerge(`re_${r.id}`, r.script, 'reel'),
    })),
    ...carousels.map(c => ({
      id: `ca_${c.id}`, platform: 'instagram' as const, format: 'carousel' as const,
      titleOrHook: c.title, copy: c.caption, scheduledAt: c.scheduledAt || new Date().toISOString(),
      status: c.status, slides: c.slides,
    })),
    ...imagePosts.map(im => ({
      id: `img_${im.id}`, platform: 'instagram' as const, format: 'post_imagem' as const,
      titleOrHook: im.title, copy: im.copy, scheduledAt: im.scheduledAt || new Date().toISOString(),
      status: im.status, imageDescription: im.imageDescription,
      imageUrl: imageUrls[`img_${im.id}`] || im.imageUrl,
      imageHtml: im.imageHtml,
      isGenerating: generatingStates[`img_${im.id}`],
      progress: generatingProgress[`img_${im.id}`],
      onRenderHtmlImage: im.imageHtml ? () => handleRenderHtmlImage(`img_${im.id}`, im.imageHtml!, 1080, 1080, im.title) : undefined,
    })),
    ...storiesIdeas.map(s => ({
      id: `st_${s.id}`, platform: 'instagram' as const, format: 'story' as const,
      titleOrHook: s.interactiveElement || s.angle, copy: `${s.day}: ${s.copy}`,
      scheduledAt: s.scheduledAt || new Date().toISOString(), status: s.status,
    })),
    ...threads.map(t => ({
      id: `th_${t.id}`, platform: 'threads' as const, format: 'thread' as const,
      titleOrHook: t.topic, copy: t.posts.join('\n\n---\n\n'),
      scheduledAt: (t as any).scheduledAt || new Date().toISOString(), status: t.status,
      threadPosts: t.posts, threadNumber: t.threadNumber,
    })),
  ];

  // ── Submit para fila ───────────────────────────────────────────────────────
  const handleScheduleApproved = async () => {
    setIsSubmitting(true);
    setSuccessResult(null);
    const approved = allCalendarItems.filter(ci => ci.status === 'aprovado');
    if (!approved.length) { setIsSubmitting(false); return; }
    const queueItems = approved.map(ci => ({
      sessionId, articleSlug: draft.suggestedSlug || 'artigo',
      articleTitle: draft.suggestedTitle || 'Artigo éozoré',
      platform: ci.platform as any, format: ci.format as any,
      title: ci.titleOrHook, copy: ci.copy,
      imageUrl: ci.imageUrl || null, imageHtml: ci.imageHtml || null,
      videoUrl: ci.videoUrl || null, slides: ci.slides || null,
      scheduledAt: ci.scheduledAt,
    }));
    try {
      // 1. Adiciona à fila de publicação
      const qRes = await fetch('/api/csm/publish-queue', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId, articleSlug: draft.suggestedSlug, articleTitle: draft.suggestedTitle, items: queueItems }),
      });
      const qData = await qRes.json();
      if (!qRes.ok) throw new Error(qData.error || 'Falha ao adicionar à fila');
      // 2. Dispara pipeline de vídeo para vídeos aprovados
      const VIDEO_FORMATS = new Set(['shorts', 'reel', 'video']);
      const videoItems = approved.filter(ci => VIDEO_FORMATS.has(ci.format) && ci.copy.trim().length > 50);
      let videoPipelineTriggered = 0;
      if (videoItems.length > 0 || draft.youtubeScript) {
        const pRes = await fetch('/api/csm/pipeline-submit', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ articleSlug: draft.suggestedSlug, articleTitle: draft.suggestedTitle, youtubeScript: draft.youtubeScript, sessionId, items: approved.map(ci => ({ ...ci, title: ci.titleOrHook, script: ci.copy, status: ci.status })) }),
        });
        const pData = await pRes.json();
        if (pRes.ok) videoPipelineTriggered = pData.videoPipelineTriggered || 0;
      }
      setSuccessResult({ totalApproved: approved.length, videoPipelineTriggered, socialQueueSaved: qData.count });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Erro ao enviar para fila');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Guard: sem dados ───────────────────────────────────────────────────────
  if (!data) {
    return (
      <div className={styles.card} style={{ textAlign: 'center', padding: '60px' }}>
        <h2 style={{ color: '#fff', marginBottom: '16px' }}>Nenhuma Derivação Gerada</h2>
        <p style={{ color: '#cbd5e1', marginBottom: '24px' }}>Volte à aba YouTube e clique em &quot;Avançar para Mídias Sociais&quot;.</p>
        <button onClick={onBack} className={styles.scheduleBtn} style={{ maxWidth: '300px', margin: '0 auto' }}>← Voltar</button>
      </div>
    );
  }

  const approvedCount = allCalendarItems.filter(i => i.status === 'aprovado').length;

  // ── Resumo de plataformas ──────────────────────────────────────────────────
  const platformSummary = allCalendarItems.reduce<Record<string, number>>((acc, item) => {
    acc[item.platform] = (acc[item.platform] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className={styles.mainCol} style={{ gap: '24px' }}>

      {/* Banner de erros da fila */}
      <QueueErrorBanner errors={queueErrors} onDismiss={handleDismissQueueError} onRetry={handleRetryQueueItem} />

      {/* Header */}
      <div className={styles.card} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ color: '#fff', fontSize: '1.4rem', fontWeight: 800 }}>Calendário Editorial</h1>
          <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '4px' }}>
            {allCalendarItems.length} peças geradas · {approvedCount} aprovadas
          </p>
          {/* Resumo por plataforma */}
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
            {Object.entries(platformSummary).map(([platform, count]) => (
              <span key={platform} style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '20px', padding: '3px 10px', fontSize: '0.75rem', color: '#cbd5e1' }}>
                {PLATFORM_ICON[platform]} {PLATFORM_LABEL[platform] || platform} <strong style={{ color: '#fff' }}>{count}</strong>
              </span>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          {(['calendar', 'list'] as const).map(mode => (
            <button key={mode} onClick={() => setViewMode(mode)}
              style={{ padding: '9px 16px', borderRadius: '10px', border: '1px solid #e67e22', background: viewMode === mode ? '#e67e22' : 'transparent', color: viewMode === mode ? '#000' : '#e67e22', fontWeight: 'bold', cursor: 'pointer', fontSize: '0.85rem' }}>
              {mode === 'calendar' ? '📅 Calendário' : '📋 Lista'}
            </button>
          ))}
        </div>
      </div>

      {/* Biblioteca de anexos */}
      <div className={styles.card}>
        <h2 style={{ color: '#f5a962', fontSize: '1rem', fontWeight: 800, marginBottom: '12px' }}>Biblioteca de Anexos</h2>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '12px', flexWrap: 'wrap' }}>
          <input type="text" value={newAttName} onChange={e => setNewAttName(e.target.value)} placeholder="Nome do anexo" style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', padding: '7px 12px', borderRadius: '8px', fontSize: '0.82rem' }} />
          <input type="text" value={newAttUrl} onChange={e => setNewAttUrl(e.target.value)} placeholder="https://..." style={{ flex: 1, minWidth: '200px', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', padding: '7px 12px', borderRadius: '8px', fontSize: '0.82rem' }} />
          <button onClick={handleAddAttachment} style={{ background: '#f5a962', color: '#000', fontWeight: 'bold', border: 'none', padding: '7px 14px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.82rem' }}>+ Anexar</button>
        </div>
        {attachments.length > 0 && (
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {attachments.map(att => (
              <div key={att.id} style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)', padding: '10px 14px', borderRadius: '10px', fontSize: '0.8rem' }}>
                <div style={{ color: '#fff', fontWeight: 'bold' }}>{att.name}</div>
                <a href={att.url} target="_blank" rel="noopener noreferrer" style={{ color: '#38bdf8', fontSize: '0.72rem' }}>{att.url.slice(0, 30)}…</a>
                <div style={{ display: 'flex', gap: '4px', marginTop: '6px', flexWrap: 'wrap' }}>
                  {(['artigo', 'linkedin', 'carrossel', 'youtube', 'reels', 'stories'] as const).map(t => {
                    const on = att.tags.includes(t);
                    return <button key={t} onClick={() => handleToggleAttTag(att.id, t)} style={{ fontSize: '0.62rem', padding: '2px 5px', borderRadius: '4px', border: '1px solid rgba(255,255,255,0.1)', background: on ? '#2ecc71' : 'transparent', color: on ? '#000' : '#94a3b8', cursor: 'pointer', fontWeight: 'bold' }}>{on ? '✓ ' : ''}{t}</button>;
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Conteúdo principal: Calendário ou Lista */}
      {viewMode === 'calendar' ? (
        <EditorialCalendar items={allCalendarItems} onUpdateItem={handleUpdateUnifiedItem} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {allCalendarItems.map(item => {
            const isVideo = item.format === 'reel' || item.format === 'shorts';
            const isThread = item.format === 'thread';
            const hasHtmlImage = !!item.imageHtml && !item.imageUrl;
            const isGen = generatingStates[item.id];
            return (
              <div key={item.id} className={styles.itemBox}>
                {/* Header do item */}
                <div className={styles.itemMetaRow}>
                  <span style={{ color: '#f5a962', fontWeight: 'bold', fontSize: '0.85rem' }}>
                    {PLATFORM_ICON[item.platform]} {PLATFORM_LABEL[item.platform] || item.platform} · {item.format.toUpperCase()}
                  </span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                    {/* Botão geração de vídeo */}
                    {isVideo && !item.videoUrl && !isGen && (
                      <button onClick={item.onGenerateVideo} style={{ background: 'linear-gradient(135deg,#7c3aed,#5b21b6)', color: '#fff', border: 'none', padding: '5px 10px', borderRadius: '7px', fontSize: '0.72rem', fontWeight: 'bold', cursor: 'pointer' }}>
                        ⚡ Gerar Vídeo
                      </button>
                    )}
                    {/* Botão geração de imagem HTML */}
                    {hasHtmlImage && !isGen && (
                      <button onClick={item.onRenderHtmlImage} style={{ background: 'linear-gradient(135deg,#0ea5e9,#0284c7)', color: '#fff', border: 'none', padding: '5px 10px', borderRadius: '7px', fontSize: '0.72rem', fontWeight: 'bold', cursor: 'pointer' }}>
                        🖼 Gerar Imagem
                      </button>
                    )}
                    {/* Progress bar */}
                    {isGen && (
                      <span style={{ fontSize: '0.72rem', color: '#7c3aed' }}>
                        {isVideo
                          ? `Passo ${videoSteps[item.id] || 1}/3 — ${item.progress || 0}%`
                          : `Renderizando — ${generatingProgress[item.id] || 0}%`}
                      </span>
                    )}
                    {/* Botões de status */}
                    <button onClick={() => handleUpdateUnifiedItem(item.id, { status: 'em_revisao' })} style={{ background: item.status === 'em_revisao' ? '#fbbf24' : 'transparent', color: item.status === 'em_revisao' ? '#000' : '#fbbf24', border: '1px solid #fbbf24', padding: '4px 8px', borderRadius: '6px', fontWeight: 'bold', fontSize: '0.72rem', cursor: 'pointer' }}>Revisão</button>
                    <button onClick={() => handleUpdateUnifiedItem(item.id, { status: 'aprovado' })} style={{ background: item.status === 'aprovado' ? '#2ecc71' : 'transparent', color: item.status === 'aprovado' ? '#000' : '#2ecc71', border: '1px solid #2ecc71', padding: '4px 8px', borderRadius: '6px', fontWeight: 'bold', fontSize: '0.72rem', cursor: 'pointer' }}>Aprovar</button>
                  </div>
                </div>

                {/* Preview de imagem gerada */}
                {item.imageUrl && (
                  <div style={{ marginBottom: '10px' }}>
                    <img src={item.imageUrl} alt="Preview" style={{ maxWidth: '100%', maxHeight: '200px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }} />
                  </div>
                )}

                {/* Preview de vídeo */}
                {item.videoUrl && (
                  <div style={{ marginBottom: '10px', background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.15)', padding: '10px', borderRadius: '8px' }}>
                    <video src={item.videoUrl} controls style={{ width: '100%', maxHeight: '200px', borderRadius: '6px' }} />
                    <a href={item.videoUrl} download={`eozore-${item.id}.mp4`} target="_blank" rel="noopener noreferrer"
                      style={{ display: 'inline-block', marginTop: '8px', background: '#10b981', color: '#fff', padding: '5px 10px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 'bold', textDecoration: 'none' }}>
                      📥 Download MP4
                    </a>
                  </div>
                )}

                {/* Threads: posts sequenciais */}
                {isThread && item.threadPosts && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '10px' }}>
                    <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 'bold', marginBottom: '4px' }}>🧵 Thread #{item.threadNumber} — {item.threadPosts.length} posts</div>
                    {item.threadPosts.map((post, idx) => (
                      <div key={idx} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', padding: '8px 12px', fontSize: '0.8rem', color: '#e2e8f0' }}>
                        <span style={{ color: '#64748b', fontSize: '0.68rem', fontWeight: 'bold', display: 'block', marginBottom: '4px' }}>Post {idx + 1}/{item.threadPosts!.length}</span>
                        {post}
                      </div>
                    ))}
                  </div>
                )}

                {/* YouTube Community: badge de referência */}
                {item.format === 'community_post' && (
                  <div style={{ background: 'rgba(255,0,0,0.06)', border: '1px solid rgba(255,0,0,0.15)', borderRadius: '6px', padding: '6px 10px', marginBottom: '8px', fontSize: '0.75rem', color: '#fca5a5' }}>
                    🎬 Espelho do LinkedIn — adaptado para inscritos do canal
                  </div>
                )}

                {/* Copy editável (exceto threads que têm UI própria) */}
                {!isThread && (
                  <textarea
                    value={item.copy}
                    onChange={e => handleUpdateUnifiedItem(item.id, { copy: e.target.value })}
                    className={styles.textarea}
                    rows={4}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Barra de submit sticky */}
      <div className={styles.card} style={{ position: 'sticky', bottom: '24px', background: '#0f172a', border: '2px solid #e67e22', boxShadow: '0 -10px 30px rgba(0,0,0,0.8)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <span style={{ color: '#fff', fontWeight: 800, fontSize: '1.1rem' }}>Enviar para a Fila de Publicação</span>
          <div style={{ color: '#94a3b8', fontSize: '0.82rem', marginTop: '4px' }}>
            <strong style={{ color: '#2ecc71' }}>{approvedCount}</strong> de <strong>{allCalendarItems.length}</strong> aprovados
            {queueErrors.length > 0 && <span style={{ marginLeft: '12px', color: '#f87171' }}>· ⚠️ {queueErrors.length} erro(s) na fila</span>}
          </div>
        </div>
        {successResult ? (
          <div style={{ color: '#2ecc71', fontWeight: 'bold', fontSize: '0.9rem', textAlign: 'right' }}>
            ✅ {successResult.totalApproved} peças na fila
            {successResult.videoPipelineTriggered ? <><br /><span style={{ color: '#a78bfa', fontSize: '0.8rem' }}>⚡ {successResult.videoPipelineTriggered} vídeos no pipeline</span></> : ''}
            {successResult.socialQueueSaved ? <><br /><span style={{ color: '#38bdf8', fontSize: '0.8rem' }}>💾 {successResult.socialQueueSaved} textos salvos</span></> : ''}
          </div>
        ) : (
          <button
            onClick={handleScheduleApproved}
            disabled={isSubmitting || approvedCount === 0}
            className={styles.scheduleBtn}
            style={{ maxWidth: '340px', margin: 0, opacity: approvedCount === 0 ? 0.4 : 1 }}
          >
            {isSubmitting ? '⏳ Enviando...' : `Commit ${approvedCount} Aprovados →`}
          </button>
        )}
      </div>
    </div>
  );
}
