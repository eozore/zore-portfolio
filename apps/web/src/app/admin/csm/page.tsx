import type { Metadata } from 'next';
import CsmDashboard from '@/components/csm/CsmDashboard';

export const metadata: Metadata = {
  title: 'Content Studio Manager | éozoré',
  description: 'Ferramenta interna de criação e gestão de conteúdo.',
  robots: { index: false, follow: false },
};

export default function CsmPage() {
  return <CsmDashboard />;
}
