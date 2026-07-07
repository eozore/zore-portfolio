'use client';

import React, { useState } from 'react';
import LogoutButton from '@/components/auth/LogoutButton';
import CaseStudyModal from '@/components/ui/CaseStudyModal';
import EmailGateModal from '@/components/auth/EmailGateModal';

interface Tool {
  id: string;
  name: string;
  nameEn: string;
  slug: string;
  descPt: string;
  descEn: string;
  icon: string;
  isPrivate: boolean;
  companyId?: string;
  caseDescription?: string;
}

interface ToolsClientPageProps {
  locale: string;
  initialSession: any;
  dictionary: any;
}

export default function ToolsClientPage({ locale, initialSession, dictionary }: ToolsClientPageProps) {
  const [isCaseModalOpen, setIsCaseModalOpen] = useState(false);
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);
  const [selectedToolSlug, setSelectedToolSlug] = useState('');

  // Catalog
  const tools: Tool[] = [
    {
      id: 'sentiment-classifier',
      name: 'Classificador de Sentimento',
      nameEn: 'Sentiment Classifier',
      slug: 'classificador-sentimento',
      descPt: 'Analise o sentimento de textos em português ou inglês usando NLP.',
      descEn: 'Analyze text sentiment in Portuguese or English using NLP.',
      icon: 'fa-brain',
      isPrivate: false,
    },
    {
      id: 'cromex-pricing',
      name: 'Cromex Solução Corporativa',
      nameEn: 'Cromex Pricing Intelligence',
      slug: 'cromex',
      descPt: 'Solução Confidencial de Precificação e margens de vendas (Mercado Interno e Externo).',
      descEn: 'Confidential pricing and margin analytics engine (Internal and External Markets).',
      icon: 'fa-building',
      isPrivate: true,
      companyId: 'cromex',
    }
  ];

  const handleToolClick = (e: React.MouseEvent, tool: Tool) => {
    if (tool.isPrivate) {
      const isAuthorized = initialSession && (initialSession.companyId === tool.companyId || initialSession.role === 'admin');
      
      if (!isAuthorized) {
        // Prevent default link redirect, open case study info modal instead
        e.preventDefault();
        setIsCaseModalOpen(true);
      }
    }
  };

  const handleLoginRedirect = () => {
    window.location.href = `/${locale}/tools/login?redirect=tools/cromex`;
  };

  return (
    <div className="max-w-container mx-auto px-4">
      {/* Page Header */}
      <div className="relative z-10 flex flex-col md:flex-row justify-between items-center gap-4 mb-12 border-b border-border pb-6">
        <div>
          <h1 className="text-3xl font-extrabold text-text-main tracking-tight">
            {dictionary?.tools?.title || 'Ferramentas de IA'}
          </h1>
          <p className="mt-2 text-text-muted text-sm font-medium">
            {locale === 'pt-BR'
              ? 'Experimente nossas demos de IA e veja cases corporativos sob medida.'
              : 'Try our public AI playgrounds and review custom enterprise solution cases.'}
          </p>
        </div>

        {initialSession && (
          <div className="flex items-center gap-3 bg-white/40 backdrop-blur-md border border-border p-2 px-4 rounded-xl shadow-sm">
            <span className="text-sm font-semibold text-text-main">
              {locale === 'pt-BR' ? 'Olá,' : 'Hi,'} {initialSession.name || initialSession.email}
            </span>
            <LogoutButton />
          </div>
        )}
      </div>

      {/* Grid */}
      <div className="relative z-10 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {tools.map((tool) => {
          const isAuthorized = !tool.isPrivate || (initialSession && (initialSession.companyId === tool.companyId || initialSession.role === 'admin'));
          const href = isAuthorized ? `/${locale}/tools/${tool.slug}` : '#';

          return (
            <a
              key={tool.id}
              href={href}
              onClick={(e) => handleToolClick(e, tool)}
              className="group relative glass rounded-card-lg p-6 flex flex-col hover:bg-white/80 hover:shadow-glow transition-all duration-500"
            >
              {/* Subtle ambient blur bubble inside card */}
              <div className="absolute top-0 right-0 w-32 h-32 rounded-full bg-primary/5 blur-3xl pointer-events-none group-hover:bg-primary/10 transition-all duration-500" />

              <div className="relative z-10 w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-5 group-hover:bg-primary/20 transition-all duration-300">
                <i className={`fa-solid ${tool.icon} text-primary text-xl`} />
              </div>
              
              <div className="relative z-10 flex items-center gap-2 mb-2">
                <h3 className="text-lg font-bold text-text-main group-hover:text-primary transition-colors">
                  {locale === 'pt-BR' ? tool.name : tool.nameEn}
                </h3>
                {tool.isPrivate && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[9px] font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20">
                    <i className="fa-solid fa-lock text-[8px]" />
                    Restrito
                  </span>
                )}
              </div>

              <p className="relative z-10 text-sm text-text-muted flex-1 leading-relaxed">
                {locale === 'pt-BR' ? tool.descPt : tool.descEn}
              </p>
              
              <span className="relative z-10 mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-primary group-hover:text-accent-data transition-colors">
                {tool.isPrivate && !isAuthorized 
                  ? (locale === 'pt-BR' ? 'Ver Solução / Case' : 'View Case Study') 
                  : (locale === 'pt-BR' ? 'Acessar' : 'Open')}
                <i className="fa-solid fa-arrow-right text-xs group-hover:translate-x-1 transition-transform" />
              </span>
            </a>
          );
        })}

        {/* Coming Soon card */}
        <div className="relative glass border-dashed border-2 rounded-card-lg p-6 flex flex-col items-center justify-center text-center min-h-[240px] opacity-60">
          <div className="w-12 h-12 rounded-2xl bg-white/50 border border-border flex items-center justify-center mb-4">
            <i className="fa-solid fa-flask text-text-muted text-xl" />
          </div>
          <h3 className="text-base font-bold text-text-main mb-1">
            {locale === 'pt-BR' ? 'Mais ferramentas em breve' : 'More tools coming soon'}
          </h3>
          <p className="text-xs text-text-muted max-w-[200px]">
            {locale === 'pt-BR'
              ? 'Modelos de recomendação, previsão de churn e clusterização.'
              : 'Recommendation models, churn forecasting and clustering.'}
          </p>
        </div>
      </div>

      {/* Case Study presentation pop-up */}
      <CaseStudyModal 
        isOpen={isCaseModalOpen}
        onClose={() => setIsCaseModalOpen(false)}
        onLoginClick={handleLoginRedirect}
      />

      {/* OTP email gate pop-up (controlled globally or on demand) */}
      <EmailGateModal 
        isOpen={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
        onSuccess={() => {
          // Success callback
          if (selectedToolSlug) {
            window.location.href = `/${locale}/tools/${selectedToolSlug}`;
          }
        }}
      />
    </div>
  );
}
