'use client';

import { useState } from 'react';
import EmailGateModal from '@/components/auth/EmailGateModal';

interface SentimentResult {
  label: 'positivo' | 'neutro' | 'negativo';
  score: number;
  emoji: string;
}

function analyzeSentiment(text: string): SentimentResult {
  // Análise simples baseada em keywords (demonstração)
  // Em produção, isso chamaria um modelo via API (Vertex AI, HuggingFace, etc.)
  const lower = text.toLowerCase();

  const positiveWords = [
    'bom', 'ótimo', 'excelente', 'incrível', 'maravilhoso', 'feliz',
    'amor', 'sucesso', 'parabéns', 'adorei', 'perfeito', 'fantástico',
    'good', 'great', 'excellent', 'amazing', 'wonderful', 'happy',
    'love', 'success', 'perfect', 'fantastic', 'awesome', 'best',
  ];

  const negativeWords = [
    'ruim', 'péssimo', 'horrível', 'terrível', 'triste', 'ódio',
    'fracasso', 'problema', 'erro', 'pior', 'detesto', 'falha',
    'bad', 'terrible', 'horrible', 'sad', 'hate', 'failure',
    'problem', 'error', 'worst', 'awful', 'poor', 'wrong',
  ];

  let positiveCount = 0;
  let negativeCount = 0;

  for (const word of lower.split(/\s+/)) {
    if (positiveWords.some(pw => word.includes(pw))) positiveCount++;
    if (negativeWords.some(nw => word.includes(nw))) negativeCount++;
  }

  const total = positiveCount + negativeCount;
  if (total === 0) return { label: 'neutro', score: 0.5, emoji: '😐' };

  const positiveRatio = positiveCount / total;

  if (positiveRatio > 0.6) {
    return { label: 'positivo', score: positiveRatio, emoji: '😊' };
  } else if (positiveRatio < 0.4) {
    return { label: 'negativo', score: 1 - positiveRatio, emoji: '😞' };
  }
  return { label: 'neutro', score: 0.5, emoji: '😐' };
}

const EXAMPLES = [
  'O produto é incrível, adorei a experiência de compra!',
  'Péssimo atendimento, nunca mais volto nessa loja.',
  'O serviço foi ok, nada de especial.',
  'This is the best AI tool I have ever used, amazing results!',
  'Terrible experience, the model failed completely.',
];

export default function ClassificadorSentimentoPage() {
  const [text, setText] = useState('');
  const [result, setResult] = useState<SentimentResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isEmailGateOpen, setIsEmailGateOpen] = useState(false);

  function handleAnalyze() {
    if (!text.trim()) return;

    // Check if user is verified lead or corporate member
    const isAuthorized = typeof document !== 'undefined' && 
      (document.cookie.includes('eozore_lead') || document.cookie.includes('eozore_session'));

    if (!isAuthorized) {
      const runs = parseInt(localStorage.getItem('sentiment_runs') || '0', 10);
      if (runs >= 2) {
        setIsEmailGateOpen(true);
        return;
      }
      localStorage.setItem('sentiment_runs', (runs + 1).toString());
    }

    setIsAnalyzing(true);

    // Simula latência de uma chamada de API
    setTimeout(() => {
      const sentiment = analyzeSentiment(text);
      setResult(sentiment);
      setIsAnalyzing(false);
    }, 800);
  }

  function handleExample(example: string) {
    setText(example);
    setResult(null);
  }

  const labelColors: Record<string, string> = {
    positivo: 'bg-green-100 text-green-800 border-green-200',
    neutro: 'bg-gray-100 text-gray-800 border-gray-200',
    negativo: 'bg-red-100 text-red-800 border-red-200',
  };

  return (
    <section className="py-16">
      <div className="max-w-3xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-10">
          <span className="inline-block px-3 py-1 text-xs font-semibold rounded-full bg-primary/10 text-primary mb-4">
            <i className="fa-solid fa-brain mr-1.5" />
            NLP Tool
          </span>
          <h1 className="text-2xl md:text-3xl font-bold text-text-main">
            Classificador de Sentimento
          </h1>
          <p className="mt-2 text-text-light max-w-lg mx-auto">
            Analise o sentimento de um texto em português ou inglês.
            Detecta se a mensagem é positiva, neutra ou negativa.
          </p>
        </div>

        {/* Input Area */}
        <div className="bg-secondary rounded-[12px] border border-border p-6 shadow-sm">
          <label htmlFor="sentiment-input" className="block text-sm font-medium text-text-main mb-2">
            Texto para análise
          </label>
          <textarea
            id="sentiment-input"
            value={text}
            onChange={(e) => { setText(e.target.value); setResult(null); }}
            placeholder="Digite ou cole um texto aqui..."
            className="w-full h-32 p-4 rounded-[8px] border border-border bg-background text-text-main placeholder:text-text-light resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
          />

          {/* Action */}
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleAnalyze}
              disabled={!text.trim() || isAnalyzing}
              className="px-5 py-2.5 bg-primary text-white font-medium rounded-[8px] hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
            >
              {isAnalyzing ? (
                <>
                  <i className="fa-solid fa-spinner fa-spin" />
                  Analisando...
                </>
              ) : (
                <>
                  <i className="fa-solid fa-magnifying-glass-chart" />
                  Analisar sentimento
                </>
              )}
            </button>
            {text && (
              <button
                onClick={() => { setText(''); setResult(null); }}
                className="px-4 py-2.5 text-text-light hover:text-text-main font-medium rounded-[8px] border border-border hover:bg-background transition-all"
              >
                Limpar
              </button>
            )}
          </div>
        </div>

        {/* Result */}
        {result && (
          <div className="mt-6 bg-secondary rounded-[12px] border border-border p-6 shadow-sm animate-in fade-in duration-300">
            <h3 className="text-sm font-medium text-text-light mb-3">Resultado</h3>
            <div className="flex items-center gap-4">
              <span className="text-5xl">{result.emoji}</span>
              <div>
                <span className={`inline-block px-3 py-1 text-sm font-semibold rounded-full border ${labelColors[result.label]}`}>
                  {result.label.charAt(0).toUpperCase() + result.label.slice(1)}
                </span>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xs text-text-light">Confiança:</span>
                  <div className="w-32 h-2 bg-border rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all duration-500"
                      style={{ width: `${result.score * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-text-main">
                    {(result.score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Examples */}
        <div className="mt-8">
          <h3 className="text-sm font-medium text-text-light mb-3">
            <i className="fa-solid fa-lightbulb mr-1.5 text-accent" />
            Experimente com exemplos:
          </h3>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((example, i) => (
              <button
                key={i}
                onClick={() => handleExample(example)}
                className="px-3 py-1.5 text-xs text-text-main bg-background border border-border rounded-full hover:border-primary hover:text-primary transition-all line-clamp-1 max-w-[280px]"
              >
                &ldquo;{example.slice(0, 40)}...&rdquo;
              </button>
            ))}
          </div>
        </div>

        {/* How it works */}
        <div className="mt-10 p-6 bg-background rounded-[12px] border border-border">
          <h3 className="text-sm font-semibold text-text-main mb-2">
            <i className="fa-solid fa-circle-info mr-1.5 text-primary" />
            Como funciona
          </h3>
          <p className="text-sm text-text-light leading-relaxed">
            Esta é uma demonstração usando análise baseada em keywords. Em produção,
            o classificador usaria um modelo de NLP treinado (ex: BERT multilíngue
            via Vertex AI) para análise de sentimento com maior precisão.
            A arquitetura suporta trocar o backend de ML sem alterar a interface.
          </p>
        </div>

        {/* Back link */}
        <div className="mt-8">
          <a
            href="/tools"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors"
          >
            <i className="fa-solid fa-arrow-left" />
            Voltar às ferramentas
          </a>
        </div>
      </div>

      <EmailGateModal 
        isOpen={isEmailGateOpen} 
        onClose={() => setIsEmailGateOpen(false)} 
        onSuccess={() => handleAnalyze()} 
      />
    </section>
  );
}
