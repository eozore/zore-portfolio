import React from 'react';
import './About.css'; // Assuming BEM class is .about-section

const About = () => (
  <section id="about" className="about-section">
    <h2>About Me</h2>
    <p>
      Hello! I'm a passionate Data Scientist with a knack for uncovering insights from complex datasets.
      My expertise lies in machine learning, statistical analysis, and data visualization.
      I'm driven by the challenge of solving real-world problems and translating data into actionable strategies.
    </p>
    <h3>Skills</h3>
    <ul>
      <li>Python (Pandas, NumPy, Scikit-learn, TensorFlow/Keras)</li>
      <li>R</li>
      <li>SQL & NoSQL Databases</li>
      <li>Data Visualization (Matplotlib, Seaborn, Plotly, Tableau)</li>
      <li>Machine Learning (Regression, Classification, Clustering, NLP)</li>
      <li>Statistical Modeling & Hypothesis Testing</li>
      <li>Big Data Technologies (Spark, Hadoop - basic understanding)</li>
    </ul>
  </section>
);
export default About;
