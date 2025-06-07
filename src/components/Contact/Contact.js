import React from 'react';
import './Contact.css'; // Assuming BEM class is .contact-section

const Contact = () => (
  <section id="contact" className="contact-section">
    <h2>Contact</h2>
    <p>If you'd like to get in touch, please fill out the form below or reach out via email at <a href="mailto:your.email@example.com">your.email@example.com</a>.</p>
    <form className="contact-section__form"> {/* Ensure this class matches your CSS */}
      <input type="text" placeholder="Your Name" required />
      <input type="email" placeholder="Your Email" required />
      <textarea placeholder="Your Message" rows="5" required></textarea>
      <button type="submit">Send Message</button>
    </form>
  </section>
);
export default Contact;
