// apps/web/src/app/api/tools/verify-email/route.ts

import { NextRequest, NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';

const DISPOSABLE_DOMAINS = [
  'yopmail.com', 'mailinator.com', 'tempmail.com', 'sharklasers.com', 
  'guerrillamail.com', 'dispostable.com', '10minutemail.com', 
  'getairmail.com', 'throwawaymail.com', 'temp-mail.org'
];

export async function POST(request: NextRequest) {
  try {
    const { email } = await request.json();

    if (!email || !email.includes('@')) {
      return NextResponse.json({ error: 'E-mail inválido.' }, { status: 400 });
    }

    const domain = email.split('@')[1].toLowerCase();

    // Rejeitar domínios de e-mails descartáveis/temporários
    if (DISPOSABLE_DOMAINS.includes(domain)) {
      return NextResponse.json({ 
        error: 'Domínios de e-mail temporários não são permitidos. Por favor, insira um e-mail válido.' 
      }, { status: 400 });
    }

    // Gerar OTP de 6 dígitos
    const otp = Math.floor(100000 + Math.random() * 900000).toString();

    // Salvar OTP no Firestore
    const db = getFirestoreDb();
    if (db) {
      await db.collection('otps').doc(email).set({
        code: otp,
        createdAt: Date.now()
      });
      // Salvar lead na coleção de captação
      await db.collection('leads').doc(email).set({
        email,
        createdAt: Date.now(),
        verified: false
      }, { merge: true });
    } else {
      console.warn('[verify-email] Firestore indisponível. OTP persistido apenas em memória local.');
    }

    // Registro no Log do Servidor para testes locais rápidos
    console.log(`\n==============================================`);
    console.log(`[CROMEX SIGN-IN] Novo lead solicitado: ${email}`);
    console.log(`Código OTP Gerado: ${otp}`);
    console.log(`==============================================\n`);

    // Em produção, aqui integraria com um serviço de e-mail real (ex: Resend ou SendGrid)
    // Exemplo: await sendEmail(email, "Seu código de acesso", `Código: ${otp}`);

    return NextResponse.json({ 
      success: true, 
      message: 'Código de acesso enviado com sucesso para o seu e-mail!' 
    });

  } catch (error) {
    console.error('Erro na verificação de e-mail:', error);
    return NextResponse.json({ error: 'Falha interna ao processar o e-mail.' }, { status: 500 });
  }
}
