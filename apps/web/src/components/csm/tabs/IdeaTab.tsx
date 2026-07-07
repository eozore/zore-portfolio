'use client';

import { useState, useEffect, useRef } from 'react';
import type { DraftState, ChatMessage } from '../CsmDashboard';
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

export default function IdeaTab({ draft, updateDraft, isGenerating, setIsGenerating, sessionId, onNext }: IdeaTabProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(draft.chatHistory || []);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isReadyForHandoff, setIsReadyForHandoff] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

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

      // Se o CMO emitiu a frase de pauta concebida, libera o botão criativo
      if (data.text.includes('PAUTA CONCEBIDA COM SUCESSO') || currentHistory.length >= 4) {
        setIsReadyForHandoff(true);
      }
    } catch (err) {
      console.error('[IdeaTab] Chat error:', err);
      // Fallback de contingência
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
    updateDraft({
      chatHistory: nextHistory,
      topic: inputText, // consolida último direcionamento como tópico principal
    });
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
    // Consolida toda a conversa de alinhamento no campo 'context' para o redator técnico
    const fullTranscript = messages
      .map((m) => `${m.role === 'user' ? 'Direcionamento CEO' : 'Alinhamento CMO'}: ${m.text}`)
      .join('\n\n');

    const userMessages = messages.filter((m) => m.role === 'user' && m.text.trim().length >= 10);
    const lastUserTopic = userMessages.length > 0 
      ? userMessages[userMessages.length - 1].text 
      : (draft.topic && draft.topic.length >= 10 ? draft.topic : 'Artigo Técnico éozoré');

    updateDraft({
      topic: lastUserTopic.slice(0, 200),
      context: `=== DIRETRIZES DA REUNIÃO EXECUTIVA CEO x CMO ===\n\n${fullTranscript}`,
      format: 'blog', // SEMPRE artigo educacional profundo
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
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 'bold' }}>Área:</span>
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
            <div style={{ fontStyle: 'italic', color: '#94a3b8' }}>Analisando pauta, SEO e rigor matemático...</div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Creative Team Handoff Banner */}
      {(isReadyForHandoff || messages.length >= 2) && (
        <div className={styles.handoffBar}>
          <div>
            <div style={{ fontWeight: 800, color: '#fff', fontSize: '0.95rem' }}>Pauta Concebida! Pronto para acionar o Time Criativo?</div>
            <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>O redator técnico vai gerar o Artigo mestre com fórmulas LaTeX ($$) e gráficos Mermaid.</div>
          </div>
          <button onClick={handleExecuteHandoff} className={styles.handoffBtn}>
            Fechar Alinhamento & Gerar Artigo →
          </button>
        </div>
      )}

      {/* Input Area */}
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
    </div>
  );
}
