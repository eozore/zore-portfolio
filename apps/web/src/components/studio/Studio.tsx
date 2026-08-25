/**
 * Studio.tsx — A experiência.
 *
 * Layout de duas colunas: TRILHA à esquerda (onde estou), PALCO à direita
 * (o que preciso fazer agora). Nunca mais de uma coisa pedindo atenção.
 *
 * O que a interface antiga fazia de errado e isto corrige:
 *   - Quatro abas com cadeado, sem dizer o que destrava cada uma.
 *   - "Gerando…" indistinguível de "esperando você" — o usuário ficava
 *     olhando uma tela que nunca ia se resolver sozinha.
 *   - O conteúdo aparecia como JSON ou texto cru, e a decisão de aprovar era
 *     tomada sem ver como a peça fica no feed.
 */
'use client';

import { useEffect, useState } from 'react';
import AuthGate from '../csm/AuthGate';
import { Badge, Button, Card, Notice, cx } from './ui/primitives';
import {
  CartaoArtigo, PainelProducao, PassoArtigo, PassoSocial, PassoTema, PassoTrabalhando, PassoVideo,
} from './steps/Steps';
import {
  type Passo, type StatusPasso, passosDaJornada, resumoDaFase, useStudio,
} from './useStudio';

// ── Trilha ───────────────────────────────────────────────────────────────────

const MARCA: Record<StatusPasso, { anel: string; ponto: string; texto: string }> = {
  feito:     { anel: 'border-accent-success bg-accent-success',   ponto: 'text-white',    texto: 'text-text-main' },
  fazendo:   { anel: 'border-primary bg-white',        ponto: 'text-primary', texto: 'text-text-main' },
  seu_turno: { anel: 'border-primary bg-primary',    ponto: 'text-white',    texto: 'text-text-main' },
  erro:      { anel: 'border-accent-error bg-accent-error',    ponto: 'text-white',    texto: 'text-accent-error' },
  pendente:  { anel: 'border-black/15 bg-white',         ponto: 'text-black/25', texto: 'text-text-faint' },
};

function Trilha({ passos }: { passos: Passo[] }) {
  return (
    <nav aria-label="Progresso" className="space-y-0">
      {passos.map((p, i) => {
        const m = MARCA[p.status];
        const ultimo = i === passos.length - 1;
        return (
          <div key={p.id} className="relative flex gap-3 pb-6 last:pb-0">
            {!ultimo && (
              <span className={cx(
                'absolute left-[11px] top-6 h-full w-px',
                p.status === 'feito' ? 'bg-accent-success/35' : 'bg-black/[0.09]',
              )} />
            )}
            <span className={cx(
              'relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2',
              m.anel, p.status === 'fazendo' && 'animate-pulse',
            )}>
              <span className={cx('text-[11px] font-bold leading-none', m.ponto)}>
                {p.status === 'feito' ? '✓' : i + 1}
              </span>
            </span>
            <div className="min-w-0 pt-0.5">
              <p className={cx('text-[13px] font-semibold leading-tight', m.texto)}>{p.rotulo}</p>
              {p.status === 'seu_turno' && (
                <span className="mt-1 inline-block"><Badge tone="active">precisa de você</Badge></span>
              )}
              {p.status === 'fazendo' && (
                <p className="mt-0.5 text-[11px] text-text-soft">trabalhando…</p>
              )}
              {p.status === 'erro' && (
                <p className="mt-0.5 text-[11px] text-accent-error">travou</p>
              )}
            </div>
          </div>
        );
      })}
    </nav>
  );
}

// ── Studio ───────────────────────────────────────────────────────────────────

export default function Studio() {
  const [sessionId, setSessionId] = useState('');

  useEffect(() => {
    // Chave PRÓPRIA do Studio. Antes era `csm_session_id`, a mesma do CSM
    // antigo — e um id herdado dele casou, por `session_id`, com quatro
    // content_projects de 16/08: a tela deu o pacote por pronto e ofereceu o
    // vídeo daquela semana para cortar.
    let id = localStorage.getItem('studio_session_id');
    if (!id) { id = crypto.randomUUID(); localStorage.setItem('studio_session_id', id); }
    setSessionId(id);
  }, []);

  const {
    estado, producao, agendamento, statusArtigo, erro, ocupado, carregando,
    iniciar, decidir, agendar, derivarVertical, publicarArtigo, recarregar,
  } = useStudio(sessionId);
  const passos = passosDaJornada(estado);
  const resumo = resumoDaFase(estado);
  const fatais = (estado?.erros || []).filter((e) => e.fatal);

  function novoCiclo() {
    const id = crypto.randomUUID();
    localStorage.setItem('studio_session_id', id);
    setSessionId(id);
  }

  function palco() {
    if (carregando && !estado) {
      return <Card><div className="h-32 animate-pulse rounded-lg bg-black/[0.04]" /></Card>;
    }
    if (fatais.length) {
      return (
        <Notice title={`O passo "${fatais[0].no}" travou`}>
          <p>{fatais[0].mensagem}</p>
          <div className="mt-3 flex gap-2">
            <Button variant="secondary" onClick={recarregar}>Verificar de novo</Button>
            <Button variant="ghost" onClick={novoCiclo}>Começar outro tema</Button>
          </div>
        </Notice>
      );
    }
    if (!estado) return <PassoTema onIniciar={iniciar} ocupado={ocupado} />;

    switch (estado.fase) {
      case 'aguardando_aprovacao_artigo':
        return <PassoArtigo estado={estado} ocupado={ocupado}
          onDecidir={(d, c) => decidir('artigo', d, c)} />;
      case 'aguardando_aprovacao_video':
        return <PassoVideo estado={estado} ocupado={ocupado}
          onDecidir={(d, c) => decidir('video', d, c)} />;
      case 'concluido':
        return (
          <div className="space-y-4">
            <CartaoArtigo
              estado={estado}
              status={statusArtigo}
              onPublicar={publicarArtigo}
              ocupado={ocupado}
            />
            {producao && producao.etapas.length > 0 && (
              <PainelProducao
                producao={producao}
                onDerivarVertical={derivarVertical}
                ocupado={ocupado}
              />
            )}
            <PassoSocial
              estado={estado}
              agendamento={agendamento}
              naFila={producao?.naFila ?? 0}
              onAgendar={agendar}
              ocupado={ocupado}
            />
          </div>
        );
      case 'erro':
        return (
          <Notice title="O fluxo parou">
            <p>{estado.erros[0]?.mensagem || 'Motivo não informado.'}</p>
            <div className="mt-3"><Button variant="ghost" onClick={novoCiclo}>Começar outro tema</Button></div>
          </Notice>
        );
      default:
        return <PassoTrabalhando titulo={resumo.titulo} sub={resumo.sub} trilha={estado.trilha} />;
    }
  }

  return (
    <AuthGate>
      <div className="min-h-screen bg-bg-deep">
        {/* Espelha components/layout/Header.tsx — a mesma altura (h-16), o
            mesmo contêiner (max-w-container = 1140px), o mesmo vidro
            (glass-strong) e a MESMA marca. O Studio desenhava um logotipo
            diferente do site: aqui o "é" era laranja, lá é o ponto final; a
            fonte era 15px contra 20px; o contêiner tinha 1152px contra 1140.
            Entrar no Studio parecia sair do site. */}
        <header className="sticky top-0 z-50 glass-strong">
          <div className="mx-auto flex h-16 max-w-container items-center justify-between px-4">
            <div className="flex items-baseline gap-2.5">
              <a href="/" className="text-xl font-bold text-text-main transition-colors hover:text-primary">
                éozoré<span className="text-primary">.</span>
              </a>
              <span className="text-sm font-medium text-text-muted">Studio</span>
            </div>
            <div className="flex items-center gap-3">
              {estado?.tema && (
                <span className="hidden max-w-xs truncate text-sm text-text-muted sm:block">
                  {estado.tema}
                </span>
              )}
              {estado && <Button variant="ghost" onClick={novoCiclo}>Novo tema</Button>}
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-5 py-8">
          <div className="mb-7">
            <h1 className="text-[26px] font-bold leading-tight tracking-tight text-text-main">
              {resumo.titulo}
            </h1>
            <p className="mt-1.5 text-[14px] text-text-muted">{resumo.sub}</p>
          </div>

          {erro && (
            <div className="mb-5">
              {/* Título neutro: este Notice mostra QUALQUER falha de ação —
                  publicar artigo, disparar produção, agendar, cortar o
                  vertical. Dizer "não consegui falar com o time de agentes"
                  para um 409 do corte vertical mandava investigar a rede
                  quando o problema era outro. */}
              <Notice title="Alguma coisa não deu certo">
                <p>{erro}</p>
                <div className="mt-3"><Button variant="secondary" onClick={recarregar}>Tentar de novo</Button></div>
              </Notice>
            </div>
          )}

          <div className="grid gap-8 lg:grid-cols-[168px_1fr]">
            <aside className="lg:sticky lg:top-24 lg:self-start">
              <Trilha passos={passos} />
            </aside>
            <div className="min-w-0">{palco()}</div>
          </div>
        </main>
      </div>
    </AuthGate>
  );
}
