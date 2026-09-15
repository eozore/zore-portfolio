'use server';

import { cookies } from 'next/headers';

export async function loginAction(email: string, password: string) {
  let sessionData = null;

  if (email === 'acesso@cromex.com.br' && password === process.env.LOGIN_PASSWORD_CROMEX) {
    sessionData = {
      email: 'acesso@cromex.com.br',
      companyId: 'cromex',
      name: 'Cromex Team',
      role: 'client',
    };
  } else if (email === 'visitante@eozore.com' && password === process.env.LOGIN_PASSWORD_VISITANTE) {
    sessionData = {
      email: 'visitante@eozore.com',
      name: 'Visitante Comum',
      role: 'user',
    };
  } else if (email === 'victorzore94@gmail.com' && password === process.env.LOGIN_PASSWORD_ADMIN) {
    sessionData = {
      email: 'victorzore94@gmail.com',
      name: 'Victor Zoré',
      role: 'admin',
    };
  }

  if (sessionData) {
    cookies().set({
      name: 'eozore_session',
      value: encodeURIComponent(JSON.stringify(sessionData)),
      path: '/',
      maxAge: 86400,
      sameSite: 'lax',
    });
    return { success: true };
  } else {
    return { success: false, error: 'E-mail ou senha incorretos.' };
  }
}
