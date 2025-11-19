import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';

const INGEST_API = process.env.REACT_APP_INGEST_API || 'http://localhost:8000';
const SERVE_API = process.env.REACT_APP_SERVE_API || 'http://localhost:8001';

function App() {
  const [userId, setUserId] = useState('user_001');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState([]);
  const [items] = useState([
    { id: 'item_001', title: 'Laptop Computer', category: 'electronics' },
    { id: 'item_002', title: 'Running Shoes', category: 'sports' },
    { id: 'item_003', title: 'Coffee Maker', category: 'home' },
    { id: 'item_004', title: 'Novel Book', category: 'books' },
    { id: 'item_005', title: 'Wireless Headphones', category: 'electronics' },
  ]);

  // Generate event when user views/clicks an item
  const handleItemInteraction = async (itemId, eventType) => {
    try {
      const event = {
        user_id: userId,
        item_id: itemId,
        event_type: eventType,
        timestamp: new Date().toISOString(),
        properties: {
          page: 'home',
          session_id: `session_${Date.now()}`,
        },
      };

      await axios.post(`${INGEST_API}/events`, event);
      
      setEvents(prev => [...prev, { ...event, timestamp: new Date() }]);
      
      // Refresh recommendations after event
      setTimeout(() => {
        fetchRecommendations();
      }, 2000); // Wait 2s for processing
    } catch (error) {
      console.error('Error sending event:', error);
      alert('Failed to send event. Make sure the ingestion service is running.');
    }
  };

  // Fetch recommendations
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

  // Load recommendations on mount and when userId changes
  useEffect(() => {
    fetchRecommendations();
  }, [userId]);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Recommendation System Demo</h1>
        <div className="user-selector">
          <label>
            User ID:
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Enter user ID"
            />
          </label>
          <button onClick={fetchRecommendations} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh Recommendations'}
          </button>
        </div>
      </header>

      <main className="App-main">
        <section className="items-section">
          <h2>Browse Items</h2>
          <p>Click on items to generate events and see recommendations update</p>
          <div className="items-grid">
            {items.map(item => (
              <div key={item.id} className="item-card">
                <h3>{item.title}</h3>
                <p className="category">{item.category}</p>
                <div className="item-actions">
                  <button onClick={() => handleItemInteraction(item.id, 'view')}>
                    View
                  </button>
                  <button onClick={() => handleItemInteraction(item.id, 'click')}>
                    Click
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="recommendations-section">
          <h2>Recommendations</h2>
          {loading ? (
            <p>Loading recommendations...</p>
          ) : recommendations.length > 0 ? (
            <div className="recommendations-list">
              {recommendations.map((rec, index) => (
                <div key={index} className="recommendation-item">
                  <span className="item-id">{rec.item_id}</span>
                  <span className="score">Score: {rec.score?.toFixed(4) || 'N/A'}</span>
                </div>
              ))}
            </div>
          ) : (
            <p>No recommendations available. Try interacting with items first.</p>
          )}
        </section>

        <section className="events-section">
          <h2>Recent Events</h2>
          <div className="events-list">
            {events.slice(-10).reverse().map((event, index) => (
              <div key={index} className="event-item">
                <span className="event-type">{event.event_type}</span>
                <span className="event-item-id">{event.item_id}</span>
                <span className="event-time">
                  {event.timestamp.toLocaleTimeString()}
                </span>
              </div>
            ))}
            {events.length === 0 && <p>No events yet. Interact with items to generate events.</p>}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;

