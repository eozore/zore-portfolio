/**
 * primitives.tsx — Vocabulário visual do Studio.
 *
 * Poucos componentes, muito reuso. O CSM antigo tinha estilo inline em cada
 * arquivo: a mesma "caixa" era escrita de nove jeitos diferentes e mudar o
 * raio da borda exigia caçar `style={{...}}` em 9.000 linhas.
 *
 * Regras da linguagem:
 *   - Uma cor de destaque só (laranja). Se tudo é destaque, nada é.
 *   - Verde e vermelho SÓ para estado (concluído / erro), nunca decoração.
 *   - Hierarquia por tamanho e espaço, não por peso de cor.
 */
'use client';

import { ReactNode } from 'react';

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}

// ── Botão ────────────────────────────────────────────────────────────────────

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const BTN: Record<BtnVariant, string> = {
  primary:   'bg-[#e67e22] text-white hover:bg-[#d8701a] shadow-sm',
  secondary: 'bg-white text-[#1e1e1e] border border-black/10 hover:border-black/25',
  ghost:     'bg-transparent text-[#6b6b6b] hover:text-[#1e1e1e] hover:bg-black/[0.04]',
  danger:    'bg-white text-[#b91c1c] border border-[#b91c1c]/25 hover:bg-[#b91c1c]/[0.06]',
};

export function Button({
  children, onClick, variant = 'primary', disabled, loading, full, type = 'button', title,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: BtnVariant;
  disabled?: boolean;
  loading?: boolean;
  full?: boolean;
  type?: 'button' | 'submit';
  title?: string;
}) {
  const off = disabled || loading;
  return (
    <button
      type={type} onClick={onClick} disabled={off} title={title}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5',
        'text-sm font-semibold transition-colors',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#e67e22]/50',
        BTN[variant],
        full && 'w-full',
        off && 'opacity-50 cursor-not-allowed',
      )}
    >
      {loading && (
        <span
          aria-hidden
          className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </button>
  );
}

// ── Superfícies ──────────────────────────────────────────────────────────────

export function Card({
  children, className, padded = true,
}: { children: ReactNode; className?: string; padded?: boolean }) {
  return (
    <div className={cx(
      'rounded-2xl border border-black/[0.08] bg-white',
      padded && 'p-6', className,
    )}>
      {children}
    </div>
  );
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-[15px] font-bold tracking-tight text-[#1e1e1e]">{children}</h2>
      {hint && <p className="mt-1 text-[13px] leading-relaxed text-[#6b6b6b]">{hint}</p>}
    </div>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-[#8a8a8a]">
      {children}
    </div>
  );
}

// ── Estado ───────────────────────────────────────────────────────────────────

type Tone = 'neutral' | 'active' | 'done' | 'error' | 'wait';

const TONE: Record<Tone, string> = {
  neutral: 'bg-black/[0.05] text-[#6b6b6b]',
  active:  'bg-[#e67e22]/12 text-[#b35f11]',
  done:    'bg-[#16a34a]/12 text-[#15803d]',
  error:   'bg-[#b91c1c]/10 text-[#b91c1c]',
  wait:    'bg-[#2563eb]/10 text-[#1d4ed8]',
};

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={cx(
      'inline-flex items-center rounded-full px-2.5 py-1',
      'text-[11px] font-semibold leading-none', TONE[tone],
    )}>
      {children}
    </span>
  );
}

/** Aviso que exige leitura — erro, bloqueio, limite. */
export function Notice({
  tone = 'error', title, children,
}: { tone?: 'error' | 'wait' | 'active'; title: string; children?: ReactNode }) {
  const ring = {
    error:  'border-[#b91c1c]/25 bg-[#b91c1c]/[0.04]',
    wait:   'border-[#2563eb]/25 bg-[#2563eb]/[0.04]',
    active: 'border-[#e67e22]/30 bg-[#e67e22]/[0.05]',
  }[tone];
  return (
    <div className={cx('rounded-xl border p-4', ring)}>
      <p className="text-[13px] font-semibold text-[#1e1e1e]">{title}</p>
      {children && <div className="mt-1.5 text-[13px] leading-relaxed text-[#4a4a4a]">{children}</div>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-black/[0.12] px-6 py-14 text-center">
      <p className="text-sm font-semibold text-[#1e1e1e]">{title}</p>
      {children && <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-[#6b6b6b]">{children}</p>}
    </div>
  );
}

/** Barra de trabalho em andamento — indeterminada de propósito: o agente não
 *  reporta percentual, e uma barra falsa que trava em 90% mina a confiança. */
export function Working({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#e67e22] border-t-transparent" />
      <span className="text-[13px] text-[#4a4a4a]">{label}</span>
    </div>
  );
}
