'use client';

import React, { useState } from 'react';
import styles from './EmailGateModal.module.css';

interface EmailGateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function EmailGateModal({ isOpen, onClose, onSuccess }: EmailGateModalProps) {
  const [step, setStep] = useState<'email' | 'otp'>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  // Step 1: Submit Email to receive OTP code
  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/tools/verify-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();

      if (res.ok) {
        setSuccess('Código enviado! Verifique seu e-mail.');
        setStep('otp');
      } else {
        setError(data.error || 'Erro ao enviar código de verificação.');
      }
    } catch (err) {
      setError('Erro de conexão. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Validate OTP code and unlock
  const handleValidateOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/tools/validate-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code: otp }),
      });
      const data = await res.json();

      if (res.ok) {
        onSuccess();
        onClose();
      } else {
        setError(data.error || 'Código incorreto ou expirado.');
      }
    } catch (err) {
      setError('Erro de conexão. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.modal}>
        <button className={styles.closeButton} onClick={onClose} aria-label="Fechar modal">
          <i className="fa-solid fa-xmark" />
        </button>

        {step === 'email' ? (
          <>
            <div className={styles.titleSection}>
              <h3>Desbloquear Acesso</h3>
              <p className={styles.subtitle}>
                Você atingiu o limite de testes gratuitos. Insira seu e-mail de contato para continuar usando as ferramentas de IA sem limites.
              </p>
            </div>

            {error && <div className={styles.errorMessage}>{error}</div>}

            <form onSubmit={handleRequestOtp} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div className={styles.formGroup}>
                <label className={styles.label}>E-mail de Trabalho ou Pessoal</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="exemplo@empresa.com"
                  className={styles.input}
                  required
                />
              </div>

              <button type="submit" className={styles.actionButton} disabled={loading}>
                {loading ? 'Enviando código...' : 'Receber Código de Acesso'}
                <i className="fa-solid fa-paper-plane" />
              </button>
            </form>
          </>
        ) : (
          <>
            <div className={styles.titleSection}>
              <h3>Verifique seu E-mail</h3>
              <p className={styles.subtitle}>
                Enviamos um código de verificação de 6 dígitos para <strong>{email}</strong>.
              </p>
            </div>

            {error && <div className={styles.errorMessage}>{error}</div>}
            {success && <div className={styles.successMessage}>{success}</div>}

            <form onSubmit={handleValidateOtp} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Código OTP (6 dígitos)</label>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  placeholder="123456"
                  className={styles.input}
                  maxLength={6}
                  required
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button 
                  type="button" 
                  className={styles.actionButton} 
                  style={{ background: 'transparent', border: '1px solid rgba(0,0,0,0.1)', color: 'var(--text-muted)', flex: 1 }}
                  onClick={() => setStep('email')}
                >
                  Voltar
                </button>
                <button type="submit" className={styles.actionButton} style={{ flex: 2 }} disabled={loading}>
                  {loading ? 'Verificando...' : 'Confirmar e Entrar'}
                  <i className="fa-solid fa-circle-check" />
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
