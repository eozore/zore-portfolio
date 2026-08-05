/* ============================================================
   CsmDashboard.tsx — fluxo único da CSM

   CMO → artigo publicado → pacote (roteiro + derivados) → aprovação → pipeline
   ============================================================ */
'use client';

import { useCallback, useEffect, useState } from 'react';
import '@/app/admin.css';
import AuthGate from './AuthGate';
import IdeaTab from './tabs/IdeaTab';
import ArticleTab from './tabs/ArticleTab';
import ReviewTab from './tabs/ReviewTab';
import TrackingTab from './tabs/TrackingTab';
import SettingsTab from './tabs/SettingsTab';
import TelemetryTab from './tabs/TelemetryTab';
import type { ArticleCategory } from '@/types/article';
import styles from './CsmDashboard.module.css';

export type OutputFormat = 'blog' | 'youtube' | 'linkedin';
export type ActiveTab = 'idea' | 'article' | 'review' | 'tracking' | 'settings' | 'telemetry';
export type ContentStatus = 'em_revisao' | 'aprovado' | 'rejeitado';
export type PackageStatus = 'idle' | 'generating' | 'script_ready' | 'ready' | 'error';
export type WorkflowStage =
  | 'idea' | 'article_draft' | 'article_published' | 'package_generating'
  | 'script_ready' | 'package_ready' | 'approved' | 'publishing' | 'published' | 'error';

export interface PautaConcebida {
  titulo: string;
  subtitulo: string;
  tese: string;
  publico: string;
  objetivo_aprendizado: string;
  hardskills: string[];
  duracao_alvo: string;
  serie: string;
  tipo_artigo?: 'tecnico' | 'conceitual' | 'estrategico';
  nivel_tecnico?: 'baixo' | 'medio' | 'alto';
}

export interface AttachmentItem {
  id: string;
  name: string;
  url: string;
  type: 'image' | 'pdf' | 'diagram' | 'data';
  tags: ('artigo' | 'linkedin' | 'carrossel' | 'youtube' | 'reels' | 'stories')[];
}

export interface LinkedInDraft { id: string; hook: string; copy: string; imageHtml?: string; imageUrl?: string; scheduledAt?: string; status: ContentStatus; }
export interface YouTubeCommunityDraft { id: string; copy: string; linkedinRefId: string; scheduledAt?: string; status: ContentStatus; }
export interface YouTubeDraft { id: string; title: string; script: string; scheduledAt?: string; status: ContentStatus; }
export interface YouTubeShortsDraft { id: string; title: string; hook3s: string; script: string; scheduledAt?: string; status: ContentStatus; }
export interface ReelDraft { id: string; title: string; hook3s: string; visualCue: string; script: string; scheduledAt?: string; status: ContentStatus; }
export interface CarouselDraft { id: string; title: string; caption: string; slides: { slideNumber: number; heading: string; body: string }[]; scheduledAt?: string; status: ContentStatus; }
export interface ImageDraft { id: string; title: string; imageDescription: string; imageHtml?: string; imageUrl?: string; copy: string; scheduledAt?: string; status: ContentStatus; }
export interface StoryDraft { id: string; day: string; angle: string; copy: string; interactiveElement?: string; scheduledAt?: string; status: ContentStatus; }
export interface ThreadDraft { id: string; threadNumber: number; topic: string; posts: string[]; scheduledAt?: string; status: ContentStatus; }

export interface RepurposedData {
  linkedinPosts: LinkedInDraft[];
  youtubeCommunityPosts?: YouTubeCommunityDraft[];
  youtubeScripts: YouTubeDraft[];
  youtubeShorts: YouTubeShortsDraft[];
  reelsScripts: ReelDraft[];
  carousels: CarouselDraft[];
  imagePosts: ImageDraft[];
  storiesIdeas: StoryDraft[];
  threads?: ThreadDraft[];
}

export interface ChatMessage { role: 'user' | 'model'; text: string; }
export interface ManifestAnchor { on_phrase: string; action: 'show_slide' | 'reveal' | 'highlight'; element?: string; }
export interface ManifestSegmentV2 { id: string; slide: string | null; beat: string; script: string; anchors: ManifestAnchor[]; min_duration_s?: number; pause_after_s?: number; }
export interface ManifestReel { reel_id: string; title?: string; deck?: string; resolution: { width: number; height: number }; overlay?: { mode: string; avatar_position: string; avatar_scale: number }; segments: ManifestSegmentV2[]; }
export interface ManifestV2 {
  version: 2;
  video_id: string;
  series?: string;
  title: string;
  language: string;
  audio_naming?: string;
  youtube: { deck?: string; resolution: { width: number; height: number }; overlay?: { mode: string; avatar_position: string; avatar_scale: number }; segments: ManifestSegmentV2[] };
  reels: ManifestReel[];
}
export interface SpecialistLinkedIn { id: string; hook: string; copy: string; hashtags: string; status: ContentStatus; }
export interface SpecialistThread { id: string; thread_number: number; topic: string; posts: string[]; hashtags: string; status: ContentStatus; }

export interface DraftState {
  topic: string;
  context: string;
  format: OutputFormat;
  category: ArticleCategory;
  language: 'pt-BR' | 'en';
  generatedContent: string;
  youtubeScript?: string;
  suggestedTitle: string;
  suggestedSlug: string;
  estimatedReadTime: number;
  repurposedData: RepurposedData | null;
  attachments: AttachmentItem[];
  chatHistory: ChatMessage[];
  blocks?: import('@/lib/blockParser').ArticleBlock[];
  youtubeScenes?: import('@/lib/scriptParser').ScriptScene[];
  pauta?: PautaConcebida;
  manifestV2?: ManifestV2 | null;
  manifestHtml?: string;
  thumbnails?: { option_minimal: string; option_provocative: string } | null;
  specialistCopies?: { linkedin_posts: SpecialistLinkedIn[]; threads: SpecialistThread[] } | null;
  publishedArticleUrl?: string;
  packageStatus?: PackageStatus;
  packageStartedAt?: number;
  workflowStage?: WorkflowStage;
}

const INITIAL_DRAFT: DraftState = {
  topic: '', context: '', format: 'blog', category: 'ml', language: 'pt-BR',
  generatedContent: '', youtubeScript: '', suggestedTitle: '', suggestedSlug: '',
  estimatedReadTime: 10, repurposedData: null, attachments: [], chatHistory: [],
  blocks: [], youtubeScenes: [], manifestV2: null, manifestHtml: '', thumbnails: null,
  specialistCopies: null, publishedArticleUrl: '', packageStatus: 'idle', workflowStage: 'idea',
};

const MAIN_TABS: { id: ActiveTab; label: string; index: string; description: string }[] = [
  { id: 'idea', label: 'CMO Chat', index: '01', description: 'Definir pauta' },
  { id: 'article', label: 'Artigo', index: '02', description: 'Gerar & publicar' },
  { id: 'review', label: 'Pacote', index: '03', description: 'Revisar & aprovar' },
  { id: 'tracking', label: 'Publicações', index: '04', description: 'Acompanhar pipeline' },
];

function isTabUnlocked(tabId: ActiveTab, draft: DraftState): boolean {
  switch (tabId) {
    case 'idea': return true;
    case 'article': return Boolean(draft.pauta?.titulo && draft.pauta?.tese);
    case 'review': return Boolean(draft.publishedArticleUrl && draft.packageStatus !== 'idle');
    case 'tracking': return ['approved', 'publishing', 'published'].includes(draft.workflowStage ?? '');
    default: return true;
  }
}

function lockMessage(tabId: ActiveTab): string {
  if (tabId === 'article') return 'Complete a pauta com o CMO primeiro';
  if (tabId === 'review') return 'Publique o artigo para gerar o pacote';
  if (tabId === 'tracking') return 'Aprove o pacote para acompanhar a pipeline';
  return 'Complete a etapa anterior';
}

export default function CsmDashboard() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('idea');
  const [lastStudioTab, setLastStudioTab] = useState<ActiveTab>('idea');
  const [draft, setDraft] = useState<DraftState>(INITIAL_DRAFT);
  const [sessionId, setSessionId] = useState('');
  const [loadingSession, setLoadingSession] = useState(true);
  const [lockTooltip, setLockTooltip] = useState<string | null>(null);

  useEffect(() => {
    let id = localStorage.getItem('csm_session_id');
    if (!id) { id = crypto.randomUUID(); localStorage.setItem('csm_session_id', id); }
    setSessionId(id);
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      try {
        const res = await fetch(`/api/csm/session?id=${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.draft) setDraft((prev) => ({ ...prev, ...data.draft }));
        }
      } catch (error) { console.error('[csm] session load failed', error); }
      finally { setLoadingSession(false); }
    })();
  }, [sessionId]);

  const saveDraft = useCallback(async (next: DraftState) => {
    if (!sessionId) return;
    await fetch('/api/csm/session', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, draft: next }),
    }).catch((error) => console.warn('[csm] draft save failed', error));
  }, [sessionId]);

  const updateDraft = useCallback((partial: Partial<DraftState>) => {
    setDraft((prev) => {
      const next = { ...prev, ...partial };
      if (partial.generatedContent !== undefined && partial.blocks === undefined) {
        const { parseMarkdownToBlocks } = require('@/lib/blockParser');
        next.blocks = parseMarkdownToBlocks(partial.generatedContent);
      }
      if (partial.youtubeScript !== undefined && partial.youtubeScenes === undefined) {
        const { parseMarkdownToScenes } = require('@/lib/scriptParser');
        next.youtubeScenes = parseMarkdownToScenes(partial.youtubeScript);
      }
      void saveDraft(next);
      return next;
    });
  }, [saveDraft]);

  useEffect(() => {
    if (!sessionId) return;
    const interval = setInterval(() => void saveDraft(draft), 30_000);
    return () => clearInterval(interval);
  }, [draft, saveDraft, sessionId]);

  const goToTab = (tab: ActiveTab) => {
    if (!isTabUnlocked(tab, draft)) {
      setLockTooltip(lockMessage(tab));
      setTimeout(() => setLockTooltip(null), 3000);
      return;
    }
    if (tab !== 'settings' && tab !== 'telemetry') setLastStudioTab(tab);
    setActiveTab(tab);
  };

  const startNewSession = () => {
    if (!window.confirm('Iniciar nova pauta? Isso limpará a sessão atual.')) return;
    const id = crypto.randomUUID();
    localStorage.setItem('csm_session_id', id);
    setDraft(INITIAL_DRAFT); setSessionId(id); setActiveTab('idea');
  };

  const tabIndex = MAIN_TABS.findIndex((tab) => tab.id === activeTab);

  return (
    <AuthGate>
      <div className={styles.layout}>
        <div className={styles.blob1} /><div className={styles.blob2} /><div className={styles.blob3} />
        <header className={styles.header}><div className={styles.headerInner}>
          <div className={styles.headerLogo}><span className={styles.logoAccent}>é</span><span className={styles.logoBase}>ozoré</span><span className={styles.headerSep}>/</span><span className={styles.headerTitle}>Content Studio</span></div>
          <div className={styles.headerMeta}><button onClick={startNewSession} className={styles.newSessionBtn}>Nova Reunião</button><span className={styles.badge}>Internal Tool</span></div>
        </div></header>

        {activeTab !== 'settings' && activeTab !== 'telemetry' && <nav className={styles.tabNav}><div className={styles.tabNavInner}>
          {MAIN_TABS.map((tab, index) => {
            const unlocked = isTabUnlocked(tab.id, draft);
            return <button key={tab.id} onClick={() => goToTab(tab.id)} disabled={loadingSession || !unlocked} title={!unlocked ? lockMessage(tab.id) : undefined} className={`${styles.tabBtn} ${activeTab === tab.id ? styles.tabBtnActive : ''} ${index < tabIndex ? styles.tabBtnDone : ''} ${!unlocked ? styles.tabBtnLocked : ''}`}>
              <span className={styles.tabIndex}>{tab.index}</span><span className={styles.tabLabel}>{tab.label}</span><span className={styles.tabDesc}>{tab.description}</span>{index < tabIndex && unlocked && <span className={styles.tabCheck}>✓</span>}{!unlocked && <span className={styles.tabLock}>🔒</span>}
            </button>;
          })}
          <div className={styles.progressBar}><div className={styles.progressFill} style={{ width: `${Math.max(0, tabIndex) / (MAIN_TABS.length - 1) * 100}%` }} /></div>
        </div>{lockTooltip && <div className={styles.lockTooltip}>🔒 {lockTooltip}</div>}</nav>}

        <main className={styles.main}>{loadingSession ? <div className={styles.loadingState}><div className={styles.loadingSpinner} /><span className={styles.loadingText}>carregando sessão...</span></div> : <>
          {activeTab === 'idea' && <IdeaTab draft={draft} updateDraft={updateDraft} isGenerating={false} setIsGenerating={() => undefined} sessionId={sessionId} onNext={() => goToTab('article')} />}
          {activeTab === 'article' && <ArticleTab draft={draft} updateDraft={updateDraft} sessionId={sessionId} onBack={() => goToTab('idea')} onPublished={(url) => { updateDraft({ publishedArticleUrl: url, packageStatus: 'generating', packageStartedAt: Date.now(), workflowStage: 'package_generating' }); goToTab('review'); }} />}
          {activeTab === 'review' && <ReviewTab draft={draft} updateDraft={updateDraft} sessionId={sessionId} onBack={() => goToTab('article')} onApproved={() => { updateDraft({ workflowStage: 'approved' }); goToTab('tracking'); }} />}
          {activeTab === 'tracking' && <TrackingTab draft={draft} sessionId={sessionId} onBack={() => goToTab('review')} />}
          {activeTab === 'settings' && <SettingsTab onBack={() => goToTab(lastStudioTab)} />}
          {activeTab === 'telemetry' && <TelemetryTab onBack={() => goToTab(lastStudioTab)} />}
        </>}</main>

        <footer className={styles.bottomBar}><span className={styles.bottomBarText}>éozoré Studio</span><div className={styles.bottomBarDivider} /><button onClick={() => goToTab(lastStudioTab)} className={`${styles.bottomBarLink} ${activeTab !== 'settings' && activeTab !== 'telemetry' ? styles.bottomBarLinkActive : ''}`}>📝 Studio</button><div className={styles.bottomBarDivider} /><button onClick={() => goToTab('settings')} className={`${styles.bottomBarLink} ${activeTab === 'settings' ? styles.bottomBarLinkActive : ''}`}>⚙️ Ajustes</button><div className={styles.bottomBarDivider} /><button onClick={() => goToTab('telemetry')} className={`${styles.bottomBarLink} ${activeTab === 'telemetry' ? styles.bottomBarLinkActive : ''}`}>📊 Telemetria</button></footer>
      </div>
    </AuthGate>
  );
}
