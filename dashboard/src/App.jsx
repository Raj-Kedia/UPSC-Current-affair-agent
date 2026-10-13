import { useState, useEffect } from 'react';
import './index.css';

const API_BASE = 'http://localhost:8000/api';

export default function App() {
  // Auth state
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('upsc_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [token, setToken] = useState(() => localStorage.getItem('upsc_token') || '');

  // Navigation tab: 'sample' | 'subscription' | 'admin' | 'auth'
  const [activeTab, setActiveTab] = useState('sample');
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'

  // Auth form inputs
  const [authName, setAuthName] = useState('');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  // User subscription state
  const [subscription, setSubscription] = useState(null);
  const [requestEmail, setRequestEmail] = useState('');
  const [submittingRequest, setSubmittingRequest] = useState(false);
  const [requestFeedback, setRequestFeedback] = useState(null);

  // Sample newsletter data
  const [sampleData, setSampleData] = useState({ cards: [], html: '', week_label: 'Recent Week' });
  const [sampleLoading, setSampleLoading] = useState(true);
  const [sampleViewMode, setSampleViewMode] = useState('cards'); // 'cards' | 'email'
  const [selectedPaper, setSelectedPaper] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Admin panel state
  const [adminOverview, setAdminOverview] = useState(null);
  const [adminSubscriptions, setAdminSubscriptions] = useState([]);
  const [adminFilter, setAdminFilter] = useState('all'); // 'all' | 'pending' | 'active' | 'cancelled'
  const [adminActionLoading, setAdminActionLoading] = useState(false);
  const [dispatchingEmail, setDispatchingEmail] = useState(false);
  const [adminNotification, setAdminNotification] = useState(null);

  // Agent status state
  const [agentStatus, setAgentStatus] = useState({ is_running: false, status_message: 'Idle' });

  // Helper headers for API requests
  const getAuthHeaders = () => {
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
  };

  // Check current session & fetch profile
  const fetchUserProfile = async (authToken = token) => {
    if (!authToken) return;
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
        setSubscription(data.subscription);
        if (data.subscription?.email) {
          setRequestEmail(data.subscription.email);
        } else if (data.user?.email) {
          setRequestEmail(data.user.email);
        }
      } else if (res.status === 401) {
        handleLogout();
      }
    } catch (e) {
      console.error('Failed to fetch user profile:', e);
    }
  };

  // Fetch sample newsletter
  const fetchSampleNewsletter = async () => {
    setSampleLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sample-newsletter`);
      if (res.ok) {
        const data = await res.json();
        setSampleData(data);
      }
    } catch (e) {
      console.error('Failed to load sample newsletter:', e);
    } finally {
      setSampleLoading(false);
    }
  };

  // Fetch agent status
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      if (res.ok) {
        const json = await res.json();
        setAgentStatus(json);
      }
    } catch {
      setAgentStatus({ is_running: false, status_message: 'Offline' });
    }
  };

  // Fetch admin dashboard data
  const fetchAdminData = async () => {
    if (!token || user?.role !== 'admin') return;
    try {
      const [ovRes, subsRes] = await Promise.all([
        fetch(`${API_BASE}/admin/overview`, { headers: getAuthHeaders() }),
        fetch(`${API_BASE}/admin/subscriptions`, { headers: getAuthHeaders() })
      ]);
      if (ovRes.ok) {
        const ovData = await ovRes.json();
        setAdminOverview(ovData);
      }
      if (subsRes.ok) {
        const subsData = await subsRes.json();
        setAdminSubscriptions(subsData.subscriptions || []);
      }
    } catch (e) {
      console.error('Failed to fetch admin data:', e);
    }
  };

  // Initial load
  useEffect(() => {
    fetchSampleNewsletter();
    fetchStatus();
    if (token) {
      fetchUserProfile(token);
    }

    const interval = setInterval(() => {
      fetchStatus();
      if (user?.role === 'admin' && activeTab === 'admin') {
        fetchAdminData();
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [token, activeTab]);

  // When switching to admin tab, fetch data
  useEffect(() => {
    if (activeTab === 'admin' && user?.role === 'admin') {
      fetchAdminData();
    }
  }, [activeTab]);

  // Authentication Handlers
  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword })
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem('upsc_token', data.token);
        localStorage.setItem('upsc_user', JSON.stringify(data.user));
        setToken(data.token);
        setUser(data.user);
        setRequestEmail(data.user.email);
        fetchUserProfile(data.token);
        setActiveTab(data.user.role === 'admin' ? 'admin' : 'subscription');
      } else {
        setAuthError(data.detail || 'Login failed. Please check credentials.');
      }
    } catch {
      setAuthError('Connection error. Is backend server running on port 8000?');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: authName, email: authEmail, password: authPassword })
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem('upsc_token', data.token);
        localStorage.setItem('upsc_user', JSON.stringify(data.user));
        setToken(data.token);
        setUser(data.user);
        setRequestEmail(data.user.email);
        fetchUserProfile(data.token);
        setActiveTab('subscription');
      } else {
        setAuthError(data.detail || 'Registration failed.');
      }
    } catch {
      setAuthError('Connection error. Is backend server running on port 8000?');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      if (token) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: getAuthHeaders()
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      localStorage.removeItem('upsc_token');
      localStorage.removeItem('upsc_user');
      setToken('');
      setUser(null);
      setSubscription(null);
      setActiveTab('sample');
    }
  };

  // Fill quick demo credentials
  const fillDemoAdmin = () => {
    setAuthEmail('admin@upscagent.com');
    setAuthPassword('admin123');
    setAuthMode('login');
  };

  // User Weekly Newsletter Request
  const handleRequestWeeklyNewsletter = async (e) => {
    e.preventDefault();
    if (!token) {
      setActiveTab('auth');
      return;
    }
    if (!requestEmail || !requestEmail.includes('@')) {
      setRequestFeedback({ type: 'error', message: 'Please enter a valid email address.' });
      return;
    }

    setSubmittingRequest(true);
    setRequestFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/user/request-subscription`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ email: requestEmail })
      });
      const data = await res.json();
      if (res.ok) {
        setSubscription(data.subscription);
        setRequestFeedback({
          type: 'success',
          message: 'Weekly delivery requested! Your plan is now awaiting admin activation.'
        });
      } else {
        setRequestFeedback({ type: 'error', message: data.detail || 'Failed to submit request.' });
      }
    } catch {
      setRequestFeedback({ type: 'error', message: 'Error communicating with server.' });
    } finally {
      setSubmittingRequest(false);
    }
  };

  // Admin Actions
  const handleAdminAccept = async (subId) => {
    setAdminActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/subscriptions/${subId}/accept`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok) {
        setAdminNotification({ type: 'success', message: data.message });
        fetchAdminData();
      } else {
        setAdminNotification({ type: 'error', message: data.detail || 'Action failed.' });
      }
    } catch {
      setAdminNotification({ type: 'error', message: 'Network error.' });
    } finally {
      setAdminActionLoading(false);
    }
  };

  const handleAdminCancel = async (subId) => {
    if (!confirm('Are you sure you want to cancel/deactivate this user\'s weekly newsletter plan?')) return;
    setAdminActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/subscriptions/${subId}/cancel`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ notes: 'Cancelled from admin dashboard' })
      });
      const data = await res.json();
      if (res.ok) {
        setAdminNotification({ type: 'success', message: data.message });
        fetchAdminData();
      } else {
        setAdminNotification({ type: 'error', message: data.detail || 'Action failed.' });
      }
    } catch {
      setAdminNotification({ type: 'error', message: 'Network error.' });
    } finally {
      setAdminActionLoading(false);
    }
  };

  const handleAdminReactivate = async (subId) => {
    setAdminActionLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/subscriptions/${subId}/reactivate`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok) {
        setAdminNotification({ type: 'success', message: data.message });
        fetchAdminData();
      } else {
        setAdminNotification({ type: 'error', message: data.detail || 'Action failed.' });
      }
    } catch {
      setAdminNotification({ type: 'error', message: 'Network error.' });
    } finally {
      setAdminActionLoading(false);
    }
  };

  // Admin: Dispatch weekly newsletter
  const handleDispatchWeekly = async () => {
    if (!confirm('Dispatch this week\'s curated UPSC digest to all active subscribers?')) return;
    setDispatchingEmail(true);
    setAdminNotification(null);
    try {
      const res = await fetch(`${API_BASE}/admin/dispatch-weekly`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok) {
        setAdminNotification({
          type: 'success',
          message: `Dispatched weekly digest to ${data.dispatched_to_active_count} active subscriber(s)!`
        });
      } else {
        setAdminNotification({ type: 'error', message: data.detail || 'Failed to dispatch email.' });
      }
    } catch {
      setAdminNotification({ type: 'error', message: 'Failed to connect to email service.' });
    } finally {
      setDispatchingEmail(false);
    }
  };

  // Admin: Run AI Intelligence Agent
  const handleRunAgent = async () => {
    try {
      const res = await fetch(`${API_BASE}/run`, { method: 'POST', headers: getAuthHeaders() });
      if (res.ok) {
        setAgentStatus({ is_running: true, status_message: 'Initializing weekly news analysis...' });
        setAdminNotification({ type: 'success', message: 'Agent workflow triggered in background.' });
      }
    } catch {
      setAdminNotification({ type: 'error', message: 'Could not trigger agent.' });
    }
  };

  // Filter study cards
  const filteredCards = (sampleData.cards || []).filter(card => {
    const topic = (card.syllabus_topic || '').toUpperCase();
    const title = (card.title || '').toLowerCase();
    const context = (card.context || '').toLowerCase();
    const query = searchQuery.toLowerCase();

    const matchesPaper =
      selectedPaper === 'ALL' ||
      (selectedPaper === 'GS-I' && (topic.includes('GS-I') || topic.includes('GS PAPER I '))) ||
      (selectedPaper === 'GS-II' && (topic.includes('GS-II') || topic.includes('GS PAPER II'))) ||
      (selectedPaper === 'GS-III' && (topic.includes('GS-III') || topic.includes('GS PAPER III'))) ||
      (selectedPaper === 'GS-IV' && (topic.includes('GS-IV') || topic.includes('GS PAPER IV')));

    const matchesSearch = !query || title.includes(query) || context.includes(query);
    return matchesPaper && matchesSearch;
  });

  // Filter admin subscriptions
  const filteredAdminSubscriptions = adminSubscriptions.filter(sub => {
    if (adminFilter === 'all') return true;
    return sub.status === adminFilter;
  });

  return (
    <div className="app-container">
      {/* Navbar */}
      <header className="navbar">
        <div className="brand" onClick={() => setActiveTab(user ? 'subscription' : 'sample')}>
          <img src="/favicon.svg" alt="UPSC Digest Logo" className="brand-icon" />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="brand-text">UPSC Digest</span>
              <span className="brand-tag">Weekly Edition</span>
            </div>
          </div>
        </div>

        <nav className="nav-links">
          {/* Main Navigation tabs */}
          <button
            className={`nav-tab ${activeTab === 'sample' ? 'active' : ''}`}
            onClick={() => setActiveTab('sample')}
          >
            Sample Newsletter
          </button>

          {user && (
            <button
              className={`nav-tab ${activeTab === 'subscription' ? 'active' : ''}`}
              onClick={() => setActiveTab('subscription')}
            >
              My Weekly Plan
            </button>
          )}

          {user?.role === 'admin' && (
            <button
              className={`nav-tab ${activeTab === 'admin' ? 'active' : ''}`}
              onClick={() => setActiveTab('admin')}
            >
              Admin Panel
            </button>
          )}

          {/* User Profile or Sign-in button */}
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div className="user-badge">
                <span>{user.name.split(' ')[0]}</span>
                <span className={`role-pill ${user.role}`}>{user.role}</span>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={handleLogout}>
                Sign Out
              </button>
            </div>
          ) : (
            <button
              className={`btn btn-primary btn-sm ${activeTab === 'auth' ? 'active' : ''}`}
              onClick={() => setActiveTab('auth')}
            >
              Sign In / Register
            </button>
          )}
        </nav>
      </header>

      {/* VIEW 1: AUTHENTICATION (Login / Register) */}
      {activeTab === 'auth' && !user && (
        <div className="auth-wrapper">
          <div className="auth-card">
            <div className="auth-tabs">
              <button
                className={`auth-tab ${authMode === 'login' ? 'active' : ''}`}
                onClick={() => { setAuthMode('login'); setAuthError(''); }}
              >
                Sign In
              </button>
              <button
                className={`auth-tab ${authMode === 'register' ? 'active' : ''}`}
                onClick={() => { setAuthMode('register'); setAuthError(''); }}
              >
                Create Account
              </button>
            </div>

            {authError && (
              <div className="alert-banner alert-error">
                {authError}
              </div>
            )}

            <form onSubmit={authMode === 'login' ? handleLogin : handleRegister}>
              {authMode === 'register' && (
                <div className="form-group">
                  <label className="form-label">Full Name</label>
                  <input
                    type="text"
                    required
                    className="form-input"
                    placeholder="e.g. Priya Sharma"
                    value={authName}
                    onChange={(e) => setAuthName(e.target.value)}
                  />
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  required
                  className="form-input"
                  placeholder="aspirant@example.com"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  type="password"
                  required
                  className="form-input"
                  placeholder="••••••••"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '0.75rem' }}
                disabled={authLoading}
              >
                {authLoading ? (
                  <>
                    <span className="spinner"></span> Processing...
                  </>
                ) : (
                  authMode === 'login' ? 'Sign In to Dashboard' : 'Register Account'
                )}
              </button>
            </form>

            <div className="auth-notice">
              <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Demo Admin Credentials:</div>
              <div>Email: <code>admin@upscagent.com</code> | Password: <code>admin123</code></div>
              <button
                type="button"
                onClick={fillDemoAdmin}
                className="btn btn-secondary btn-sm"
                style={{ marginTop: '0.5rem', width: '100%' }}
              >
                Auto-Fill Admin Credentials
              </button>
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: USER SUBSCRIPTION & REQUEST MANAGEMENT */}
      {activeTab === 'subscription' && user && (
        <div>
          {/* Hero Banner: Plan Status */}
          <div className="subscription-hero">
            <div className="status-highlight-card">
              <div>
                <div className="status-title-row">
                  <span style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)' }}>
                    Weekly Newsletter Subscription
                  </span>
                  {subscription?.status === 'active' ? (
                    <span className="status-pill active">
                      <span className="status-dot"></span> Active Subscriber
                    </span>
                  ) : subscription?.status === 'pending' ? (
                    <span className="status-pill pending">
                      <span className="status-dot"></span> Pending Admin Approval
                    </span>
                  ) : subscription?.status === 'cancelled' ? (
                    <span className="status-pill cancelled">
                      <span className="status-dot"></span> Plan Cancelled / Inactive
                    </span>
                  ) : (
                    <span className="status-pill none">
                      <span className="status-dot"></span> Not Subscribed
                    </span>
                  )}
                </div>

                <h2 style={{ fontSize: '1.4rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                  {subscription?.status === 'active'
                    ? 'Your Weekly Digest is Active'
                    : subscription?.status === 'pending'
                    ? 'Activation Request Under Review'
                    : subscription?.status === 'cancelled'
                    ? 'Subscription Currently Inactive'
                    : 'Get Curated UPSC Notes Every Week'}
                </h2>

                <p className="status-info-text">
                  {subscription?.status === 'active' ? (
                    <>
                      You are subscribed to receive the <strong>Weekly Intelligence Digest</strong> directly at{' '}
                      <code>{subscription.email}</code>. Every Sunday morning, you receive curated GS syllabus mapping, Prelims pointers, and Mains PYQ synthesis.
                    </>
                  ) : subscription?.status === 'pending' ? (
                    <>
                      Your request to send the weekly newsletter to <code>{subscription.email}</code> has been submitted. An administrator will review and activate your plan shortly.
                    </>
                  ) : subscription?.status === 'cancelled' ? (
                    <>
                      Your weekly newsletter delivery was cancelled by the administrator. If this was unexpected or you wish to resume delivery, submit an updated request below.
                    </>
                  ) : (
                    <>
                      Instead of daily noise, receive a single, high-yield weekly digest summarizing the most critical UPSC current affairs, GS Mains dimensions, and semantic PYQ connections directly in your inbox.
                    </>
                  )}
                </p>
              </div>

              {subscription?.status === 'active' && (
                <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Delivery Frequency:</span>
                  <span className="brand-tag">Weekly (Every Sunday)</span>
                </div>
              )}
            </div>

            {/* Request Form Card */}
            <div className="card" style={{ margin: 0 }}>
              <div className="card-header">
                <div>
                  <h3 className="card-title">
                    {subscription ? 'Update or Request Delivery' : 'Request Weekly Newsletter'}
                  </h3>
                  <p className="card-description">
                    Provide the email address where you want to receive the digest.
                  </p>
                </div>
              </div>

              {requestFeedback && (
                <div className={`alert-banner ${requestFeedback.type === 'success' ? 'alert-success' : 'alert-error'}`}>
                  {requestFeedback.message}
                </div>
              )}

              <form onSubmit={handleRequestWeeklyNewsletter}>
                <div className="form-group">
                  <label className="form-label">Email ID for Weekly Dispatch</label>
                  <input
                    type="email"
                    required
                    className="form-input"
                    placeholder="your-email@example.com"
                    value={requestEmail}
                    onChange={(e) => setRequestEmail(e.target.value)}
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: '100%', marginTop: '0.5rem' }}
                  disabled={submittingRequest}
                >
                  {submittingRequest ? (
                    <>
                      <span className="spinner"></span> Submitting...
                    </>
                  ) : subscription?.status === 'pending' ? (
                    'Update Pending Request Email'
                  ) : subscription?.status === 'active' ? (
                    'Update Delivery Email'
                  ) : (
                    'Request Weekly Newsletter'
                  )}
                </button>
              </form>

              <div style={{ marginTop: '1.25rem', fontSize: '0.8rem', color: 'var(--text-dim)', lineHeight: 1.4 }}>
                💡 <em>Note: All activation requests are verified by our custom admin panel before dispatching. You can check a sample of what the newsletter looks like below.</em>
              </div>
            </div>
          </div>

          {/* Quick link to sample */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', padding: '1rem 1.25rem', background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Want to see what you will receive?</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Explore our sample weekly synthesis cards and full email format.</div>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => setActiveTab('sample')}>
              View Sample Newsletter &rarr;
            </button>
          </div>
        </div>
      )}

      {/* VIEW 3: SAMPLE WEEKLY NEWSLETTER (Available to all visitors / aspirants) */}
      {activeTab === 'sample' && (
        <div>
          {/* Header Strip */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                <h1 style={{ fontSize: '1.6rem', fontWeight: 700, margin: 0 }}>Sample Weekly Intelligence Digest</h1>
                <span className="brand-tag">Weekly Cadence</span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Coverage: <strong>{sampleData.week_label || 'Weekly Edition'}</strong> | {sampleData.total_cards || sampleData.cards?.length || 0} high-priority issues synthesized
              </p>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              {/* View Switcher: Cards vs Full Email */}
              <div className="pills-group" style={{ background: 'var(--bg-surface)', padding: '4px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <button
                  className={`btn btn-sm ${sampleViewMode === 'cards' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ border: 'none' }}
                  onClick={() => setSampleViewMode('cards')}
                >
                  Study Cards View
                </button>
                <button
                  className={`btn btn-sm ${sampleViewMode === 'email' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ border: 'none' }}
                  onClick={() => setSampleViewMode('email')}
                >
                  Email Newsletter Preview
                </button>
              </div>

              {!user && (
                <button className="btn btn-primary btn-sm" onClick={() => setActiveTab('auth')}>
                  Subscribe to Weekly Digest
                </button>
              )}
            </div>
          </div>

          {/* MODE A: STUDY CARDS */}
          {sampleViewMode === 'cards' && (
            <div>
              {/* Filter & Search Bar */}
              <div className="filter-bar">
                <div className="pills-group">
                  {['ALL', 'GS-I', 'GS-II', 'GS-III', 'GS-IV'].map(paper => (
                    <button
                      key={paper}
                      className={`filter-pill ${selectedPaper === paper ? 'active' : ''}`}
                      onClick={() => setSelectedPaper(paper)}
                    >
                      {paper === 'ALL' ? 'All Papers' : paper}
                    </button>
                  ))}
                </div>

                <input
                  type="text"
                  className="search-input"
                  placeholder="Filter cards by keyword..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              {sampleLoading ? (
                <div className="empty-box">
                  <div className="spinner" style={{ width: '24px', height: '24px', marginBottom: '1rem' }}></div>
                  <div>Loading sample weekly intelligence cards...</div>
                </div>
              ) : filteredCards.length > 0 ? (
                <div className="study-cards-grid">
                  {filteredCards.map((card, idx) => (
                    <div key={idx} className="study-card">
                      <div className="study-card-head">
                        <span className="paper-badge">
                          {card.syllabus_topic || 'GS General'}
                        </span>
                        <h3 className="study-card-title">{card.title}</h3>
                        <div className="study-card-meta">
                          Source: <strong style={{ color: 'var(--text-muted)' }}>{card.source || 'The Hindu / Indian Express'}</strong>
                          {card.date && ` • ${card.date}`}
                        </div>
                      </div>

                      <div className="study-card-body">
                        {/* Context */}
                        {card.context && (
                          <div className="study-card-section">
                            <div className="section-label">Context / Why in News?</div>
                            <div className="context-box">{card.context}</div>
                          </div>
                        )}

                        {/* Prelims Facts */}
                        {card.prelims_pointers?.length > 0 && (
                          <div className="study-card-section">
                            <div className="section-label" style={{ color: '#fbbf24' }}>
                              🎯 Key Prelims Pointers
                            </div>
                            <ul className="pointers-list">
                              {card.prelims_pointers.map((p, i) => (
                                <li key={i} className="pointer-item">
                                  📌 {p}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Mains Dimensions */}
                        {card.mains_concepts && (
                          <div className="study-card-section">
                            <div className="section-label" style={{ color: '#60a5fa' }}>
                              💡 Mains Dimensions
                            </div>
                            {card.mains_concepts.background && (
                              <div style={{ fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                                <strong>Background:</strong> {card.mains_concepts.background}
                              </div>
                            )}

                            {card.mains_concepts.significance?.length > 0 && (
                              <div style={{ marginBottom: '0.5rem' }}>
                                <div style={{ fontSize: '0.78rem', color: '#34d399', fontWeight: 600 }}>Key Arguments / Significance:</div>
                                <ul style={{ paddingLeft: '1.2rem', fontSize: '0.84rem', color: '#cbd5e1' }}>
                                  {card.mains_concepts.significance.map((s, si) => (
                                    <li key={si}>{s}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {card.mains_concepts.challenges?.length > 0 && (
                              <div style={{ marginBottom: '0.5rem' }}>
                                <div style={{ fontSize: '0.78rem', color: '#f87171', fontWeight: 600 }}>Challenges / Concerns:</div>
                                <ul style={{ paddingLeft: '1.2rem', fontSize: '0.84rem', color: '#cbd5e1' }}>
                                  {card.mains_concepts.challenges.map((c, ci) => (
                                    <li key={ci}>{c}</li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {card.mains_concepts.way_forward && (
                              <div style={{ fontSize: '0.85rem', color: '#a7f3d0', background: 'rgba(16, 185, 129, 0.08)', padding: '0.5rem 0.75rem', borderRadius: '4px' }}>
                                <strong>Way Forward:</strong> {card.mains_concepts.way_forward}
                              </div>
                            )}
                          </div>
                        )}

                        {/* PYQ Connection */}
                        {card.pyq_connection && (
                          <div className="study-card-section">
                            <div className="section-label" style={{ color: '#93c5fd' }}>
                              📚 Previous Years Questions (PYQ) Connection
                            </div>
                            <div className="pyq-box">{card.pyq_connection}</div>
                          </div>
                        )}
                      </div>

                      {card.link && (
                        <div className="study-card-foot">
                          <a href={card.link} target="_blank" rel="noreferrer" className="link-read">
                            Read Original Source &rarr;
                          </a>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-box card">
                  <div className="empty-icon">🔍</div>
                  <div>No cards match your filter or search criteria.</div>
                </div>
              )}
            </div>
          )}

          {/* MODE B: RENDERED EMAIL PREVIEW */}
          {sampleViewMode === 'email' && (
            <div>
              {sampleData.html ? (
                <div className="email-preview-wrapper">
                  <div dangerouslySetInnerHTML={{ __html: sampleData.html }} />
                </div>
              ) : (
                <div className="empty-box card">
                  <div>No rendered sample email available yet.</div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* VIEW 4: CUSTOM ADMIN PANEL (Only accessible to admin role) */}
      {activeTab === 'admin' && user?.role === 'admin' && (
        <div>
          {/* Notification Alert */}
          {adminNotification && (
            <div className={`alert-banner ${adminNotification.type === 'success' ? 'alert-success' : 'alert-error'}`}>
              <span>{adminNotification.message}</span>
              <button
                style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '1.1rem' }}
                onClick={() => setAdminNotification(null)}
              >
                &times;
              </button>
            </div>
          )}

          {/* Admin Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Custom Administration Panel</h1>
                <span className="role-pill admin">Administrator</span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                Manage weekly newsletter activation requests, active subscriber plans, and dispatches.
              </p>
            </div>

            {/* Quick Actions */}
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleRunAgent}
                disabled={agentStatus.is_running}
              >
                {agentStatus.is_running ? (
                  <>
                    <span className="spinner"></span> Agent Running...
                  </>
                ) : (
                  'Run Weekly News Agent'
                )}
              </button>

              <button
                className="btn btn-success btn-sm"
                onClick={handleDispatchWeekly}
                disabled={dispatchingEmail}
              >
                {dispatchingEmail ? (
                  <>
                    <span className="spinner"></span> Dispatching...
                  </>
                ) : (
                  `Dispatch Weekly Digest (${adminOverview?.active_subscribers || 0} Active)`
                )}
              </button>
            </div>
          </div>

          {/* KPI Summary Cards */}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Pending Requests</div>
              <div className="kpi-value" style={{ color: 'var(--warning-text)' }}>
                {adminOverview?.pending_requests ?? 0}
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-label">Active Subscribers</div>
              <div className="kpi-value" style={{ color: 'var(--success-text)' }}>
                {adminOverview?.active_subscribers ?? 0}
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-label">Cancelled Plans</div>
              <div className="kpi-value" style={{ color: 'var(--danger-text)' }}>
                {adminOverview?.cancelled_subscribers ?? 0}
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-label">Total Users</div>
              <div className="kpi-value">
                {adminOverview?.total_users ?? 0}
              </div>
            </div>
          </div>

          {/* Subscriptions Table Card */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">User Weekly Newsletter Requests & Plans</h3>
                <p className="card-description">
                  Accept incoming requests to activate weekly newsletter delivery, or cancel existing plans.
                </p>
              </div>

              {/* Filter Tabs */}
              <div className="pills-group">
                <button
                  className={`filter-pill ${adminFilter === 'all' ? 'active' : ''}`}
                  onClick={() => setAdminFilter('all')}
                >
                  All ({adminSubscriptions.length})
                </button>
                <button
                  className={`filter-pill ${adminFilter === 'pending' ? 'active' : ''}`}
                  onClick={() => setAdminFilter('pending')}
                >
                  Pending ({adminSubscriptions.filter(s => s.status === 'pending').length})
                </button>
                <button
                  className={`filter-pill ${adminFilter === 'active' ? 'active' : ''}`}
                  onClick={() => setAdminFilter('active')}
                >
                  Active ({adminSubscriptions.filter(s => s.status === 'active').length})
                </button>
                <button
                  className={`filter-pill ${adminFilter === 'cancelled' ? 'active' : ''}`}
                  onClick={() => setAdminFilter('cancelled')}
                >
                  Cancelled ({adminSubscriptions.filter(s => s.status === 'cancelled').length})
                </button>
              </div>
            </div>

            <div className="table-container">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Aspirant Name</th>
                    <th>Delivery Email ID</th>
                    <th>Cadence</th>
                    <th>Status</th>
                    <th>Requested At</th>
                    <th style={{ textAlign: 'right' }}>Admin Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAdminSubscriptions.length > 0 ? (
                    filteredAdminSubscriptions.map((sub) => (
                      <tr key={sub.id}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{sub.user_name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{sub.user_account_email}</div>
                        </td>
                        <td>
                          <code style={{ fontSize: '0.85rem', color: '#93c5fd' }}>{sub.email}</code>
                        </td>
                        <td>
                          <span className="brand-tag">Weekly</span>
                        </td>
                        <td>
                          {sub.status === 'active' ? (
                            <span className="status-pill active">
                              <span className="status-dot"></span> Active
                            </span>
                          ) : sub.status === 'pending' ? (
                            <span className="status-pill pending">
                              <span className="status-dot"></span> Pending Approval
                            </span>
                          ) : (
                            <span className="status-pill cancelled">
                              <span className="status-dot"></span> Cancelled
                            </span>
                          )}
                        </td>
                        <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {sub.requested_at ? new Date(sub.requested_at).toLocaleDateString() : 'N/A'}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: '0.5rem' }}>
                            {sub.status === 'pending' && (
                              <>
                                <button
                                  className="btn btn-success btn-sm"
                                  onClick={() => handleAdminAccept(sub.id)}
                                  disabled={adminActionLoading}
                                >
                                  Accept & Activate
                                </button>
                                <button
                                  className="btn btn-danger-outline btn-sm"
                                  onClick={() => handleAdminCancel(sub.id)}
                                  disabled={adminActionLoading}
                                >
                                  Decline
                                </button>
                              </>
                            )}

                            {sub.status === 'active' && (
                              <button
                                className="btn btn-danger-outline btn-sm"
                                onClick={() => handleAdminCancel(sub.id)}
                                disabled={adminActionLoading}
                              >
                                Cancel Plan
                              </button>
                            )}

                            {sub.status === 'cancelled' && (
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleAdminReactivate(sub.id)}
                                disabled={adminActionLoading}
                              >
                                Reactivate Plan
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-dim)' }}>
                        No subscription requests found under this filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
