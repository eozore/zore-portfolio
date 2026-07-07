const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 'default-encryption-key-for-dev-32chars';

async function getCryptoKey(password: string): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const rawKey = enc.encode(password.padEnd(32, '0').slice(0, 32)); // Ensure 32 bytes
  return crypto.subtle.importKey(
    'raw',
    rawKey,
    { name: 'AES-GCM' },
    false,
    ['encrypt', 'decrypt']
  );
}

export async function encrypt(text: string): Promise<string> {
  if (!text) return '';
  const cryptoKey = await getCryptoKey(ENCRYPTION_KEY);
  const enc = new TextEncoder();
  const encodedText = enc.encode(text);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    cryptoKey,
    encodedText
  );
  
  const combined = new Uint8Array(iv.length + encrypted.byteLength);
  combined.set(iv, 0);
  combined.set(new Uint8Array(encrypted), iv.length);
  
  return Buffer.from(combined).toString('base64');
}

export async function decrypt(encryptedBase64: string): Promise<string> {
  if (!encryptedBase64) return '';
  try {
    const cryptoKey = await getCryptoKey(ENCRYPTION_KEY);
    const combined = Buffer.from(encryptedBase64, 'base64');
    const iv = combined.slice(0, 12);
    const ciphertext = combined.slice(12);
    
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      cryptoKey,
      ciphertext
    );
    
    const dec = new TextDecoder();
    return dec.decode(decrypted);
  } catch (err) {
    // Graceful fallback for legacy plaintext API keys
    return encryptedBase64;
  }
}
