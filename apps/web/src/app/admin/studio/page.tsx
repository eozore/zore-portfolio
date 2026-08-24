import type { Metadata } from 'next';
import Studio from '@/components/studio/Studio';

export const metadata: Metadata = {
  title: 'Studio | éozoré',
  description: 'Do tema ao pacote publicado, com dois pontos de aprovação.',
  robots: { index: false, follow: false },
};

export default function StudioPage() {
  return <Studio />;
}
