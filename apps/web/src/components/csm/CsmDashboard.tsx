/* ============================================================
   CsmDashboard.tsx — Dashboard principal da CSM Tool
   Gerencia estado global da sessão de criação e navegação entre abas
   ============================================================ */
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import AuthGate from './AuthGate';
import IdeaTab from './tabs/IdeaTab';
import GenerateTab from './tabs/GenerateTab';
import PublishTab from './tabs/PublishTab';
import YoutubeTab from './tabs/YoutubeTab';
import RepurposeTab from './tabs/RepurposeTab';
import SettingsTab from './tabs/SettingsTab';
import TelemetryTab from './tabs/TelemetryTab';
import type { ArticleCategory } from '@/types/article';
import styles from './CsmDashboard.module.css';

export type OutputFormat = 'blog' | 'youtube' | 'linkedin';
export type ActiveTab = 'idea' | 'generate' | 'publish' | 'youtube' | 'repurpose' | 'settings' | 'telemetry';
export type ContentStatus = 'em_revisao' | 'aprovado' | 'rejeitado';

export interface AttachmentItem {
  id: string;
  name: string;
  url: string;
  type: 'image' | 'pdf' | 'diagram' | 'data';
  tags: ('artigo' | 'linkedin' | 'carrossel' | 'youtube' | 'reels' | 'stories')[];
}

export interface LinkedInDraft {
  id: string;
  hook: string;
  copy: string;
  scheduledAt?: string;
  status: ContentStatus;
}

export interface YouTubeDraft {
  id: string;
  title: string;
  script: string;
  scheduledAt?: string;
  status: ContentStatus;
}

export interface YouTubeShortsDraft {
  id: string;
  title: string;
  hook3s: string;
  script: string;
  scheduledAt?: string;
  status: ContentStatus;
}

export interface ReelDraft {
  id: string;
  title: string;
  hook3s: string;
  visualCue: string;
  script: string;
  scheduledAt?: string;
  status: ContentStatus;
}

export interface CarouselDraft {
  id: string;
  title: string;
  caption: string;
  slides: { slideNumber: number; heading: string; body: string }[];
  scheduledAt?: string;
  status: ContentStatus;
}

export interface ImageDraft {
  id: string;
  title: string;
  imageDescription: string;
  copy: string;
  scheduledAt?: string;
  status: ContentStatus;
}

export interface StoryDraft {
  id: string;
  day: string;
  angle: string;
  copy: string;
  interactiveElement?: string;
  scheduledAt?: string;
  status: ContentStatus;
}

export interface RepurposedData {
  linkedinPosts: LinkedInDraft[];
  youtubeScripts: YouTubeDraft[];
  youtubeShorts: YouTubeShortsDraft[];
  reelsScripts: ReelDraft[];
  carousels: CarouselDraft[];
  imagePosts: ImageDraft[];
  storiesIdeas: StoryDraft[];
}

export interface ChatMessage {
  role: 'user' | 'model';
  text: string;
}

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
}

const INITIAL_DRAFT: DraftState = {
  topic: '',
  context: '',
  format: 'blog',
  category: 'ml',
  language: 'pt-BR',
  generatedContent: '',
  youtubeScript: '',
  suggestedTitle: '',
  suggestedSlug: '',
  estimatedReadTime: 10,
  repurposedData: null,
  attachments: [],
  chatHistory: [],
  blocks: [],
  youtubeScenes: [],
};

const TABS: { id: ActiveTab; label: string; index: string; description: string }[] = [
  { id: 'idea', label: 'Bate-Papo CMO', index: '01', description: 'Entrevista estratégica' },
  { id: 'generate', label: 'Geração', index: '02', description: 'Editor & preview' },
  { id: 'publish', label: 'Publicação', index: '03', description: 'Metadados & publish' },
  { id: 'youtube', label: 'YouTube Roteiro', index: '04', description: 'Editor de roteiro' },
  { id: 'repurpose', label: 'Derivações', index: '05', description: 'Agendamento semanal' },
];

export default function CsmDashboard() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('idea');
  const [lastActiveStudioTab, setLastActiveStudioTab] = useState<ActiveTab>('idea');
  const [draft, setDraft] = useState<DraftState>(INITIAL_DRAFT);
  const [isGenerating, setIsGenerating] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [isLoadingSession, setIsLoadingSession] = useState(true);

  // Initialize session ID from localStorage on mount
  useEffect(() => {
    let id = localStorage.getItem('csm_session_id');
    if (!id) {
      id = typeof crypto !== 'undefined'
        ? crypto.randomUUID()
        : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem('csm_session_id', id);
    }
    setSessionId(id);
  }, []);

  // Load session from Firestore when sessionId is available
  useEffect(() => {
    if (!sessionId) return;

    const fetchSession = async () => {
      try {
        setIsLoadingSession(true);
        const res = await fetch(`/api/csm/session?id=${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.draft) {
            // Restore entire draft workspace state with safe default fallbacks
            setDraft((prev) => ({
              ...prev,
              ...data.draft,
              chatHistory: data.draft.chatHistory || prev.chatHistory || [],
              attachments: data.draft.attachments || prev.attachments || [],
              blocks: data.draft.blocks || prev.blocks || [],
              youtubeScenes: data.draft.youtubeScenes || prev.youtubeScenes || [],
            }));
          } else {
            // Fallback for older sessions
            setDraft((prev) => ({
              ...prev,
              chatHistory: data.messages || [],
              topic: data.messages && data.messages.length > 0
                ? data.messages.filter((m: any) => m.role === 'user').pop()?.text || ''
                : '',
            }));
          }
        } else {
          console.log('[csm] No existing session found on Firestore. Starting fresh.');
        }
      } catch (err) {
        console.error('[csm] Failed to load session:', err);
      } finally {
        setIsLoadingSession(false);
      }
    };

    fetchSession();
  }, [sessionId]);

  const saveDraftToServer = useCallback(async (currentDraft: DraftState) => {
    if (!sessionId) return;
    try {
      await fetch('/api/csm/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId, draft: currentDraft }),
      });
    } catch (err) {
      console.warn('[csm] Failed to autosave draft to server:', err);
    }
  }, [sessionId]);

  // Background auto-save every 30 seconds to prevent data loss
  useEffect(() => {
    if (!sessionId) return;
    const interval = setInterval(() => {
      saveDraftToServer(draft);
    }, 30000);
    return () => clearInterval(interval);
  }, [sessionId, draft, saveDraftToServer]);

  const updateDraft = (partial: Partial<DraftState>) => {
    setDraft((prev) => {
      const next = { ...prev, ...partial };
      
      // Auto-parse generatedContent into blocks if it changed and blocks are not explicitly provided
      if (partial.generatedContent !== undefined && partial.blocks === undefined) {
        const { parseMarkdownToBlocks } = require('@/lib/blockParser');
        next.blocks = parseMarkdownToBlocks(partial.generatedContent);
      }

      // Auto-parse youtubeScript into scenes if it changed and scenes are not explicitly provided
      if (partial.youtubeScript !== undefined && partial.youtubeScenes === undefined) {
        const { parseMarkdownToScenes } = require('@/lib/scriptParser');
        next.youtubeScenes = parseMarkdownToScenes(partial.youtubeScript);
      }
      
      saveDraftToServer(next);
      return next;
    });
  };

  const startNewSession = () => {
    const confirmNew = window.confirm('Deseja iniciar uma nova pauta e reunião? Isso limpará a pauta em andamento.');
    if (!confirmNew) return;

    const newId = typeof crypto !== 'undefined'
      ? crypto.randomUUID()
      : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem('csm_session_id', newId);
    setDraft(INITIAL_DRAFT);
    setSessionId(newId);
    setActiveTab('idea');
  };

  const goToTab = (tab: ActiveTab) => {
    if (tab !== 'settings' && tab !== 'telemetry') {
      setLastActiveStudioTab(tab);
    }
    setActiveTab(tab);
  };

  const tabIndex = TABS.findIndex((t) => t.id === activeTab);

  return (
    <AuthGate>
      <div className={styles.layout}>
        {/* Global blobs */}
        <div className={styles.blob1} />
        <div className={styles.blob2} />
        <div className={styles.blob3} />

        {/* Header */}
        <header className={styles.header}>
          <div className={styles.headerInner}>
            <div className={styles.headerLogo}>
              <span className={styles.logoAccent}>é</span>
              <span className={styles.logoBase}>ozoré</span>
              <span className={styles.headerSep}>/</span>
              <span className={styles.headerTitle}>Content Studio</span>
            </div>
            <div className={styles.headerMeta}>
              <button onClick={startNewSession} className={styles.newSessionBtn}>
                Nova Reunião
              </button>
              <span className={styles.badge}>Internal Tool</span>
            </div>
          </div>
        </header>

        {/* Tab Navigation */}
        {activeTab !== 'settings' && activeTab !== 'telemetry' && (
          <nav className={styles.tabNav}>
            <div className={styles.tabNavInner}>
              {TABS.map((tab, idx) => (
                <button
                  key={tab.id}
                  onClick={() => goToTab(tab.id)}
                  className={`${styles.tabBtn} ${activeTab === tab.id ? styles.tabBtnActive : ''} ${
                    idx < tabIndex ? styles.tabBtnDone : ''
                  }`}
                  aria-current={activeTab === tab.id ? 'page' : undefined}
                  disabled={isLoadingSession}
                >
                  <span className={styles.tabIndex}>{tab.index}</span>
                  <span className={styles.tabLabel}>{tab.label}</span>
                  <span className={styles.tabDesc}>{tab.description}</span>
                  {idx < tabIndex && (
                    <span className={styles.tabCheck}>✓</span>
                  )}
                </button>
              ))}
              {/* Progress line */}
              <div className={styles.progressBar}>
                <div
                  className={styles.progressFill}
                  style={{ width: `${(tabIndex / (TABS.length - 1)) * 100}%` }}
                />
              </div>
            </div>
          </nav>
        )}

        {/* Main content */}
        <main className={styles.main}>
          {isLoadingSession ? (
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '300px', gap: '1rem', color: '#94a3b8' }}>
              <div style={{
                width: '40px',
                height: '40px',
                border: '3px solid rgba(230, 126, 34, 0.1)',
                borderTopColor: '#e67e22',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
              }}>
                <style>{`
                  @keyframes spin {
                    to { transform: rotate(360deg); }
                  }
                `}</style>
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.9rem', letterSpacing: '0.05em' }}>Carregando reunião com CMO...</span>
            </div>
          ) : (
            <>
              {activeTab === 'idea' && (
                <IdeaTab
                  draft={draft}
                  updateDraft={updateDraft}
                  isGenerating={isGenerating}
                  setIsGenerating={setIsGenerating}
                  sessionId={sessionId}
                  onNext={() => goToTab('generate')}
                />
              )}
              {activeTab === 'generate' && (
                <GenerateTab
                  draft={draft}
                  updateDraft={updateDraft}
                  sessionId={sessionId}
                  onBack={() => goToTab('idea')}
                  onNext={() => goToTab('publish')}
                />
              )}
              {activeTab === 'publish' && (
                <PublishTab
                  draft={draft}
                  updateDraft={updateDraft}
                  onBack={() => goToTab('generate')}
                  onNext={() => goToTab('youtube')}
                />
              )}
              {activeTab === 'youtube' && (
                <YoutubeTab
                  draft={draft}
                  updateDraft={updateDraft}
                  sessionId={sessionId}
                  onBack={() => goToTab('publish')}
                  onNext={() => goToTab('repurpose')}
                />
              )}
              {activeTab === 'repurpose' && (
                <RepurposeTab
                  draft={draft}
                  updateDraft={updateDraft}
                  sessionId={sessionId}
                  onBack={() => goToTab('youtube')}
                />
              )}
              {activeTab === 'settings' && (
                <SettingsTab
                  onBack={() => goToTab(lastActiveStudioTab)}
                />
              )}
              {activeTab === 'telemetry' && (
                <TelemetryTab
                  onBack={() => goToTab(lastActiveStudioTab)}
                />
              )}
            </>
          )}
        </main>

        {/* Bottom Floating Bar */}
        <footer className={styles.bottomBar}>
          <span className={styles.bottomBarText}>éozoré Studio</span>
          <div className={styles.bottomBarDivider} />
          <button
            onClick={() => goToTab(lastActiveStudioTab)}
            className={`${styles.bottomBarLink} ${activeTab !== 'settings' && activeTab !== 'telemetry' ? styles.bottomBarLinkActive : ''}`}
          >
            📝 Studio de Criação
          </button>
          <div className={styles.bottomBarDivider} />
          <button
            onClick={() => goToTab('settings')}
            className={`${styles.bottomBarLink} ${activeTab === 'settings' ? styles.bottomBarLinkActive : ''}`}
          >
            ⚙️ Ajustes de IA
          </button>
          <div className={styles.bottomBarDivider} />
          <button
            onClick={() => goToTab('telemetry')}
            className={`${styles.bottomBarLink} ${activeTab === 'telemetry' ? styles.bottomBarLinkActive : ''}`}
          >
            📊 Uso & Telemetria
          </button>
        </footer>
      </div>
    </AuthGate>
  );
}
