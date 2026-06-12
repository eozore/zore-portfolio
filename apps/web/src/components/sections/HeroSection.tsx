'use client';

import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import type { Locale, Dictionary } from '@/types/i18n';

interface HeroSectionProps {
  locale: Locale;
  dictionary: Dictionary['hero'];
}

const ROTATING_WORDS_PT = ['dados', 'modelos', 'decisões', 'produção', 'IA'];
const ROTATING_WORDS_EN = ['data', 'models', 'decisions', 'production', 'AI'];

function ParticleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let mouse = { x: 0, y: 0 };

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener('resize', resize);

    const particles: Array<{ x: number; y: number; vx: number; vy: number; size: number }> = [];
    const count = 60;
    const w = () => canvas.offsetWidth;
    const h = () => canvas.offsetHeight;

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * w(),
        y: Math.random() * h(),
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 2 + 1,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, w(), h());

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w()) p.vx *= -1;
        if (p.y < 0 || p.y > h()) p.vy *= -1;

        // Draw particle
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(99, 102, 241, 0.25)';
        ctx.fill();
      }

      // Connect nearby particles
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(99, 102, 241, ${0.08 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      // Mouse interaction — attract nearby particles slightly
      for (const p of particles) {
        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150 && dist > 0) {
          p.vx += dx * 0.00005;
          p.vy += dy * 0.00005;
        }
      }

      animId = requestAnimationFrame(draw);
    };

    draw();

    const handleMouse = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };
    canvas.addEventListener('mousemove', handleMouse);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
      canvas.removeEventListener('mousemove', handleMouse);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-auto"
    />
  );
}

function RotatingWord({ words }: { words: string[] }) {
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setIndex((i) => (i + 1) % words.length);
        setVisible(true);
      }, 300);
    }, 2500);
    return () => clearInterval(interval);
  }, [words]);

  return (
    <span
      className={`inline-block text-accent-data transition-all duration-300 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      }`}
    >
      {words[index]}
    </span>
  );
}

function CountUp({ target, suffix = '' }: { target: number; suffix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          const duration = 1500;
          const start = Date.now();
          const animate = () => {
            const elapsed = Date.now() - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.floor(eased * target));
            if (progress < 1) requestAnimationFrame(animate);
          };
          animate();
        }
      },
      { threshold: 0.5 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target]);

  return <span ref={ref}>{count}{suffix}</span>;
}

export default function HeroSection({ locale, dictionary }: HeroSectionProps) {
  const words = locale === 'pt-BR' ? ROTATING_WORDS_PT : ROTATING_WORDS_EN;

  return (
    <section id="home" className="relative min-h-[90vh] flex items-center overflow-hidden">
      {/* Organic blobs background (hero-specific — extra density) */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="blob blob-primary w-[500px] h-[500px] -top-20 -left-20 animate-float" />
        <div className="blob blob-cyan w-[400px] h-[400px] top-1/3 right-0 animate-float" style={{ animationDelay: '2s' }} />
      </div>

      <div className="relative z-10 max-w-container mx-auto px-4 py-20 flex flex-col lg:flex-row items-center gap-12">
        {/* Text */}
        <div className="flex-1 text-center lg:text-left">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-text-main leading-tight">
            {dictionary.greeting}
          </h1>
          <h2 className="mt-3 text-xl md:text-2xl text-text-muted">
            {dictionary.title}
          </h2>
          <p className="mt-4 text-lg text-text-muted leading-relaxed max-w-xl">
            {locale === 'pt-BR'
              ? 'Junto tecnologia e inteligência artificial para criar soluções que resolvem problemas reais de negócio.'
              : 'I combine technology and artificial intelligence to build solutions that solve real business problems.'
            }
          </p>
          <div className="mt-8 flex flex-wrap gap-4 justify-center lg:justify-start">
            <a
              href="https://www.ainewz.com.br/"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 bg-primary text-white font-medium rounded-lg hover:bg-glow hover:shadow-glow transition-all"
            >
              {dictionary.cta} <i className="fa-solid fa-arrow-right ml-2" />
            </a>
            <a
              href="#projetos"
              className="px-6 py-3 border border-border text-text-main font-medium rounded-lg hover:border-primary hover:text-primary transition-all"
            >
              {locale === 'pt-BR' ? 'Ver projetos' : 'View projects'}
            </a>
          </div>
          {/* Social links */}
          <div className="mt-6 flex gap-5 justify-center lg:justify-start text-text-muted">
            <a href="https://github.com/eozore" target="_blank" rel="noopener noreferrer" className="hover:text-text-main transition-colors text-xl" aria-label="GitHub">
              <i className="fa-brands fa-github" />
            </a>
            <a href="https://www.linkedin.com/in/victor-zor%C3%A9/" target="_blank" rel="noopener noreferrer" className="hover:text-text-main transition-colors text-xl" aria-label="LinkedIn">
              <i className="fa-brands fa-linkedin" />
            </a>
            <a href="https://www.youtube.com/@eozore" target="_blank" rel="noopener noreferrer" className="hover:text-text-main transition-colors text-xl" aria-label="YouTube">
              <i className="fa-brands fa-youtube" />
            </a>
          </div>
        </div>

        {/* Photo */}
        <div className="shrink-0 relative">
          <div className="w-[250px] h-[250px] md:w-[300px] md:h-[300px] rounded-full overflow-hidden border-2 border-primary/20 shadow-glow animate-float">
            <Image src="/image/hero.png" alt="Victor Zoré" width={300} height={300} className="w-full h-full object-cover" priority />
          </div>
          {/* Glass ring */}
          <div className="absolute -inset-3 rounded-full border border-primary/10 animate-pulse-slow" />
          <div className="absolute -inset-6 rounded-full border border-primary/5" />
        </div>
      </div>

      {/* Metrics bar — glass */}
      <div className="absolute bottom-0 left-0 right-0 glass-strong">
        <div className="max-w-container mx-auto px-4 py-5 grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-accent-data"><CountUp target={8} suffix="+" /></div>
            <div className="text-xs text-text-muted">{locale === 'pt-BR' ? 'Anos em dados' : 'Years in data'}</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-accent-data"><CountUp target={30} suffix="+" /></div>
            <div className="text-xs text-text-muted">{locale === 'pt-BR' ? 'Projetos ML/AI' : 'ML/AI Projects'}</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-accent-data"><CountUp target={20} suffix="+" /></div>
            <div className="text-xs text-text-muted">{locale === 'pt-BR' ? 'Empresas atendidas' : 'Companies served'}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
