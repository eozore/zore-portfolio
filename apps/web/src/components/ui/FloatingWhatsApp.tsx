'use client';

export default function FloatingWhatsApp() {
  const phoneNumber = '5521999999999'; // placeholder number
  const url = `https://wa.me/${phoneNumber}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-green-500 text-white shadow-lg hover:scale-110 transition-transform flex items-center justify-center"
      aria-label="Contact via WhatsApp"
    >
      <i className="fab fa-whatsapp text-2xl" />
    </a>
  );
}
