import type { Metadata } from 'next';

export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

/**
 * O wrapper do /admin pintava um tema ESCURO (#0a0a0f de fundo, #e2e8f0 de
 * texto) — sobra da versão anterior do CSM. As duas interfaces são claras hoje,
 * então isso só não aparecia porque o Studio pinta um `min-h-screen` claro por
 * cima. Sobrava nas bordas: área de overscroll, e qualquer texto que não
 * declarasse cor própria herdava quase-branco sobre branco.
 *
 * Agora usa os mesmos tokens do site.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg-deep text-text-main">
      {children}
    </div>
  );
}
