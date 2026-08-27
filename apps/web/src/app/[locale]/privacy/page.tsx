import type { Metadata } from 'next';
import type { Locale } from '@/types/i18n';
import LegalDocument, { type LegalSection } from '@/components/legal/LegalDocument';

/**
 * Política de Privacidade.
 *
 * Existe por exigência do Google: publicar a tela de consentimento OAuth em
 * "In production" requer uma política de privacidade acessível no MESMO
 * domínio do app. Enquanto a tela fica em "Testing", o refresh token do
 * YouTube expira a cada 7 dias e a publicação da pipeline quebra sozinha.
 *
 * O conteúdo descreve o que o sistema REALMENTE faz — conferido contra o
 * código, não contra um modelo genérico:
 *   - Google Analytics G-X2JQPFL0QR em app/layout.tsx
 *   - captação de lead (só e-mail) em api/tools/verify-email
 *   - escopos do YouTube usados pelo publisher_job
 * Se algum desses mudar, esta página muda junto.
 */

// Canal de contato publicado. Numa constante porque aparece nos dois idiomas
// e também nos Termos — trocar em um lugar só deixaria os textos divergentes.
const CONTATO = 'contato@eozore.com';

const ATUALIZADO = {
  'pt-BR': 'Atualizada em 27 de agosto de 2026',
  en: 'Last updated 27 August 2026',
};

export async function generateMetadata({
  params,
}: {
  params: { locale: Locale };
}): Promise<Metadata> {
  const { locale } = params;
  const title = locale === 'pt-BR' ? 'Política de Privacidade' : 'Privacy Policy';
  const description =
    locale === 'pt-BR'
      ? 'Como o eozore.com trata dados pessoais, cookies e os dados acessados via APIs do Google, YouTube, LinkedIn e Meta.'
      : 'How eozore.com handles personal data, cookies, and data accessed through the Google, YouTube, LinkedIn and Meta APIs.';

  return {
    title,
    description,
    openGraph: { title, description, url: `https://eozore.com/${locale}/privacy`, type: 'website' },
    alternates: {
      canonical: `/${locale}/privacy`,
      languages: { 'pt-BR': '/pt-BR/privacy', en: '/en/privacy', 'x-default': '/pt-BR/privacy' },
    },
  };
}

const SECOES_PT: LegalSection[] = [
  {
    titulo: '1. Quem opera este site',
    blocos: [
      'O <strong>eozore.com</strong> é o site pessoal e profissional de Victor Zoré. Não é uma empresa de software com base de usuários: é um portfólio, um blog e um conjunto de ferramentas de demonstração.',
      `Para qualquer assunto relacionado a privacidade, incluindo pedidos de acesso ou exclusão, escreva para <strong>${CONTATO}</strong>.`,
    ],
  },
  {
    titulo: '2. Que dados são coletados',
    blocos: [
      'Apenas o necessário, e apenas em duas situações:',
      {
        lista: [
          '<strong>Navegação.</strong> O site usa Google Analytics (identificador <code>G-X2JQPFL0QR</code>), que registra páginas visitadas, tempo de permanência, tipo de dispositivo, navegador e uma localização aproximada por região. Esses dados são agregados e não identificam você pessoalmente.',
          '<strong>Acesso às Tools.</strong> Para entrar nas ferramentas você informa um <strong>endereço de e-mail</strong> e recebe um código de verificação de 6 dígitos. São gravados o e-mail, a data do cadastro e se o e-mail foi verificado. <strong>Nenhum outro dado é pedido</strong> — não há nome, telefone, empresa nem cartão.',
        ],
      },
      'Não há formulário de cadastro aberto, não há criação de senha e não são processados dados de pagamento em nenhum ponto do site.',
    ],
  },
  {
    titulo: '3. Cookies',
    blocos: [
      'São usados dois cookies próprios, ambos funcionais:',
      {
        lista: [
          '<code>eozore_session</code> — mantém você conectado às Tools depois da verificação por código.',
          '<code>eozore_lead</code> — evita pedir o e-mail de novo a cada visita.',
        ],
      },
      'O Google Analytics grava seus próprios cookies de medição. Você pode bloqueá-los pelas configurações do navegador ou pelo <a href="https://tools.google.com/dlpage/gaoptout" class="underline" target="_blank" rel="noopener noreferrer">complemento de desativação do Google Analytics</a>. Bloquear os cookies de análise não afeta o funcionamento do site; bloquear os funcionais impede o acesso às Tools.',
    ],
  },
  {
    titulo: '4. Dados acessados através de APIs do Google e do YouTube',
    blocos: [
      'Esta seção descreve o <strong>Content Studio</strong>, uma ferramenta interna e privada, usada exclusivamente por Victor Zoré para publicar conteúdo nos <strong>próprios canais</strong>. Ela não está aberta ao público, não tem cadastro e não acessa a conta de terceiros.',
      'O Content Studio usa os <strong>YouTube API Services</strong>. Ao usar o site você concorda com os <a href="https://www.youtube.com/t/terms" class="underline" target="_blank" rel="noopener noreferrer">Termos de Serviço do YouTube</a>, e o tratamento de dados pelo Google é regido pela <a href="https://policies.google.com/privacy" class="underline" target="_blank" rel="noopener noreferrer">Política de Privacidade do Google</a>.',
      'As permissões solicitadas ao Google, e para que servem:',
      {
        lista: [
          '<code>youtube.upload</code> — enviar vídeos ao canal do próprio titular da conta. Os vídeos são enviados com visibilidade <strong>privada</strong>; torná-los públicos é sempre uma decisão manual posterior.',
          '<code>youtube.readonly</code> — confirmar que a autorização está válida e identificar o canal de destino antes de enviar.',
        ],
      },
      'O token de autorização é guardado criptografado no <strong>Google Secret Manager</strong>, dentro do projeto do próprio titular, e é usado apenas pelos serviços desta pipeline. Ele <strong>não é compartilhado com terceiros</strong>, não é usado para publicidade, não alimenta treinamento de modelos e não é transferido para nenhum outro sistema.',
      'A autorização pode ser revogada a qualquer momento em <a href="https://myaccount.google.com/permissions" class="underline" target="_blank" rel="noopener noreferrer">myaccount.google.com/permissions</a>. A revogação tem efeito imediato e impede qualquer envio posterior.',
    ],
  },
  {
    titulo: '5. Outras plataformas',
    blocos: [
      'O Content Studio também publica, sempre em contas de titularidade de Victor Zoré, no LinkedIn, no Instagram e no Threads. Valem as mesmas regras da seção anterior: os tokens ficam no Secret Manager, não são compartilhados, e a autorização é revogável nas configurações de cada plataforma.',
    ],
  },
  {
    titulo: '6. Onde os dados ficam e por quanto tempo',
    blocos: [
      'Os dados são armazenados no <strong>Google Cloud Platform</strong>, em servidores nos Estados Unidos. Os códigos de verificação são temporários e perdem a validade em minutos. Os endereços de e-mail cadastrados nas Tools são mantidos enquanto forem úteis ao contato ou até você pedir a exclusão.',
    ],
  },
  {
    titulo: '7. Compartilhamento',
    blocos: [
      '<strong>Seus dados não são vendidos, alugados nem cedidos a terceiros.</strong> Os únicos terceiros envolvidos são os provedores de infraestrutura que tornam o site possível — Google Cloud, que hospeda, e Google Analytics, que mede audiência.',
    ],
  },
  {
    titulo: '8. Seus direitos',
    blocos: [
      'Pela Lei Geral de Proteção de Dados (LGPD, Lei nº 13.709/2018) você pode pedir confirmação de tratamento, acesso, correção, portabilidade, anonimização ou exclusão dos seus dados, e revogar consentimento.',
      `Escreva para <strong>${CONTATO}</strong>. O pedido é respondido em até 15 dias.`,
    ],
  },
  {
    titulo: '9. Alterações',
    blocos: [
      'Mudanças nesta política aparecem nesta página, com a data de atualização revista no topo. Alterações relevantes na forma de tratar dados pessoais são anunciadas no site antes de entrarem em vigor.',
    ],
  },
];

const SECOES_EN: LegalSection[] = [
  {
    titulo: '1. Who operates this site',
    blocos: [
      '<strong>eozore.com</strong> is the personal and professional website of Victor Zoré. It is not a software company with a user base: it is a portfolio, a blog, and a small set of demo tools.',
      `For anything related to privacy, including access or deletion requests, write to <strong>${CONTATO}</strong>.`,
    ],
  },
  {
    titulo: '2. What data is collected',
    blocos: [
      'Only what is needed, and only in two situations:',
      {
        lista: [
          '<strong>Browsing.</strong> The site uses Google Analytics (property <code>G-X2JQPFL0QR</code>), which records pages visited, time on page, device type, browser, and an approximate region-level location. This data is aggregated and does not identify you personally.',
          '<strong>Tools access.</strong> To sign in to the tools you provide an <strong>email address</strong> and receive a 6-digit verification code. We store the email, the sign-up date, and whether the email was verified. <strong>Nothing else is requested</strong> — no name, phone, company, or card.',
        ],
      },
      'There is no open registration form, no password to create, and no payment data is processed anywhere on the site.',
    ],
  },
  {
    titulo: '3. Cookies',
    blocos: [
      'Two first-party cookies are used, both functional:',
      {
        lista: [
          '<code>eozore_session</code> — keeps you signed in to the Tools after code verification.',
          '<code>eozore_lead</code> — avoids asking for your email again on every visit.',
        ],
      },
      'Google Analytics sets its own measurement cookies. You can block them through your browser settings or the <a href="https://tools.google.com/dlpage/gaoptout" class="underline" target="_blank" rel="noopener noreferrer">Google Analytics opt-out add-on</a>. Blocking analytics cookies does not affect how the site works; blocking functional cookies prevents access to the Tools.',
    ],
  },
  {
    titulo: '4. Data accessed through Google and YouTube APIs',
    blocos: [
      'This section describes the <strong>Content Studio</strong>, a private internal tool used exclusively by Victor Zoré to publish content to <strong>his own channels</strong>. It is not open to the public, has no sign-up, and does not access anyone else&rsquo;s account.',
      'The Content Studio uses <strong>YouTube API Services</strong>. By using this site you agree to the <a href="https://www.youtube.com/t/terms" class="underline" target="_blank" rel="noopener noreferrer">YouTube Terms of Service</a>, and Google&rsquo;s handling of data is governed by the <a href="https://policies.google.com/privacy" class="underline" target="_blank" rel="noopener noreferrer">Google Privacy Policy</a>.',
      'The permissions requested from Google, and what they are for:',
      {
        lista: [
          '<code>youtube.upload</code> — upload videos to the account holder&rsquo;s own channel. Videos are uploaded as <strong>private</strong>; making them public is always a separate, manual decision.',
          '<code>youtube.readonly</code> — confirm the authorization is still valid and identify the destination channel before uploading.',
        ],
      },
      'The authorization token is stored encrypted in <strong>Google Secret Manager</strong>, inside the account holder&rsquo;s own project, and is used only by this pipeline&rsquo;s services. It is <strong>not shared with third parties</strong>, not used for advertising, does not feed model training, and is not transferred to any other system.',
      'Authorization can be revoked at any time at <a href="https://myaccount.google.com/permissions" class="underline" target="_blank" rel="noopener noreferrer">myaccount.google.com/permissions</a>. Revocation takes effect immediately and prevents any further upload.',
    ],
  },
  {
    titulo: '5. Other platforms',
    blocos: [
      'The Content Studio also publishes to LinkedIn, Instagram, and Threads, always to accounts owned by Victor Zoré. The same rules as above apply: tokens live in Secret Manager, are never shared, and authorization is revocable in each platform&rsquo;s settings.',
    ],
  },
  {
    titulo: '6. Where data lives and for how long',
    blocos: [
      'Data is stored on <strong>Google Cloud Platform</strong>, on servers in the United States. Verification codes are temporary and expire within minutes. Email addresses registered through the Tools are kept while they remain useful for contact, or until you request deletion.',
    ],
  },
  {
    titulo: '7. Sharing',
    blocos: [
      '<strong>Your data is not sold, rented, or handed to third parties.</strong> The only third parties involved are the infrastructure providers that make the site possible — Google Cloud, which hosts it, and Google Analytics, which measures audience.',
    ],
  },
  {
    titulo: '8. Your rights',
    blocos: [
      'Under Brazil&rsquo;s General Data Protection Law (LGPD, Law 13.709/2018) you may request confirmation of processing, access, correction, portability, anonymization, or deletion of your data, and withdraw consent.',
      `Write to <strong>${CONTATO}</strong>. Requests are answered within 15 days.`,
    ],
  },
  {
    titulo: '9. Changes',
    blocos: [
      'Changes to this policy appear on this page, with the date at the top revised. Material changes to how personal data is handled are announced on the site before taking effect.',
    ],
  },
];

export default function PrivacyPage({ params }: { params: { locale: Locale } }) {
  const { locale } = params;
  const pt = locale === 'pt-BR';

  return (
    <LegalDocument
      titulo={pt ? 'Política de Privacidade' : 'Privacy Policy'}
      atualizadoEm={ATUALIZADO[pt ? 'pt-BR' : 'en']}
      resumo={
        pt
          ? 'Este site coleta pouco: métricas agregadas de navegação e, se você usar as Tools, um endereço de e-mail. As seções 4 e 5 descrevem o Content Studio, a ferramenta interna que publica nos canais do próprio titular via APIs do Google, YouTube, LinkedIn e Meta.'
          : 'This site collects very little: aggregated browsing metrics and, if you use the Tools, an email address. Sections 4 and 5 describe the Content Studio, the internal tool that publishes to the owner&rsquo;s own channels through the Google, YouTube, LinkedIn and Meta APIs.'
      }
      secoes={pt ? SECOES_PT : SECOES_EN}
    />
  );
}
