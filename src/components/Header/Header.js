import React from 'react';
import './Header.css';

const Header = () => (
  <header className="header-section"> {/* Using only header-section as styles are consolidated */}
    <h1>Data Scientist Name</h1>
    <nav>
      <a href="#about">About</a>
      <a href="#projects">Projects</a>
      <a href="#contact">Contact</a>
    </nav>
  </header>
);
export default Header;
