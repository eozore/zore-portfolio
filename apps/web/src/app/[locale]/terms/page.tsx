import type { Metadata } from 'next';
import type { Locale } from '@/types/i18n';
import LegalDocument, { type LegalSection } from '@/components/legal/LegalDocument';

/**
 * Termos de Serviço.
 *
 * Exigidos pelo Google junto com a Política de Privacidade para publicar a
 * tela de consentimento OAuth. Descrevem o que o site oferece de fato —
 * portfólio, blog e as Tools com acesso por código de e-mail —, sem prometer
 * disponibilidade ou suporte que não existem.
 */

const CONTATO = 'contato@eozore.com';

const ATUALIZADO = {
  'pt-BR': 'Atualizados em 27 de agosto de 2026',
  en: 'Last updated 27 August 2026',
};

export async function generateMetadata({
  params,
}: {
  params: { locale: Locale };
}): Promise<Metadata> {
  const { locale } = params;
  const title = locale === 'pt-BR' ? 'Termos de Serviço' : 'Terms of Service';
  const description =
    locale === 'pt-BR'
      ? 'Condições de uso do eozore.com: o que o site oferece, o que se espera de quem usa, e os limites de responsabilidade.'
      : 'Terms of use for eozore.com: what the site offers, what is expected of visitors, and the limits of liability.';

  return {
    title,
    description,
    openGraph: { title, description, url: `https://eozore.com/${locale}/terms`, type: 'website' },
    alternates: {
      canonical: `/${locale}/terms`,
      languages: { 'pt-BR': '/pt-BR/terms', en: '/en/terms', 'x-default': '/pt-BR/terms' },
    },
  };
}

const SECOES_PT: LegalSection[] = [
  {
    titulo: '1. Aceitação',
    blocos: [
      'Ao acessar o <strong>eozore.com</strong> você concorda com estes Termos. Se não concordar com algum ponto, não use o site.',
      'Estes Termos devem ser lidos em conjunto com a <a href="/pt-BR/privacy" class="underline">Política de Privacidade</a>, que faz parte deles.',
    ],
  },
  {
    titulo: '2. O que o site oferece',
    blocos: [
      'O eozore.com é o site pessoal e profissional de Victor Zoré, e reúne três coisas:',
      {
        lista: [
          '<strong>Portfólio</strong> — apresentação de trabalho e experiência profissional.',
          '<strong>Blog</strong> — artigos técnicos sobre engenharia, machine learning e inteligência artificial.',
          '<strong>Tools</strong> — ferramentas de demonstração, oferecidas gratuitamente, com acesso liberado por um código enviado ao seu e-mail.',
        ],
      },
      'Há também o <strong>Content Studio</strong>, uma ferramenta interna de uso exclusivo do titular do site, que publica conteúdo nos canais dele próprio. Ela não é acessível ao público e não faz parte do que é oferecido aqui.',
    ],
  },
  {
    titulo: '3. Uso das Tools',
    blocos: [
      'As Tools são demonstrações técnicas, disponibilizadas <strong>como estão</strong>, sem garantia de disponibilidade, exatidão ou adequação a qualquer finalidade específica.',
      'Ao usá-las, você concorda em:',
      {
        lista: [
          'informar um endereço de e-mail válido e de sua titularidade;',
          'não tentar burlar limites de uso, autenticação ou qualquer controle de acesso;',
          'não enviar conteúdo ilegal, ofensivo, ou que viole direitos de terceiros;',
          'não usar as ferramentas para automação em escala, mineração de dados ou revenda do serviço.',
        ],
      },
      '<strong>Não use as Tools para decisões críticas.</strong> Os resultados são gerados por modelos de inteligência artificial e podem conter erros. Não substituem avaliação profissional, jurídica, médica ou financeira.',
    ],
  },
  {
    titulo: '4. Conteúdo e propriedade intelectual',
    blocos: [
      'Os textos, artigos, código, imagens e a identidade visual publicados neste site são de autoria de Victor Zoré, salvo indicação em contrário.',
      'Você pode <strong>ler, compartilhar e citar</strong> o conteúdo, desde que atribua a autoria e aponte para a página original. Reprodução integral, uso comercial ou criação de obra derivada exigem autorização prévia por escrito.',
      'O conteúdo que você envia às Tools continua sendo seu. Ele é processado para gerar o resultado que você pediu e não é usado para nenhuma outra finalidade.',
    ],
  },
  {
    titulo: '5. Disponibilidade',
    blocos: [
      'O site é mantido como projeto pessoal. Não há garantia de funcionamento ininterrupto, nem compromisso de nível de serviço ou de tempo de resposta a suporte.',
      'Funcionalidades podem ser alteradas, suspensas ou removidas a qualquer momento, sem aviso prévio.',
    ],
  },
  {
    titulo: '6. Limitação de responsabilidade',
    blocos: [
      'Na máxima extensão permitida pela lei brasileira, Victor Zoré não responde por danos indiretos, incidentais ou consequentes decorrentes do uso ou da impossibilidade de uso do site, incluindo perda de dados, de lucros ou de oportunidade de negócio.',
      'Isto não exclui responsabilidades que a lei não permite excluir.',
    ],
  },
  {
    titulo: '7. Links para terceiros',
    blocos: [
      'O site contém links para serviços de terceiros — entre eles YouTube, LinkedIn, Instagram e Threads. Esses serviços têm termos e políticas próprios, e o eozore.com não responde pelo conteúdo nem pelas práticas deles.',
    ],
  },
  {
    titulo: '8. Alterações nestes Termos',
    blocos: [
      'Estes Termos podem ser revistos. A versão vigente é sempre a publicada nesta página, com a data de atualização no topo. Continuar usando o site após uma alteração significa aceitá-la.',
    ],
  },
  {
    titulo: '9. Lei aplicável e contato',
    blocos: [
      'Estes Termos são regidos pelas leis da República Federativa do Brasil, e fica eleito o foro da comarca de domicílio do titular do site para dirimir controvérsias.',
      `Dúvidas sobre estes Termos: <strong>${CONTATO}</strong>.`,
    ],
  },
];

const SECOES_EN: LegalSection[] = [
  {
    titulo: '1. Acceptance',
    blocos: [
      'By accessing <strong>eozore.com</strong> you agree to these Terms. If you disagree with any part of them, do not use the site.',
      'These Terms should be read together with the <a href="/en/privacy" class="underline">Privacy Policy</a>, which forms part of them.',
    ],
  },
  {
    titulo: '2. What the site offers',
    blocos: [
      'eozore.com is the personal and professional website of Victor Zoré, and brings together three things:',
      {
        lista: [
          '<strong>Portfolio</strong> — a presentation of professional work and experience.',
          '<strong>Blog</strong> — technical articles on engineering, machine learning, and artificial intelligence.',
          '<strong>Tools</strong> — demo tools, offered free of charge, with access granted through a code sent to your email.',
        ],
      },
      'There is also the <strong>Content Studio</strong>, an internal tool used exclusively by the site owner to publish content to his own channels. It is not accessible to the public and is not part of what is offered here.',
    ],
  },
  {
    titulo: '3. Using the Tools',
    blocos: [
      'The Tools are technical demonstrations, provided <strong>as is</strong>, without any warranty of availability, accuracy, or fitness for a particular purpose.',
      'By using them, you agree to:',
      {
        lista: [
          'provide a valid email address that belongs to you;',
          'not attempt to circumvent usage limits, authentication, or any access control;',
          'not submit unlawful or offensive content, or content that infringes the rights of others;',
          'not use the tools for large-scale automation, data mining, or resale of the service.',
        ],
      },
      '<strong>Do not use the Tools for critical decisions.</strong> Results are generated by artificial intelligence models and may contain errors. They are no substitute for professional, legal, medical, or financial advice.',
    ],
  },
  {
    titulo: '4. Content and intellectual property',
    blocos: [
      'The text, articles, code, images, and visual identity published on this site are authored by Victor Zoré unless stated otherwise.',
      'You may <strong>read, share, and quote</strong> the content, provided you attribute the author and link to the original page. Full reproduction, commercial use, or derivative works require prior written permission.',
      'Content you submit to the Tools remains yours. It is processed to produce the result you asked for and is not used for any other purpose.',
    ],
  },
  {
    titulo: '5. Availability',
    blocos: [
      'The site is maintained as a personal project. There is no guarantee of uninterrupted operation, no service level commitment, and no guaranteed support response time.',
      'Features may be changed, suspended, or removed at any time without prior notice.',
    ],
  },
  {
    titulo: '6. Limitation of liability',
    blocos: [
      'To the fullest extent permitted by Brazilian law, Victor Zoré is not liable for indirect, incidental, or consequential damages arising from the use of, or inability to use, the site — including loss of data, profits, or business opportunity.',
      'This does not exclude liabilities that the law does not permit to be excluded.',
    ],
  },
  {
    titulo: '7. Third-party links',
    blocos: [
      'The site contains links to third-party services, including YouTube, LinkedIn, Instagram, and Threads. Those services have their own terms and policies, and eozore.com is not responsible for their content or practices.',
    ],
  },
  {
    titulo: '8. Changes to these Terms',
    blocos: [
      'These Terms may be revised. The version in force is always the one published on this page, with the update date at the top. Continuing to use the site after a change means accepting it.',
    ],
  },
  {
    titulo: '9. Governing law and contact',
    blocos: [
      'These Terms are governed by the laws of the Federative Republic of Brazil, and the courts of the site owner&rsquo;s domicile are elected to settle disputes.',
      `Questions about these Terms: <strong>${CONTATO}</strong>.`,
    ],
  },
];

export default function TermsPage({ params }: { params: { locale: Locale } }) {
  const { locale } = params;
  const pt = locale === 'pt-BR';

  return (
    <LegalDocument
      titulo={pt ? 'Termos de Serviço' : 'Terms of Service'}
      atualizadoEm={ATUALIZADO[pt ? 'pt-BR' : 'en']}
      resumo={
        pt
          ? 'O eozore.com é um site pessoal: portfólio, blog e ferramentas de demonstração oferecidas gratuitamente e como estão. Estas condições descrevem o que o site oferece, o que se espera de quem usa, e onde termina a responsabilidade.'
          : 'eozore.com is a personal website: a portfolio, a blog, and demo tools offered free of charge and as is. These terms describe what the site offers, what is expected of visitors, and where liability ends.'
      }
      secoes={pt ? SECOES_PT : SECOES_EN}
    />
  );
}
