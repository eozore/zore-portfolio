import { Project } from '@/types/project';

export const projects: Project[] = [
  {
    id: 'ai-newz',
    title: {
      'pt-BR': 'AI Newz',
      en: 'AI Newz',
    },
    description: {
      'pt-BR':
        'Newsletter escrita por agentes de inteligência artificial e enviada diariamente para o seu email.',
      en: 'AI-agent-written newsletter delivered daily to your inbox.',
    },
    category: 'ai',
    technologies: ['Cloud Run (GCP)', 'Flask', 'SendGrid'],
    image: '/image/projeto_ainewz.png',
    link: 'https://www.ainewz.com.br/',
  },
  {
    id: 'churn',
    title: {
      'pt-BR': 'Redução de Churn',
      en: 'Churn Reduction',
    },
    description: {
      'pt-BR':
        'Identificação de usuários com alto risco de churn e recomendação de ações personalizadas de retenção',
      en: 'High-risk churn detection and personalized retention action recommendations.',
    },
    category: 'ml',
    technologies: ['Scikit-learn', 'LTV', 'SageMaker (AWS)'],
    image: '/image/projeto_churn.png',
  },
  {
    id: 'ai-articlez',
    title: {
      'pt-BR': 'AI Articlez',
      en: 'AI Articlez',
    },
    description: {
      'pt-BR':
        'Agentes autônomos de inteligência artificial capazes de planejar, redigir e ilustrar conteúdos completos para blogs e redes sociais.',
      en: 'Autonomous AI agents that can plan, write, and illustrate full content for blogs and social platforms.',
    },
    category: 'ai',
    technologies: ['Cloud Run (GCP)', 'LLM', 'API'],
    image: '/image/projeto_aiarticlez.png',
    link: '/blog',
  },
  {
    id: 'mmm',
    title: {
      'pt-BR': 'Marketing Mix Modelling',
      en: 'Marketing Mix Modeling',
    },
    description: {
      'pt-BR':
        'Mix de modelos de regressão e série temporal para estimar os efeitos de investimento no resultado e calcular o share ótimo de investimentos em mídias pagas.',
      en: 'Regression and time-series model mix to estimate media investment effects and optimize paid media share.',
    },
    category: 'ml',
    technologies: ['Scikit-learn', 'R', 'Google Analytics'],
    image: '/image/projeto_mmm.png',
  },
  {
    id: 'ai-chatz',
    title: {
      'pt-BR': 'AI Chatz',
      en: 'AI Chatz',
    },
    description: {
      'pt-BR':
        'Assistente de atendimento humanizado com fluxo personalizado aplicável a qualquer área de negócios, capaz de responder perguntas baseado em processos internos.',
      en: 'Humanized support assistant with custom workflow, applicable to any business area, with process-grounded responses.',
    },
    category: 'ai',
    technologies: ['Bedrock (AWS)', 'Lambda (AWS)', 'RAG'],
    image: '/image/projeto_aichat.png',
  },
  {
    id: 'recomendacao',
    title: {
      'pt-BR': 'Sistema de Recomendação',
      en: 'Recommendation System',
    },
    description: {
      'pt-BR':
        'Algoritmo de recomendação personalizada baseado em comportamento do usuário e características do item para streaming de música.',
      en: 'Personalized recommendation algorithm based on user behavior and item features for music streaming.',
    },
    category: 'ml',
    technologies: ['Personalize (AWS)', 'APIGateway (AWS)', 'Lambda (AWS)'],
    image: '/image/projeto_recom.png',
  },
];
