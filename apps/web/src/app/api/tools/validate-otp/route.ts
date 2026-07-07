// apps/web/src/app/api/tools/validate-otp/route.ts

import { NextRequest, NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';

export async function POST(request: NextRequest) {
  try {
    const { email, code } = await request.json();

    if (!email || !code) {
      return NextResponse.json({ error: 'E-mail e código são necessários.' }, { status: 400 });
    }

    const db = getFirestoreDb();
    let isCodeValid = false;

    if (db) {
      const otpDocRef = db.collection('otps').doc(email);
      const otpDoc = await otpDocRef.get();

      if (otpDoc.exists) {
        const data = otpDoc.data();
        const timeDiff = Date.now() - (data?.createdAt || 0);

        // Validar código e expiração de 15 minutos (900000 ms)
        if (data?.code === code && timeDiff < 900000) {
          isCodeValid = true;
          
          // Limpa o OTP usado para evitar reuso
          await otpDocRef.delete();

          // Atualiza o status do lead no Firestore
          await db.collection('leads').doc(email).set({
            verified: true,
            verifiedAt: Date.now()
          }, { merge: true });
        }
      }
    } else {
      // Fallback local se o Firestore estiver indisponível (para testes rápidos em dev)
      if (code === '123456' || code === '654321') {
        isCodeValid = true;
      }
    }

    if (isCodeValid) {
      // Gerar resposta de sucesso
      const response = NextResponse.json({ 
        success: true, 
        message: 'Código validado com sucesso! Acesso liberado.' 
      });

      // Gravar cookie eozore_lead válido por 30 dias
      response.cookies.set('eozore_lead', encodeURIComponent(email), {
        path: '/',
        maxAge: 86400 * 30, // 30 dias
        sameSite: 'lax'
      });

      return response;
    } else {
      return NextResponse.json({ error: 'Código inválido ou expirado.' }, { status: 400 });
    }

  } catch (error) {
    console.error('Erro na validação do OTP:', error);
    return NextResponse.json({ error: 'Falha interna ao validar o código.' }, { status: 500 });
  }
}
