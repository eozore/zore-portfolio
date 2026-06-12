import type { Locale } from '@/types/i18n';
import MarkdownRenderer from '@/components/blog/MarkdownRenderer';
import { PART1, PART2, PART3, PART4 } from './content';

interface ExemploPageProps {
  params: { locale: Locale };
}

function DistributionChart() {
  return (
    <svg viewBox="0 0 600 300" xmlns="http://www.w3.org/2000/svg" className="my-6 rounded-lg border border-border" style={{ background: '#fafafa' }}>
      {/* Eixos */}
      <line x1="60" y1="250" x2="560" y2="250" stroke="#2d2d2d" strokeWidth="1.5" />
      <line x1="60" y1="250" x2="60" y2="30" stroke="#2d2d2d" strokeWidth="1.5" />

      {/* Grid */}
      <line x1="60" y1="200" x2="560" y2="200" stroke="#e8e3d8" strokeWidth="0.5" strokeDasharray="4" />
      <line x1="60" y1="150" x2="560" y2="150" stroke="#e8e3d8" strokeWidth="0.5" strokeDasharray="4" />
      <line x1="60" y1="100" x2="560" y2="100" stroke="#e8e3d8" strokeWidth="0.5" strokeDasharray="4" />
      <line x1="60" y1="50" x2="560" y2="50" stroke="#e8e3d8" strokeWidth="0.5" strokeDasharray="4" />

      {/* Curva Log-Normal */}
      <path
        d="M60,250 C80,250 100,248 120,240 C140,228 160,200 180,160 C200,110 220,70 240,55 C260,50 280,60 300,85 C320,115 340,145 360,175 C380,200 400,218 420,230 C440,238 460,243 480,246 C500,248 520,249 560,250"
        fill="rgba(219,74,43,0.12)" stroke="#db4a2b" strokeWidth="2.5"
      />

      {/* Linha P99 */}
      <line x1="420" y1="30" x2="420" y2="250" stroke="#db4a2b" strokeWidth="1.5" strokeDasharray="6,3" />
      <text x="425" y="45" fontSize="11" fill="#db4a2b" fontWeight="600">P99 = 500ms</text>

      {/* Área SLA violação */}
      <path d="M420,230 C440,238 460,243 480,246 C500,248 520,249 560,250 L560,250 L420,250 Z" fill="rgba(219,74,43,0.3)" />

      {/* Mediana */}
      <line x1="200" y1="30" x2="200" y2="250" stroke="#6C757D" strokeWidth="1" strokeDasharray="4,2" />
      <text x="205" y="45" fontSize="10" fill="#6C757D">Mediana = 90ms</text>

      {/* Labels eixo X */}
      <text x="55" y="268" fontSize="10" fill="#6C757D" textAnchor="middle">0</text>
      <text x="160" y="268" fontSize="10" fill="#6C757D" textAnchor="middle">100</text>
      <text x="260" y="268" fontSize="10" fill="#6C757D" textAnchor="middle">200</text>
      <text x="360" y="268" fontSize="10" fill="#6C757D" textAnchor="middle">300</text>
      <text x="460" y="268" fontSize="10" fill="#6C757D" textAnchor="middle">500</text>
      <text x="310" y="290" fontSize="12" fill="#2d2d2d" textAnchor="middle" fontWeight="500">Latência (ms)</text>

      {/* Label eixo Y */}
      <text x="25" y="145" fontSize="11" fill="#2d2d2d" textAnchor="middle" transform="rotate(-90 25 145)" fontWeight="500">Densidade</text>

      {/* Legenda */}
      <rect x="435" y="60" width="115" height="55" rx="6" fill="white" stroke="#e8e3d8" />
      <rect x="445" y="75" width="14" height="3" fill="#db4a2b" />
      <text x="465" y="79" fontSize="9" fill="#2d2d2d">PDF Log-Normal</text>
      <rect x="445" y="92" width="14" height="14" fill="rgba(219,74,43,0.3)" stroke="#db4a2b" strokeWidth="0.5" />
      <text x="465" y="102" fontSize="9" fill="#2d2d2d">Violação SLA</text>
    </svg>
  );
}

export default function ExemploPage({ params }: ExemploPageProps) {
  const { locale } = params;

  return (
    <article className="py-16">
      <div className="max-w-3xl mx-auto px-4">
        {/* Header */}
        <header className="mb-8">
          <span className="inline-block px-3 py-1 text-xs font-semibold rounded bg-primary/10 text-primary mb-4">
            Estatística
          </span>
          <h1 className="text-3xl md:text-4xl font-bold text-text-main">
            Variáveis Aleatórias: O Alicerce de Todo Modelo
          </h1>
          <div className="mt-4 flex items-center gap-4 text-sm text-text-light">
            <span><i className="fa-regular fa-calendar mr-1.5" />01 Jun 2025</span>
            <span><i className="fa-regular fa-clock mr-1.5" />12 {locale === 'pt-BR' ? 'min de leitura' : 'min read'}</span>
          </div>
        </header>

        {/* Article Content */}

        {/* Part 1: intro + conceito + distribuição */}
        <MarkdownRenderer content={PART1} />

        {/* Part 2: valor esperado + quantis */}
        <MarkdownRenderer content={PART2} />

        {/* Gráfico SVG — distribuição Log-Normal */}
        <h2 className="text-[1.6rem] font-bold mt-10 mb-3 text-text-main pb-2 border-b border-border">
          Visualizando a distribuição
        </h2>
        <DistributionChart />
        <p className="text-[1.075rem] leading-[1.8] text-[#334155] mb-5">
          O gráfico mostra a distribuição Log-Normal das latências da FlashLog. A área vermelha à direita de P99 representa os ~2% de requisições que violam o SLA. Note como a mediana (89ms) está distante do P99 (621ms) — é a cauda longa em ação.
        </p>

        {/* Part 3: caso prático */}
        <MarkdownRenderer content={PART3} />

        {/* Part 4: quando usar + resumo + próximo */}
        <MarkdownRenderer content={PART4} />

        {/* Back */}
        <div className="mt-12 pt-6 border-t border-border">
          <a href={`/${locale}/blog`} className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors">
            <i className="fa-solid fa-arrow-left" />
            {locale === 'pt-BR' ? 'Voltar ao blog' : 'Back to blog'}
          </a>
        </div>
      </div>
    </article>
  );
}
