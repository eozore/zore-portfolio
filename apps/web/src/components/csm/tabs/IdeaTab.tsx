'use client';

import { useState, useEffect, useRef } from 'react';
import type { DraftState, ChatMessage, PautaConcebida } from '../CsmDashboard';
import type { ArticleCategory } from '@/types/article';
import styles from './IdeaTab.module.css';

interface IdeaTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  isGenerating: boolean;
  setIsGenerating: (v: boolean) => void;
  sessionId: string;
  onNext: () => void;
}

const CATEGORIES: { id: ArticleCategory; label: string }[] = [
  { id: 'ml', label: 'Machine Learning & MLOps' },
  { id: 'ia', label: 'GenAI & LLMs' },
  { id: 'estatistica', label: 'Matemática & Probabilidade' },
];

const EXAMPLE_PROMPTS = [
  'Quero explicar por que fine-tuning com LoRA reduz tanto o custo de memória.',
  'Vamos falar sobre como RAG resolve alucinação em LLMs de produção.',
  'Tenho uma tese sobre o trade-off entre latência e qualidade em modelos servidos na GCP.',
  'Quero desmistificar attention mechanism com uma analogia geométrica simples.',
];

/**
 * Tenta extrair o bloco JSON { "pauta": {...} } do texto do CMO.
 * O CMO emite o bloco delimitado por ```json … ``` após "PAUTA CONCEBIDA COM SUCESSO".
 * Retorna null se não encontrar ou se o parse falhar.
 */
function extractPautaFromCmoText(text: string): PautaConcebida | null {
  // Aceita ```json ou ``` simples, com ou sem nova linha antes das chaves
  const jsonBlockMatch = text.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/);
  if (!jsonBlockMatch) return null;

  try {
    const raw = jsonBlockMatch[1].replace(/,\s*([}\]])/g, '$1'); // trailing commas
    const parsed = JSON.parse(raw);
    const pauta = parsed?.pauta;
    if (
      pauta &&
      typeof pauta.titulo === 'string' &&
      pauta.titulo.trim().length >= 5
    ) {
      return {
        titulo:               pauta.titulo.trim(),
        subtitulo:            (pauta.subtitulo ?? '').trim(),
        tese:                 (pauta.tese ?? '').trim(),
        publico:              (pauta.publico ?? '').trim(),
        objetivo_aprendizado: (pauta.objetivo_aprendizado ?? '').trim(),
        hardskills:           Array.isArray(pauta.hardskills) ? pauta.hardskills : [],
        duracao_alvo:         (pauta.duracao_alvo ?? '').trim(),
        serie:                (pauta.serie ?? '').trim(),
        tipo_artigo: (['tecnico', 'conceitual', 'estrategico'].includes(pauta.tipo_artigo)
          ? pauta.tipo_artigo
          : 'tecnico') as 'tecnico' | 'conceitual' | 'estrategico',
        nivel_tecnico: (['baixo', 'medio', 'alto'].includes(pauta.nivel_tecnico)
          ? pauta.nivel_tecnico
          : 'medio') as 'baixo' | 'medio' | 'alto',
      };
    }
  } catch {
    // parse silencioso — fallback no caller
  }
  return null;
}

/** Verifica se a pauta tem os 8 campos obrigatórios preenchidos */
function isPautaCompleta(pauta: PautaConcebida | null): boolean {
  if (!pauta) return false;
  return (
    pauta.titulo.length >= 5 &&
    pauta.tese.length > 0 &&
    pauta.publico.length > 0 &&
    pauta.objetivo_aprendizado.length > 0 &&
    Array.isArray(pauta.hardskills) && pauta.hardskills.length > 0 &&
    pauta.duracao_alvo.length > 0
  );
}

export default function IdeaTab({ draft, updateDraft, isGenerating, setIsGenerating, sessionId, onNext }: IdeaTabProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(draft.chatHistory || []);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isReadyForHandoff, setIsReadyForHandoff] = useState(false);
  /** Pauta extraída do último bloco JSON do CMO — usada no handoff (G7) */
  const [detectedPauta, setDetectedPauta] = useState<PautaConcebida | null>(draft.pauta ?? null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Se sessão restaurada já tem pauta completa, libera o handoff automaticamente
  // (não dispara geração — o PackageTab só gera quando o usuário clicar no botão)
  useEffect(() => {
    if (draft.pauta && isPautaCompleta(draft.pauta)) {
      setDetectedPauta(draft.pauta);
      setIsReadyForHandoff(true);
    }
  }, [draft.pauta]); // roda quando a sessão é restaurada do Firestore

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const triggerInterviewTurn = async (currentHistory: ChatMessage[]) => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/csm/interview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: currentHistory,
          sessionId,
          category: draft.category || 'ml',
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Falha no chat');

      const cmoReply: ChatMessage = { role: 'model', text: data.text };
      const nextHistory = [...currentHistory, cmoReply];
      setMessages(nextHistory);
      updateDraft({ chatHistory: nextHistory });

      // G7: detecta bloco JSON { "pauta": {...} } no texto do CMO
      if (data.text.includes('PAUTA CONCEBIDA COM SUCESSO')) {
        const pauta = extractPautaFromCmoText(data.text);
        if (pauta) {
          setDetectedPauta(pauta);
          updateDraft({ pauta });
          // Só libera handoff se a pauta tem TODOS os 8 campos obrigatórios
          if (isPautaCompleta(pauta)) {
            setIsReadyForHandoff(true);
          }
        }
      }
      // Safety net removido: handoff só com pauta JSON completa (todos os 8 campos)
    } catch (err) {
      console.error('[IdeaTab] Chat error:', err);
      const fbMsg: ChatMessage = {
        role: 'model',
        text: 'Olá Victor! Sou seu CMO AI. Tive um breve soluço de rede, mas estou pronto: qual é a grande tese matemática ou aprendizado de nuvem que vamos transformar no artigo educacional desta semana?',
      };
      setMessages((prev) => [...prev, fbMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = () => {
    if (!inputText.trim() || isLoading) return;

    const userMsg: ChatMessage = { role: 'user', text: inputText };
    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);
    updateDraft({ chatHistory: nextHistory });
    setInputText('');

    triggerInterviewTurn(nextHistory);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleExecuteHandoff = () => {
    const fullTranscript = messages
      .map((m) => `${m.role === 'user' ? 'Direcionamento CEO' : 'Alinhamento CMO'}: ${m.text}`)
      .join('\n\n');

    // G7: usa o título aprovado pelo CMO (pauta.titulo), não a última frase do usuário
    const topicFromPauta = detectedPauta?.titulo;

    // Fallback progressivo: pauta JSON → última msg do CEO → draft.topic existente
    const userMessages = messages.filter((m) => m.role === 'user' && m.text.trim().length >= 10);
    const fallbackTopic = userMessages.length > 0
      ? userMessages[userMessages.length - 1].text
      : (draft.topic && draft.topic.length >= 10 ? draft.topic : 'Artigo Técnico éozoré');

    const resolvedTopic = topicFromPauta ?? fallbackTopic;

    updateDraft({
      topic: resolvedTopic.slice(0, 200),
      suggestedTitle: topicFromPauta ?? '',
      context: `=== DIRETRIZES DA REUNIÃO EXECUTIVA CEO x CMO ===\n\n${fullTranscript}`,
      format: 'blog',
      // garante que pauta está no estado mesmo se updateDraft(pauta) veio antes
      ...(detectedPauta ? { pauta: detectedPauta } : {}),
    });

    onNext();
  };

  return (
    <div className={styles.chatLayout}>
      {/* Top Glass Header */}
      <div className={styles.chatHeader}>
        <div className={styles.roomTitle}>
          <span>Sala de Pauta & Alinhamento Privado (CEO x CMO)</span>
          <span className={styles.cmoBadge}>Especialista AI</span>
        </div>

        <div className={styles.metaToolbar}>
          <span style={{ fontSize: '0.8rem', color: '#6b6b6b', fontWeight: 'bold' }}>Área:</span>
          <select
            value={draft.category}
            onChange={(e) => updateDraft({ category: e.target.value as ArticleCategory })}
            className={styles.select}
          >
            {CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className={styles.messagesContainer}>
        {messages.length === 0 && !isLoading && (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>💬</div>
            <div className={styles.emptyTitle}>Sobre o que vamos escrever esta semana?</div>
            <div className={styles.emptyDesc}>
              Direcione o CMO com um tema, uma tese ou um aprendizado prático. Ele vai perguntar
              o essencial (público, ângulo, profundidade) até fechar a pauta com você.
            </div>
            <div className={styles.exampleGrid}>
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className={styles.exampleChip}
                  onClick={() => setInputText(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>

            {/* Segundo ponto de entrada: o CMO não é obrigatório. Quem já tem
                artigo publicado pode pular direto para a geração do pacote. */}
            <div className={styles.altEntry}>
              <span className={styles.altEntryLine} />
              <span className={styles.altEntryLabel}>ou</span>
              <span className={styles.altEntryLine} />
            </div>
            <button type="button" className={styles.altEntryBtn} onClick={onNext}>
              Partir de um artigo já publicado →
            </button>
          </div>
        )}
        {messages.map((m, i) => {
          const isCmo = m.role === 'model';
          return (
            <div
              key={i}
              className={`${styles.messageBubble} ${isCmo ? styles.bubbleCmo : styles.bubbleCeo}`}
            >
              <span className={`${styles.senderName} ${isCmo ? styles.senderCmo : styles.senderCeo}`}>
                {isCmo ? 'Diretor de Marketing (CMO AI)' : 'Victor Zore (CEO)'}
              </span>
              <div style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
            </div>
          );
        })}

        {isLoading && (
          <div className={`${styles.messageBubble} ${styles.bubbleCmo}`}>
            <span className={`${styles.senderName} ${styles.senderCmo}`}>Diretor de Marketing (CMO AI)</span>
            <div style={{ fontStyle: 'italic', color: '#6b6b6b' }}>Analisando pauta, SEO e rigor matemático...</div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Creative Team Handoff Banner */}
      {isReadyForHandoff && (
        <div className={styles.handoffBar}>
          <div>
            <div style={{ fontWeight: 800, color: '#1e1e1e', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {detectedPauta
            ? `✅ Pauta Concebida: "${detectedPauta.titulo}"`
            : 'Pauta Concebida! Pronto para acionar o Time Criativo?'}
              {/* Badge tipo_artigo */}
              {detectedPauta?.tipo_artigo && (
                <span style={{
                  fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
                  padding: '2px 8px', borderRadius: '9999px', border: '1px solid',
                  ...(detectedPauta.tipo_artigo === 'tecnico'
                    ? { background: 'rgba(30,64,175,0.3)', color: '#2563eb', borderColor: '#2563eb' }
                    : detectedPauta.tipo_artigo === 'conceitual'
                      ? { background: 'rgba(109,40,217,0.3)', color: '#7c3aed', borderColor: '#7c3aed' }
                      : { background: 'rgba(6,95,70,0.3)', color: '#16a34a', borderColor: '#16a34a' }),
                }}>
                  {detectedPauta.tipo_artigo}
                </span>
              )}
              {/* Badge nivel_tecnico */}
              {detectedPauta?.nivel_tecnico && (
                <span style={{
                  fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
                  padding: '2px 8px', borderRadius: '9999px', border: '1px solid',
                  ...(detectedPauta.nivel_tecnico === 'alto'
                    ? { background: 'rgba(220,38,38,0.2)', color: '#dc2626', borderColor: '#dc2626' }
                    : detectedPauta.nivel_tecnico === 'baixo'
                      ? { background: 'rgba(22,163,74,0.2)', color: '#16a34a', borderColor: '#16a34a' }
                      : { background: 'rgba(217,119,6,0.2)', color: '#d97706', borderColor: '#d97706' }),
                }}>
                  nível {detectedPauta.nivel_tecnico}
                </span>
              )}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#4a4a4a' }}>
              {detectedPauta
                ? 'O sistema vai gerar o pacote completo automaticamente (artigo + derivações).'
                : 'O redator técnico vai gerar o Artigo mestre com fórmulas LaTeX ($$) e gráficos Mermaid.'}
            </div>
            {detectedPauta?.hardskills && detectedPauta.hardskills.length > 0 && (
              <div style={{ fontSize: '0.72rem', color: '#6b6b6b', marginTop: '4px', fontFamily: 'JetBrains Mono, monospace' }}>
                🎓 Hardskills: {detectedPauta.hardskills.slice(0, 3).join(' · ')}
              </div>
            )}
          </div>
          <button onClick={handleExecuteHandoff} className={styles.handoffBtn}>
            {detectedPauta ? 'Gerar Pacote Completo →' : 'Fechar Alinhamento & Gerar Artigo →'}
          </button>
        </div>
      )}

      {/* Input Area — oculto quando pacote já foi gerado (projeto em andamento) */}
      {!!draft.generatedContent?.trim() ? (
        <div className={styles.projectReadyBar}>
          <div className={styles.projectReadyText}>
            <div className={styles.projectReadyTitle}>✓ Pacote gerado para este projeto</div>
            <div className={styles.projectReadyDesc}>
              Para continuar, vá para a aba Pacote. Para novo projeto, clique em &ldquo;Nova Reunião&rdquo;.
            </div>
          </div>
          <button className={styles.projectReadyBtn} onClick={onNext}>
            Ver Pacote →
          </button>
        </div>
      ) : (
        <div className={styles.inputArea}>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Direcione a pauta como CEO (ex: 'Quero falar sobre como LoRA reduz custo de memória de ativação...')"
            className={styles.textarea}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputText.trim() || isLoading}
            className={styles.sendBtn}
          >
            {isLoading ? 'Aguardando...' : 'Enviar'}
          </button>
        </div>
      )}
    </div>
  );
}
