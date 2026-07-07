// apps/web/src/app/api/tools/route.ts

import { NextRequest, NextResponse } from 'next/server';
import { ToolInfo } from '@/types/user';

export async function GET(request: NextRequest) {
  // Read session cookie
  const sessionCookie = request.cookies.get('eozore_session')?.value;
  let userSession: any = null;

  if (sessionCookie) {
    try {
      userSession = JSON.parse(decodeURIComponent(sessionCookie));
    } catch (e) {
      // Ignore parsing errors
    }
  }

  // Predefined tools catalog
  const toolsCatalog: ToolInfo[] = [
    {
      id: 'sentiment-classifier',
      name: 'Classificador de Sentimento',
      slug: 'classificador-sentimento',
      description: 'Analise o sentimento de textos em português ou inglês usando NLP.',
      icon: 'fa-brain',
      isPrivate: false, // Public
    },
    {
      id: 'cromex-intelligence',
      name: 'Cromex Intelligence',
      slug: 'cromex',
      description: 'Visualização de aderência mercado interno/externo e cálculo automatizado de CM1.',
      icon: 'fa-chart-pie',
      isPrivate: true, // Private
    }
  ];

  // Filter tools based on permissions
  const filteredTools = toolsCatalog.filter(tool => {
    if (!tool.isPrivate) return true; // Public tools are always accessible
    
    // Private tools require matching companyId or admin role
    if (!userSession) return false;
    if (userSession.role === 'admin') return true;
    
    if (tool.slug === 'cromex' && userSession.companyId === 'cromex') {
      return true;
    }
    
    return false;
  });

  return NextResponse.json({ tools: filteredTools });
}
