import Image from 'next/image';
import type { Locale, Dictionary } from '@/types/i18n';
import type { Project } from '@/types/project';

interface ProjectCardProps {
  project: Project;
  locale: Locale;
  tags: Dictionary['projects']['tags'];
}

export default function ProjectCard({ project, locale, tags }: ProjectCardProps) {
  return (
    <div className="bg-secondary rounded-card overflow-hidden border border-border shadow-sm hover:-translate-y-[5px] hover:shadow-lg transition-all duration-300">
      {/* Project Image */}
      <div className="relative w-full aspect-[16/10] overflow-hidden">
        <Image
          src={project.image}
          alt={project.title[locale]}
          fill
          className="object-cover"
          sizes="(max-width: 768px) 100vw, 33vw"
        />
      </div>

      {/* Card Content */}
      <div className="p-5">
        <span className="inline-block px-2.5 py-0.5 text-xs font-semibold rounded bg-primary/10 text-primary uppercase">
          {tags[project.category] ?? project.category.toUpperCase()}
        </span>
        <h3 className="mt-2 text-lg font-semibold text-text-main">
          {project.title[locale]}
        </h3>
        <p className="mt-1.5 text-sm text-text-light leading-relaxed line-clamp-3">
          {project.description[locale]}
        </p>

        {/* Technology tags */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {project.technologies.map((tech) => (
            <span
              key={tech}
              className="px-2 py-0.5 text-xs bg-background rounded text-text-main"
            >
              {tech}
            </span>
          ))}
        </div>

        {/* Optional link */}
        {project.link && (
          <a
            href={project.link}
            target={project.link.startsWith('http') ? '_blank' : undefined}
            rel={project.link.startsWith('http') ? 'noopener noreferrer' : undefined}
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary/80 transition-colors"
          >
            Ver Projeto
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        )}
      </div>
    </div>
  );
}
