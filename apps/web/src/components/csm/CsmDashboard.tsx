/* ============================================================
   CsmDashboard.tsx — fluxo único da CSM

   CMO → artigo publicado → pacote (roteiro + derivados) → aprovação → pipeline
   ============================================================ */
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import '@/app/admin.css';
import AuthGate from './AuthGate';
import IdeaTab from './tabs/IdeaTab';
import ArticleTab from './tabs/ArticleTab';
import ReviewTab from './tabs/ReviewTab';
import TrackingTab from './tabs/TrackingTab';
import SettingsTab from './tabs/SettingsTab';
import TelemetryTab from './tabs/TelemetryTab';
import OverviewTab from './tabs/OverviewTab';
import type { ArticleCategory } from '@/types/article';
import styles from './CsmDashboard.module.css';

export type OutputFormat = 'blog' | 'youtube' | 'linkedin';
export type ActiveTab = 'idea' | 'article' | 'review' | 'tracking' | 'settings' | 'telemetry' | 'overview';
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
  packageError?: string;
  /** Checkpoint publicado pelo package-job (ex.: "script:persistindo").
   *  É o que transforma o spinner cego em progresso legível. */
  packageStage?: string;
  packageStageDetail?: string;
  packageStageAt?: number;
  workflowStage?: WorkflowStage;
  /** Plano de publicação da semana (D+1..D+7), persistido na aprovação para
   * continuar visível após reload — antes vivia só na memória do ReviewTab. */
  publishPlan?: { day: number; date: string; items: { platform: string; format: string; title: string; scheduledAt: string }[] }[];
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

/** Frase curta de orientação por etapa — reduz a chance de o usuário se perder no fluxo. */
const STEP_HINTS: Record<ActiveTab, string> = {
  idea: 'Converse com o CMO sobre o tema da semana até ele fechar a pauta com título, tese e público.',
  article: 'Revise e edite o artigo gerado. Publicar dispara automaticamente a geração do roteiro em background.',
  review: 'Revise o roteiro, thumbnails e derivações. Aprovar dispara a produção de vídeo e a publicação agendada.',
  tracking: 'Acompanhe o status de cada etapa da pipeline de produção em tempo real.',
  settings: '',
  telemetry: '',
  overview: '',
};

/** Nome do workspace atual — hoje só existe um (Victor Zore), mas o badge já
 * prepara a UI para múltiplos workspaces/tenants futuramente. */
const WORKSPACE_NAME = process.env.NEXT_PUBLIC_TENANT_ID || 'éozoré · Pessoal';

/**
 * "Artigo" fica sempre destravado: além de escrever um artigo novo a partir da
 * pauta do CMO, essa aba também lista artigos JÁ publicados para retomar o
 * pacote (roteiro/thumbnails/copies) sem precisar conversar com o CMO de novo
 * — CMO e artigos prontos são dois pontos de entrada independentes no fluxo,
 * não uma sequência obrigatória.
 */
function isTabUnlocked(tabId: ActiveTab, draft: DraftState): boolean {
  switch (tabId) {
    case 'idea': return true;
    case 'article': return true;
    case 'review': return Boolean(draft.publishedArticleUrl && draft.packageStatus !== 'idle');
    case 'tracking': return ['approved', 'publishing', 'published'].includes(draft.workflowStage ?? '');
    default: return true;
  }
}

function lockMessage(tabId: ActiveTab): string {
  if (tabId === 'review') return 'Publique um artigo (novo ou retomado) para gerar o pacote';
  if (tabId === 'tracking') return 'Aprove o pacote para acompanhar a pipeline';
  return 'Complete a etapa anterior';
}

/** Abas fora do fluxo de 4 passos — não entram no stepper nem travam navegação. */
const META_TABS: ActiveTab[] = ['settings', 'telemetry', 'overview'];
function isMetaTab(tab: ActiveTab): boolean {
  return META_TABS.includes(tab);
}

export default function CsmDashboard() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('idea');
  const [lastStudioTab, setLastStudioTab] = useState<ActiveTab>('idea');
  const [draft, setDraft] = useState<DraftState>(INITIAL_DRAFT);
  const [sessionId, setSessionId] = useState('');
  const [loadingSession, setLoadingSession] = useState(true);
  const [lockTooltip, setLockTooltip] = useState<string | null>(null);
  /** Alerta ambiente: soma de projetos travados/com erro em QUALQUER sessão,
   * não só a atual — visível no rodapé o tempo todo, sem precisar abrir a
   * Visão Geral para descobrir que algo parou de responder. */
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    let id = localStorage.getItem('csm_session_id');
    if (!id) { id = crypto.randomUUID(); localStorage.setItem('csm_session_id', id); }
    setSessionId(id);
  }, []);

  useEffect(() => {
    const checkAlerts = async () => {
      try {
        const res = await fetch('/api/csm/overview');
        if (res.ok) {
          const data = await res.json();
          setAlertCount((data.stuckCount ?? 0) + (data.errorCount ?? 0));
        }
      } catch { /* silencioso — não é crítico */ }
    };
    checkAlerts();
    const interval = setInterval(checkAlerts, 90_000);
    return () => clearInterval(interval);
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

  /**
   * Autosave com debounce.
   *
   * Antes, `updateDraft` disparava um POST a cada chamada — ou seja, uma
   * escrita no Firestore por TECLA digitada no editor do artigo e por chunk de
   * SSE durante a geração. O Firestore sustenta ~1 escrita/s por documento;
   * isso ficava ordens de grandeza acima, gerando contenção e escritas
   * perdidas. Agora acumulamos em um ref e gravamos uma vez após a pausa.
   */
  const pendingDraftRef = useRef<DraftState | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [saveError, setSaveError] = useState('');

  const flushDraft = useCallback(async () => {
    if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
    const next = pendingDraftRef.current;
    if (!next || !sessionId) return;

    // Durante a geração do pacote quem escreve na sessão é o servidor
    // (/api/csm/package grava manifesto, thumbnails e copies). Um autosave do
    // cliente com estado anterior ao último poll sobrescreveria esses campos.
    // O ReviewTab já faz polling, então nada se perde ao pular aqui.
    if (next.packageStatus === 'generating') return;

    pendingDraftRef.current = null;
    setSaveState('saving');
    try {
      const res = await fetch('/api/csm/session', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId, draft: next }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      setSaveState('saved'); setSaveError('');
    } catch (error) {
      // Mantém o draft pendente para a próxima tentativa em vez de descartá-lo.
      pendingDraftRef.current = next;
      setSaveState('error');
      setSaveError(error instanceof Error ? error.message : 'falha ao salvar');
      console.error('[csm] draft save failed', error);
    }
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
      pendingDraftRef.current = next;
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => void flushDraft(), 2_500);
      return next;
    });
  }, [flushDraft]);

  // Rede de segurança: grava o que estiver pendente ao trocar de aba do
  // navegador, ao fechar e ao desmontar — o debounce nunca pode custar a
  // última edição do usuário.
  useEffect(() => {
    if (!sessionId) return;
    const onHide = () => { if (document.visibilityState === 'hidden') void flushDraft(); };
    document.addEventListener('visibilitychange', onHide);
    window.addEventListener('pagehide', onHide);
    const interval = setInterval(() => void flushDraft(), 30_000);
    return () => {
      document.removeEventListener('visibilitychange', onHide);
      window.removeEventListener('pagehide', onHide);
      clearInterval(interval);
      void flushDraft();
    };
  }, [flushDraft, sessionId]);

  const goToTab = (tab: ActiveTab) => {
    if (!isMetaTab(tab) && !isTabUnlocked(tab, draft)) {
      setLockTooltip(lockMessage(tab));
      setTimeout(() => setLockTooltip(null), 3000);
      return;
    }
    if (!isMetaTab(tab)) setLastStudioTab(tab);
    setActiveTab(tab);
  };

  const startNewSession = () => {
    if (!window.confirm('Iniciar nova pauta? Isso limpará a sessão atual.')) return;
    const id = crypto.randomUUID();
    localStorage.setItem('csm_session_id', id);
    setDraft(INITIAL_DRAFT); setSessionId(id); setActiveTab('idea');
  };

  /** Usado pela Visão Geral: pula direto para a sessão de outro projeto. */
  const openSession = (targetSessionId: string) => {
    if (targetSessionId === sessionId) { setActiveTab('review'); return; }
    localStorage.setItem('csm_session_id', targetSessionId);
    setLoadingSession(true);
    setSessionId(targetSessionId);
    // O useEffect de [sessionId] recarrega o draft; manda para "Pacote" — é
    // onde faz sentido pousar ao abrir um projeto que já tem conteúdo gerado.
    setActiveTab('review');
  };

  /**
   * Enfileira a geração do pacote e volta na hora.
   *
   * Antes esta função aguardava o fetch inteiro — de 4 a 8 minutos — e só
   * gravava estado quando a promise resolvia. Fechar a aba no meio perdia
   * tudo. Agora /api/csm/package devolve 202 e o package-job (Cloud Run Job)
   * executa em background gravando checkpoints; o polling do ReviewTab lê
   * esses checkpoints do Firestore e mostra o progresso real.
   */
  const startPackageGeneration = useCallback(async (articleContent: string) => {
    updateDraft({
      packageStatus: 'generating',
      packageStartedAt: Date.now(),
      workflowStage: 'package_generating',
      packageStage: 'script:enviando',
      packageError: '',
    } as Partial<DraftState>);

    try {
      const response = await fetch('/api/csm/package', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pauta: draft.pauta,
          chatTranscript: (draft.chatHistory ?? []).map((message) => `${message.role}: ${message.text}`).join('\n\n'),
          category: draft.category,
          language: draft.language,
          sessionId,
          articleContent,
          phase: 'script',
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      // 202 — a partir daqui quem manda é o job. O estado vem do polling.
    } catch (error) {
      updateDraft({
        packageStatus: 'error',
        workflowStage: 'error',
        packageError: error instanceof Error ? error.message : 'Falha ao enfileirar a geração do pacote',
      } as Partial<DraftState>);
    }
  }, [draft, sessionId, updateDraft]);

  const handlePublished = useCallback((url: string, packageAlreadyStarted = false) => {
    updateDraft({ publishedArticleUrl: url });
    setActiveTab('review');
    if (!packageAlreadyStarted) void startPackageGeneration(draft.generatedContent);
  }, [draft.generatedContent, startPackageGeneration, updateDraft]);

  const tabIndex = MAIN_TABS.findIndex((tab) => tab.id === activeTab);

  return (
    <AuthGate>
      <div className={styles.layout}>
        <div className={styles.blob1} /><div className={styles.blob2} /><div className={styles.blob3} />
        <header className={styles.header}><div className={styles.headerInner}>
          <div className={styles.headerLogo}><span className={styles.logoAccent}>é</span><span className={styles.logoBase}>ozoré</span><span className={styles.headerSep}>/</span><span className={styles.headerTitle}>Content Studio</span></div>
          <div className={styles.headerMeta}>
            <span className={styles.workspaceBadge} title="Workspace atual — cada workspace terá pauta, canais e chaves isolados">
              <span className={styles.workspaceBadgeDot} />{WORKSPACE_NAME}
            </span>
            <button onClick={startNewSession} className={styles.newSessionBtn}>Nova Reunião</button>
            <span className={styles.badge}>Internal Tool</span>
          </div>
        </div></header>

        {!isMetaTab(activeTab) && <nav className={styles.tabNav}><div className={styles.tabNavInner}>
          {MAIN_TABS.map((tab, index) => {
            const unlocked = isTabUnlocked(tab.id, draft);
            return <button key={tab.id} onClick={() => goToTab(tab.id)} disabled={loadingSession || !unlocked} title={!unlocked ? lockMessage(tab.id) : undefined} className={`${styles.tabBtn} ${activeTab === tab.id ? styles.tabBtnActive : ''} ${index < tabIndex ? styles.tabBtnDone : ''} ${!unlocked ? styles.tabBtnLocked : ''}`}>
              <span className={styles.tabIndex}>{tab.index}</span><span className={styles.tabLabel}>{tab.label}</span><span className={styles.tabDesc}>{tab.description}</span>{index < tabIndex && unlocked && <span className={styles.tabCheck}>✓</span>}{!unlocked && <span className={styles.tabLock}>🔒</span>}
            </button>;
          })}
          <div className={styles.progressBar}><div className={styles.progressFill} style={{ width: `${Math.max(0, tabIndex) / (MAIN_TABS.length - 1) * 100}%` }} /></div>
        </div>{lockTooltip && <div className={styles.lockTooltip}>🔒 {lockTooltip}</div>}
        {STEP_HINTS[activeTab] && (
          <div className={styles.stepHint}><span className={styles.stepHintDot} />{STEP_HINTS[activeTab]}</div>
        )}
        </nav>}

        <main className={styles.main}>{loadingSession ? <div className={styles.loadingState}><div className={styles.loadingSpinner} /><span className={styles.loadingText}>carregando sessão...</span></div> : <>
          {activeTab === 'idea' && <IdeaTab draft={draft} updateDraft={updateDraft} isGenerating={false} setIsGenerating={() => undefined} sessionId={sessionId} onNext={() => goToTab('article')} />}
          {activeTab === 'article' && <ArticleTab draft={draft} updateDraft={updateDraft} sessionId={sessionId} onBack={() => goToTab('idea')} onPublished={handlePublished} />}
          {activeTab === 'review' && <ReviewTab draft={draft} updateDraft={updateDraft} sessionId={sessionId} onBack={() => goToTab('article')} onApproved={() => { updateDraft({ workflowStage: 'approved' }); goToTab('tracking'); }} onRetryPackage={() => void startPackageGeneration(draft.generatedContent)} />}
          {activeTab === 'tracking' && <TrackingTab draft={draft} sessionId={sessionId} onBack={() => goToTab('review')} />}
          {activeTab === 'settings' && <SettingsTab onBack={() => goToTab(lastStudioTab)} />}
          {activeTab === 'telemetry' && <TelemetryTab onBack={() => goToTab(lastStudioTab)} />}
          {activeTab === 'overview' && <OverviewTab onBack={() => goToTab(lastStudioTab)} onOpenSession={openSession} />}
        </>}</main>

        <footer className={styles.bottomBar}><span className={styles.bottomBarText}>éozoré Studio</span>
          {/* Estado do autosave. Antes a gravação falhava em silêncio e o
              usuário só descobria no reload seguinte, com o trabalho perdido. */}
          {saveState !== 'idle' && (
            <span
              className={styles.saveState}
              title={saveState === 'error' ? saveError : undefined}
              style={{ color: saveState === 'error' ? '#dc2626' : saveState === 'saving' ? '#8a8a8a' : '#16a34a' }}
            >
              {saveState === 'saving' ? '⟳ salvando…' : saveState === 'saved' ? '✓ salvo' : `✗ não salvo — ${saveError}`}
            </span>
          )}
          <div className={styles.bottomBarDivider} /><button onClick={() => goToTab(lastStudioTab)} className={`${styles.bottomBarLink} ${!isMetaTab(activeTab) ? styles.bottomBarLinkActive : ''}`}>📝 Studio</button><div className={styles.bottomBarDivider} /><button onClick={() => goToTab('overview')} className={`${styles.bottomBarLink} ${activeTab === 'overview' ? styles.bottomBarLinkActive : ''}`} style={{ position: 'relative' }}>
            🗂️ Visão Geral
            {alertCount > 0 && <span className={styles.alertBadge}>{alertCount}</span>}
          </button><div className={styles.bottomBarDivider} /><button onClick={() => goToTab('settings')} className={`${styles.bottomBarLink} ${activeTab === 'settings' ? styles.bottomBarLinkActive : ''}`}>⚙️ Ajustes</button><div className={styles.bottomBarDivider} /><button onClick={() => goToTab('telemetry')} className={`${styles.bottomBarLink} ${activeTab === 'telemetry' ? styles.bottomBarLinkActive : ''}`}>📊 Telemetria</button></footer>
      </div>
    </AuthGate>
  );
}
