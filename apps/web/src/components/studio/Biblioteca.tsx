/**
 * Biblioteca.tsx — a home do Studio.
 *
 * O Studio abria no formulário "qual o tema" e o único ponteiro para o
 * trabalho anterior era um id no `localStorage`; "Começar outro tema" o
 * sobrescrevia e o ciclo antigo sumia da interface.
 *
 * A produção também é assíncrona e paralela — o vídeo leva de 20 a 40
 * minutos, o artigo já está no ar, a semana já está agendada — e não havia
 * tela que respondesse "o que está acontecendo agora, em tudo?".
 *
 * Cada projeto tem QUATRO entregáveis independentes, cada um com estado
 * próprio. Por isso a linha é uma matriz e não uma barra de progresso: as
 * combinações reais incluem "artigo publicado, vídeo travado, social
 * agendada" — que nenhuma barra representa.
 */
'use client';

import { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Card, Empty, Working, cx } from './ui/primitives';

export type EstadoEntregavel = 'na' | 'pendente' | 'produzindo' | 'pronto' | 'erro';

export interface ProjetoResumo {
  sessionId: string;
  tema: string;
  criadoEm: string;
  atualizadoEm: string;
  fase: string;
  projectId: string | null;
  artigo:   { estado: EstadoEntregavel; status?: string; slug?: string; url?: string };
  video:    { estado: EstadoEntregavel; etapa?: string; youtubeUrl?: string; erro?: string };
  social:   { estado: EstadoEntregavel; agendadas: number; publicadas: number; falhas: number };
  vertical: { estado: EstadoEntregavel };
}

/** Cor E forma: quem não distingue verde de vermelho lê o rótulo. */
const TOM: Record<EstadoEntregavel, 'neutral' | 'active' | 'done' | 'error' | 'wait'> = {
  na: 'neutral', pendente: 'wait', produzindo: 'active', pronto: 'done', erro: 'error',
};

function Celula({
  rotulo, estado, detalhe, acao,
}: {
  rotulo: string;
  estado: EstadoEntregavel;
  detalhe?: string;
  acao?: { texto: string; onClick: () => void };
}) {
  return (
    // `items-start` porque o Badge é inline-flex: num flex column o padrão
    // é `stretch`, e a pílula esticava na largura inteira da coluna.
    <div className="flex min-w-0 flex-col items-start gap-1.5">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-text-faint">
        {rotulo}
      </div>
      <Badge tone={TOM[estado]}>{detalhe ?? ROTULO_ESTADO[estado]}</Badge>
      {acao && (
        <button
          type="button"
          onClick={acao.onClick}
          className="self-start text-[12px] font-medium text-primary underline-offset-2 hover:underline"
        >
          {acao.texto}
        </button>
      )}
    </div>
  );
}

const ROTULO_ESTADO: Record<EstadoEntregavel, string> = {
  na: '—', pendente: 'pendente', produzindo: 'em produção', pronto: 'pronto', erro: 'travado',
};

function quando(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const min = Math.round((Date.now() - d.getTime()) / 60000);
  if (min < 1) return 'agora';
  if (min < 60) return `há ${min} min`;
  if (min < 60 * 24) return `há ${Math.round(min / 60)} h`;
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}

function Linha({
  p, onAbrir,
}: {
  p: ProjetoResumo;
  onAbrir: (sessionId: string) => void;
}) {
  const travado = p.video.estado === 'erro';
  return (
    <Card>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <button
              type="button"
              onClick={() => onAbrir(p.sessionId)}
              className="text-left text-[15px] font-semibold text-text-main hover:text-primary"
            >
              {p.tema}
            </button>
            <div className="mt-1 text-[12px] text-text-faint">
              {quando(p.atualizadoEm)}
              {p.fase ? ` · ${p.fase.replace(/_/g, ' ')}` : ''}
            </div>
          </div>
          <Button variant="secondary" onClick={() => onAbrir(p.sessionId)}>
            Abrir
          </Button>
        </div>

        {travado && p.video.erro && (
          <div className="rounded-lg bg-accent-error/[0.07] px-3 py-2 text-[12.5px] text-accent-error">
            {p.video.etapa}: {p.video.erro}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Celula
            rotulo="Artigo"
            estado={p.artigo.estado}
            detalhe={p.artigo.status === 'draft' ? 'rascunho' : undefined}
            acao={p.artigo.url ? { texto: 'ver', onClick: () => window.open(p.artigo.url, '_blank') } : undefined}
          />
          <Celula
            rotulo="Vídeo"
            estado={p.video.estado}
            detalhe={p.video.estado === 'produzindo' ? p.video.etapa : undefined}
            acao={p.video.youtubeUrl
              ? { texto: 'ver', onClick: () => window.open(p.video.youtubeUrl, '_blank') }
              : undefined}
          />
          <Celula
            rotulo="Social"
            estado={p.social.estado}
            detalhe={
              p.social.publicadas || p.social.agendadas
                ? `${p.social.publicadas} pub · ${p.social.agendadas} na fila`
                : undefined
            }
          />
          <Celula rotulo="Vertical" estado={p.vertical.estado} />
        </div>
      </div>
    </Card>
  );
}

export default function Biblioteca({
  onAbrir, onNovo,
}: {
  onAbrir: (sessionId: string) => void;
  onNovo: () => void;
}) {
  const [projetos, setProjetos] = useState<ProjetoResumo[] | null>(null);
  const [erro, setErro] = useState('');

  const buscar = useCallback(async () => {
    try {
      const r = await fetch('/api/csm/projects');
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      setProjetos(d.projetos ?? []);
      setErro('');
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
      setProjetos([]);
    }
  }, []);

  useEffect(() => { void buscar(); }, [buscar]);

  // Só há polling quando ALGO está em produção. Uma biblioteca parada não
  // precisa de rede — é a mesma regra do polling do fluxo.
  const emCurso = (projetos ?? []).some(
    (p) => p.video.estado === 'produzindo' || p.vertical.estado === 'produzindo',
  );
  useEffect(() => {
    if (!emCurso) return;
    const t = setTimeout(() => void buscar(), 15000);
    return () => clearTimeout(t);
  }, [emCurso, projetos, buscar]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[17px] font-semibold text-text-main">Seus projetos</h2>
          <p className="mt-0.5 text-[12.5px] text-text-muted">
            Cada projeto tem quatro entregáveis, e cada um anda no seu tempo.
          </p>
        </div>
        <Button onClick={onNovo}>Novo tema</Button>
      </div>

      {erro && (
        <div className="rounded-lg bg-accent-error/[0.07] px-3 py-2 text-[13px] text-accent-error">
          {erro}
        </div>
      )}

      {projetos === null && <Working label="Carregando seus projetos" />}

      {projetos?.length === 0 && !erro && (
        <Empty title="Nenhum projeto ainda">
          Comece por um tema. O artigo, o vídeo e a semana de posts saem daí.
        </Empty>
      )}

      <div className={cx('space-y-3')}>
        {projetos?.map((p) => (
          <Linha key={p.sessionId} p={p} onAbrir={onAbrir} />
        ))}
      </div>
    </div>
  );
}
