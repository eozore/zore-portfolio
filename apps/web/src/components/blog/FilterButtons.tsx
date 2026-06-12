'use client';

import { useState } from 'react';
import type { ArticleCategory } from '@/types/article';

interface FilterButtonsProps {
  filters: Record<string, string>;
  onFilterChange: (category: ArticleCategory | 'all') => void;
}

export default function FilterButtons({ filters, onFilterChange }: FilterButtonsProps) {
  const [active, setActive] = useState<string>('all');

  const categories = ['all', 'estatistica', 'ml', 'ia'] as const;

  const handleClick = (category: (typeof categories)[number]) => {
    setActive(category);
    onFilterChange(category === 'all' ? 'all' : category);
  };

  return (
    <div className="flex flex-wrap gap-2 justify-center mb-8">
      {categories.map((cat) => (
        <button
          key={cat}
          onClick={() => handleClick(cat)}
          className={`px-4 py-2 rounded-card text-sm font-medium transition-colors ${
            active === cat
              ? 'bg-primary text-white'
              : 'bg-secondary border border-border text-text-main hover:border-primary'
          }`}
        >
          {filters[cat] || cat}
        </button>
      ))}
    </div>
  );
}
