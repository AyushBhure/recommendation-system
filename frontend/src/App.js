import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';

const INGEST_API = process.env.REACT_APP_INGEST_API || 'http://localhost:8000';
const SERVE_API = process.env.REACT_APP_SERVE_API || 'http://localhost:8001';

const SAMPLE_ITEMS = [
  { id: 'item_001', title: 'Laptop Computer', category: 'electronics' },
  { id: 'item_002', title: 'Running Shoes', category: 'sports' },
  { id: 'item_003', title: 'Coffee Maker', category: 'home' },
  { id: 'item_004', title: 'Novel Book', category: 'books' },
  { id: 'item_005', title: 'Wireless Headphones', category: 'electronics' },
];

function App() {
  const [userId, setUserId] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState([]);

  const handleItemInteraction = async (itemId, eventType) => {
    try {
      const event = {
        user_id: userId,
        item_id: itemId,
        event_type: eventType,
        timestamp: new Date().toISOString(),
        properties: {
          page: 'simple-ui',
          session_id: `session_${Date.now()}`,
        },
      };

      await axios.post(`${INGEST_API}/events`, event);
      setEvents((prev) => [...prev, { ...event, timestamp: new Date() }]);

      setTimeout(() => fetchRecommendations(), 1500);
    } catch (error) {
      console.error('Error sending event:', error);
      alert('Failed to send event. Make sure the ingestion service is running.');
    }
  };

  const fetchRecommendations = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${SERVE_API}/recommend`, {
        params: {
          user_id: userId,
          k: 10,
        },
      });

      setRecommendations(response.data.recommendations || []);
    } catch (error) {
      console.error('Error fetching recommendations:', error);
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, [userId]);

  return (
    <div className="App">
      <div className="notice-banner">
        Note: Features require backend services (ingest and serve) to be running on localhost:8000 and localhost:8001
      </div>
      <header className="app-header">
        <div className="header-content">
          <div className="header-title">
            <h1>Recommendation System</h1>
            <p className="lead">Interactive demo for testing recommendation engine</p>
          </div>
        </div>
      </header>

      <main className="app-main">
        <section className="control-section">
          <div className="control-card">
            <div className="control-group">
              <div className="input-group">
                <label htmlFor="userId">User ID</label>
                <input
                  id="userId"
                  type="text"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Enter your user ID"
                  className="modern-input"
                />
              </div>
              <button
                className="btn-primary"
                onClick={fetchRecommendations}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="btn-spinner"></span>
                    Refreshing...
                  </>
                ) : (
                  'Refresh'
                )}
              </button>
            </div>
          </div>
        </section>

        <section className="content-grid">
          <div className="content-card">
            <div className="card-header">
              <h2>Sample Items</h2>
              <p className="card-subtitle">Click to send view events</p>
            </div>
            <div className="items-grid">
              {SAMPLE_ITEMS.map((item) => (
                <div key={item.id} className="item-card">
                  <div className="item-content">
                    <h3 className="item-title">{item.title}</h3>
                    <span className="item-badge">{item.category}</span>
                  </div>
                  <button
                    className="btn-secondary"
                    onClick={() => handleItemInteraction(item.id, 'view')}
                  >
                    Send View Event
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="content-card">
            <div className="card-header">
              <h2>Recommendations</h2>
              <p className="card-subtitle">Personalized suggestions based on your activity</p>
            </div>
            {loading ? (
              <div className="loading-state">
                <div className="spinner"></div>
                <p className="muted">Loading recommendations…</p>
              </div>
            ) : recommendations.length === 0 ? (
              <div className="empty-state">
                <p className="muted">No recommendations yet. Send a quick event above.</p>
              </div>
            ) : (
              <div className="recommendations-list">
                {recommendations.map((rec, index) => (
                  <div key={`${rec.item_id}-${index}`} className="recommendation-item">
                    <div className="rec-rank">#{index + 1}</div>
                    <div className="rec-content">
                      <div className="rec-item-id">{rec.item_id}</div>
                      <div className="rec-score">
                        Score: <span className="score-value">{rec.score ? rec.score.toFixed(4) : 'n/a'}</span>
                      </div>
                    </div>
                    <div className="rec-badge">Top {index < 3 ? 'Pick' : 'Choice'}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="content-card">
            <div className="card-header">
              <h2>Recent Activity</h2>
              <p className="card-subtitle">Your latest interactions</p>
            </div>
            {events.length === 0 ? (
              <div className="empty-state">
                <p className="muted">Events will appear here as you interact.</p>
              </div>
            ) : (
              <div className="events-timeline">
                {events
                  .slice(-6)
                  .reverse()
                  .map((event, index) => (
                    <div key={`${event.item_id}-${event.timestamp}-${index}`} className="event-item">
                      <div className="event-icon">
                        {event.event_type === 'view' ? 'V' : 'E'}
                      </div>
                      <div className="event-content">
                        <div className="event-type">{event.event_type}</div>
                        <div className="event-item-id">{event.item_id}</div>
                      </div>
                      <div className="event-time">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;