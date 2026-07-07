import { useState, useEffect } from 'react';
import './index.css';

const API_BASE = 'http://localhost:8000/api';

function App() {
  const [status, setStatus] = useState({ is_running: false, status_message: 'Checking status...' });
  const [data, setData] = useState({ cards: [], html: '' });
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);
  const [approvalMessage, setApprovalMessage] = useState('');

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      const json = await res.json();
      setStatus(json);
      return json.is_running;
    } catch (e) {
      setStatus({ is_running: false, status_message: 'API Offline' });
      return false;
    }
  };

  const fetchData = async () => {
    try {
      const res = await fetch(`${API_BASE}/latest-cards`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchData();
    
    // Poll status every 3 seconds if running
    const interval = setInterval(async () => {
      const isRunning = await fetchStatus();
      if (!isRunning) {
        // If it just stopped running, fetch new data
        fetchData();
      }
    }, 3000);
    
    return () => clearInterval(interval);
  }, []);

  const handleRun = async () => {
    try {
      await fetch(`${API_BASE}/run`, { method: 'POST' });
      setStatus({ is_running: true, status_message: 'Initializing...' });
    } catch (e) {
      alert('Failed to trigger run');
    }
  };

  const handleApprove = async () => {
    if (!data.html) return;
    setApproving(true);
    setApprovalMessage('');
    try {
      const res = await fetch(`${API_BASE}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html_content: data.html })
      });
      if (res.ok) {
        setApprovalMessage('Newsletter successfully sent!');
      } else {
        setApprovalMessage('Failed to send email.');
      }
    } catch (e) {
      setApprovalMessage('Error connecting to API.');
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="container">
      <header className="header">
        <div>
          <h1>UPSC Intelligence System</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Automated Agentic News Curation & Analysis</p>
        </div>
        
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div className={`status-badge ${status.is_running ? 'running' : 'idle'}`}>
            {status.is_running && <div className="spinner" style={{ width: '12px', height: '12px', borderWidth: '2px' }}></div>}
            {status.status_message}
          </div>
          
          <button 
            className="btn btn-primary" 
            onClick={handleRun} 
            disabled={status.is_running}
          >
            {status.is_running ? 'Agent Running...' : 'Run Agents Now'}
          </button>
        </div>
      </header>

      <div className="dashboard-grid">
        {/* Left Column: Today's Cards */}
        <div className="card">
          <h2 className="card-title">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            Generated Study Cards
          </h2>
          
          {loading ? (
            <div className="empty-state">Loading cards...</div>
          ) : data.cards.length > 0 ? (
            <div className="article-list">
              {data.cards.map((card, idx) => (
                <div key={idx} className="article-item">
                  <h4>{card.title}</h4>
                  <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem', color: '#cbd5e1' }}>{card.syllabus_topic}</p>
                  
                  <div className="article-meta">
                    <span>Score: {card._evaluation_score || 'N/A'}</span>
                    <span>{card.source}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <svg style={{ margin: '0 auto 1rem', opacity: 0.5 }} width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
              No cards generated for today yet. Run the agent to fetch news.
            </div>
          )}
        </div>

        {/* Right Column: Email Preview */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 className="card-title" style={{ margin: 0 }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
              Newsletter Preview
            </h2>
            
            <button 
              className="btn btn-success" 
              onClick={handleApprove}
              disabled={!data.html || status.is_running || approving}
            >
              {approving ? 'Sending...' : 'Approve & Send'}
            </button>
          </div>
          
          {approvalMessage && (
            <div style={{ padding: '0.75rem', marginBottom: '1rem', borderRadius: '0.5rem', backgroundColor: approvalMessage.includes('success') ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)', color: approvalMessage.includes('success') ? '#34d399' : '#f87171' }}>
              {approvalMessage}
            </div>
          )}

          {data.html ? (
            <div className="email-preview" dangerouslySetInnerHTML={{ __html: data.html }} />
          ) : (
            <div className="empty-state">
              Preview will appear here after the agent completes a run.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
