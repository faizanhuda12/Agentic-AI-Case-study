import React, { useState } from 'react';
import './App.css';
import ClassificationForm from './components/ClassificationForm';
import ResultsDisplay from './components/ResultsDisplay';

function App() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleClassification = async (formData) => {
    setLoading(true);
    setError(null);
    setResults(null);

    try {
      // Use workflow endpoint that orchestrates Agent 1 → Agent 2 → Agent 3 → Agent 4
      const apiUrl = process.env.REACT_APP_API_URL || 'https://fedex-workflow-214205443062.us-central1.run.app/workflow';
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to classify exception');
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setResults(null);
    setError(null);
  };

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <h1>🚚 FedEx Exception Classifier</h1>
          <p>Classify delivery exceptions using AI</p>
        </header>

        {!results ? (
          <ClassificationForm 
            onSubmit={handleClassification} 
            loading={loading}
            error={error}
          />
        ) : (
          <ResultsDisplay 
            results={results} 
            onReset={handleReset}
          />
        )}
      </div>
    </div>
  );
}

export default App;

