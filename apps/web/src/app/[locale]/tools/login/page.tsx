'use client';

import React, { useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import styles from './login.module.css';

function LoginForm() {
  const searchParams = useSearchParams();
  const redirect = searchParams.get('redirect') || 'tools';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const { loginAction } = await import('./actions');
      const result = await loginAction(email, password);
      
      if (result.success) {
        // Use full page reload to force middleware cookie parsing
        window.location.href = `/${redirect}`;
      } else {
        setError(result.error || 'E-mail ou senha incorretos.');
        setIsLoading(false);
      }
    } catch (err) {
      setError('Erro ao realizar login.');
      setIsLoading(false);
    }
  };

  const fillDemo = (demoType: 'cromex' | 'public') => {
    if (demoType === 'cromex') {
      setEmail('acesso@cromex.com.br');
      setPassword('');
    } else {
      setEmail('visitante@eozore.com');
      setPassword('');
    }
  };

  return (
    <div className={styles.loginCard}>
      <div className={styles.titleSection}>
        <h2>Acesso à Plataforma</h2>
        <p className={styles.subtitle}>Gerencie suas ferramentas e relatórios de IA corporativos.</p>
      </div>

      {error && <div className={styles.errorMessage}>{error}</div>}

      <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div className={styles.formGroup}>
          <label htmlFor="email-input" className={styles.label}>E-mail</label>
          <input
            id="email-input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={styles.input}
            placeholder="seu.email@empresa.com"
            required
          />
        </div>

        <div className={styles.formGroup}>
          <label htmlFor="password-input" className={styles.label}>Senha</label>
          <input
            id="password-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={styles.input}
            placeholder="••••••••"
            required
          />
        </div>

        <button
          id="btn-login-submit"
          type="submit"
          className={styles.loginButton}
          disabled={isLoading}
        >
          {isLoading ? 'Autenticando...' : 'Entrar'}
        </button>
      </form>

      {process.env.NODE_ENV === 'development' && (
        <>
          <div className={styles.divider}>Acesso de Demonstração</div>

          <div className={styles.demoSection}>
            <button
              id="btn-demo-cromex"
              className={styles.demoButton}
              onClick={() => fillDemo('cromex')}
            >
              <i className="fa-solid fa-building text-amber-500" />
              Entrar como Cromex (Privado)
            </button>
            <button
              id="btn-demo-public"
              className={styles.demoButton}
              onClick={() => fillDemo('public')}
            >
              <i className="fa-solid fa-globe text-blue-500" />
              Entrar como Visitante (Público)
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default function LoginPage() {
  return (
    <section className={styles.container}>
      <Suspense fallback={<div className={styles.loginCard} style={{ textAlign: 'center', padding: '3rem' }}>Carregando formulário...</div>}>
        <LoginForm />
      </Suspense>
    </section>
  );
}
