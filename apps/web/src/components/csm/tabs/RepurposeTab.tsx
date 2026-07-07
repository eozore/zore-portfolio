import { useState, useEffect } from 'react';
import type {
  DraftState,
  LinkedInDraft,
  YouTubeDraft,
  YouTubeShortsDraft,
  ReelDraft,
  CarouselDraft,
  ImageDraft,
  StoryDraft,
  AttachmentItem
} from '../CsmDashboard';
import EditorialCalendar, { type CalendarItem } from './EditorialCalendar';
import styles from './RepurposeTab.module.css';

interface RepurposeTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  sessionId: string;
  onBack: () => void;
}

export default function RepurposeTab({ draft, updateDraft, sessionId, onBack }: RepurposeTabProps) {
  const data = draft.repurposedData;

  const [viewMode, setViewMode] = useState<'calendar' | 'list'>('calendar');
  const [attachments, setAttachments] = useState<AttachmentItem[]>(draft.attachments || []);
  const [newAttUrl, setNewAttUrl] = useState('');
  const [newAttName, setNewAttName] = useState('');

  const [linkedinPosts, setLinkedinPosts] = useState<LinkedInDraft[]>([]);
  const [ytScripts, setYtScripts] = useState<YouTubeDraft[]>([]);
  const [ytShortsScripts, setYtShortsScripts] = useState<YouTubeShortsDraft[]>([]);
  const [reelsScripts, setReelsScripts] = useState<ReelDraft[]>([]);
  const [carousels, setCarousels] = useState<CarouselDraft[]>([]);
  const [imagePosts, setImagePosts] = useState<ImageDraft[]>([]);
  const [storiesIdeas, setStoriesIdeas] = useState<StoryDraft[]>([]);

  // HeyGen video state
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({});
  const [generatingStates, setGeneratingStates] = useState<Record<string, boolean>>({});
  const [generatingProgress, setGeneratingProgress] = useState<Record<string, number>>({});
  const [videoSteps, setVideoSteps] = useState<Record<string, number>>({});
  const [avatarVideoUrls, setAvatarVideoUrls] = useState<Record<string, string>>({});
  const [motionVideoUrls, setMotionVideoUrls] = useState<Record<string, string>>({});
  const [videoErrors, setVideoErrors] = useState<Record<string, string>>({});
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successResult, setSuccessResult] = useState<{ totalReceived: number; totalApproved: number } | null>(null);

  useEffect(() => {
    if (data) {
      const now = new Date();
      const getISO = (daysAdd: number, hour: number) => {
        const d = new Date(now);
        d.setDate(d.getDate() + daysAdd);
        d.setHours(hour, 0, 0, 0);
        return d.toISOString();
      };

      // Mapeia urls dos vídeos salvas anteriormente
      const initialVideoUrls: Record<string, string> = {};
      data.youtubeShorts?.forEach(ys => {
        if (ys.videoUrl) initialVideoUrls[`yts_${ys.id}`] = ys.videoUrl;
      });
      data.reelsScripts?.forEach(r => {
        if (r.videoUrl) initialVideoUrls[`re_${r.id}`] = r.videoUrl;
      });
      setVideoUrls(initialVideoUrls);

      setLinkedinPosts(
        data.linkedinPosts?.map((p, i) => ({
          ...p,
          status: p.status || 'em_revisao',
          scheduledAt: p.scheduledAt || getISO((i % 5) + 1, 9 + i),
        })) || []
      );

      if (draft.youtubeScript) {
        setYtScripts([
          {
            id: 'yt-long-1',
            title: draft.suggestedTitle || 'Vídeo de Deep Dive do YouTube',
            script: draft.youtubeScript,
            status: 'aprovado',
            scheduledAt: getISO(1, 10),
          }
        ]);
      } else {
        setYtScripts([]);
      }

      setYtShortsScripts(
        data.youtubeShorts?.map((ys, i) => ({
          ...ys,
          status: ys.status || 'em_revisao',
          scheduledAt: ys.scheduledAt || getISO((i % 5) + 1, 15 + i),
        })) || []
      );

      setReelsScripts(
        data.reelsScripts?.map((r, i) => ({
          ...r,
          status: r.status || 'em_revisao',
          scheduledAt: r.scheduledAt || getISO((i % 5) + 1, 12 + i),
        })) || []
      );

      setCarousels(
        data.carousels?.map((c, i) => ({
          ...c,
          status: c.status || 'em_revisao',
          scheduledAt: c.scheduledAt || getISO((i % 5) + 1, 14 + i),
        })) || []
      );

      setImagePosts(
        data.imagePosts?.map((im, i) => ({
          ...im,
          status: im.status || 'em_revisao',
          scheduledAt: im.scheduledAt || getISO((i % 5) + 1, 11 + i),
        })) || []
      );

      setStoriesIdeas(
        data.storiesIdeas?.map((s, i) => ({
          ...s,
          status: s.status || 'em_revisao',
          scheduledAt: s.scheduledAt || getISO((i % 5) + 1, 8 + (i % 12)),
        })) || []
      );
    }
  }, [data, draft.youtubeScript, draft.suggestedTitle]);

  const handleGenerateVideo = async (itemId: string, script: string, format: string) => {
    if (generatingStates[itemId] || videoUrls[itemId]) return;

    setGeneratingStates(prev => ({ ...prev, [itemId]: true }));
    setVideoSteps(prev => ({ ...prev, [itemId]: 1 }));
    setGeneratingProgress(prev => ({ ...prev, [itemId]: 10 }));
    setVideoErrors(prev => ({ ...prev, [itemId]: '' }));

    try {
      // ── STEP 1: HEYGEN AVATAR ──
      const res = await fetch('/api/csm/heygen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script,
          format,
          avatarProfile: format === 'shorts' || format === 'reel' ? 'vertical' : 'horizontal',
          id: itemId
        })
      });

      const resData = await res.json();
      if (!res.ok) throw new Error(resData.error || 'Erro ao criar vídeo no HeyGen');
      const videoId = resData.videoId;

      // Poll HeyGen Status
      let avatarVideoUrl = '';
      await new Promise<void>((resolve, reject) => {
        let attempts = 0;
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const pollRes = await fetch(`/api/csm/heygen?videoId=${videoId}`);
            const pollData = await pollRes.json();
            if (!pollRes.ok) {
              clearInterval(pollInterval);
              reject(new Error(pollData.error || 'Erro no status do HeyGen'));
              return;
            }

            if (pollData.status === 'completed') {
              clearInterval(pollInterval);
              avatarVideoUrl = pollData.videoUrl;
              setAvatarVideoUrls(prev => ({ ...prev, [itemId]: avatarVideoUrl }));
              setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 }));
              resolve();
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              reject(new Error(pollData.error || 'A renderização falhou no HeyGen'));
            } else {
              setGeneratingProgress(prev => ({
                ...prev,
                [itemId]: pollData.progress || Math.min(95, attempts * 25)
              }));
            }
          } catch (err) {
            clearInterval(pollInterval);
            reject(err);
          }
        }, 3000);
      });

      // ── STEP 2: RENDER MOTION GRAPHICS OVERLAY ──
      setVideoSteps(prev => ({ ...prev, [itemId]: 2 }));
      setGeneratingProgress(prev => ({ ...prev, [itemId]: 10 }));

      const motionRes = await fetch('/api/csm/render-motion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          itemId,
          scenes: script,
          sessionId
        })
      });
      const motionData = await motionRes.json();
      if (!motionRes.ok) throw new Error(motionData.error || 'Erro ao iniciar render-motion');
      const motionJobId = motionData.jobId;

      // Poll Motion Graphics Status
      let motionVideoUrl = '';
      await new Promise<void>((resolve, reject) => {
        let attempts = 0;
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const pollRes = await fetch(`/api/csm/render-motion?jobId=${motionJobId}`);
            const pollData = await pollRes.json();
            if (!pollRes.ok) {
              clearInterval(pollInterval);
              reject(new Error(pollData.error || 'Erro no status do render-motion'));
              return;
            }

            if (pollData.status === 'completed') {
              clearInterval(pollInterval);
              motionVideoUrl = pollData.motionUrl;
              setMotionVideoUrls(prev => ({ ...prev, [itemId]: motionVideoUrl }));
              setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 }));
              resolve();
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              reject(new Error('A renderização dos gráficos de motion falhou.'));
            } else {
              setGeneratingProgress(prev => ({
                ...prev,
                [itemId]: pollData.progress || Math.min(95, attempts * 25)
              }));
            }
          } catch (err) {
            clearInterval(pollInterval);
            reject(err);
          }
        }, 3000);
      });

      // ── STEP 3: FUSION/MERGE (FFMPEG) ──
      setVideoSteps(prev => ({ ...prev, [itemId]: 3 }));
      setGeneratingProgress(prev => ({ ...prev, [itemId]: 10 }));

      const mergeRes = await fetch('/api/csm/merge-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          avatarVideoUrl,
          motionVideoUrl,
          sessionId,
          script
        })
      });
      const mergeData = await mergeRes.json();
      if (!mergeRes.ok) throw new Error(mergeData.error || 'Erro ao iniciar merge-video');
      const mergeJobId = mergeData.jobId;

      // Poll Merge Status
      let finalVideoUrl = '';
      await new Promise<void>((resolve, reject) => {
        let attempts = 0;
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const pollRes = await fetch(`/api/csm/merge-video?jobId=${mergeJobId}`);
            const pollData = await pollRes.json();
            if (!pollRes.ok) {
              clearInterval(pollInterval);
              reject(new Error(pollData.error || 'Erro no status do merge-video'));
              return;
            }

            if (pollData.status === 'completed') {
              clearInterval(pollInterval);
              finalVideoUrl = pollData.mergedVideoUrl;
              setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 }));
              resolve();
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              reject(new Error('A fusão de vídeo falhou.'));
            } else {
              setGeneratingProgress(prev => ({
                ...prev,
                [itemId]: pollData.progress || Math.min(95, attempts * 25)
              }));
            }
          } catch (err) {
            clearInterval(pollInterval);
            reject(err);
          }
        }, 3000);
      });

      // Pipeline complete
      setVideoUrls(prev => ({ ...prev, [itemId]: finalVideoUrl }));
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));

      // Persist in Firestore
      const [prefix, rawId] = itemId.split('_');
      if (draft.repurposedData) {
        const updatedData = { ...draft.repurposedData };
        if (prefix === 'yts') {
          updatedData.youtubeShorts = (updatedData.youtubeShorts || []).map(ys => 
            ys.id === rawId ? { ...ys, videoUrl: finalVideoUrl } : ys
          );
        } else if (prefix === 're') {
          updatedData.reelsScripts = (updatedData.reelsScripts || []).map(r => 
            r.id === rawId ? { ...r, videoUrl: finalVideoUrl } : r
          );
        }
        updateDraft({ repurposedData: updatedData });
      }

    } catch (err: any) {
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));
      setVideoErrors(prev => ({ ...prev, [itemId]: err.message }));
      alert(err.message || 'Falha ao processar o pipeline de vídeo');
    }
  };

  const handleRetryMerge = async (itemId: string, script: string, format: string) => {
    const avatarVideoUrl = avatarVideoUrls[itemId];
    const motionVideoUrl = motionVideoUrls[itemId];
    if (!avatarVideoUrl || !motionVideoUrl) {
      alert('Não é possível retentar a fusão: faltam as URLs dos vídeos intermediários (avatar ou motion).');
      return;
    }

    setGeneratingStates(prev => ({ ...prev, [itemId]: true }));
    setVideoSteps(prev => ({ ...prev, [itemId]: 3 })); // Start directly on step 3 (merge)
    setGeneratingProgress(prev => ({ ...prev, [itemId]: 10 }));
    setVideoErrors(prev => ({ ...prev, [itemId]: '' }));

    try {
      const mergeRes = await fetch('/api/csm/retry-merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          avatarVideoUrl,
          motionVideoUrl,
          sessionId,
          script,
          format
        })
      });
      const mergeData = await mergeRes.json();
      if (!mergeRes.ok) throw new Error(mergeData.error || 'Erro ao iniciar retry-merge');
      const retryJobId = mergeData.jobId;

      let finalVideoUrl = '';
      await new Promise<void>((resolve, reject) => {
        let attempts = 0;
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const pollRes = await fetch(`/api/csm/retry-merge?jobId=${retryJobId}`);
            const pollData = await pollRes.json();
            if (!pollRes.ok) {
              clearInterval(pollInterval);
              reject(new Error(pollData.error || 'Erro no status do retry-merge'));
              return;
            }

            if (pollData.status === 'completed') {
              clearInterval(pollInterval);
              finalVideoUrl = pollData.mergedVideoUrl;
              setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 }));
              resolve();
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              reject(new Error('A fusão de vídeo falhou novamente.'));
            } else {
              setGeneratingProgress(prev => ({
                ...prev,
                [itemId]: pollData.progress || Math.min(95, attempts * 25)
              }));
            }
          } catch (err) {
            clearInterval(pollInterval);
            reject(err);
          }
        }, 3000);
      });

      // Retry complete
      setVideoUrls(prev => ({ ...prev, [itemId]: finalVideoUrl }));
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));

      // Persist in Firestore
      const [prefix, rawId] = itemId.split('_');
      if (draft.repurposedData) {
        const updatedData = { ...draft.repurposedData };
        if (prefix === 'yts') {
          updatedData.youtubeShorts = (updatedData.youtubeShorts || []).map(ys => 
            ys.id === rawId ? { ...ys, videoUrl: finalVideoUrl } : ys
          );
        } else if (prefix === 're') {
          updatedData.reelsScripts = (updatedData.reelsScripts || []).map(r => 
            r.id === rawId ? { ...r, videoUrl: finalVideoUrl } : r
          );
        }
        updateDraft({ repurposedData: updatedData });
      }
    } catch (err: any) {
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));
      setVideoErrors(prev => ({ ...prev, [itemId]: err.message }));
      alert(err.message || 'Falha ao retentar a fusão de vídeo');
    }
  };

  const handleGenerateImage = async (itemId: string, title: string, imageDescription: string, copy: string) => {
    if (generatingStates[itemId] || imageUrls[itemId]) return;

    setGeneratingStates(prev => ({ ...prev, [itemId]: true }));
    setGeneratingProgress(prev => ({ ...prev, [itemId]: 20 }));

    try {
      const res = await fetch('/api/csm/generate-image-post', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          imageDescription,
          copy,
          sessionId,
          itemId
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erro ao iniciar geração de imagem');
      const jobId = data.jobId;

      let imageUrl = '';
      await new Promise<void>((resolve, reject) => {
        let attempts = 0;
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const pollRes = await fetch(`/api/csm/generate-image-post?jobId=${jobId}`);
            const pollData = await pollRes.json();
            if (!pollRes.ok) {
              clearInterval(pollInterval);
              reject(new Error(pollData.error || 'Erro no status da geração de imagem'));
              return;
            }

            if (pollData.status === 'completed') {
              clearInterval(pollInterval);
              imageUrl = pollData.imageUrl;
              setGeneratingProgress(prev => ({ ...prev, [itemId]: 100 }));
              resolve();
            } else if (pollData.status === 'failed') {
              clearInterval(pollInterval);
              reject(new Error('A geração de imagem falhou.'));
            } else {
              setGeneratingProgress(prev => ({
                ...prev,
                [itemId]: pollData.progress || Math.min(95, attempts * 25)
              }));
            }
          } catch (err) {
            clearInterval(pollInterval);
            reject(err);
          }
        }, 2000);
      });

      // Complete
      setImageUrls(prev => ({ ...prev, [itemId]: imageUrl }));
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));

      // Persist in Firestore
      const [prefix, rawId] = itemId.split('_');
      if (draft.repurposedData && prefix === 'img') {
        const updatedData = { ...draft.repurposedData };
        updatedData.imagePosts = (updatedData.imagePosts || []).map(im => 
          im.id === rawId ? { ...im, imageUrl } : im
        );
        updateDraft({ repurposedData: updatedData });
      }
    } catch (err: any) {
      setGeneratingStates(prev => ({ ...prev, [itemId]: false }));
      alert(err.message || 'Falha ao gerar imagem HTML');
    }
  };

  const handleAddAttachment = () => {
    if (!newAttUrl.startsWith('https://')) {
      alert('URL deve começar com https://');
      return;
    }
    const newItem: AttachmentItem = {
      id: Math.random().toString(36).slice(2, 9),
      name: newAttName || 'Anexo Externo',
      url: newAttUrl,
      type: newAttUrl.endsWith('.pdf') ? 'pdf' : 'image',
      tags: ['artigo', 'linkedin'],
    };
    const next = [...attachments, newItem];
    setAttachments(next);
    updateDraft({ attachments: next });
    setNewAttUrl('');
    setNewAttName('');
  };

  const handleToggleAttTag = (attId: string, tag: 'artigo' | 'linkedin' | 'carrossel' | 'youtube' | 'reels' | 'stories') => {
    const next = attachments.map((att) => {
      if (att.id !== attId) return att;
      const has = att.tags.includes(tag);
      const newTags = has ? att.tags.filter((t) => t !== tag) : [...att.tags, tag];
      return { ...att, tags: newTags };
    });
    setAttachments(next);
    updateDraft({ attachments: next });
  };

  // Consolida todos em CalendarItem[]
  const allCalendarItems: CalendarItem[] = [
    ...linkedinPosts.map((p) => ({
      id: `li_${p.id}`,
      platform: 'linkedin' as const,
      format: 'image' as const,
      titleOrHook: p.hook,
      copy: p.copy,
      scheduledAt: p.scheduledAt || new Date().toISOString(),
      status: p.status,
      articleTitle: draft.suggestedTitle || 'Artigo do Blog éozoré',
    })),
    ...ytScripts.map((y) => ({
      id: `yt_${y.id}`,
      platform: 'youtube' as const,
      format: 'video' as const,
      titleOrHook: y.title,
      copy: y.script,
      scheduledAt: y.scheduledAt || new Date().toISOString(),
      status: y.status,
    })),
    ...ytShortsScripts.map((ys) => ({
      id: `yts_${ys.id}`,
      platform: 'youtube' as const,
      format: 'shorts' as const,
      titleOrHook: ys.title,
      copy: ys.script,
      scheduledAt: ys.scheduledAt || new Date().toISOString(),
      status: ys.status,
      hook3s: ys.hook3s,
      videoUrl: videoUrls[`yts_${ys.id}`],
      isGenerating: generatingStates[`yts_${ys.id}`],
      progress: generatingProgress[`yts_${ys.id}`],
      avatarVideoUrl: avatarVideoUrls[`yts_${ys.id}`],
      motionVideoUrl: motionVideoUrls[`yts_${ys.id}`],
      videoError: videoErrors[`yts_${ys.id}`],
      onGenerateVideo: () => handleGenerateVideo(`yts_${ys.id}`, ys.script, 'shorts'),
      onRetryMerge: () => handleRetryMerge(`yts_${ys.id}`, ys.script, 'shorts'),
    })),
    ...reelsScripts.map((r) => ({
      id: `re_${r.id}`,
      platform: 'instagram' as const,
      format: 'reel' as const,
      titleOrHook: r.title,
      copy: r.script,
      scheduledAt: r.scheduledAt || new Date().toISOString(),
      status: r.status,
      hook3s: r.hook3s,
      visualCue: r.visualCue,
      videoUrl: videoUrls[`re_${r.id}`],
      isGenerating: generatingStates[`re_${r.id}`],
      progress: generatingProgress[`re_${r.id}`],
      avatarVideoUrl: avatarVideoUrls[`re_${r.id}`],
      motionVideoUrl: motionVideoUrls[`re_${r.id}`],
      videoError: videoErrors[`re_${r.id}`],
      onGenerateVideo: () => handleGenerateVideo(`re_${r.id}`, r.script, 'reel'),
      onRetryMerge: () => handleRetryMerge(`re_${r.id}`, r.script, 'reel'),
    })),
    ...carousels.map((c) => ({
      id: `ca_${c.id}`,
      platform: 'instagram' as const,
      format: 'carousel' as const,
      titleOrHook: c.title,
      copy: c.caption,
      scheduledAt: c.scheduledAt || new Date().toISOString(),
      status: c.status,
      slides: c.slides,
    })),
    ...imagePosts.map((im) => ({
      id: `img_${im.id}`,
      platform: 'instagram' as const,
      format: 'post_imagem' as const,
      titleOrHook: im.title,
      copy: im.copy,
      scheduledAt: im.scheduledAt || new Date().toISOString(),
      status: im.status,
      imageDescription: im.imageDescription,
      imageUrl: imageUrls[`img_${im.id}`] || im.imageUrl,
      isGenerating: generatingStates[`img_${im.id}`],
      progress: generatingProgress[`img_${im.id}`],
      onGenerateImage: () => handleGenerateImage(`img_${im.id}`, im.title, im.imageDescription || '', im.copy),
    })),
    ...storiesIdeas.map((s) => ({
      id: `st_${s.id}`,
      platform: 'instagram' as const,
      format: 'story' as const,
      titleOrHook: s.interactiveElement || s.angle,
      copy: `${s.day}: ${s.copy}`,
      scheduledAt: s.scheduledAt || new Date().toISOString(),
      status: s.status,
    })),
  ];

  const handleUpdateUnifiedItem = (unifiedId: string, partial: Partial<CalendarItem>) => {
    const [prefix, rawId] = unifiedId.split('_');
    const st = partial.status;
    const dt = partial.scheduledAt;
    const txt = partial.copy;
    const title = partial.titleOrHook;

    if (prefix === 'li') {
      setLinkedinPosts((prev) =>
        prev.map((p) => (p.id === rawId ? { ...p, status: st || p.status, scheduledAt: dt || p.scheduledAt, copy: txt || p.copy, hook: title || p.hook } : p))
      );
    } else if (prefix === 'yt') {
      setYtScripts((prev) =>
        prev.map((y) => (y.id === rawId ? { ...y, status: st || y.status, scheduledAt: dt || y.scheduledAt, script: txt || y.script, title: title || y.title } : y))
      );
    } else if (prefix === 'yts') {
      setYtShortsScripts((prev) =>
        prev.map((ys) => (ys.id === rawId ? { ...ys, status: st || ys.status, scheduledAt: dt || ys.scheduledAt, script: txt || ys.script, title: title || ys.title } : ys))
      );
    } else if (prefix === 're') {
      setReelsScripts((prev) =>
        prev.map((r) => (r.id === rawId ? { ...r, status: st || r.status, scheduledAt: dt || r.scheduledAt, script: txt || r.script, title: title || r.title } : r))
      );
    } else if (prefix === 'ca') {
      setCarousels((prev) =>
        prev.map((c) => (c.id === rawId ? { ...c, status: st || c.status, scheduledAt: dt || c.scheduledAt, caption: txt || c.caption, title: title || c.title } : c))
      );
    } else if (prefix === 'img') {
      setImagePosts((prev) =>
        prev.map((im) => (im.id === rawId ? { ...im, status: st || im.status, scheduledAt: dt || im.scheduledAt, copy: txt || im.copy, title: title || im.title } : im))
      );
    } else if (prefix === 'st') {
      setStoriesIdeas((prev) =>
        prev.map((s) => (s.id === rawId ? { ...s, status: st || s.status, scheduledAt: dt || s.scheduledAt, copy: txt || s.copy } : s))
      );
    }
  };

  const handleScheduleApproved = async () => {
    setIsSubmitting(true);
    setSuccessResult(null);

    const itemsPayload = allCalendarItems.map((ci) => ({
      id: ci.id,
      platform: ci.platform,
      format: ci.format,
      title: ci.titleOrHook,
      copy: ci.copy,
      scheduledAt: ci.scheduledAt,
      slides: ci.slides,
      status: ci.status,
      imageDescription: ci.imageDescription,
      videoUrl: ci.videoUrl,
    }));

    try {
      const res = await fetch('/api/csm/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          articleSlug: draft.suggestedSlug || 'artigo',
          articleTitle: draft.suggestedTitle,
          items: itemsPayload,
        }),
      });

      const resData = await res.json();
      if (!res.ok) throw new Error(resData.error || 'Falha na requisição');

      setSuccessResult({ totalReceived: resData.totalReceived, totalApproved: resData.totalApproved });
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Erro ao persistir na fila social');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!data) {
    return (
      <div className={styles.card} style={{ textAlign: 'center', padding: '60px' }}>
        <h2 style={{ color: '#fff', marginBottom: '16px' }}>Nenhuma Derivação Gerada</h2>
        <p style={{ color: '#cbd5e1', marginBottom: '24px' }}>
          Volte à aba de Publicação e clique em &quot;Testar Derivações em Rascunho&quot; ou publique no blog.
        </p>
        <button onClick={onBack} className={styles.scheduleBtn} style={{ maxWidth: '300px', margin: '0 auto' }}>
          ← Voltar
        </button>
      </div>
    );
  }

  const approvedCount = allCalendarItems.filter((i) => i.status === 'aprovado').length;

  return (
    <div className={styles.mainCol} style={{ gap: '24px' }}>
      {/* Top Header & Toolbar */}
      <div className={styles.card} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ color: '#fff', fontSize: '1.4rem', fontWeight: 800 }}>Calendário Editorial & Time de Marketing AI</h1>
          <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
            {allCalendarItems.length} peças geradas. Default: Em Revisão. Avalie e passe para Aprovado.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={() => setViewMode('calendar')}
            style={{ padding: '10px 18px', borderRadius: '12px', border: '1px solid #e67e22', background: viewMode === 'calendar' ? '#e67e22' : 'transparent', color: viewMode === 'calendar' ? '#000' : '#e67e22', fontWeight: 'bold', cursor: 'pointer' }}
          >
            Visão Calendário
          </button>
          <button
            onClick={() => setViewMode('list')}
            style={{ padding: '10px 18px', borderRadius: '12px', border: '1px solid #e67e22', background: viewMode === 'list' ? '#e67e22' : 'transparent', color: viewMode === 'list' ? '#000' : '#e67e22', fontWeight: 'bold', cursor: 'pointer' }}
          >
            Visão Lista Rápida
          </button>
        </div>
      </div>

      {/* Attachments Bar */}
      <div className={styles.card}>
        <h2 style={{ color: '#f5a962', fontSize: '1.05rem', fontWeight: 800, marginBottom: '16px' }}>Biblioteca de Anexos do Artigo</h2>
        
        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={newAttName}
            onChange={(e) => setNewAttName(e.target.value)}
            placeholder="Nome (ex: Grafo de Perda)"
            style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', padding: '8px 14px', borderRadius: '8px', fontSize: '0.85rem' }}
          />
          <input
            type="text"
            value={newAttUrl}
            onChange={(e) => setNewAttUrl(e.target.value)}
            placeholder="https://storage.googleapis.com/..."
            style={{ flex: 1, minWidth: '240px', background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', padding: '8px 14px', borderRadius: '8px', fontSize: '0.85rem' }}
          />
          <button onClick={handleAddAttachment} style={{ background: '#f5a962', color: '#000', fontWeight: 'bold', border: 'none', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer' }}>
            + Anexar URL
          </button>
        </div>

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {attachments.map((att) => (
            <div key={att.id} style={{ background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(255,255,255,0.1)', padding: '12px', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '260px' }}>
              <div style={{ fontWeight: 'bold', color: '#fff', fontSize: '0.9rem' }}>{att.name}</div>
              <a href={att.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.75rem', color: '#38bdf8', wordBreak: 'break-all' }}>{att.url.slice(0, 35)}...</a>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
                {(['artigo', 'linkedin', 'carrossel', 'youtube', 'reels', 'stories'] as const).map((t) => {
                  const on = att.tags.includes(t);
                  return (
                    <button
                      key={t}
                      onClick={() => handleToggleAttTag(att.id, t)}
                      style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.15)', background: on ? '#2ecc71' : 'transparent', color: on ? '#000' : '#94a3b8', fontWeight: 'bold', cursor: 'pointer' }}
                    >
                      {on ? '✓ ' : ''}{t}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Calendar vs List View */}
      {viewMode === 'calendar' ? (
        <EditorialCalendar items={allCalendarItems} onUpdateItem={handleUpdateUnifiedItem} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {allCalendarItems.map((item) => {
            const hasHeyGen = item.format === 'reel' || item.format === 'shorts';
            const isGen = item.isGenerating;
            const videoUrl = item.videoUrl;
            
            return (
              <div key={item.id} className={styles.itemBox}>
                <div className={styles.itemMetaRow}>
                  <span style={{ color: '#f5a962', fontWeight: 'bold' }}>
                    [{item.platform.toUpperCase()} - {item.format.toUpperCase()}] {item.titleOrHook}
                  </span>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {hasHeyGen && !videoUrl && !isGen && (
                      <button
                        onClick={item.onGenerateVideo}
                        style={{
                          background: 'linear-gradient(135deg, #7c3aed, #5b21b6)',
                          color: '#ffffff',
                          border: 'none',
                          padding: '6px 12px',
                          borderRadius: '8px',
                          fontSize: '0.75rem',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          boxShadow: '0 2px 8px rgba(124, 58, 237, 0.3)',
                        }}
                      >
                        ⚡ Gerar Vídeo Completo (3 Passos)
                      </button>
                    )}
                    <button onClick={() => handleUpdateUnifiedItem(item.id, { status: 'em_revisao' })} style={{ background: item.status === 'em_revisao' ? '#fbbf24' : 'transparent', color: item.status === 'em_revisao' ? '#000' : '#fbbf24', border: '1px solid #fbbf24', padding: '4px 8px', borderRadius: '6px', fontWeight: 'bold', fontSize: '0.75rem' }}>Revisão</button>
                    <button onClick={() => handleUpdateUnifiedItem(item.id, { status: 'aprovado' })} style={{ background: item.status === 'aprovado' ? '#2ecc71' : 'transparent', color: item.status === 'aprovado' ? '#000' : '#2ecc71', border: '1px solid #2ecc71', padding: '4px 8px', borderRadius: '6px', fontWeight: 'bold', fontSize: '0.75rem' }}>Aprovar</button>
                  </div>
                </div>
                
                {/* 3-Step Video Pipeline Rendering */}
                {hasHeyGen && isGen && (
                  <div style={{ marginTop: '12px', background: 'rgba(124, 58, 237, 0.04)', border: '1px solid rgba(124, 58, 237, 0.15)', padding: '12px', borderRadius: '8px', marginBottom: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '0.78rem', fontWeight: 'bold', color: '#7c3aed' }}>
                        ⚡ {videoSteps[item.id] === 1 
                          ? 'Passo 1/3: Renderizando Avatar (HeyGen)...' 
                          : videoSteps[item.id] === 2 
                          ? 'Passo 2/3: Gerando Motion Graphics...' 
                          : 'Passo 3/3: Mesclando Vídeos (FFmpeg)...'}
                      </span>
                      <span style={{ fontSize: '0.78rem', fontWeight: 'bold', color: '#7c3aed' }}>{item.progress}%</span>
                    </div>
                    {/* Progress Bar */}
                    <div style={{ height: '6px', background: 'rgba(124, 58, 237, 0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', background: '#7c3aed', width: `${item.progress}%`, transition: 'width 0.3s ease' }} />
                    </div>
                    {/* Step Labels */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px' }}>
                      <span style={{ fontSize: '0.65rem', color: (videoSteps[item.id] || 1) >= 1 ? '#7c3aed' : '#94a3b8', fontWeight: (videoSteps[item.id] || 1) === 1 ? 'bold' : 'normal' }}>1. HeyGen Avatar</span>
                      <span style={{ fontSize: '0.65rem', color: (videoSteps[item.id] || 1) >= 2 ? '#7c3aed' : '#94a3b8', fontWeight: (videoSteps[item.id] || 1) === 2 ? 'bold' : 'normal' }}>2. Motion Overlay</span>
                      <span style={{ fontSize: '0.65rem', color: (videoSteps[item.id] || 1) >= 3 ? '#7c3aed' : '#94a3b8', fontWeight: (videoSteps[item.id] || 1) === 3 ? 'bold' : 'normal' }}>3. Fusão FFmpeg</span>
                    </div>
                  </div>
                )}

                {/* Final Merged Video Player + Download */}
                {hasHeyGen && videoUrl && (
                  <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '12px', background: 'rgba(16, 185, 129, 0.03)', border: '1px solid rgba(16, 185, 129, 0.15)', padding: '12px', borderRadius: '10px' }}>
                    <div style={{ borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(0,0,0,0.08)', background: '#000' }}>
                      <video src={videoUrl} controls style={{ width: '100%', maxHeight: '240px' }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                      <a
                        href={videoUrl}
                        download={`eozore-video-${item.id}.mp4`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          background: '#10b981',
                          color: '#ffffff',
                          fontWeight: 'bold',
                          border: 'none',
                          padding: '6px 12px',
                          borderRadius: '6px',
                          fontSize: '0.78rem',
                          cursor: 'pointer',
                          textDecoration: 'none',
                          boxShadow: '0 2px 6px rgba(16, 185, 129, 0.3)',
                        }}
                      >
                        📥 Download MP4
                      </a>
                    </div>
                  </div>
                )}
                {item.imageDescription && (
                  <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px dashed rgba(255,255,255,0.1)', padding: '10px', borderRadius: '6px', fontSize: '0.8rem', color: '#cbd5e1', marginBottom: '10px' }}>
                    <strong>Diretriz Visual:</strong> {item.imageDescription}
                  </div>
                )}
                <textarea
                  value={item.copy}
                  onChange={(e) => handleUpdateUnifiedItem(item.id, { copy: e.target.value })}
                  className={styles.textarea}
                />
              </div>
            );
          })}
        </div>
      )}

      {/* Bottom Submit Toolbar */}
      <div className={styles.card} style={{ position: 'sticky', bottom: '24px', background: '#0f172a', border: '2px solid #e67e22', boxShadow: '0 -10px 30px rgba(0,0,0,0.8)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <span style={{ color: '#fff', fontWeight: 800, fontSize: '1.2rem' }}>Pronto para Agendar na Semana?</span>
          <div style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '4px' }}>
            Exatamente <strong>{approvedCount} de {allCalendarItems.length}</strong> conteúdos estão marcados com status Aprovado.
          </div>
        </div>

        {successResult ? (
          <div style={{ color: '#2ecc71', fontWeight: 'bold', fontSize: '1.1rem' }}>
            {successResult.totalApproved} conteúdos agendados na fila Firestore com sucesso!
          </div>
        ) : (
          <button
            onClick={handleScheduleApproved}
            disabled={isSubmitting || approvedCount === 0}
            className={styles.scheduleBtn}
            style={{ maxWidth: '360px', margin: 0 }}
          >
            {isSubmitting ? 'Persistindo Fila Social...' : `Commit (${approvedCount}) Aprovados na Fila →`}
          </button>
        )}
      </div>
    </div>
  );
}
