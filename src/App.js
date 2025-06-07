import React from 'react';
import './App.css';
import Header from './components/Header/Header.js';
import About from './components/About/About.js';
import Projects from './components/Projects/Projects.js';
import Contact from './components/Contact/Contact.js';
import Footer from './components/Footer/Footer.js';

function App() {
  return (
    <div className="App">
      <Header />
      <About />
      <Projects />
      <Contact />
      <Footer />
    </div>
  );
}

export default App;
