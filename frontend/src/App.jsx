import React, { useState } from 'react';
import './App.css';
import WhiteLightPanel from './WhiteLightPanel';
import OptionsJournal from './OptionsJournal';
import HealthStatus from './HealthStatus';

export default function App() {
  const [activeTab, setActiveTab] = useState('pipeline');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#0B0D0F', color: '#E8E6E1', fontFamily: 'Inter, sans-serif' }}>
      {/* Banner */}
      <div style={{ borderBottom: '1px solid #24282D' }}>
        <HealthStatus />
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar */}
        <div style={{ width: '220px', borderRight: '1px solid #24282D', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px', backgroundColor: '#14171A' }}>
          <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.12em', color: '#7D848D', marginBottom: '16px' }}>Navigation</div>
          
          <button 
            onClick={() => setActiveTab('pipeline')}
            style={{ padding: '8px 12px', textAlign: 'left', backgroundColor: activeTab === 'pipeline' ? '#24282D' : 'transparent', color: activeTab === 'pipeline' ? '#FFB000' : '#E8E6E1', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            Pipeline
          </button>
        </div>

        {/* Main Content */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {activeTab === 'pipeline' && <WhiteLightPanel />}
        </div>
      </div>
    </div>
  );
}
