import React, { useEffect, useState } from 'react';
import './HealthStatus.css';

const API_BASE = 'http://127.0.0.1:8000/api';

function HealthStatus() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then(res => {
        if (!res.ok) throw new Error('Network response was not ok');
        return res.json();
      })
      .then(data => setStatus(data.status))
      .catch(err => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="health-banner error">
        <span>API Health: Error</span>
        <span className="tooltip">{error}</span>
      </div>
    );
  }
  if (status === null) {
    return (
      <div className="health-banner loading">
        Checking API health...
      </div>
    );
  }
  return (
    <div className="health-banner success">
      <span>API Health: OK</span>
    </div>
  );
}

export default HealthStatus;
