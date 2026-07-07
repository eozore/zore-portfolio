'use client';

import { useState, useEffect } from 'react';
import styles from './SettingsTab.module.css';

interface AgentConfig {
  name: string;
  label: string;
  fallbackPrompt: string;
  activePrompt: string;
  isCustomized: boolean;
}

interface ApiKey {
  name: string;
  label: string;
  maskedValue: string;
  isSet: boolean;
}

interface SettingsTabProps {
  onBack: () => void;
}

export default function SettingsTab({ onBack }: SettingsTabProps) {
  const [configs, setConfigs] = useState<AgentConfig[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [editedPrompt, setEditedPrompt] = useState<string>('');
  const [editedKeys, setEditedKeys] = useState<Record<string, string>>({});
  const [keysEnvironment, setKeysEnvironment] = useState<'production' | 'development'>('development');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSavingKey, setIsSavingKey] = useState<Record<string, boolean>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [showFallback, setShowFallback] = useState(false);

  // Video Templates States
  const [templates, setTemplates] = useState<any[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [editedHtml, setEditedHtml] = useState<string>('');
  const [isSavingTemplate, setIsSavingTemplate] = useState(false);

  // Avatars Config State
  const [avatarsConfig, setAvatarsConfig] = useState({
    horizontal: { avatarId: '', voiceId: '' },
    vertical: { avatarId: '', voiceId: '' },
  });
  const [isSavingAvatars, setIsSavingAvatars] = useState(false);

  const fetchAvatars = async () => {
    try {
      const res = await fetch('/api/csm/config/avatars', {
        headers: {
          'x-csm-session': 'authenticated',
        },
      });
      if (res.ok) {
        const data = await res.json();
        setAvatarsConfig({
          horizontal: data.horizontal || { avatarId: '', voiceId: '' },
          vertical: data.vertical || { avatarId: '', voiceId: '' },
        });
      }
    } catch (err) {
      console.error('Failed to fetch avatars:', err);
    }
  };

  const handleSaveAvatars = async () => {
    setIsSavingAvatars(true);
    setToastMessage(null);
    try {
      const res = await fetch('/api/csm/config/avatars', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csm-session': 'authenticated',
        },
        body: JSON.stringify(avatarsConfig),
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || 'Configurações de avatares salvas com sucesso!');
      } else {
        alert(data.error || 'Erro ao salvar avatares.');
      }
    } catch (err) {
      console.error(err);
      alert('Erro ao salvar avatares.');
    } finally {
      setIsSavingAvatars(false);
    }
  };

  const fetchKeys = async () => {
    try {
      const res = await fetch('/api/csm/config/keys', {
        method: 'GET',
        headers: {
          'x-csm-session': 'authenticated',
        },
      });
      if (res.ok) {
        const data = await res.json();
        setApiKeys(data.keys || []);
        setKeysEnvironment(data.environment || 'development');
      }
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
    }
  };

  const fetchTemplates = async () => {
    try {
      const res = await fetch('/api/csm/config/templates', {
        method: 'GET',
        headers: {
          'x-csm-session': 'authenticated',
        },
      });
      if (res.ok) {
        const data = await res.json();
        setTemplates(data.templates || []);
        if (data.templates && data.templates.length > 0) {
          const first = data.templates[0];
          setSelectedTemplateId(first.id);
          setEditedHtml(first.activeHtml);
        }
      }
    } catch (err) {
      console.error('Failed to fetch video templates:', err);
    }
  };

  // Fetch configurations on mount
  useEffect(() => {
    const fetchConfigs = async () => {
      try {
        setIsLoading(true);
        const res = await fetch('/api/csm/config', {
          method: 'GET',
          headers: {
            'x-csm-session': 'authenticated',
          },
        });

        if (res.ok) {
          const data = await res.json();
          setConfigs(data.configs || []);
          if (data.configs && data.configs.length > 0) {
            const first = data.configs[0];
            setSelectedAgent(first.name);
            setEditedPrompt(first.activePrompt);
          }
        } else {
          console.error('Failed to load agent configurations');
        }
      } catch (err) {
        console.error('Error fetching configurations:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchConfigs();
    fetchKeys();
    fetchTemplates();
    fetchAvatars();
  }, []);

  const activeAgentConfig = configs.find((c) => c.name === selectedAgent);

  const handleSelectAgent = (name: string) => {
    setSelectedAgent(name);
    const target = configs.find((c) => c.name === name);
    if (target) {
      setEditedPrompt(target.activePrompt);
    }
    setShowFallback(false);
  };

  const handleSelectTemplate = (id: string) => {
    setSelectedTemplateId(id);
    const target = templates.find((t) => t.id === id);
    if (target) {
      setEditedHtml(target.activeHtml);
    }
  };

  const handleSaveTemplate = async () => {
    if (!selectedTemplateId) return;
    setIsSavingTemplate(true);
    setToastMessage(null);

    try {
      const res = await fetch('/api/csm/config/templates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csm-session': 'authenticated',
        },
        body: JSON.stringify({
          templateId: selectedTemplateId,
          htmlContent: editedHtml,
        }),
      });

      const resData = await res.json();

      if (res.ok) {
        setTemplates((prev) =>
          prev.map((t) =>
            t.id === selectedTemplateId
              ? {
                  ...t,
                  activeHtml: editedHtml,
                  isCustomized: editedHtml !== t.fallbackHtml,
                }
              : t
          )
        );
        showToast(resData.message || 'Template salvo com sucesso!');
      } else {
        alert(resData.error || 'Erro ao gravar o template.');
      }
    } catch (err) {
      console.error('Error updating template:', err);
      alert('Erro de comunicação ao salvar.');
    } finally {
      setIsSavingTemplate(false);
    }
  };

  const handleResetTemplate = () => {
    const target = templates.find((t) => t.id === selectedTemplateId);
    if (!target) return;
    const confirmReset = window.confirm(
      'Tem certeza que deseja restaurar este template para o padrão de fábrica?'
    );
    if (!confirmReset) return;

    setEditedHtml(target.fallbackHtml);
    setTimeout(async () => {
      setIsSavingTemplate(true);
      try {
        const res = await fetch('/api/csm/config/templates', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-csm-session': 'authenticated',
          },
          body: JSON.stringify({
            templateId: selectedTemplateId,
            htmlContent: target.fallbackHtml,
          }),
        });
        const resData = await res.json();
        if (res.ok) {
          setTemplates((prev) =>
            prev.map((t) =>
              t.id === selectedTemplateId
                ? {
                    ...t,
                    activeHtml: t.fallbackHtml,
                    isCustomized: false,
                  }
                : t
            )
          );
          showToast('Template redefinido com sucesso!');
        }
      } catch (err) {
        console.error(err);
      } finally {
        setIsSavingTemplate(false);
      }
    }, 100);
  };

  const handleSave = async () => {
    if (!selectedAgent) return;
    setIsSaving(true);
    setToastMessage(null);

    try {
      const res = await fetch('/api/csm/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csm-session': 'authenticated',
        },
        body: JSON.stringify({
          agentName: selectedAgent,
          systemInstruction: editedPrompt,
        }),
      });

      const resData = await res.json();

      if (res.ok) {
        setConfigs((prev) =>
          prev.map((c) =>
            c.name === selectedAgent
              ? {
                  ...c,
                  activePrompt: editedPrompt,
                  isCustomized: editedPrompt !== c.fallbackPrompt,
                }
              : c
          )
        );
        showToast(resData.message || 'Configuração salva com sucesso!');
      } else {
        alert(resData.error || 'Erro ao gravar as configurações.');
      }
    } catch (err) {
      console.error('Error updating configuration:', err);
      alert('Erro de comunicação ao salvar.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveKey = async (keyName: string) => {
    const val = editedKeys[keyName];
    if (val === undefined || val.trim() === '') return;

    setIsSavingKey((prev) => ({ ...prev, [keyName]: true }));
    setToastMessage(null);

    try {
      const res = await fetch('/api/csm/config/keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csm-session': 'authenticated',
        },
        body: JSON.stringify({
          keyName,
          keyValue: val,
        }),
      });

      const resData = await res.json();

      if (res.ok) {
        showToast(resData.message || `Chave ${keyName} gravada com sucesso!`);
        // Clean form field state
        setEditedKeys((prev) => {
          const next = { ...prev };
          delete next[keyName];
          return next;
        });
        // Reload API keys representation to get fresh masks
        await fetchKeys();
      } else {
        alert(resData.error || 'Erro ao salvar a chave.');
      }
    } catch (err) {
      console.error('Error updating key:', err);
      alert('Erro ao enviar dados.');
    } finally {
      setIsSavingKey((prev) => ({ ...prev, [keyName]: false }));
    }
  };

  const handleReset = () => {
    if (!activeAgentConfig) return;
    const confirmReset = window.confirm(
      'Tem certeza que deseja restaurar as instruções deste agente para o padrão de fábrica?'
    );
    if (!confirmReset) return;

    setEditedPrompt(activeAgentConfig.fallbackPrompt);
    setTimeout(async () => {
      setIsSaving(true);
      try {
        const res = await fetch('/api/csm/config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-csm-session': 'authenticated',
          },
          body: JSON.stringify({
            agentName: selectedAgent,
            systemInstruction: activeAgentConfig.fallbackPrompt,
          }),
        });
        const resData = await res.json();
        if (res.ok) {
          setConfigs((prev) =>
            prev.map((c) =>
              c.name === selectedAgent
                ? {
                    ...c,
                    activePrompt: c.fallbackPrompt,
                    isCustomized: false,
                  }
                : c
            )
          );
          showToast('Redefinido para o padrão com sucesso!');
        }
      } catch (err) {
        console.error(err);
      } finally {
        setIsSaving(false);
      }
    }, 100);
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 4500);
  };

  if (isLoading) {
    return (
      <div className={styles.card} style={{ textAlign: 'center', padding: '60px' }}>
        <div style={{ color: '#e67e22', fontSize: '2rem', animation: 'spin 2s linear infinite' }}>⚙️</div>
        <p style={{ color: '#94a3b8', marginTop: '16px' }}>Carregando configurações de agentes...</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.card}>
        <div className={styles.headerRow}>
          <div>
            <h1 className={styles.title}>Configurações de Agentes & Chaves</h1>
            <p className={styles.subtitle}>
              Modifique instruções de IA e gerencie credenciais de API de forma centralizada e segura.
            </p>
          </div>
          <button onClick={onBack} className={styles.btnBack}>
            ← Voltar ao CMO
          </button>
        </div>
      </div>

      {/* Main Split Panel */}
      <div className={styles.layout}>
        {/* Sidebar */}
        <div className={styles.sidebar}>
          <div style={{ color: 'rgba(255,255,255,0.25)', fontSize: '0.75rem', fontWeight: 'bold', padding: '4px 12px 8px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Prompts de Agentes
          </div>
          {configs.map((cfg) => {
            const isActive = cfg.name === selectedAgent;
            return (
              <button
                key={cfg.name}
                onClick={() => handleSelectAgent(cfg.name)}
                className={`${styles.agentBtn} ${isActive ? styles.agentBtnActive : ''}`}
              >
                <div>{cfg.label}</div>
                <span
                  className={`${styles.agentBadge} ${
                    cfg.isCustomized ? styles.agentBadgeActive : ''
                  }`}
                >
                  {cfg.isCustomized ? '● Personalizado' : 'Padrão Local'}
                </span>
              </button>
            );
          })}
          
          <div style={{ height: '1px', background: 'rgba(255,255,255,0.06)', margin: '16px 0 8px' }} />
          
          <div style={{ color: 'rgba(255,255,255,0.25)', fontSize: '0.75rem', fontWeight: 'bold', padding: '4px 12px 8px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Credenciais
          </div>
          <button
            onClick={() => setSelectedAgent('api_keys')}
            className={`${styles.agentBtn} ${selectedAgent === 'api_keys' ? styles.agentBtnActive : ''}`}
          >
            <div>🔑 Chaves de API</div>
            <span
              className={`${styles.agentBadge} ${
                keysEnvironment === 'production' ? styles.agentBadgeActive : ''
              }`}
            >
              {keysEnvironment === 'production' ? 'GCP Secret Manager' : 'Firestore Local'}
            </span>
          </button>

          <button
            onClick={() => setSelectedAgent('avatars')}
            className={`${styles.agentBtn} ${selectedAgent === 'avatars' ? styles.agentBtnActive : ''}`}
          >
            <div>👤 Avatares & Vozes</div>
            <span className={styles.agentBadge}>
              Configuração HeyGen
            </span>
          </button>

          <div style={{ height: '1px', background: 'rgba(255,255,255,0.06)', margin: '16px 0 8px' }} />

          <div style={{ color: 'rgba(255,255,255,0.25)', fontSize: '0.75rem', fontWeight: 'bold', padding: '4px 12px 8px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            Templates & Design
          </div>
          <button
            onClick={() => {
              setSelectedAgent('html_templates');
              const videoTmpls = templates.filter((t) => !t.id.startsWith('blog_'));
              if (videoTmpls.length > 0) {
                const target = videoTmpls.find((t) => t.id === selectedTemplateId) || videoTmpls[0];
                setSelectedTemplateId(target.id);
                setEditedHtml(target.activeHtml);
              }
            }}
            className={`${styles.agentBtn} ${selectedAgent === 'html_templates' ? styles.agentBtnActive : ''}`}
          >
            <div>🎬 Templates de Vídeo</div>
            <span
              className={`${styles.agentBadge} ${
                templates.filter((t) => !t.id.startsWith('blog_')).some((t) => t.isCustomized) ? styles.agentBadgeActive : ''
              }`}
            >
              {templates.filter((t) => !t.id.startsWith('blog_')).some((t) => t.isCustomized) ? '● Personalizados' : 'Padrão'}
            </span>
          </button>

          <button
            onClick={() => {
              setSelectedAgent('blog_templates');
              const blogTmpls = templates.filter((t) => t.id.startsWith('blog_'));
              if (blogTmpls.length > 0) {
                const target = blogTmpls.find((t) => t.id === selectedTemplateId) || blogTmpls[0];
                setSelectedTemplateId(target.id);
                setEditedHtml(target.activeHtml);
              }
            }}
            className={`${styles.agentBtn} ${selectedAgent === 'blog_templates' ? styles.agentBtnActive : ''}`}
          >
            <div>📝 Componentes do Blog</div>
            <span
              className={`${styles.agentBadge} ${
                templates.filter((t) => t.id.startsWith('blog_')).some((t) => t.isCustomized) ? styles.agentBadgeActive : ''
              }`}
            >
              {templates.filter((t) => t.id.startsWith('blog_')).some((t) => t.isCustomized) ? '● Personalizados' : 'Padrão'}
            </span>
          </button>
        </div>

        {/* Editor or Keys Panel */}
        {selectedAgent === 'avatars' ? (
          <div className={styles.card} style={{ width: '100%' }}>
            <div className={styles.editorPane}>
              <div className={styles.headerRow}>
                <h2 className={styles.paneTitle}>Configurações de Avatares & Vozes (HeyGen)</h2>
                {toastMessage && <div className={styles.toast}>{toastMessage}</div>}
              </div>
              <p style={{ color: '#6b6b6b', fontSize: '0.85rem', lineHeight: '1.5', margin: '0 0 16px 0' }}>
                Configure as identidades digitais do HeyGen para geração de vídeo. O perfil Horizontal é usado em vídeos longos para o YouTube. O perfil Vertical é usado em vídeos curtos (Shorts, Reels, TikTok).
              </p>

              <div className={styles.keysContainer}>
                {/* Horizontal Profile */}
                <div style={{ padding: '16px', background: 'rgba(30, 30, 30, 0.02)', borderRadius: '12px', border: '1px solid rgba(30, 30, 30, 0.08)' }}>
                  <h3 style={{ color: '#d35400', fontSize: '1rem', fontWeight: 'bold', marginBottom: '12px' }}>📺 Perfil Horizontal (Landscape 16:9)</h3>
                  <div className={styles.keyRow} style={{ marginBottom: '12px' }}>
                    <label className={styles.keyLabel}>Avatar ID</label>
                    <input
                      type="text"
                      value={avatarsConfig.horizontal.avatarId}
                      onChange={(e) => setAvatarsConfig(prev => ({
                        ...prev,
                        horizontal: { ...prev.horizontal, avatarId: e.target.value }
                      }))}
                      className={styles.keyInput}
                      placeholder="Ex: db66746ef7d848cca675c74239857d42"
                    />
                  </div>
                  <div className={styles.keyRow}>
                    <label className={styles.keyLabel}>Voz ID (Voice ID)</label>
                    <input
                      type="text"
                      value={avatarsConfig.horizontal.voiceId}
                      onChange={(e) => setAvatarsConfig(prev => ({
                        ...prev,
                        horizontal: { ...prev.horizontal, voiceId: e.target.value }
                      }))}
                      className={styles.keyInput}
                      placeholder="Ex: 1bd0091de9434efda90327f2269a84f3"
                    />
                  </div>
                </div>

                {/* Vertical Profile */}
                <div style={{ padding: '16px', background: 'rgba(30, 30, 30, 0.02)', borderRadius: '12px', border: '1px solid rgba(30, 30, 30, 0.08)' }}>
                  <h3 style={{ color: '#d35400', fontSize: '1rem', fontWeight: 'bold', marginBottom: '12px' }}>📱 Perfil Vertical (Portrait 9:16)</h3>
                  <div className={styles.keyRow} style={{ marginBottom: '12px' }}>
                    <label className={styles.keyLabel}>Avatar ID</label>
                    <input
                      type="text"
                      value={avatarsConfig.vertical.avatarId}
                      onChange={(e) => setAvatarsConfig(prev => ({
                        ...prev,
                        vertical: { ...prev.vertical, avatarId: e.target.value }
                      }))}
                      className={styles.keyInput}
                      placeholder="Ex: db66746ef7d848cca675c74239857d42"
                    />
                  </div>
                  <div className={styles.keyRow}>
                    <label className={styles.keyLabel}>Voz ID (Voice ID)</label>
                    <input
                      type="text"
                      value={avatarsConfig.vertical.voiceId}
                      onChange={(e) => setAvatarsConfig(prev => ({
                        ...prev,
                        vertical: { ...prev.vertical, voiceId: e.target.value }
                      }))}
                      className={styles.keyInput}
                      placeholder="Ex: 1bd0091de9434efda90327f2269a84f3"
                    />
                  </div>
                </div>
              </div>

              <div className={styles.actionRow} style={{ marginTop: '16px' }}>
                <div />
                <button
                  onClick={handleSaveAvatars}
                  className={styles.btnSave}
                  disabled={isSavingAvatars}
                >
                  {isSavingAvatars ? 'Salvando...' : 'Salvar Avatares & Vozes →'}
                </button>
              </div>
            </div>
          </div>
        ) : selectedAgent === 'api_keys' ? (
          <div className={styles.card}>
            <div className={styles.editorPane}>
              <div className={styles.headerRow}>
                <div className={styles.badgeContainer}>
                  <h2 className={styles.paneTitle}>Chaves de API do Sistema</h2>
                  {keysEnvironment === 'production' ? (
                    <span className={styles.envBadgeProduction}>🟢 Produção (GCP Secret Manager)</span>
                  ) : (
                    <span className={styles.envBadgeDevelopment}>🟡 Desenvolvimento (Firestore Local)</span>
                  )}
                </div>
                {toastMessage && <div className={styles.toast}>{toastMessage}</div>}
              </div>

              <p style={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: '1.5' }}>
                As credenciais inseridas abaixo são protegidas com máscaras de segurança para evitar vazamento na tela. 
                {keysEnvironment === 'production' 
                  ? ' Ao salvar em ambiente de deploy, uma nova versão do segredo será inserida no Google Cloud Secret Manager automaticamente.' 
                  : ' Em ambiente local, os valores são armazenados de forma isolada em seu banco de dados Firestore local.'}
              </p>

              <div className={styles.keysContainer}>
                {apiKeys.map((key) => {
                  const hasEdited = editedKeys[key.name] !== undefined && editedKeys[key.name].trim() !== '';
                  const loadingKey = !!isSavingKey[key.name];
                  
                  return (
                    <div key={key.name} className={styles.keyRow}>
                      <label className={styles.keyLabel}>{key.label}</label>
                      <div className={styles.keyInputGroup}>
                        <input
                          type="password"
                          value={editedKeys[key.name] !== undefined ? editedKeys[key.name] : ''}
                          placeholder={key.maskedValue || 'Não configurada (Digite um valor para salvar)'}
                          onChange={(e) => setEditedKeys(prev => ({ ...prev, [key.name]: e.target.value }))}
                          className={styles.keyInput}
                        />
                        <button
                          onClick={() => handleSaveKey(key.name)}
                          disabled={!hasEdited || loadingKey}
                          className={styles.btnKeySave}
                        >
                          {loadingKey ? 'Salvando...' : 'Salvar'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (selectedAgent === 'html_templates' || selectedAgent === 'blog_templates') ? (
          <div className={styles.card} style={{ width: '100%' }}>
            <div className={styles.editorPane}>
              <div className={styles.headerRow}>
                <h2 className={styles.paneTitle}>
                  {selectedAgent === 'html_templates' ? 'Templates de Vídeo HTML' : 'Componentes de Design do Blog'}
                </h2>
                {toastMessage && <div className={styles.toast}>{toastMessage}</div>}
              </div>
              <p style={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: '1.5', margin: '0 0 8px 0' }}>
                {selectedAgent === 'html_templates'
                  ? 'Estes templates definem os elementos visuais animados que são sobrepostos ao vídeo final (ex: blocos de código ou equações em LaTeX). Edite o código-fonte abaixo e veja a visualização renderizada no celular simulado à direita em tempo real.'
                  : 'Estes templates definem o design e os estilos CSS de componentes renderizados no corpo do artigo de blog público (como blocos de código ou blocos matemáticos LaTeX). Edite e pré-visualize o componente em tempo real.'}
              </p>

              <div className={styles.selectorContainer}>
                {templates
                  .filter((t) => (selectedAgent === 'html_templates' ? !t.id.startsWith('blog_') : t.id.startsWith('blog_')))
                  .map((t) => (
                    <button
                      key={t.id}
                      onClick={() => handleSelectTemplate(t.id)}
                      className={`${styles.templateSelectBtn} ${selectedTemplateId === t.id ? styles.templateSelectBtnActive : ''}`}
                    >
                      {t.name} {t.isCustomized ? '●' : ''}
                    </button>
                  ))}
              </div>

              <div className={styles.templateGrid}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <textarea
                    value={editedHtml}
                    onChange={(e) => setEditedHtml(e.target.value)}
                    className={styles.textarea}
                    style={{ minHeight: '440px', fontSize: '0.82rem' }}
                    placeholder="Escreva o código HTML/CSS/JS do template..."
                  />

                  <div className={styles.actionRow}>
                    <button onClick={handleResetTemplate} className={styles.btnReset} disabled={isSavingTemplate}>
                      Restaurar Padrão
                    </button>
                    <button
                      onClick={handleSaveTemplate}
                      className={styles.btnSave}
                      disabled={isSavingTemplate || editedHtml.trim() === ''}
                    >
                      {isSavingTemplate ? 'Salvando...' : 'Salvar Template no Firestore →'}
                    </button>
                  </div>
                </div>

                <div className={styles.phonePreviewContainer}>
                  <div className={styles.phoneFrameSim}>
                    <div className={styles.phoneNotchSim} />
                    <iframe
                      srcDoc={editedHtml}
                      title="Template Preview"
                      className={styles.iframeSim}
                      sandbox="allow-scripts"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          activeAgentConfig && (
            <div className={styles.card}>
              <div className={styles.editorPane}>
                <div className={styles.headerRow}>
                  <h2 className={styles.paneTitle}>Instruções do Sistema: {activeAgentConfig.label}</h2>
                  {toastMessage && <div className={styles.toast}>{toastMessage}</div>}
                </div>

                <textarea
                  value={editedPrompt}
                  onChange={(e) => setEditedPrompt(e.target.value)}
                  className={styles.textarea}
                  placeholder="Insira as instruções do sistema..."
                />

                <div className={styles.actionRow}>
                  <button onClick={handleReset} className={styles.btnReset} disabled={isSaving}>
                    Restaurar Padrão
                  </button>
                  <button
                    onClick={handleSave}
                    className={styles.btnSave}
                    disabled={isSaving || editedPrompt.trim() === ''}
                  >
                    {isSaving ? 'Salvando...' : 'Salvar Alterações na Nuvem →'}
                  </button>
                </div>

                {/* Collapsible Local Fallback Prompt */}
                <div>
                  <div
                    className={styles.collapseHeader}
                    onClick={() => setShowFallback((prev) => !prev)}
                  >
                    <span>{showFallback ? '▼ Ocultar' : '▶ Visualizar'} Instruções de Fallback Local (Padrão de Fábrica)</span>
                    <span style={{ fontSize: '0.8rem' }}>{activeAgentConfig.isCustomized ? 'Customizado' : 'Ativo'}</span>
                  </div>
                  {showFallback && (
                    <div className={styles.collapseContent}>
                      {activeAgentConfig.fallbackPrompt}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
