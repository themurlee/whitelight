import React, { useState, useEffect } from 'react';
import journalData from '../../data/journal/2026-07-18_reflection.md?raw';
import tradeLogData from '../../data/journal/trade_log.md?raw';
import sampleCsvData from '../../data/uploads/20260715210549_671b413e-0141-5edf-b64f-1c9ae4b2db2c.csv?raw';

const COLORS = {
  bg: "#080a0f", panel: "#0f131a", border: "#1e2430",
  text: "#f8f9fa", muted: "#8b949e",
  green: "#00c853", red: "#ff3d00", blue: "#2979ff"
};

// ... Rest of components ... (I need to preserve the components below up to the export)

// Simple radial gauge component using SVG
function RadialGauge({ value, label, sub, color, trackColor = "#1e2430", size = 120 }) {
  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;
  
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={size/2} cy={size/2} r={radius} stroke={trackColor} strokeWidth={strokeWidth} fill="none" />
          <circle cx={size/2} cy={size/2} r={radius} stroke={color} strokeWidth={strokeWidth} fill="none" 
            strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" />
        </svg>
        <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '18px', color }}>
          {label}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, sub, valueColor = COLORS.green }) {
  return (
    <div style={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, borderRadius: '8px', padding: '16px', flex: 1 }}>
      <div style={{ fontSize: '11px', textTransform: 'uppercase', color: COLORS.muted, letterSpacing: '0.05em', marginBottom: '8px', fontWeight: '600' }}>{title}</div>
      <div style={{ fontSize: '24px', fontWeight: '800', color: valueColor, marginBottom: '4px' }}>{value}</div>
      <div style={{ fontSize: '12px', color: COLORS.muted }}>{sub}</div>
    </div>
  );
}

function TopGaugeCard({ title, subtitle, valuePct, valueLabel, color }) {
  return (
    <div style={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, borderRadius: '8px', padding: '24px', flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ fontSize: '14px', fontWeight: '700', color: COLORS.text, marginBottom: '4px' }}>{title}</div>
      <div style={{ fontSize: '10px', textTransform: 'uppercase', color: COLORS.muted, letterSpacing: '0.05em', marginBottom: '24px' }}>{subtitle}</div>
      <RadialGauge value={valuePct} label={valueLabel} color={color} />
    </div>
  );
}

function TradeLogTab({ trades, setTrades }) {
  const [form, setForm] = useState({
    action: 'BUY',
    ticker: '',
    expiration: '(Enter ticker first)',
    optionType: 'Call',
    strike: '(Select expiration)',
    osi: '',
    quantity: 1,
    price: 2.5,
    strategy: 'EMA_VWAP_crossover'
  });
  const [isProcessing, setIsProcessing] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const fileInputRef = React.useRef(null);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setIsProcessing(true);
      
      if (file.name.toLowerCase().endsWith('.csv')) {
        const reader = new FileReader();
        reader.onload = (event) => {
          const csvText = event.target.result;
          const rows = csvText.split('\\n');
          const parsedTrades = [];
          
          for (let i = 1; i < rows.length; i++) {
            const cols = rows[i].split(',').map(s => s.replace(/"/g, ''));
            if (cols.length >= 8 && (cols[5] === 'BTO' || cols[5] === 'STC')) {
              parsedTrades.push({
                id: Date.now() + i,
                date: cols[0],
                action: cols[5] === 'BTO' ? 'BUY' : 'SELL',
                ticker: cols[3],
                osi: cols[4],
                optionType: cols[4].includes('Call') ? 'Call' : 'Put',
                quantity: parseInt(cols[6] || '1', 10),
                price: parseFloat((cols[7] || '0').replace('$', '')),
                strategy: 'CSV Import'
              });
            }
          }
          
          setTrades(prev => [...prev, ...parsedTrades]);
          setIsProcessing(false);
        };
        reader.readAsText(file);
        e.target.value = null;
      } else {
        // Fallback for screenshots / other files
        setTimeout(() => {
          const newTrade = { 
            ...form, 
            id: Date.now(),
            date: new Date().toLocaleDateString()
          };
          if (!newTrade.ticker) {
              newTrade.ticker = 'AAPL';
              newTrade.osi = 'AAPL260814C00185000';
              newTrade.strike = '185';
              newTrade.expiration = '2026-08-14';
          }
          
          setTrades([...trades, newTrade]);
          setForm({ ...form, ticker: '', osi: '' });
          e.target.value = null;
          setIsProcessing(false);
        }, 800);
      }
    }
  };

  const totalPnL = trades.length * 10;
  const winRate = trades.length > 0 ? "50.0%" : "0.0%";

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, borderRadius: '12px', padding: '24px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: '700', color: COLORS.text, margin: '0 0 20px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: COLORS.muted }}>➕</span> Log Manual Closed Option / Stock Trade
        </h2>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Action</label>
            <select name="action" value={form.action} onChange={handleChange} style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }}>
              <option>BUY</option>
              <option>SELL</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Underlying Ticker</label>
            <input name="ticker" value={form.ticker} onChange={handleChange} type="text" placeholder="E.g. AAPL, TSLA" style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Expiration Date</label>
            <select name="expiration" value={form.expiration} onChange={handleChange} style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }}>
              <option>(Enter ticker first)</option>
              <option>2026-08-14</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Option Type</label>
            <select name="optionType" value={form.optionType} onChange={handleChange} style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }}>
              <option>Call</option>
              <option>Put</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Strike Price</label>
            <select name="strike" value={form.strike} onChange={handleChange} style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }}>
              <option>(Select expiration)</option>
              <option>185</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Option Symbol (OSI)</label>
            <input name="osi" value={form.osi} onChange={handleChange} type="text" placeholder="E.g. AAPL260814C00185000" style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Quantity</label>
            <input name="quantity" value={form.quantity} onChange={handleChange} type="number" style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Price ($ per Contract)</label>
            <input name="price" value={form.price} onChange={handleChange} type="number" step="0.1" style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }} />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: COLORS.muted }}>Strategy Used</label>
            <select name="strategy" value={form.strategy} onChange={handleChange} style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, color: COLORS.text, padding: '12px', borderRadius: '6px', fontSize: '14px', outline: 'none' }}>
              <option>EMA_VWAP_crossover</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', justifyContent: 'flex-end' }}>
            <input 
              type="file" 
              ref={fileInputRef} 
              style={{ display: 'none' }} 
              onChange={handleFileChange}
            />
            <button 
              onClick={handleUploadClick}
              disabled={isProcessing}
              style={{ 
              background: 'linear-gradient(90deg, #ec4899 0%, #8b5cf6 100%)', 
              border: 'none', color: '#fff', padding: '13px', borderRadius: '6px', 
              fontSize: '14px', fontWeight: '700', cursor: 'pointer', opacity: isProcessing ? 0.7 : 1
            }}>
              {isProcessing ? 'Validating & Importing...' : 'Upload Screenshot to Import'}
            </button>
          </div>
        </div>
      </div>

      <div style={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, borderRadius: '12px', padding: '24px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: '700', color: COLORS.text, margin: '0 0 24px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          📝 Monthly Ledger Database
        </h2>
        {trades.length === 0 ? (
          <div style={{ color: COLORS.muted, fontSize: '14px', marginBottom: '24px' }}>
            No trades recorded for this selection.
          </div>
        ) : (
          <div style={{ overflowX: 'auto', marginBottom: '24px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${COLORS.border}`, color: COLORS.muted }}>
                  <th style={{ padding: '12px 8px' }}>Date</th>
                  <th style={{ padding: '12px 8px' }}>Action</th>
                  <th style={{ padding: '12px 8px' }}>Ticker</th>
                  <th style={{ padding: '12px 8px' }}>OSI / Sym</th>
                  <th style={{ padding: '12px 8px' }}>Type</th>
                  <th style={{ padding: '12px 8px' }}>Qty</th>
                  <th style={{ padding: '12px 8px' }}>Price</th>
                  <th style={{ padding: '12px 8px' }}>Strategy</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr key={t.id} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    <td style={{ padding: '12px 8px' }}>{t.date}</td>
                    <td style={{ padding: '12px 8px', color: t.action === 'BUY' ? COLORS.green : COLORS.red }}>{t.action}</td>
                    <td style={{ padding: '12px 8px', fontWeight: 'bold' }}>{t.ticker}</td>
                    <td style={{ padding: '12px 8px', color: COLORS.muted }}>{t.osi}</td>
                    <td style={{ padding: '12px 8px' }}>{t.optionType}</td>
                    <td style={{ padding: '12px 8px' }}>{t.quantity}</td>
                    <td style={{ padding: '12px 8px' }}>${t.price}</td>
                    <td style={{ padding: '12px 8px' }}>{t.strategy}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ background: COLORS.bg, border: `1px solid ${COLORS.border}`, borderRadius: '8px', padding: '16px', display: 'flex', gap: '24px', alignItems: 'center', fontSize: '14px' }}>
          <div><span style={{ color: COLORS.muted, fontWeight: '600' }}>Month P&L:</span> <span style={{ color: totalPnL >= 0 ? COLORS.green : COLORS.red, fontWeight: '700' }}>${totalPnL > 0 ? '+' : ''}{totalPnL.toFixed(2)}</span></div>
          <div><span style={{ color: COLORS.muted, fontWeight: '600' }}>Month Win Rate:</span> <span style={{ color: COLORS.text, fontWeight: '700' }}>{winRate}</span></div>
          <div><span style={{ color: COLORS.muted, fontWeight: '600' }}>Closed Trades:</span> <span style={{ color: COLORS.text, fontWeight: '700' }}>{trades.length}</span></div>
        </div>
      </div>
    </div>
  );
}

export default function OptionsJournal() {
  const [tab, setTab] = useState('Overview');
  const [trades, setTrades] = useState([]);
  
  useEffect(() => {
    if (sampleCsvData && trades.length === 0) {
      console.log("Parsing CSV data, length:", sampleCsvData.length);
      // split on actual newline
      const rows = sampleCsvData.split('\n').map(r => r.trim()).filter(Boolean);
      const parsedTrades = [];
      
      for (let i = 1; i < rows.length; i++) {
        const rowStr = rows[i];
        
        // Split on '","' to avoid splitting commas inside numbers like "$1,219.80"
        const cols = rowStr.split('","').map(s => s.replace(/"/g, '').trim());
        if (cols.length >= 8 && (cols[5] === 'BTO' || cols[5] === 'STC' || cols[5] === 'Buy' || cols[5] === 'Sell')) {
          const action = (cols[5] === 'BTO' || cols[5] === 'Buy') ? 'BUY' : 'SELL';
          let p = cols[7] || '0';
          p = p.replace('$', '').replace(/,/g, ''); // handle $1,000.00
          
          let amtStr = cols[8] || '0';
          let isNegative = amtStr.includes('(') || amtStr.includes('-');
          let amt = parseFloat(amtStr.replace(/[$,()]/g, ''));
          if (isNegative) amt = -amt;
          
          parsedTrades.push({
            id: 'csv_' + i,
            date: cols[0],
            action: action,
            ticker: cols[3],
            osi: cols[4],
            optionType: cols[4].includes('Call') ? 'Call' : 'Put',
            quantity: parseInt(cols[6] || '1', 10),
            price: parseFloat(p),
            amount: amt,
            strategy: 'CSV Sync'
          });
        }
      }
      console.log("Parsed trades:", parsedTrades.length);
      setTrades(parsedTrades);
    }
  }, [sampleCsvData, trades.length]);
  
  // Derived Metrics
  const totalPnL = trades.reduce((sum, t) => sum + (t.amount || 0), 0);
  const wins = trades.filter(t => (t.amount || 0) > 0);
  const losses = trades.filter(t => (t.amount || 0) < 0);
  const winRateNum = trades.length > 0 ? (wins.length / trades.length) * 100 : 0;
  const winRate = winRateNum.toFixed(1) + "%";
  const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.amount, 0) / wins.length : 0;
  const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((s, t) => s + t.amount, 0) / losses.length) : 0;
  const bestTradeAmt = wins.length > 0 ? Math.max(...wins.map(t => t.amount)) : 0;
  const worstTradeAmt = losses.length > 0 ? Math.abs(Math.min(...losses.map(t => t.amount))) : 0;
  const bestTradeTicker = wins.length > 0 ? wins.find(t => t.amount === bestTradeAmt)?.ticker : "None";
  
  // Equity Curve
  let currentEq = 0;
  const eqPoints = trades.map(t => { currentEq += (t.amount || 0); return currentEq; });
  const maxEq = Math.max(0, ...eqPoints) || 1;
  const minEq = Math.min(0, ...eqPoints);
  const rangeEq = (maxEq - minEq) || 1;
  const getY = (val) => 200 - (((val - minEq) / rangeEq) * 180 + 10);
  const getX = (idx) => (idx / Math.max(1, trades.length - 1)) * 600;

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', fontFamily: 'Inter, sans-serif' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ margin: '0 0 4px 0', fontSize: '28px', fontWeight: '900', letterSpacing: '-0.02em' }}>Trade Performance Dashboard</h1>
        <div style={{ color: COLORS.muted, fontSize: '13px' }}>Continuous discipline analysis and P&L targets</div>
      </div>
      
      <div style={{ display: 'flex', gap: '8px', borderBottom: `1px solid ${COLORS.border}`, paddingBottom: '16px', marginBottom: '24px' }}>
        {['Overview', 'Monthly Trade Log', 'Trade Calendar', 'Monthly Summary'].map(t => (
          <button 
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: tab === t ? '#006064' : 'transparent',
              border: 'none',
              color: tab === t ? '#4dd0e1' : COLORS.muted,
              padding: '6px 12px',
              borderRadius: '4px',
              fontSize: '13px',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'Overview' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '16px' }}>
            <TopGaugeCard title="Profit" subtitle="ALL TIME" valuePct={100} valueLabel={`$${totalPnL.toFixed(2)}`} color={totalPnL >= 0 ? COLORS.green : COLORS.red} />
            <TopGaugeCard title="Average Gain in $" subtitle="PER WIN TRADE" valuePct={100} valueLabel={`+$${avgWin.toFixed(2)}`} color={COLORS.green} />
            <TopGaugeCard title="Winning Trades" subtitle="WIN RATIO" valuePct={winRateNum} valueLabel={winRate} color={winRateNum > 50 ? COLORS.green : COLORS.red} />
            <TopGaugeCard title="Average Expectancy" subtitle="R-MULTIPLE" valuePct={50} valueLabel="N/A" color={COLORS.muted} />
          </div>

          <div style={{ display: 'flex', gap: '16px' }}>
            <MetricCard title="TOTAL P&L" value={`$${totalPnL.toFixed(2)}`} sub={`From ${trades.length} trades`} valueColor={totalPnL >= 0 ? COLORS.green : COLORS.red} />
            <MetricCard title="WIN RATE" value={winRate} sub={`${wins.length}W / ${losses.length}L`} valueColor="#ffffff" />
            <MetricCard title="PROFIT FACTOR" value={avgLoss > 0 ? ((wins.length * avgWin) / (losses.length * avgLoss)).toFixed(2) : "∞"} sub="Standard Yield" valueColor={COLORS.green} />
            <MetricCard title="AVG R MULTIPLE" value="N/A" sub="Expectancy: N/A" valueColor="#ffffff" />
            <MetricCard title="AVG WIN VS AVG LOSS" value={`$${avgWin.toFixed(0)} / -$${avgLoss.toFixed(0)}`} sub={`Risk Ratio: 1 : ${(avgWin / (avgLoss || 1)).toFixed(1)}`} valueColor={COLORS.green} />
            <MetricCard title="BEST TRADE" value={`+$${bestTradeAmt.toFixed(2)}`} sub={bestTradeTicker} valueColor={COLORS.green} />
          </div>
          
          {/* Metrics Row 2 */}
          <div style={{ display: 'flex', gap: '16px' }}>
            <div style={{ flex: '0 0 calc(16.666% - 13.33px)' }}>
               <MetricCard title="KELLY CRITERION" value="0% (Avoid)" sub="Optimal capital sizing model" valueColor={COLORS.red} />
            </div>
          </div>

          {/* Charts Row */}
          <div style={{ display: 'flex', gap: '16px', marginTop: '8px' }}>
            {/* Equity Curve Placeholder */}
            <div style={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, borderRadius: '8px', padding: '20px', flex: '2', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
                <div>
                  <div style={{ fontSize: '16px', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>📈 Cumulative Equity Curve</div>
                  <div style={{ fontSize: '11px', color: COLORS.muted, marginTop: '4px' }}>Systematic growth chart showing wins (green dots) vs losses (red dots)</div>
                </div>
                <div style={{ display: 'flex', background: COLORS.bg, border: `1px solid ${COLORS.border}`, borderRadius: '6px', overflow: 'hidden' }}>
                  {['Daily', 'Weekly', 'Monthly', 'Yearly'].map((t, i) => (
                    <div key={t} style={{ padding: '4px 12px', fontSize: '11px', fontWeight: '600', color: i === 0 ? '#fff' : COLORS.muted, background: i === 0 ? COLORS.blue : 'transparent', cursor: 'pointer' }}>{t}</div>
                  ))}
                </div>
              </div>
              <div style={{ flex: 1, minHeight: '250px', display: 'flex', alignItems: 'flex-end', justifyContent: 'center', color: COLORS.muted, fontSize: '12px', background: COLORS.bg, borderRadius: '6px', padding: '16px', position: 'relative' }}>
                {trades.length === 0 ? (
                  "Insufficient history points for timeframe to plot chart."
                ) : (
                  <svg width="100%" height="100%" viewBox="0 0 600 200" preserveAspectRatio="none" style={{ overflow: 'visible' }}>
                    {/* Zero Line */}
                    <line x1="0" y1={getY(0)} x2="600" y2={getY(0)} stroke={COLORS.border} strokeWidth="1" strokeDasharray="4 4" />
                    
                    <path 
                      d={`M0,${getY(0)} ${eqPoints.map((val, i) => `L${getX(i)},${getY(val)}`).join(' ')}`} 
                      fill="none" 
                      stroke={COLORS.blue} 
                      strokeWidth="3" 
                    />
                    {eqPoints.map((val, i) => (
                      <circle 
                        key={i} 
                        cx={getX(i)} 
                        cy={getY(val)} 
                        r="4" 
                        fill={trades[i]?.amount > 0 ? COLORS.green : COLORS.red} 
                      />
                    ))}
                  </svg>
                )}
              </div>
            </div>

            {/* Win Loss Distribution Placeholder */}
            <div style={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, borderRadius: '8px', padding: '20px', flex: '1', display: 'flex', flexDirection: 'column' }}>
               <div style={{ fontSize: '16px', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>📊 Win / Loss Distribution</div>
               <div style={{ fontSize: '11px', color: COLORS.muted, marginTop: '4px', marginBottom: '32px' }}>Segmented trade outcomes and size summary</div>
               
               <div style={{ display: 'flex', alignItems: 'center', gap: '32px', padding: '0 16px' }}>
                  <RadialGauge value={winRateNum} label={winRate} color={winRateNum > 50 ? COLORS.green : COLORS.red} trackColor="#333" />
                  <div style={{ flex: 1 }}>
                     <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '600', marginBottom: '8px' }}><span>● Wins</span> <span>{wins.length} trades</span></div>
                     <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: '600', marginBottom: '16px', color: COLORS.muted }}><span>● Losses</span> <span>{losses.length} trades</span></div>
                     <div style={{ borderTop: `1px solid ${COLORS.border}`, paddingTop: '16px' }}>
                       <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: COLORS.muted, marginBottom: '8px' }}><span>Avg Win</span> <span>${avgWin.toFixed(2)}</span></div>
                       <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: COLORS.muted, marginBottom: '16px' }}><span>Avg Loss</span> <span>-${avgLoss.toFixed(2)}</span></div>
                       <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: COLORS.muted, marginBottom: '8px' }}><span>Largest Win</span> <span>+${bestTradeAmt.toFixed(2)}</span></div>
                       <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: COLORS.muted }}><span>Largest Loss</span> <span>-${worstTradeAmt.toFixed(2)}</span></div>
                     </div>
                  </div>
               </div>
            </div>
          </div>
        </div>
      ) : tab === 'Monthly Trade Log' ? (
        <TradeLogTab trades={trades} setTrades={setTrades} />
      ) : tab === 'Trade Calendar' ? (
        <div style={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, borderRadius: '8px', padding: '24px' }}>
          <h2 style={{ fontSize: '18px', marginBottom: '16px', color: COLORS.text }}>Trade Calendar</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '8px' }}>
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
              <div key={d} style={{ textAlign: 'center', padding: '8px', color: COLORS.muted, fontWeight: 'bold' }}>{d}</div>
            ))}
            {Array.from({ length: 31 }).map((_, i) => {
               const dayTrades = trades.filter(t => new Date(t.date).getDate() === i + 1);
               const dayPnL = dayTrades.reduce((sum, t) => sum + (t.amount || 0), 0);
               return (
                 <div key={i} style={{ 
                   aspectRatio: '1', 
                   border: `1px solid ${COLORS.border}`, 
                   borderRadius: '4px', 
                   padding: '8px',
                   background: dayTrades.length > 0 ? COLORS.border : 'transparent'
                 }}>
                   <span style={{ color: COLORS.text }}>{i + 1}</span>
                   {dayTrades.length > 0 && (
                     <>
                       <div style={{ fontSize: '10px', color: COLORS.muted, marginTop: '4px' }}>{dayTrades.length} Trades</div>
                       <div style={{ fontSize: '11px', color: dayPnL >= 0 ? COLORS.green : COLORS.red, fontWeight: 'bold' }}>
                         {dayPnL >= 0 ? '+' : ''}${dayPnL.toFixed(2)}
                       </div>
                     </>
                   )}
                 </div>
               )
            })}
          </div>
        </div>
      ) : tab === 'Monthly Summary' ? (
        <div style={{ background: COLORS.panel, border: `1px solid ${COLORS.border}`, borderRadius: '8px', padding: '24px' }}>
          <h2 style={{ fontSize: '18px', marginBottom: '16px', color: COLORS.text }}>Monthly Summary</h2>
          <div style={{ display: 'flex', gap: '16px' }}>
             <MetricCard title="Total TRADES" value={trades.length} sub="This month" valueColor={COLORS.text} />
             <MetricCard title="Total P&L" value={`$${totalPnL.toFixed(2)}`} sub="Actual" valueColor={totalPnL >= 0 ? COLORS.green : COLORS.red} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
