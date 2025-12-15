import React from 'react';
import './ResultsDisplay.css';

const ResultsDisplay = ({ results, onReset }) => {
  const { 
    predicted_label, 
    confidence, 
    top_predictions,
    // Agent 2 results
    sop_retrieved,
    sop_content,
    sop_score,
    // Agent 3 results
    decision,
    // Agent 4 results
    action,
    agents_executed
  } = results;

  const getConfidenceColor = (conf) => {
    if (conf >= 0.8) return '#27ae60';
    if (conf >= 0.6) return '#f39c12';
    return '#e74c3c';
  };

  const getConfidenceLabel = (conf) => {
    if (conf >= 0.8) return 'High';
    if (conf >= 0.6) return 'Medium';
    return 'Low';
  };

  return (
    <div className="results-container">
      <div className="results-header">
        <h2>Classification Results</h2>
        <button onClick={onReset} className="reset-button">
          New Classification
        </button>
      </div>

      <div className="main-result">
        <div className="predicted-label">
          <span className="label-badge">Predicted Exception</span>
          <h1>{predicted_label}</h1>
        </div>

        <div className="confidence-section">
          <div className="confidence-bar-container">
            <div className="confidence-label">
              <span>Confidence: {getConfidenceLabel(confidence)}</span>
              <span className="confidence-value">{(confidence * 100).toFixed(2)}%</span>
            </div>
            <div className="confidence-bar">
              <div 
                className="confidence-fill"
                style={{
                  width: `${confidence * 100}%`,
                  backgroundColor: getConfidenceColor(confidence)
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {top_predictions && top_predictions.length > 0 && (
        <div className="top-predictions">
          <h3>Top Predictions</h3>
          <div className="predictions-list">
            {top_predictions.map((pred, index) => (
              <div key={index} className="prediction-item">
                <div className="prediction-rank">#{index + 1}</div>
                <div className="prediction-content">
                  <div className="prediction-label">{pred.label}</div>
                  <div className="prediction-confidence">
                    {(pred.confidence * 100).toFixed(2)}%
                  </div>
                </div>
                <div className="prediction-bar">
                  <div 
                    className="prediction-bar-fill"
                    style={{
                      width: `${pred.confidence * 100}%`,
                      backgroundColor: getConfidenceColor(pred.confidence)
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Agent 2: SOP Retrieval Results */}
      {sop_retrieved && sop_content && (
        <div className="sop-section">
          <h3>📋 Standard Operating Procedure (Agent 2)</h3>
          <div className="sop-header">
            <span className="sop-badge">SOP Retrieved</span>
            {sop_score && (
              <span className="sop-score">Relevance: {(sop_score * 100).toFixed(1)}%</span>
            )}
          </div>
          <div className="sop-content">
            <pre>{sop_content}</pre>
          </div>
        </div>
      )}

      {/* Agent 3: Decision Results */}
      {decision && (
        <div className="decision-section">
          <h3>🧠 Operational Decision (Agent 3)</h3>
          <div className="decision-header">
            <span className={`escalation-badge ${decision.requires_escalation ? 'escalation-required' : 'no-escalation'}`}>
              {decision.requires_escalation ? '⚠️ Escalation Required' : '✅ No Escalation Needed'}
            </span>
            <span className="decision-confidence">
              LLM Confidence: {(decision.confidence * 100).toFixed(1)}%
            </span>
          </div>
          
          <div className="decision-content">
            <div className="decision-item">
              <label>📌 Recommended Action:</label>
              <p>{decision.recommended_action}</p>
            </div>
            
            <div className="decision-item">
              <label>🚚 Driver Instruction:</label>
              <p>{decision.driver_instruction}</p>
            </div>
            
            <div className="decision-item">
              <label>📧 Customer Message:</label>
              <p className="customer-message">{decision.customer_message}</p>
            </div>
            
            <div className="decision-item reasoning">
              <label>💭 Reasoning:</label>
              <p>{decision.reasoning_summary}</p>
            </div>
          </div>
        </div>
      )}

      {/* Agent 4: Action Execution Results */}
      {action && (
        <div className="action-section">
          <h3>⚡ Action Execution (Agent 4)</h3>
          <div className="action-content">
            <div className="action-items">
              <div className={`action-item ${action.sheet_updated ? 'success' : 'pending'}`}>
                <span className="action-icon">{action.sheet_updated ? '✅' : '⏳'}</span>
                <span className="action-label">Google Sheets Log</span>
                <span className="action-status">{action.sheet_updated ? 'Updated' : 'Pending'}</span>
              </div>
              
              <div className={`action-item ${action.email_simulated ? 'success' : 'skipped'}`}>
                <span className="action-icon">{action.email_simulated ? '📧' : '➖'}</span>
                <span className="action-label">Customer Notification</span>
                <span className="action-status">{action.email_simulated ? 'Sent (Simulated)' : 'Not Required'}</span>
              </div>
              
              <div className={`action-item ${action.escalated ? 'escalated' : 'normal'}`}>
                <span className="action-icon">{action.escalated ? '🚨' : '✅'}</span>
                <span className="action-label">Escalation Status</span>
                <span className="action-status">{action.escalated ? 'Escalated to Dispatcher' : 'Normal Processing'}</span>
              </div>
            </div>
            
            {action.timestamp && (
              <div className="action-timestamp">
                Processed at: {new Date(action.timestamp).toLocaleString()}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Agents Executed */}
      {agents_executed && agents_executed.length > 0 && (
        <div className="agents-executed">
          <h4>🤖 Agents Executed</h4>
          <div className="agents-list">
            {agents_executed.map((agent, index) => (
              <span key={index} className="agent-badge">
                {agent === 'agent1_classification' && '✅ Agent 1: Classification'}
                {agent === 'agent2_sop_retrieval' && '✅ Agent 2: SOP Retrieval'}
                {agent === 'agent3_decision' && '✅ Agent 3: Decision'}
                {agent === 'agent4_action' && '✅ Agent 4: Action'}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="results-footer">
        <button onClick={onReset} className="reset-button-large">
          Classify Another Exception
        </button>
      </div>
    </div>
  );
};

export default ResultsDisplay;
