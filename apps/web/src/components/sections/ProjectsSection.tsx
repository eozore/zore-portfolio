import Image from 'next/image';
import type { Locale, Dictionary } from '@/types/i18n';
import type { Project } from '@/types/project';

interface ProjectsSectionProps {
  locale: Locale;
  dictionary: Dictionary['projects'];
  projects: Project[];
}

function ProjectCard({ project, locale }: { project: Project; locale: Locale }) {
  return (
    <div className="group relative glass rounded-card-lg p-6 flex flex-col hover:bg-white/10 hover:shadow-glow transition-all duration-500" style={{ background: 'rgba(255,255,255,0.04)' }}>
      {/* Subtle blob inside card */}
      <div className="absolute top-0 right-0 w-32 h-32 rounded-full bg-primary/5 blur-3xl pointer-events-none group-hover:bg-primary/8 transition-all duration-500" />

      {/* Image */}
      <div className="h-[160px] rounded-2xl overflow-hidden mb-4 bg-bg-elevated">
        <Image
          src={project.image}
          alt={project.title[locale]}
          width={400}
          height={160}
          className="w-full h-full object-cover group-hover:scale-105 transition-all duration-500"
          loading="lazy"
        />
      </div>

      {/* Category */}
      <span className="inline-block self-start px-3 py-1 text-[0.7rem] font-bold uppercase tracking-wider text-primary bg-primary/10 rounded-full mb-3">
        {project.category.toUpperCase()}
      </span>

      {/* Title */}
      <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-glow transition-colors">
        {project.title[locale]}
      </h3>

      {/* Description */}
      <p className="text-sm text-slate-400 flex-1 mb-4 leading-relaxed">
        {project.description[locale]}
      </p>

      {/* Tech tags */}
      <div className="flex flex-wrap gap-2 mb-4">
        {project.technologies.map((tech) => (
          <span key={tech} className="text-[0.7rem] px-2.5 py-1 rounded-full bg-white/[0.06] text-slate-300 border border-white/[0.08]">
            {tech}
          </span>
        ))}
      </div>

      {/* Link */}
      {project.link && (
        <a
          href={project.link}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-glow transition-colors"
          target={project.link.startsWith('http') ? '_blank' : undefined}
          rel={project.link.startsWith('http') ? 'noopener noreferrer' : undefined}
        >
          Ver projeto <i className="fa-solid fa-arrow-up-right-from-square text-xs" />
        </a>
      )}
    </div>
  );
}

export default function ProjectsSection({ locale, dictionary, projects }: ProjectsSectionProps) {
  return (
    <section id="projetos" className="relative py-24 overflow-hidden bg-[#0f0f1a]">
      {/* Decorative blobs */}
      <div className="blob blob-purple w-[300px] h-[300px] -top-10 -right-20" />
      <div className="blob blob-cyan w-[250px] h-[250px] bottom-20 -left-10" />

      <div className="relative z-10 max-w-container mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-bold text-white">{dictionary.title}</h2>
          <p className="mt-3 text-slate-400 text-lg">{dictionary.subtitle}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-7">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} locale={locale} />
          ))}
        </div>
      </div>
    </section>
  );
}
