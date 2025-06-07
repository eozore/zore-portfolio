import React from 'react';
import './Projects.css'; // Assuming BEM class is .projects-section and .project-item

const Projects = () => (
  <section id="projects" className="projects-section">
    <h2>My Projects</h2>
    <div className="projects-section__item">
      <h3>Customer Churn Prediction</h3>
      <p>
        Developed a machine learning model to predict customer churn for a telecom company,
        achieving an accuracy of X% and helping to identify key factors driving churn.
      </p>
      <p><strong>Technologies used:</strong> Python, Scikit-learn, Pandas, Matplotlib</p>
      <a href="#" target="_blank" rel="noopener noreferrer">View Project (Link to GitHub/Demo)</a>
    </div>
    <div className="projects-section__item">
      <h3>Sales Forecasting Model</h3>
      <p>
        Built a time series forecasting model to predict monthly sales for a retail client,
        improving forecast accuracy by Y% compared to previous methods.
      </p>
      <p><strong>Technologies used:</strong> Python, StatsModels, Pandas, Seaborn</p>
      <a href="#" target="_blank" rel="noopener noreferrer">View Project (Link to GitHub/Demo)</a>
    </div>
    <div className="projects-section__item">
      <h3>Sentiment Analysis of Product Reviews</h3>
      <p>
        Performed sentiment analysis on customer reviews for an e-commerce platform to identify
        areas for product improvement and gauge customer satisfaction.
      </p>
      <p><strong>Technologies used:</strong> Python, NLTK, VaderSentiment, Plotly</p>
      <a href="#" target="_blank" rel="noopener noreferrer">View Project (Link to GitHub/Demo)</a>
    </div>
  </section>
);
export default Projects;
