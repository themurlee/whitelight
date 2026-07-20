import React, { useState, useEffect } from 'react';
import './App.css';
import WhiteLightPanel from './WhiteLightPanel';
import AlpacaPanel from './AlpacaPanel';
import OptionsTradingPanel from './OptionsTradingPanel';
import ShadowCortexPanel from './ShadowCortexPanel';
import WhitelightCortexIntegratedPanel from './WhitelightCortexIntegratedPanel';

const API_BASE = 'http://127.0.0.1:8000/api';

function App() {
  const [activeTab, setActiveTab] = useState('options');
  const [optionsSubTab, setOptionsSubTab] = useState('overview');
  const [calYear, setCalYear] = useState(new Date().getFullYear());
  const [calMonth, setCalMonth] = useState(new Date().getMonth());
  const [filterType, setFilterType] = useState('month');
  const [filterValue, setFilterValue] = useState('');
  const [chartTimeframe, setChartTimeframe] = useState('daily');
  const [selectedCalFilter, setSelectedCalFilter] = useState({ type: 'all', value: '' });

  const getWeekRangeString = (date) => {
    const d = new Date(date);
    const day = d.getDay();
    const diffToSunday = d.getDate() - day;
    const sunday = new Date(d.setDate(diffToSunday));
    const saturday = new Date(sunday);
    saturday.setDate(sunday.getDate() + 6);
    
    const formatDate = (dateObj) => {
      return `${dateObj.getFullYear()}-${String(dateObj.getMonth() + 1).padStart(2, '0')}-${String(dateObj.getDate()).padStart(2, '0')}`;
    };
    return `Week: ${formatDate(sunday)} to ${formatDate(saturday)}`;
  };

  const [state, setState] = useState({ lockdown_active: false, drawdown_locked_at: null, equity_history: [] });
  const [positions, setPositions] = useState({ active_positions: [] });
  const [trades, setTrades] = useState([]);
  const [psychology, setPsychology] = useState([]);
  const [weekly, setWeekly] = useState([]);
  const [loading, setLoading] = useState(true);
  const [signalsMatrix, setSignalsMatrix] = useState([]);
  const [loadingSignals, setLoadingSignals] = useState(false);

  const [systematicStatus, setSystematicStatus] = useState({ tickers: {}, account: { configured: false }, logs: "", signal: null });
  const [loadingSystematic, setLoadingSystematic] = useState(false);
  const [ingestTicker, setIngestTicker] = useState("");
  const [ingestLoading, setIngestLoading] = useState(false);

  const [signalTicker, setSignalTicker] = useState("");
  const [signalLoading, setSignalLoading] = useState(false);
  const [executingLoading, setExecutingLoading] = useState(false);

  // Form states
  const [preMood, setPreMood] = useState('Calm');
  const [preSleep, setPreSleep] = useState(8);
  const [preFocus, setPreFocus] = useState(7);
  const [preRulesReady, setPreRulesReady] = useState(true);

  const [postRevenge, setPostRevenge] = useState(false);
  const [postFomo, setPostFomo] = useState(false);
  const [postFocus, setPostFocus] = useState(8);
  const [postNotes, setPostNotes] = useState('');

  const [simEquity, setSimEquity] = useState(10000);
  const [adjAmt, setAdjAmt] = useState(0);

  const [tAction, setTAction] = useState('BUY');
  const [tSymbol, setTSymbol] = useState('');
  const [tQty, setTQty] = useState(1);
  const [tPrice, setTPrice] = useState(2.50);
  const [tStrategy, setTStrategy] = useState('EMA_VWAP_crossover');
  const [tPnl, setTPnl] = useState(0);
  const [tAttachments, setTAttachments] = useState([]);
  const [tUploading, setTUploading] = useState(false);
  const [tTickerInput, setTTickerInput] = useState('');
  const [tTickerSuggestions, setTTickerSuggestions] = useState([]);
  const [tExpirations, setTExpirations] = useState([]);
  const [tSelectedExpiration, setTSelectedExpiration] = useState('');
  const [tContracts, setTContracts] = useState([]);
  const [tSelectedContract, setTSelectedContract] = useState(null);
  const [tOptionType, setTOptionType] = useState('call');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [modalFiles, setModalFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [activePreviewImage, setActivePreviewImage] = useState(null);

  const [wkPnl, setWkPnl] = useState(0);
  const [wkRating, setWkRating] = useState(8);
  const [wkMistakes, setWkMistakes] = useState('');
  const [wkLearnings, setWkLearnings] = useState('');

  const [selectedReview, setSelectedReview] = useState(null);
  const [selectedReviewContent, setSelectedReviewContent] = useState('');

  const [selectedLogMonth, setSelectedLogMonth] = useState('');

  // Autocomplete & Option Contract Builder handlers
  const handleTickerChange = async (val) => {
    setTTickerInput(val.toUpperCase());
    if (val.trim().length > 0) {
      try {
        const res = await fetch(`http://localhost:8000/api/tickers/search?q=${val.trim()}`);
        const data = await res.json();
        setTTickerSuggestions(data);
      } catch (err) {
        console.error("Ticker search error:", err);
      }
    } else {
      setTTickerSuggestions([]);
    }
  };

  const handleSelectTicker = async (tickerSym) => {
    setTTickerInput(tickerSym);
    setTTickerSuggestions([]);
    setTExpirations([]);
    setTSelectedExpiration('');
    setTContracts([]);
    setTSelectedContract(null);
    setTSymbol('');
    
    try {
      const res = await fetch(`http://localhost:8000/api/options/expirations?ticker=${tickerSym}`);
      const dates = await res.json();
      setTExpirations(dates);
      if (dates && dates.length > 0) {
        handleSelectExpiration(tickerSym, dates[0]);
      }
    } catch (err) {
      console.error("Fetch expirations error:", err);
    }
  };

  const handleSelectExpiration = async (ticker, date) => {
    setTSelectedExpiration(date);
    setTContracts([]);
    setTSelectedContract(null);
    setTSymbol('');

    try {
      const res = await fetch(`http://localhost:8000/api/options/contracts?ticker=${ticker}&expiration=${date}`);
      const contracts = await res.json();
      setTContracts(contracts);
      const filtered = contracts.filter(c => c.option_type.toLowerCase() === tOptionType.toLowerCase());
      if (filtered.length > 0) {
        setTSelectedContract(filtered[0]);
        setTSymbol(filtered[0].symbol);
      }
    } catch (err) {
      console.error("Fetch contracts error:", err);
    }
  };

  const handleOptionTypeChange = (type) => {
    setTOptionType(type);
    const filtered = tContracts.filter(c => c.option_type.toLowerCase() === type.toLowerCase());
    if (filtered.length > 0) {
      setTSelectedContract(filtered[0]);
      setTSymbol(filtered[0].symbol);
    } else {
      setTSelectedContract(null);
      setTSymbol('');
    }
  };

  const handleStrikeChange = (strikeVal) => {
    const filtered = tContracts.filter(c => c.option_type.toLowerCase() === tOptionType.toLowerCase());
    const contract = filtered.find(c => Number(c.strike_price) === Number(strikeVal));
    if (contract) {
      setTSelectedContract(contract);
      setTSymbol(contract.symbol);
    }
  };

  // Fetch all data
  const fetchData = async () => {
    try {
      const resState = await fetch(`${API_BASE}/state`);
      const dataState = await resState.json();
      setState(dataState);
      if (dataState.equity_history.length > 0) {
        setSimEquity(dataState.equity_history[dataState.equity_history.length - 1].equity);
      }

      const resPos = await fetch(`${API_BASE}/positions`);
      setPositions(await resPos.json());

      const resTrades = await fetch(`${API_BASE}/trades`);
      const dataTrades = await resTrades.json();
      setTrades(dataTrades);
      if (dataTrades.length > 0) {
        const latestTradeDate = new Date(dataTrades[dataTrades.length - 1].timestamp);
        const monthStr = latestTradeDate.toLocaleString('default', { month: 'long', year: 'numeric' });
        setSelectedLogMonth(monthStr);
        setFilterType(prev => prev || 'month');
        setFilterValue(prev => prev || monthStr);
      }

      const resPsych = await fetch(`${API_BASE}/psychology`);
      setPsychology(await resPsych.json());

      const resWeekly = await fetch(`${API_BASE}/weekly`);
      const dataWeekly = await resWeekly.json();
      setWeekly(dataWeekly);
      if (dataWeekly.length > 0 && !selectedReview) {
        setSelectedReview(dataWeekly[0].filename);
        setSelectedReviewContent(dataWeekly[0].content);
      }

      setLoading(false);
    } catch (e) {
      console.error("Error loading data from local API server: ", e);
    }
  };

  const fetchSignals = async () => {
    setLoadingSignals(true);
    try {
      const res = await fetch(`${API_BASE}/market/signals`);
      if (res.ok) {
        const data = await res.json();
        setSignalsMatrix(data);
      }
    } catch (e) {
      console.error("Error fetching live signals:", e);
    } finally {
      setLoadingSignals(false);
    }
  };

  const fetchSystematicStatus = async () => {
    setLoadingSystematic(true);
    try {
      const res = await fetch(`${API_BASE}/systematic/status`);
      const data = await res.json();
      setSystematicStatus(data);
    } catch (err) {
      console.error("Error fetching systematic status:", err);
    } finally {
      setLoadingSystematic(false);
    }
  };

  const handleIngestSubmit = async (e) => {
    e.preventDefault();
    if (!ingestTicker.trim()) return;
    setIngestLoading(true);
    try {
      const res = await fetch(`${API_BASE}/systematic/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: ingestTicker.trim() })
      });
      const data = await res.json();
      if (data.success) {
        setIngestTicker("");
        await fetchSystematicStatus();
      } else {
        alert("Ingestion failed: check console/logs.");
      }
    } catch (err) {
      console.error("Error running ingestion:", err);
      alert("Error running Ingestion: " + err.message);
    } finally {
      setIngestLoading(false);
    }
  };

  const handleGenerateSignal = async (e) => {
    e.preventDefault();
    if (!signalTicker.trim()) return;
    setSignalLoading(true);
    try {
      const res = await fetch(`${API_BASE}/systematic/signal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: signalTicker.trim() })
      });
      const data = await res.json();
      if (data.success) {
        setSignalTicker("");
        await fetchSystematicStatus();
      } else {
        alert("Signal generation failed: " + (data.data?.error || "unknown error"));
      }
    } catch (err) {
      console.error("Error generating signal:", err);
      alert("Error generating signal: " + err.message);
    } finally {
      setSignalLoading(false);
    }
  };

  const handleExecuteSignal = async () => {
    setExecutingLoading(true);
    try {
      const res = await fetch(`${API_BASE}/systematic/execute`, {
        method: "POST"
      });
      const data = await res.json();
      if (data.success) {
        await fetchSystematicStatus();
      } else {
        alert("Order execution failed: " + (data.error || "unknown error"));
      }
    } catch (err) {
      console.error("Error executing order:", err);
      alert("Error executing order: " + err.message);
    } finally {
      setExecutingLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    fetchSignals();
  }, []);

  useEffect(() => {
    if (activeTab === 'systematic' || activeTab === 'alpaca') {
      fetchSystematicStatus();
    }
  }, [activeTab]);

  const handleResetLockdown = async () => {
    try {
      const res = await fetch(`${API_BASE}/state/reset`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleTriggerLockdown = async () => {
    try {
      const res = await fetch(`${API_BASE}/state/lockdown`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handlePreSessionSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/psychology/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pre_mood: preMood,
          pre_sleep: Number(preSleep),
          pre_focus: Number(preFocus),
          pre_rules_ready: preRulesReady
        })
      });
      if ((await res.json()).success) {
        alert("Pre-session assessment recorded!");
        fetchData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handlePostSessionSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/psychology/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          post_revenge: postRevenge,
          post_fomo: postFomo,
          post_focus: Number(postFocus),
          post_notes: postNotes
        })
      });
      if ((await res.json()).success) {
        alert("Post-session assessment recorded!");
        setPostNotes('');
        fetchData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleEquitySliderChange = async (val) => {
    setSimEquity(val);
    try {
      const res = await fetch(`${API_BASE}/state/update_equity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ equity: Number(val) })
      });
      const data = await res.json();
      if (data.success) {
        fetchData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleApplyAdjustment = async (e) => {
    e.preventDefault();
    const newEquity = simEquity + Number(adjAmt);
    setSimEquity(newEquity);
    setAdjAmt(0);
    try {
      const res = await fetch(`${API_BASE}/state/update_equity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ equity: Number(newEquity) })
      });
      if ((await res.json()).success) {
        fetchData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fileToBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result);
      reader.onerror = (error) => reject(error);
    });
  };

  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;
    
    setTUploading(true);
    const uploadedList = [...tAttachments];
    
    for (const file of files) {
      try {
        const base64Content = await fileToBase64(file);
        const res = await fetch(`${API_BASE}/uploads`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: file.name,
            content: base64Content
          })
        });
        const data = await res.json();
        if (data.success) {
          uploadedList.push({ name: file.name, url: data.url });
        }
      } catch (err) {
        console.error("Error uploading file: ", err);
        alert(`Failed to upload ${file.name}`);
      }
    }
    
    setTAttachments(uploadedList);
    setTUploading(false);
  };

  const submitTrade = async (attachments) => {
    try {
      const res = await fetch(`${API_BASE}/trades/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: tAction,
          symbol: tSymbol,
          quantity: Number(tQty),
          price: Number(tPrice),
          pnl: Number(tPnl),
          strategy: tStrategy,
          attachments: attachments
        })
      });
      if ((await res.json()).success) {
        alert("Trade logged!");
        setTSymbol('');
        setTQty(1);
        setTPrice(2.50);
        setTPnl(0);
        setTAttachments([]);
        setTTickerInput('');
        setTTickerSuggestions([]);
        setTExpirations([]);
        setTSelectedExpiration('');
        setTContracts([]);
        setTSelectedContract(null);
        setTOptionType('call');
        fetchData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleLogTradeSubmit = async (e) => {
    e.preventDefault();
    if (tTickerInput.trim() !== '') {
      if (!tSymbol.trim()) {
        alert("Please specify or build an option symbol first.");
        return;
      }
      if (!tQty || Number(tQty) < 1) {
        alert("Please enter a valid quantity (minimum 1).");
        return;
      }
      if (!tPrice || Number(tPrice) <= 0) {
        alert("Please enter a valid price (greater than 0).");
        return;
      }
    }
    setIsUploadModalOpen(true);
  };

  const handleModalUploadAndSubmit = async () => {
    if (modalFiles.length === 0) return;
    setTUploading(true);
    const uploadedList = [];
    
    for (const file of modalFiles) {
      try {
        const base64Content = await fileToBase64(file);
        const res = await fetch(`${API_BASE}/uploads`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: file.name,
            content: base64Content
          })
        });
        const data = await res.json();
        if (data.success) {
          uploadedList.push({ name: file.name, url: data.url });
        }
      } catch (err) {
        console.error("Error uploading file: ", err);
        alert(`Failed to upload ${file.name}`);
      }
    }
    
    setTUploading(false);
    setIsUploadModalOpen(false);
    setModalFiles([]);
    
    submitTrade(uploadedList);
  };

  const handleModalImportAndSubmit = async () => {
    if (modalFiles.length === 0) return;
    setTUploading(true);
    
    for (const file of modalFiles) {
      try {
        const base64Content = await fileToBase64(file);
        await fetch(`${API_BASE}/uploads`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: file.name,
            content: base64Content
          })
        });
      } catch (err) {
        console.error("Upload error during import:", err);
      }
    }
    
    try {
      const res = await fetch(`${API_BASE}/trades/import_screenshot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filenames: modalFiles.map(f => f.name) })
      });
      const data = await res.json();
      if (data.success) {
        alert(`Successfully imported ${data.imported_count} trades from screenshot!`);
        setIsUploadModalOpen(false);
        setModalFiles([]);
        fetchData();
      } else {
        alert("Failed to import trades from screenshot.");
      }
    } catch (err) {
      console.error("Import error:", err);
      alert("Error importing screenshot.");
    } finally {
      setTUploading(false);
    }
  };

  const handleDeleteTrade = async (timestamp) => {
    if (!window.confirm("Are you sure you want to delete this trade entry?")) {
      return;
    }
    try {
      const res = await fetch(`http://localhost:8000/api/trades/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timestamp })
      });
      const data = await res.json();
      if (data.success) {
        alert("Trade entry deleted.");
        fetchData();
      }
    } catch (err) {
      console.error("Error deleting trade:", err);
    }
  };

  const handleWeeklyReviewSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/weekly/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pnl: Number(wkPnl),
          rating: Number(wkRating),
          mistakes: wkMistakes,
          learnings: wkLearnings
        })
      });
      if ((await res.json()).success) {
        alert("Weekly review published!");
        setWkPnl(0);
        setWkMistakes('');
        setWkLearnings('');
        fetchData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleReviewSelectChange = (filename) => {
    setSelectedReview(filename);
    const rev = weekly.find(w => w.filename === filename);
    if (rev) {
      setSelectedReviewContent(rev.content);
    }
  };

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Loading WhiteLight Control Panel...</p>
      </div>
    );
  }

  // General metrics calculations
  // Filter for Options portfolio trades only (discretionary)
  const optionsTrades = trades.filter(t => {
    const isOptionOSI = /^[A-Z]+\d{6}[CP]\d{8}$/.test(t.symbol);
    const isManualOrSpread = t.details?.strategy === 'Manual' || t.details?.strategy === 'Vertical Spread';
    const isDiv = t.action === 'DIVIDEND';
    return isOptionOSI || isManualOrSpread || isDiv;
  });

  const history = (() => {
    const list = [{ timestamp: '2026-07-01T09:00:00Z', equity: 10000.0 }];
    let running = 10000.0;
    const closed = optionsTrades
      .filter(t => (t.action === 'SELL' || t.action === 'DIVIDEND') && t.details?.pnl !== undefined)
      .sort((a, b) => {
        const timeDiff = new Date(a.timestamp) - new Date(b.timestamp);
        if (timeDiff !== 0) return timeDiff;
        return (a.sequence || 0) - (b.sequence || 0);
      });
    closed.forEach(t => {
      running += t.details.pnl;
      list.push({
        timestamp: t.timestamp,
        equity: running
      });
    });
    return list;
  })();

  const currentEquity = history.length > 0 ? history[history.length - 1].equity : 10000;
  const peakEquity = history.length > 0 ? Math.max(...history.map(h => h.equity)) : 10000;
  const drawdown = peakEquity > 0 ? (peakEquity - currentEquity) / peakEquity : 0;
  const isLocked = state.lockdown_active;

  const closedTrades = optionsTrades.filter(t => t.action === 'SELL');
  const winCount = closedTrades.filter(t => t.details?.pnl > 0).length;
  const totalPnl = closedTrades.reduce((sum, t) => sum + (t.details?.pnl || 0), 0);
  const winRate = closedTrades.length > 0 ? (winCount / closedTrades.length) * 100 : 0;

  const latestPsych = psychology.length > 0 ? psychology[psychology.length - 1] : {};
  const rulesFollowed = latestPsych.pre_rules_ready || false;
  const noRevenge = !latestPsych.post_revenge;
  const noFomo = !latestPsych.post_fomo;
  const disciplineScore = ((Number(rulesFollowed) + Number(noRevenge) + Number(noFomo)) / 3) * 100;

  // Filter trades by month, week, or date
  const tradeMonths = Array.from(new Set(optionsTrades.map(t => {
    const dt = new Date(t.timestamp);
    return dt.toLocaleString('default', { month: 'long', year: 'numeric' });
  })));

  const tradeWeeks = Array.from(new Set(optionsTrades.map(t => getWeekRangeString(new Date(t.timestamp)))));

  const tradeDates = Array.from(new Set(optionsTrades.map(t => {
    const dt = new Date(t.timestamp);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
  })));

  const filteredTrades = optionsTrades.filter(t => {
    const dt = new Date(t.timestamp);
    if (filterType === 'date') {
      const dStr = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
      return dStr === filterValue;
    } else if (filterType === 'week') {
      return getWeekRangeString(dt) === filterValue;
    } else {
      const mStr = dt.toLocaleString('default', { month: 'long', year: 'numeric' });
      return mStr === filterValue;
    }
  });

  const monthClosedTrades = filteredTrades.filter(t => t.action === 'SELL');
  const monthPnl = monthClosedTrades.reduce((sum, t) => sum + (t.details?.pnl || 0), 0);
  const monthWinCount = monthClosedTrades.filter(t => t.details?.pnl > 0).length;
  const monthWinRate = monthClosedTrades.length > 0 ? (monthWinCount / monthClosedTrades.length) * 100 : 0;

  // Options Performance Tab calculations
  const totalWinsList = closedTrades.filter(t => (t.details?.pnl || 0) > 0);
  const totalLossesList = closedTrades.filter(t => (t.details?.pnl || 0) < 0);
  const profitFactorVal = (() => {
    const grossWins = totalWinsList.reduce((sum, t) => sum + (t.details?.pnl || 0), 0);
    const grossLosses = Math.abs(totalLossesList.reduce((sum, t) => sum + (t.details?.pnl || 0), 0));
    return grossLosses > 0 ? grossWins / grossLosses : grossWins;
  })();
  const avgRMultipleVal = closedTrades.length > 0 ? closedTrades.reduce((sum, t) => sum + (t.details?.r_multiple || 0), 0) / closedTrades.length : 0;
  const avgWinVal = totalWinsList.length > 0 ? totalWinsList.reduce((sum, t) => sum + (t.details?.pnl || 0), 0) / totalWinsList.length : 0;
  const avgLossVal = totalLossesList.length > 0 ? Math.abs(totalLossesList.reduce((sum, t) => sum + (t.details?.pnl || 0), 0)) / totalLossesList.length : 0;
  const expectancyVal = (winRate / 100) * avgWinVal - ((100 - winRate) / 100) * avgLossVal;
  const kellyCriterionVal = (() => {
    if (closedTrades.length === 0 || winRate === 0) return 0;
    const ratio = avgLossVal > 0 ? avgWinVal / avgLossVal : 0;
    if (ratio === 0) return 0;
    const w = winRate / 100;
    const kelly = w - (1 - w) / ratio;
    return Math.max(0, kelly * 100);
  })();
  const bestTradeVal = closedTrades.length > 0 ? closedTrades.reduce((best, t) => (t.details?.pnl || 0) > (best.details?.pnl || 0) ? t : best, closedTrades[0]) : null;

  // Group P&L by Ticker (e.g. AVGO, META, MSFT)
  const pnlBySymbol = (() => {
    const groups = {};
    closedTrades.forEach(t => {
      const rawSym = t.symbol;
      const match = rawSym.match(/^([A-Z]+)\d{6}[CP]\d{8}$/i);
      const ticker = match ? match[1].toUpperCase() : rawSym.split(' ')[0].toUpperCase();
      groups[ticker] = (groups[ticker] || 0) + (t.details?.pnl || 0);
    });
    return Object.entries(groups).map(([symbol, pnl]) => ({ symbol, pnl })).sort((a, b) => b.pnl - a.pnl);
  })();

  // Group by Setup (strategy)
  const setupPerformance = (() => {
    const groups = {};
    closedTrades.forEach(t => {
      const setup = t.details?.strategy || 'Manual';
      if (!groups[setup]) {
        groups[setup] = { name: setup, count: 0, pnl: 0, bestR: -Infinity, wins: 0 };
      }
      const p = groups[setup];
      p.count += 1;
      p.pnl += t.details?.pnl || 0;
      if ((t.details?.r_multiple || 0) > p.bestR) {
        p.bestR = t.details?.r_multiple || 0;
      }
      if ((t.details?.pnl || 0) > 0) {
        p.wins += 1;
      }
    });
    return Object.values(groups).map(g => ({
      ...g,
      winRate: g.count > 0 ? (g.wins / g.count) * 100 : 0
    })).sort((a, b) => b.pnl - a.pnl);
  })();

  // Group by Session
  const sessionBreakdown = (() => {
    const sessions = {
      'New York': { name: 'New York', count: 0, pnl: 0, wins: 0, losses: 0 },
      'London': { name: 'London', count: 0, pnl: 0, wins: 0, losses: 0 },
      'Asia': { name: 'Asia', count: 0, pnl: 0, wins: 0, losses: 0 }
    };
    closedTrades.forEach(t => {
      const session = t.details?.session || 'New York';
      if (!sessions[session]) {
        sessions[session] = { name: session, count: 0, pnl: 0, wins: 0, losses: 0 };
      }
      const s = sessions[session];
      s.count += 1;
      s.pnl += t.details?.pnl || 0;
      if ((t.details?.pnl || 0) > 0) {
        s.wins += 1;
      } else if ((t.details?.pnl || 0) < 0) {
        s.losses += 1;
      }
    });
    return Object.values(sessions);
  })();

  // Generate Actionable Insights dynamically
  // Generate Actionable Insights dynamically
  const actionableInsights = (() => {
    const insights = [];
    
    // 1. Analyze Expiration Durations (Weekly vs Long Contracts)
    let weeklyCount = 0;
    let longCount = 0;
    
    trades.forEach(t => {
      const match = t.symbol.match(/([A-Z]+)(\d{6})(C|P)(\d{8})/);
      if (match) {
        const expStr = match[2];
        const yy = parseInt("20" + expStr.substring(0, 2));
        const mm = parseInt(expStr.substring(2, 4)) - 1;
        const dd = parseInt(expStr.substring(4, 6));
        const expDate = new Date(yy, mm, dd);
        const tradeDate = new Date(t.timestamp);
        
        const dte = (expDate - tradeDate) / (1000 * 60 * 60 * 24);
        if (dte <= 7) {
          weeklyCount++;
        } else {
          longCount++;
        }
      }
    });

    if (weeklyCount > 0) {
      insights.push({
        icon: '⏳',
        title: 'Strategy Shift: High Weekly Expiration Exposure',
        explanation: `You have logged ${weeklyCount} weekly contract trades (expiring in <= 7 DTE). Weekly option premiums decay rapidly due to accelerated theta curves, leaving no room for structural recovery.`,
        recommendation: 'Try shifting a portion of your capital into longer-term calls (30-60 DTE) to buy time and mitigate directional friction.'
      });
    }

    // 2. Scan for Underwater trades ($100+ Loss) -> Institutional Basis Repair Framework!
    const underwaterTrades = closedTrades.filter(t => (t.details?.pnl || 0) <= -100);
    if (underwaterTrades.length > 0) {
      const worstTrade = underwaterTrades.reduce((worst, t) => (t.details?.pnl || 0) < (worst.details?.pnl || 0) ? t : worst, underwaterTrades[0]);
      const tickerSymbol = worstTrade.symbol.replace(/[\dCP].*/, '');
      
      insights.push({
        icon: '💎',
        title: `Institutional Basis Repair: ${tickerSymbol}`,
        explanation: `Significant drawdown detected on your ${tickerSymbol} position (-$${Math.abs(worstTrade.details.pnl).toFixed(2)}). Refrain from selling puts to recover—this increases risk exposure.`,
        recommendation: `Apply the Institutional Basis Repair Framework: (1) Transform the position into a yield-generating asset by selling OTM Covered Calls into Green Days. (2) Benefit from pre-earnings IV Expansion. (3) Effective Basis Anchor: New Effective Basis = Current Basis - Premium Collected.`
      });
    }

    // 3. Underperforming Setup
    const lowWrSetup = setupPerformance.find(s => s.winRate < 45);
    if (lowWrSetup) {
      insights.push({
        icon: '⚠️',
        title: `Rework Underperforming Setup: ${lowWrSetup.name}`,
        explanation: `${lowWrSetup.name} setup has a low win rate of ${lowWrSetup.winRate.toFixed(1)}% across ${lowWrSetup.count} trades, accumulating $${lowWrSetup.pnl.toFixed(2)} in P&L.`,
        recommendation: 'Temporarily pause trading this setup or tighten its entry parameters to avoid unnecessary drawdown.'
      });
    }

    // 4. Best Setup to Double Down
    const bestSetup = setupPerformance[0];
    if (bestSetup && bestSetup.pnl > 0) {
      insights.push({
        icon: '🚀',
        title: `Double Down on ${bestSetup.name}`,
        explanation: `${bestSetup.name} is your highest-performing setup, yielding +$${bestSetup.pnl.toFixed(2)} over ${bestSetup.count} trades with a ${bestSetup.winRate.toFixed(1)}% win rate.`,
        recommendation: 'Prioritize taking these setups when they align with your criteria, and consider increasing contract sizing by 25%.'
      });
    }

    // 5. Risk management check
    if (avgWinVal < avgLossVal) {
      insights.push({
        icon: '🛑',
        title: 'Risk Alert: Average Loss Exceeds Average Win',
        explanation: `Your average win ($${avgWinVal.toFixed(2)}) is smaller than your average loss ($${avgLossVal.toFixed(2)}). Your Profit Factor is ${profitFactorVal.toFixed(2)}.`,
        recommendation: 'Strictly enforce 1:1.5 minimum risk-to-reward exit targets and tighten stop losses immediately.'
      });
    } else {
      insights.push({
        icon: '🛡️',
        title: 'Risk Profile: Healthy Profit Expectancy',
        explanation: `Your average win ($${avgWinVal.toFixed(2)}) outpaces average loss ($${avgLossVal.toFixed(2)}). Expectancy is $${expectancyVal.toFixed(2)} per trade.`,
        recommendation: 'Maintain your current stop-loss discipline and continue letting winning trades run to their defined strategy targets.'
      });
    }

    return insights;
  })();

  // SVG Line Chart coordinates helper
  const renderSVGChart = () => {
    if (history.length < 2) return <p className="text-muted">Insufficient history points to plot chart.</p>;
    
    const width = 600;
    const height = 220;
    const padding = 20;

    const minX = 0;
    const maxX = history.length - 1;
    const equities = history.map(h => h.equity);
    const minY = Math.min(...equities, 5000);
    const maxY = Math.max(...equities, 12000);

    const points = history.map((h, i) => {
      const x = padding + (i / maxX) * (width - 2 * padding);
      const y = height - padding - ((h.equity - minY) / (maxY - minY)) * (height - 2 * padding);
      return { x, y, equity: h.equity, time: new Date(h.timestamp).toLocaleDateString() };
    });

    const pathD = points.reduce((path, p, i) => {
      return i === 0 ? `M ${p.x} ${p.y}` : `${path} L ${p.x} ${p.y}`;
    }, '');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="equity-chart-svg">
        {/* Grids */}
        {[0.25, 0.5, 0.75].map((ratio, idx) => (
          <line
            key={idx}
            x1={padding}
            y1={padding + ratio * (height - 2 * padding)}
            x2={width - padding}
            y2={padding + ratio * (height - 2 * padding)}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="4 4"
          />
        ))}
        {/* Line Path */}
        <path d={pathD} fill="none" stroke="url(#chartGrad)" strokeWidth="3" />
        {/* Data Circles */}
        {points.map((p, idx) => (
          <g key={idx} className="chart-point-group">
            <circle cx={p.x} cy={p.y} r="4" fill="#FF007F" className="chart-circle" />
            <title>{`${p.time}\n$${p.equity.toLocaleString()}`}</title>
          </g>
        ))}
        {/* Gradients */}
        <defs>
          <linearGradient id="chartGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#FF007F" />
            <stop offset="100%" stopColor="#7F00FF" />
          </linearGradient>
        </defs>
      </svg>
    );
  };

  const getAggregatedHistory = () => {
    if (history.length === 0) return [];
    const baseEntry = history[0];
    const rest = history.slice(1);
    
    if (chartTimeframe === 'daily') {
      const dailyMap = {};
      rest.forEach(h => {
        const dateKey = h.timestamp.split('T')[0];
        dailyMap[dateKey] = h;
      });
      const aggregated = Object.values(dailyMap).sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      return [baseEntry, ...aggregated];
    } else if (chartTimeframe === 'weekly') {
      const weeklyMap = {};
      rest.forEach(h => {
        const d = new Date(h.timestamp);
        const oneJan = new Date(d.getFullYear(), 0, 1);
        const numberOfDays = Math.floor((d - oneJan) / (24 * 60 * 60 * 1000));
        const weekNum = Math.ceil((d.getDay() + 1 + numberOfDays) / 7);
        const weekKey = `${d.getFullYear()}-W${weekNum}`;
        weeklyMap[weekKey] = h;
      });
      const aggregated = Object.values(weeklyMap).sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      return [baseEntry, ...aggregated];
    } else if (chartTimeframe === 'monthly') {
      const monthlyMap = {};
      rest.forEach(h => {
        const d = new Date(h.timestamp);
        const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
        monthlyMap[monthKey] = h;
      });
      const aggregated = Object.values(monthlyMap).sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      return [baseEntry, ...aggregated];
    } else if (chartTimeframe === 'yearly') {
      const yearlyMap = {};
      rest.forEach(h => {
        const d = new Date(h.timestamp);
        const yearKey = `${d.getFullYear()}`;
        yearlyMap[yearKey] = h;
      });
      const aggregated = Object.values(yearlyMap).sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      return [baseEntry, ...aggregated];
    }
    return history;
  };

  const renderSVGPerformanceChart = () => {
    const activeHistory = getAggregatedHistory();
    if (activeHistory.length < 2) return <p className="text-muted">Insufficient history points for timeframe to plot chart.</p>;
    
    const width = 800;
    const height = 300;
    const padding = 40;

    const minX = 0;
    const maxX = activeHistory.length - 1;
    const equities = activeHistory.map(h => h.equity);
    const minY = Math.min(...equities, 9000);
    const maxY = Math.max(...equities, 14000);

    const points = activeHistory.map((h, i) => {
      const x = padding + (i / maxX) * (width - 2 * padding);
      const y = height - padding - ((h.equity - minY) / (maxY - minY)) * (height - 2 * padding);
      return { x, y, equity: h.equity, time: new Date(h.timestamp).toLocaleDateString(), idx: i };
    });

    const pathD = points.reduce((path, p, i) => {
      return i === 0 ? `M ${p.x} ${p.y}` : `${path} L ${p.x} ${p.y}`;
    }, '');

    const areaD = `${pathD} L ${points[points.length - 1].x} ${height - padding} L ${points[0].x} ${height - padding} Z`;

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="equity-chart-svg-large">
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FF007F" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#7F00FF" stopOpacity="0.0" />
          </linearGradient>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#FF007F" />
            <stop offset="100%" stopColor="#7F00FF" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map((ratio, idx) => (
          <line
            key={idx}
            x1={padding}
            y1={padding + ratio * (height - 2 * padding)}
            x2={width - padding}
            y2={padding + ratio * (height - 2 * padding)}
            stroke="rgba(255,255,255,0.05)"
            strokeDasharray="4 4"
          />
        ))}

        <text x={padding} y={height - 15} fill="#64748B" fontSize="10">
          {activeHistory.length > 0 ? new Date(activeHistory[0].timestamp).toLocaleDateString() : ''}
        </text>
        <text x={width - padding} y={height - 15} fill="#64748B" fontSize="10" textAnchor="end">
          {activeHistory.length > 0 ? new Date(activeHistory[activeHistory.length - 1].timestamp).toLocaleDateString() : ''}
        </text>

        {/* Area Gradient Fill */}
        <path d={areaD} fill="url(#areaGrad)" />

        {/* Line Path */}
        <path d={pathD} fill="none" stroke="url(#lineGrad)" strokeWidth="3" />

        {/* Color-coded Dots for wins and losses */}
        {points.map((p, idx) => {
          if (idx === 0) return null;
          const prevPoint = points[idx - 1];
          const isWin = p.equity >= prevPoint.equity;
          const dotColor = isWin ? '#10b981' : '#ef4444';

          return (
            <g key={idx} className="chart-point-group">
              <circle cx={p.x} cy={p.y} r="5" fill={dotColor} stroke="#020617" strokeWidth="1.5" />
              <title>{`${p.time}\nValuation: $${p.equity.toLocaleString()}\nChange: ${isWin ? '+' : ''}${(p.equity - prevPoint.equity).toFixed(2)}`}</title>
            </g>
          );
        })}
      </svg>
    );
  };

  const renderMiniMonthChart = (monthTrades, monthPnl) => {
    if (monthTrades.length === 0) return null;
    
    const width = 450;
    const height = 80;
    const padding = 10;
    
    let current = 10000;
    const equities = [10000];
    
    const sorted = [...monthTrades].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    sorted.forEach(t => {
      current += t.details?.pnl || 0;
      equities.push(current);
    });
    
    const minEq = Math.min(...equities);
    const maxEq = Math.max(...equities);
    const eqRange = maxEq - minEq || 1;
    
    const svgPoints = equities.map((eq, idx) => {
      const x = padding + (idx / (equities.length - 1)) * (width - 2 * padding);
      const y = height - padding - ((eq - minEq) / eqRange) * (height - 2 * padding);
      return { x, y };
    });
    
    const pathD = svgPoints.reduce((path, p, idx) => {
      return idx === 0 ? `M ${p.x} ${p.y}` : `${path} L ${p.x} ${p.y}`;
    }, '');
    
    const strokeColor = monthPnl >= 0 ? '#10b981' : '#ef4444';
    
    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="mini-month-chart-svg">
        <line 
          x1={padding} 
          y1={height / 2} 
          x2={width - padding} 
          y2={height / 2} 
          stroke="rgba(255,255,255,0.05)" 
          strokeDasharray="3 3" 
        />
        <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="2.5" />
      </svg>
    );
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation (Docusaurus-inspired layout) */}
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <span className="brand-bolt">⚡</span>
          <span className="brand-text">WhiteLight</span>
        </div>
        <div className="sidebar-status">
          <span className={`status-dot ${isLocked ? 'dot-locked' : 'dot-active'}`}></span>
          <span className="status-label">{isLocked ? 'SYSTEM LOCKED' : 'OPERATIONAL'}</span>
        </div>

        <nav className="sidebar-nav">
          <button 
            className={`nav-item ${activeTab === 'options' ? 'active' : ''}`}
            onClick={() => { setActiveTab('options'); setOptionsSubTab('overview'); }}
          >
            <span className="nav-icon">📊</span> Options
          </button>
          <button 
            className={`nav-item ${activeTab === 'systematic' ? 'active' : ''}`}
            onClick={() => setActiveTab('systematic')}
          >
            <span className="nav-icon">🤖</span> Systematic Pipeline
          </button>
          <button 
            className={`nav-item ${activeTab === 'alpaca' ? 'active' : ''}`}
            onClick={() => setActiveTab('alpaca')}
          >
            <span className="nav-icon">🦙</span> Alpaca Migration
          </button>
          <button 
            className={`nav-item ${activeTab === 'options_trading' ? 'active' : ''}`}
            onClick={() => setActiveTab('options_trading')}
          >
            <span className="nav-icon">⚡</span> Options Trading
          </button>
          <button 
            className={`nav-item ${activeTab === 'shadow_cortex' ? 'active' : ''}`}
            onClick={() => setActiveTab('shadow_cortex')}
          >
            <span className="nav-icon">🧠</span> Shadow Cortex
          </button>
          <button 
            className={`nav-item ${activeTab === 'whitelight_cortex' ? 'active' : ''}`}
            onClick={() => setActiveTab('whitelight_cortex')}
          >
            <span className="nav-icon">⚡🧠</span> Whitelight + Cortex
          </button>
        </nav>

        <div className="sidebar-footer">
          <p>Local-First Desktop Portal</p>
          <p className="footer-ver">V2.0.0 (API Connected)</p>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="app-main">
        {/* Main Content Header */}
        <header className="main-header">
          <div>
            <h1>Trade Performance Dashboard</h1>
            <p className="header-subtitle">Continuous discipline analysis and P&L targets</p>
          </div>
        </header>

        {/* Global Kinfo-style KPI Rings for Options Tab */}
        {activeTab === 'options' && (
          <div style={{ display: 'flex', gap: '8px', padding: '0 24px 0', marginBottom: '4px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexWrap: 'wrap' }}>
            {[
              { key: 'overview',        label: '📊 Overview' },
              { key: 'trades',          label: '📝 Monthly Trade Log' },
              { key: 'calendar',        label: '📅 Trade Calendar' },
              { key: 'monthly_summary', label: '🗂️ Monthly Summary' },
              { key: 'weekly',          label: '🗓️ Weekly Reviews' },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setOptionsSubTab(key)}
                style={{
                  padding: '8px 16px',
                  background: optionsSubTab === key ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                  border: 'none',
                  borderBottom: optionsSubTab === key ? '2px solid #00F2FE' : '2px solid transparent',
                  color: optionsSubTab === key ? '#00F2FE' : '#94A3B8',
                  fontSize: '0.82rem',
                  fontWeight: optionsSubTab === key ? 700 : 400,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap',
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        {activeTab === 'options' && optionsSubTab === 'overview' && (
          <section className="kinfo-kpi-rings-row">
            {/* Ring 1: Profit */}
            <div className="kpi-ring-card">
              <span className="ring-label-title">Profit</span>
              <span className="ring-label-subtitle">All Time</span>
              <div className="kinfo-ring" style={{
                background: `conic-gradient(#10b981 0% 100%, rgba(255, 255, 255, 0.05) 100% 100%)`
              }}>
                <div className="kinfo-ring-inner">
                  <span className={`ring-value ${totalPnl >= 0 ? 'txt-profit' : 'txt-loss'}`}>
                    ${totalPnl >= 0 ? '+' : ''}{(totalPnl / 1000).toFixed(2)}K
                  </span>
                </div>
              </div>
            </div>

            {/* Ring 2: Average Gain in $ */}
            <div className="kpi-ring-card">
              <span className="ring-label-title">Average Gain in $</span>
              <span className="ring-label-subtitle">Per Win Trade</span>
              <div className="kinfo-ring" style={{
                background: `conic-gradient(#10b981 0% ${(winRate).toFixed(0)}%, #ef4444 ${(winRate).toFixed(0)}% 100%)`
              }}>
                <div className="kinfo-ring-inner">
                  <span className="ring-value txt-profit">
                    +${avgWinVal.toFixed(0)}
                  </span>
                </div>
              </div>
            </div>

            {/* Ring 3: Winning Trades */}
            <div className="kpi-ring-card">
              <span className="ring-label-title">Winning Trades</span>
              <span className="ring-label-subtitle">Win Ratio</span>
              <div className="kinfo-ring" style={{
                background: `conic-gradient(#10b981 0% ${(winRate).toFixed(0)}%, #ef4444 ${(winRate).toFixed(0)}% 100%)`
              }}>
                <div className="kinfo-ring-inner">
                  <span className="ring-value txt-profit">
                    {winRate.toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Ring 4: Average Expectancy */}
            <div className="kpi-ring-card">
              <span className="ring-label-title">Average Expectancy</span>
              <span className="ring-label-subtitle">R-Multiple</span>
              <div className="kinfo-ring" style={{
                background: `conic-gradient(#10b981 0% ${Math.min(Math.max((avgRMultipleVal + 1) * 50, 0), 100).toFixed(0)}%, rgba(255, 255, 255, 0.05) ${Math.min(Math.max((avgRMultipleVal + 1) * 50, 0), 100).toFixed(0)}% 100%)`
              }}>
                <div className="kinfo-ring-inner">
                  <span className="ring-value txt-profit">
                    {avgRMultipleVal >= 0 ? '+' : ''}{avgRMultipleVal.toFixed(2)}R
                  </span>
                </div>
              </div>
            </div>
          </section>
        )}



        {/* Tab-driven Content Panels */}
        <div className="content-panel">

          {/* Tab: Options Performance Dashboard */}
          {activeTab === 'options' && optionsSubTab === 'overview' && (
            <div className="performance-tab-content">
              {/* 1. KPI Row */}
              <div className="perf-kpi-row">
                <div className="metric-glass-card">
                  <span className="card-label">Total P&L</span>
                  <span className={`card-value ${totalPnl >= 0 ? 'txt-profit' : 'txt-loss'}`}>
                    ${totalPnl >= 0 ? '+' : ''}{totalPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  <span className="card-sub-secondary">From {closedTrades.length} trades</span>
                </div>
                
                <div className="metric-glass-card">
                  <span className="card-label">Win Rate</span>
                  <span className="card-value">{winRate.toFixed(1)}%</span>
                  <span className="card-sub-secondary">{totalWinsList.length}W / {totalLossesList.length}L</span>
                </div>

                <div className="metric-glass-card">
                  <span className="card-label">Profit Factor</span>
                  <span className={`card-value ${profitFactorVal > 2 ? 'txt-profit' : (profitFactorVal > 1 ? 'txt-warn' : 'txt-loss')}`}>
                    {profitFactorVal.toFixed(2)}
                  </span>
                  <span className="card-sub-secondary">{profitFactorVal > 2 ? 'Excellent Expectancy' : 'Standard Yield'}</span>
                </div>

                <div className="metric-glass-card">
                  <span className="card-label">Avg R Multiple</span>
                  <span className="card-value">{avgRMultipleVal.toFixed(2)}R</span>
                  <span className="card-sub-secondary">Expectancy: ${expectancyVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </div>

                <div className="metric-glass-card">
                  <span className="card-label">Avg Win vs Avg Loss</span>
                  <span className="card-value">
                    <span className="txt-profit">${avgWinVal.toFixed(0)}</span>
                    <span style={{ color: '#64748b', fontSize: '1rem', margin: '0 5px' }}>/</span>
                    <span className="txt-loss">-${avgLossVal.toFixed(0)}</span>
                  </span>
                  <span className="card-sub-secondary">Risk Ratio: 1 : {(avgLossVal > 0 ? avgWinVal / avgLossVal : 0).toFixed(1)}</span>
                </div>

                <div className="metric-glass-card">
                  <span className="card-label">Best Trade</span>
                  <span className="card-value txt-profit">
                    +${bestTradeVal ? bestTradeVal.details?.pnl.toFixed(0) : '0'}
                  </span>
                  <span className="card-sub-secondary">
                    {bestTradeVal ? `${bestTradeVal.symbol} · ${bestTradeVal.details?.strategy}` : 'No trades logged'}
                  </span>
                </div>

                <div className="metric-glass-card">
                  <span className="card-label">Kelly Criterion</span>
                  <span className="card-value" style={{ color: kellyCriterionVal > 0 ? '#10b981' : '#f87171' }}>
                    {kellyCriterionVal > 0 ? `${kellyCriterionVal.toFixed(1)}%` : '0% (Avoid)'}
                  </span>
                  <span className="card-sub-secondary">Optimal capital sizing model</span>
                </div>
              </div>

              {/* 2. Equity Curve & 3. Win/Loss Distribution */}
              <div className="perf-charts-row">
                <div className="dashboard-block chart-block-large">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '15px' }}>
                    <div>
                      <h2>📈 Cumulative Equity Curve</h2>
                      <p className="block-desc" style={{ margin: 0 }}>Systematic growth chart showing wins (green dots) vs losses (red dots)</p>
                    </div>
                    <div className="timeframe-pills" style={{ display: 'flex', gap: '6px', background: 'rgba(255,255,255,0.03)', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                      {['daily', 'weekly', 'monthly', 'yearly'].map((tf) => (
                        <button
                          key={tf}
                          onClick={() => setChartTimeframe(tf)}
                          style={{
                            background: chartTimeframe === tf ? '#3b82f6' : 'transparent',
                            color: chartTimeframe === tf ? '#ffffff' : '#94a3b8',
                            border: 'none',
                            padding: '6px 12px',
                            borderRadius: '6px',
                            fontSize: '0.75rem',
                            fontWeight: '600',
                            textTransform: 'capitalize',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease'
                          }}
                        >
                          {tf}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="large-chart-container">
                    {renderSVGPerformanceChart()}
                  </div>
                </div>

                <div className="dashboard-block donut-block">
                  <h2>📊 Win / Loss Distribution</h2>
                  <p className="block-desc">Segmented trade outcomes and size summary</p>
                  
                  <div className="donut-layout">
                    <div className="donut-chart-outer" style={{
                      background: `conic-gradient(#10b981 0% ${winRate}%, #ef4444 ${winRate}% 100%)`
                    }}>
                      <div className="donut-chart-inner">
                        <span className="donut-percent">{winRate.toFixed(0)}%</span>
                        <span className="donut-lbl">WIN RATE</span>
                      </div>
                    </div>

                    <div className="donut-stats-col">
                      <div className="donut-stat-row">
                        <span className="dot-win">● Wins</span>
                        <strong>{totalWinsList.length} trades</strong>
                      </div>
                      <div className="donut-stat-row">
                        <span className="dot-loss">● Losses</span>
                        <strong>{totalLossesList.length} trades</strong>
                      </div>
                      <div className="donut-stat-divider"></div>
                      <div className="donut-stat-row">
                        <span>Avg Win</span>
                        <span className="txt-profit">${avgWinVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                      </div>
                      <div className="donut-stat-row">
                        <span>Avg Loss</span>
                        <span className="txt-loss">-${avgLossVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                      </div>
                      <div className="donut-stat-divider"></div>
                      <div className="donut-stat-row">
                        <span>Largest Win</span>
                        <span className="txt-profit">+${bestTradeVal ? bestTradeVal.details?.pnl.toFixed(0) : '0'}</span>
                      </div>
                      <div className="donut-stat-row">
                        <span>Largest Loss</span>
                        <span className="txt-loss">
                          -${Math.abs(closedTrades.reduce((worst, t) => (t.details?.pnl || 0) < (worst.details?.pnl || 0) ? t : worst, closedTrades[0])?.details?.pnl || 0).toFixed(0)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 4. P&L by Ticker */}
              <div className="perf-grouped-row">
                <div className="dashboard-block group-block-symbols" style={{ width: '100%' }}>
                  <h2>🎯 P&L by Ticker Symbol</h2>
                  <p className="block-desc">Contribution of individual underlying ticker assets</p>
                  
                  <div className="symbol-bars-list">
                    {pnlBySymbol.map((item, idx) => {
                      const maxAbs = Math.max(...pnlBySymbol.map(s => Math.abs(s.pnl)), 1);
                      const pctWidth = Math.min((Math.abs(item.pnl) / maxAbs) * 100, 100);
                      const isProfit = item.pnl >= 0;
                      
                      return (
                        <div key={idx} className="symbol-bar-row">
                          <div className="symbol-name" style={{ minWidth: '80px', fontWeight: 'bold' }}>{item.symbol}</div>
                          <div className="bar-track">
                            <div 
                              className={`bar-fill ${isProfit ? 'fill-profit' : 'fill-loss'}`}
                              style={{ width: `${pctWidth}%` }}
                            ></div>
                          </div>
                          <div className={`symbol-val ${isProfit ? 'txt-profit' : 'txt-loss'}`} style={{ minWidth: '80px', textAlign: 'right' }}>
                            {isProfit ? '+' : ''}${item.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Actionable Insights */}
              <div className="perf-insights-row-full" style={{ marginTop: '20px' }}>
                <div className="dashboard-block insights-block" style={{ width: '100%' }}>
                  <h2>💡 Actionable Trading Insights</h2>
                  <p className="block-desc">Dynamic data-driven recommendations to minimize leakage</p>
                  
                  <div className="insights-cards-list">
                    {actionableInsights.map((ins, idx) => (
                      <div key={idx} className="insight-card-item">
                        <div className="insight-card-icon">{ins.icon}</div>
                        <div className="insight-card-body">
                          <h4>{ins.title}</h4>
                          <p className="insight-explanation">{ins.explanation}</p>
                          <p className="insight-rec"><strong>Recommendation: </strong>{ins.recommendation}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}



          {/* Tab 4: Monthly Trade Log */}
          {activeTab === 'options' && optionsSubTab === 'trades' && (
            <div className="panel-vertical">
              <div className="dashboard-block">
                <h2>➕ Log Manual Closed Option / Stock Trade</h2>
                <form onSubmit={handleLogTradeSubmit} className="trade-log-form">
                  <div className="form-row">
                    <div className="form-group">
                      <label>Action</label>
                      <select value={tAction} onChange={(e) => setTAction(e.target.value)}>
                        <option value="BUY">BUY</option>
                        <option value="SELL">SELL</option>
                      </select>
                    </div>

                    <div className="form-group ticker-autocomplete-group">
                      <label>Underlying Ticker</label>
                      <input 
                        type="text" 
                        value={tTickerInput} 
                        onChange={(e) => handleTickerChange(e.target.value)} 
                        placeholder="E.g. AAPL, TSLA"
                      />
                      {tTickerSuggestions.length > 0 && (
                        <div className="autocomplete-suggestions-dropdown">
                          {tTickerSuggestions.map((item, idx) => (
                            <div 
                              key={idx} 
                              className="suggestion-item"
                              onClick={() => handleSelectTicker(item.symbol)}
                            >
                              <strong>{item.symbol}</strong> - {item.name}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="form-group">
                      <label>Expiration Date</label>
                      <select 
                        value={tSelectedExpiration} 
                        onChange={(e) => handleSelectExpiration(tTickerInput, e.target.value)}
                        disabled={tExpirations.length === 0}
                      >
                        {tExpirations.length === 0 ? (
                          <option value="">(Enter ticker first)</option>
                        ) : (
                          tExpirations.map((date, idx) => (
                            <option key={idx} value={date}>{date}</option>
                          ))
                        )}
                      </select>
                    </div>

                    <div className="form-group">
                      <label>Option Type</label>
                      <select 
                        value={tOptionType} 
                        onChange={(e) => handleOptionTypeChange(e.target.value)}
                        disabled={tExpirations.length === 0}
                      >
                        <option value="call">Call</option>
                        <option value="put">Put</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Strike Price</label>
                      <select 
                        value={tSelectedContract ? tSelectedContract.strike_price : ''}
                        onChange={(e) => handleStrikeChange(e.target.value)}
                        disabled={tContracts.length === 0}
                      >
                        {tContracts.length === 0 ? (
                          <option value="">(Select expiration)</option>
                        ) : (
                          tContracts
                            .filter(c => c.option_type.toLowerCase() === tOptionType.toLowerCase())
                            .map((c, idx) => (
                              <option key={idx} value={c.strike_price}>
                                ${c.strike_price.toFixed(2)} (Vol: {c.volume || 0})
                              </option>
                            ))
                        )}
                      </select>
                    </div>

                    <div className="form-group">
                      <label>Option Symbol (OSI)</label>
                      <input 
                        type="text" 
                        value={tSymbol} 
                        onChange={(e) => setTSymbol(e.target.value)} 
                        placeholder="E.g. AAPL260814C00185000" 
                      />
                    </div>

                    <div className="form-group">
                      <label>Quantity</label>
                      <input 
                        type="number" 
                        min="1" 
                        value={tQty} 
                        onChange={(e) => setTQty(e.target.value)} 
                      />
                    </div>

                    <div className="form-group">
                      <label>Price ($ per Contract)</label>
                      <input 
                        type="number" 
                        step="0.01" 
                        value={tPrice} 
                        onChange={(e) => setTPrice(e.target.value)} 
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <label>Strategy Used</label>
                      <input 
                        type="text" 
                        value={tStrategy} 
                        onChange={(e) => setTStrategy(e.target.value)} 
                      />
                    </div>
                    {tAction === 'SELL' && (
                      <div className="form-group">
                        <label>Net P&L ($)</label>
                        <input 
                          type="number" 
                          step="0.01" 
                          value={tPnl} 
                          onChange={(e) => setTPnl(e.target.value)} 
                        />
                      </div>
                    )}
                    <div className="form-group btn-align">
                      <button type="submit" className="add-trade-btn" disabled={tUploading}>
                        {tTickerInput.trim() === '' ? 'Upload Screenshot to Import' : 'Upload / Publish Trade'}
                      </button>
                    </div>
                  </div>
                </form>
              </div>

              <div className="dashboard-block">
                <div className="trade-log-header">
                  <h2>📝 Monthly Ledger Database</h2>
                  
                  {(tradeMonths.length > 0 || tradeWeeks.length > 0 || tradeDates.length > 0) && (
                    <div className="select-month-container">
                      <label>Filter Ledger: </label>
                      <select 
                        value={`${filterType}:${filterValue}`} 
                        onChange={(e) => {
                          const [type, val] = e.target.value.split(':', 2);
                          setFilterType(type);
                          setFilterValue(val);
                          if (type === 'month') {
                            setSelectedLogMonth(val);
                          }
                        }}
                        style={{ background: '#1e293b', border: '1px solid rgba(255, 255, 255, 0.1)', color: '#ffffff', borderRadius: '8px', padding: '6px 12px', fontSize: '0.85rem' }}
                      >
                        <optgroup label="Months">
                          {tradeMonths.map((m, idx) => (
                            <option key={`m-${idx}`} value={`month:${m}`}>{m}</option>
                          ))}
                        </optgroup>
                        <optgroup label="Weeks">
                          {tradeWeeks.map((w, idx) => (
                            <option key={`w-${idx}`} value={`week:${w}`}>{w}</option>
                          ))}
                        </optgroup>
                        <optgroup label="Dates">
                          {tradeDates.map((d, idx) => (
                            <option key={`d-${idx}`} value={`date:${d}`}>{d}</option>
                          ))}
                        </optgroup>
                      </select>
                    </div>
                  )}
                </div>

                {filteredTrades.length === 0 ? (
                  <p className="text-muted">No trades recorded for this selection.</p>
                ) : (
                  <div className="table-responsive">
                    <table className="trades-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Action</th>
                          <th>Symbol</th>
                          <th>Qty</th>
                          <th>Price</th>
                          <th>Strategy</th>
                          <th>Net P&L</th>
                          <th>Attachments</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredTrades.map((t, idx) => (
                          <tr key={idx}>
                            <td>{new Date(t.timestamp).toLocaleDateString()}</td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '4px' }}>
                                <span className={`badge-action ${t.action === 'BUY' ? 'act-buy' : (t.action === 'DIVIDEND' ? 'act-div' : 'act-sell')}`}>
                                  {t.action}
                                </span>
                                {t.details?.wash_sale_warning && (
                                  <span className="wash-sale-badge" title={t.details.notes || "Wash Sale basis adjustment"}>
                                    ⚠️ Wash Sale
                                  </span>
                                )}
                                {t.details?.wash_sale_disallowed && (
                                  <span className="wash-sale-badge disallowed" title={t.details.notes || "Wash Sale disallowed loss"}>
                                    ⚠️ Disallowed Loss
                                  </span>
                                )}
                              </div>
                            </td>
                            <td><strong>{t.symbol}</strong></td>
                            <td>{t.quantity || '-'}</td>
                            <td>{t.price > 0 ? `$${t.price.toFixed(2)}` : '-'}</td>
                            <td>{t.details?.strategy}</td>
                            <td className={t.details?.pnl > 0 ? 'txt-profit' : (t.details?.pnl < 0 ? 'txt-loss' : '')}>
                              {(t.action === 'SELL' || t.action === 'DIVIDEND') ? (
                                <strong>
                                  {t.details?.pnl >= 0 ? '+' : ''}${t.details?.pnl.toFixed(2)}
                                </strong>
                              ) : '-'}
                            </td>
                            <td>
                              {t.details?.attachments && t.details.attachments.length > 0 ? (
                                <div className="table-attachments-cell">
                                  {t.details.attachments.map((att, attIdx) => {
                                    const isImg = /\.(png|jpe?g|webp|gif|svg|bmp)$/i.test(att.name);
                                    const fullUrl = `http://localhost:8000${att.url}`;
                                    return (
                                      <span key={attIdx} className="table-att-link">
                                        {isImg ? (
                                          <span 
                                            className="att-thumbnail-trigger"
                                            onClick={() => setActivePreviewImage(fullUrl)}
                                            title="Click to view image screenshot"
                                          >
                                            🖼️ {att.name.length > 10 ? att.name.substring(0, 8) + '...' : att.name}
                                          </span>
                                        ) : (
                                          <a 
                                            href={fullUrl} 
                                            target="_blank" 
                                            rel="noopener noreferrer" 
                                            title="Click to open file in new tab"
                                          >
                                            📄 {att.name.length > 10 ? att.name.substring(0, 8) + '...' : att.name}
                                          </a>
                                        )}
                                      </span>
                                    );
                                  })}
                                </div>
                              ) : '-'}
                            </td>
                            <td>
                              <button 
                                className="table-trash-btn"
                                onClick={() => handleDeleteTrade(t.timestamp)}
                                title="Delete this trade entry"
                              >
                                🗑️
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="monthly-stats-summary">
                  <div className="stat-pill">
                    <span>Month P&L: </span>
                    <strong className={monthPnl >= 0 ? 'txt-profit' : 'txt-loss'}>
                      ${monthPnl >= 0 ? '+' : ''}{monthPnl.toFixed(2)}
                    </strong>
                  </div>
                  <div className="stat-pill">
                    <span>Month Win Rate: </span>
                    <strong>{monthWinRate.toFixed(1)}%</strong>
                  </div>
                  <div className="stat-pill">
                    <span>Closed Trades: </span>
                    <strong>{monthClosedTrades.length}</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab: Trade Calendar */}
          {activeTab === 'options' && optionsSubTab === 'calendar' && (() => {
            const activeDatesInCal = Array.from(new Set(optionsTrades.filter(t => {
              const d = new Date(t.timestamp);
              return d.getFullYear() === calYear && d.getMonth() === calMonth;
            }).map(t => {
              const d = new Date(t.timestamp);
              return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
            }))).sort();

            const activeWeeksInCal = Array.from(new Set(optionsTrades.filter(t => {
              const d = new Date(t.timestamp);
              return d.getFullYear() === calYear && d.getMonth() === calMonth;
            }).map(t => getWeekRangeString(new Date(t.timestamp))))).sort();

            return (
              <div className="panel-vertical">
                <div className="dashboard-block">
                  <div className="calendar-header-controls" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '15px' }}>
                    <h2>📅 Trade Performance Calendar</h2>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '15px', flexWrap: 'wrap' }}>
                      <div className="cal-focus-container" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <label style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: '600' }}>Details Focus: </label>
                        <select
                          value={selectedCalFilter.type === 'all' ? 'all' : `${selectedCalFilter.type}:${selectedCalFilter.value}`}
                          onChange={(e) => {
                            if (e.target.value === 'all') {
                              setSelectedCalFilter({ type: 'all', value: '' });
                            } else {
                              const [type, val] = e.target.value.split(':', 2);
                              setSelectedCalFilter({ type, value: val });
                            }
                          }}
                          style={{ background: '#1e293b', border: '1px solid rgba(255, 255, 255, 0.1)', color: '#ffffff', borderRadius: '8px', padding: '6px 12px', fontSize: '0.85rem', outline: 'none' }}
                        >
                          <option value="all">🔍 Full Month Overview</option>
                          {activeWeeksInCal.length > 0 && (
                            <optgroup label="Weeks">
                              {activeWeeksInCal.map((w, idx) => (
                                <option key={`cal-w-${idx}`} value={`week:${w}`}>{w}</option>
                              ))}
                            </optgroup>
                          )}
                          {activeDatesInCal.length > 0 && (
                            <optgroup label="Dates">
                              {activeDatesInCal.map((d, idx) => (
                                <option key={`cal-d-${idx}`} value={`date:${d}`}>{d}</option>
                              ))}
                            </optgroup>
                          )}
                        </select>
                      </div>

                      <div className="calendar-nav-buttons" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <button 
                          className="nav-month-btn"
                          onClick={() => {
                            if (calMonth === 0) {
                              setCalMonth(11);
                              setCalYear(prev => prev - 1);
                            } else {
                              setCalMonth(prev => prev - 1);
                            }
                            setSelectedCalFilter({ type: 'all', value: '' });
                          }}
                        >
                          ◀ Previous
                        </button>
                        
                        <strong className="calendar-current-month-year" style={{ minWidth: '120px', textAlign: 'center' }}>
                          {["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][calMonth]} {calYear}
                        </strong>
                        
                        <button 
                          className="nav-month-btn"
                          onClick={() => {
                            if (calMonth === 11) {
                              setCalMonth(0);
                              setCalYear(prev => prev + 1);
                            } else {
                              setCalMonth(prev => prev + 1);
                            }
                            setSelectedCalFilter({ type: 'all', value: '' });
                          }}
                        >
                          Next ▶
                        </button>
                      </div>
                    </div>
                  </div>

                  <p className="block-desc">Daily net P&L aggregation. Profitable days are highlighted in green, losing days in red. The <strong>WEEK</strong> column summarizes weekly performance.</p>

                  {/* Calendar Grid */}
                  <div className="calendar-grid-container">
                    {/* Days of Week Headers */}
                    <div className="calendar-week-headers-8col">
                      {["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT", "WEEK"].map((day, idx) => (
                        <div key={idx} className="week-header-cell">{day}</div>
                      ))}
                    </div>

                    <div className="calendar-days-grid-8col">
                      {(() => {
                        const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
                        const startDayOfWeek = new Date(calYear, calMonth, 1).getDay();
                        
                        const dayElements = [];
                        for (let i = 0; i < startDayOfWeek; i++) {
                          dayElements.push(null);
                        }
                        for (let d = 1; d <= daysInMonth; d++) {
                          dayElements.push(d);
                        }
                        while (dayElements.length % 7 !== 0) {
                          dayElements.push(null);
                        }
                        
                        const weeks = [];
                        for (let i = 0; i < dayElements.length; i += 7) {
                          weeks.push(dayElements.slice(i, i + 7));
                        }
                        
                        const cells = [];
                        
                        weeks.forEach((week, weekIdx) => {
                          week.forEach((day, dayIdx) => {
                            if (day === null) {
                              cells.push(<div key={`empty-${weekIdx}-${dayIdx}`} className="calendar-day-cell cell-empty"></div>);
                            } else {
                              const dayTrades = optionsTrades.filter(t => {
                                if (t.action !== 'SELL' && t.action !== 'DIVIDEND') return false;
                                const d = new Date(t.timestamp);
                                return d.getFullYear() === calYear && d.getMonth() === calMonth && d.getDate() === day;
                              });
                              
                              const dayPnl = dayTrades.length > 0 ? dayTrades.reduce((sum, t) => sum + (t.details?.pnl || 0), 0) : null;
                              
                              let cellClass = "calendar-day-cell cell-active";
                              let pnlText = "";
                              
                              if (dayPnl !== null) {
                                if (dayPnl > 0) {
                                  cellClass += " cell-profit";
                                  pnlText = `+$${dayPnl.toFixed(0)}`;
                                } else if (dayPnl < 0) {
                                  cellClass += " cell-loss";
                                  pnlText = `-$${Math.abs(dayPnl).toFixed(0)}`;
                                } else {
                                  cellClass += " cell-flat";
                                  pnlText = "$0";
                                }
                              }
                              
                              const cellDateStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                              const isCellSelected = selectedCalFilter.type === 'date' && selectedCalFilter.value === cellDateStr;
                              if (isCellSelected) {
                                cellClass += " selected-cal-cell";
                              }
                              
                              cells.push(
                                <div 
                                  key={`day-${day}`} 
                                  className={cellClass}
                                  onClick={() => {
                                    setSelectedCalFilter({ type: 'date', value: cellDateStr });
                                  }}
                                  style={{ cursor: 'pointer' }}
                                >
                                  <span className="day-number">{day}</span>
                                  {pnlText && <span className="day-pnl-val">{pnlText}</span>}
                                  {dayTrades.length > 0 && (
                                    <span className="day-trade-count-badge">
                                      {dayTrades.length} trades
                                    </span>
                                  )}
                                </div>
                              );
                            }
                          });
                          
                          // Render 8th cell: Week summary
                          let weekPnl = 0;
                          let weekTradesCount = 0;
                          let hasTrades = false;
                          
                          week.forEach(day => {
                            if (day !== null) {
                              const dayTrades = optionsTrades.filter(t => {
                                if (t.action !== 'SELL' && t.action !== 'DIVIDEND') return false;
                                const d = new Date(t.timestamp);
                                return d.getFullYear() === calYear && d.getMonth() === calMonth && d.getDate() === day;
                              });
                              if (dayTrades.length > 0) {
                                hasTrades = true;
                                weekTradesCount += dayTrades.length;
                                weekPnl += dayTrades.reduce((sum, t) => sum + (t.details?.pnl || 0), 0);
                              }
                            }
                          });
                          
                          if (hasTrades) {
                            let weekClass = "calendar-day-cell week-summary-cell";
                            let weekPnlText = "";
                            if (weekPnl > 0) {
                              weekClass += " cell-profit";
                              weekPnlText = `+$${weekPnl.toFixed(0)}`;
                            } else if (weekPnl < 0) {
                              weekClass += " cell-loss";
                              weekPnlText = `-$${Math.abs(weekPnl).toFixed(0)}`;
                            } else {
                              weekClass += " cell-flat";
                              weekPnlText = "$0";
                            }
                            
                            const firstDay = week.find(d => d !== null);
                            let isWeekSelected = false;
                            let weekRangeStr = "";
                            if (firstDay !== undefined) {
                              const refDate = new Date(calYear, calMonth, firstDay);
                              weekRangeStr = getWeekRangeString(refDate);
                              isWeekSelected = selectedCalFilter.type === 'week' && selectedCalFilter.value === weekRangeStr;
                            }
                            if (isWeekSelected) {
                              weekClass += " selected-cal-cell";
                            }
                            
                            cells.push(
                              <div 
                                key={`week-sum-${weekIdx}`} 
                                className={weekClass}
                                onClick={() => {
                                  if (weekRangeStr) {
                                    setSelectedCalFilter({ type: 'week', value: weekRangeStr });
                                  }
                                }}
                                style={{ cursor: 'pointer' }}
                              >
                                <span className="week-lbl-text">WEEK</span>
                                <span className="day-pnl-val">{weekPnlText}</span>
                                <span className="day-trade-count-badge font-bold">
                                  {weekTradesCount} trades
                                </span>
                              </div>
                            );
                          } else {
                            cells.push(
                              <div key={`week-sum-${weekIdx}`} className="calendar-day-cell week-summary-cell cell-empty">
                                <span className="week-lbl-text">WEEK</span>
                                <span className="day-pnl-val text-muted">-</span>
                              </div>
                            );
                          }
                        });
                        
                        return cells;
                      })()}
                    </div>
                  </div>
                </div>

                {/* Focused Details Section */}
                {selectedCalFilter.type !== 'all' && (
                  <div className="dashboard-block" style={{ marginTop: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <h3>📋 Focused Trades for {selectedCalFilter.value}</h3>
                      <button 
                        onClick={() => setSelectedCalFilter({ type: 'all', value: '' })}
                        style={{ background: 'rgba(255,255,255,0.05)', color: '#ffffff', border: '1px solid rgba(255,255,255,0.1)', padding: '4px 10px', borderRadius: '6px', fontSize: '0.75rem', cursor: 'pointer' }}
                      >
                        Clear Focus
                      </button>
                    </div>
                    
                    {(() => {
                      const calFilteredTrades = optionsTrades.filter(t => {
                        const dt = new Date(t.timestamp);
                        if (selectedCalFilter.type === 'date') {
                          const dStr = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
                          return dStr === selectedCalFilter.value;
                        } else if (selectedCalFilter.type === 'week') {
                          return getWeekRangeString(dt) === selectedCalFilter.value;
                        }
                        return false;
                      });
                      
                      if (calFilteredTrades.length === 0) {
                        return <p className="text-muted">No trades recorded for this selection.</p>;
                      }
                      
                      return (
                        <div className="table-responsive">
                          <table className="trades-table">
                            <thead>
                              <tr>
                                <th>Date</th>
                                <th>Action</th>
                                <th>Symbol</th>
                                <th>Qty</th>
                                <th>Price</th>
                                <th>Strategy</th>
                                <th>Net P&L</th>
                                <th>Attachments</th>
                              </tr>
                            </thead>
                            <tbody>
                              {calFilteredTrades.map((t, idx) => (
                                <tr key={idx}>
                                  <td>{new Date(t.timestamp).toLocaleDateString()}</td>
                                  <td>
                                    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '4px' }}>
                                      <span className={`badge-action ${t.action === 'BUY' ? 'act-buy' : (t.action === 'DIVIDEND' ? 'act-div' : 'act-sell')}`}>
                                        {t.action}
                                      </span>
                                      {t.details?.wash_sale_warning && (
                                        <span className="wash-sale-badge" title={t.details.notes || "Wash Sale basis adjustment"}>
                                          ⚠️ Wash Sale
                                        </span>
                                      )}
                                      {t.details?.wash_sale_disallowed && (
                                        <span className="wash-sale-badge disallowed" title={t.details.notes || "Wash Sale disallowed loss"}>
                                          ⚠️ Disallowed Loss
                                        </span>
                                      )}
                                    </div>
                                  </td>
                                  <td><strong>{t.symbol}</strong></td>
                                  <td>{t.quantity || '-'}</td>
                                  <td>{t.price > 0 ? `$${t.price.toFixed(2)}` : '-'}</td>
                                  <td>{t.details?.strategy}</td>
                                  <td className={t.details?.pnl > 0 ? 'txt-profit' : (t.details?.pnl < 0 ? 'txt-loss' : '')}>
                                    {(t.action === 'SELL' || t.action === 'DIVIDEND') ? (
                                      <strong>
                                        {t.details?.pnl >= 0 ? '+' : ''}${t.details?.pnl.toFixed(2)}
                                      </strong>
                                    ) : '-'}
                                  </td>
                                  <td>
                                    {t.details?.attachments && t.details.attachments.length > 0 ? (
                                      <div className="table-attachments-cell">
                                        {t.details.attachments.map((att, attIdx) => {
                                          const isImg = /\.(png|jpe?g|webp|gif|svg|bmp)$/i.test(att.name);
                                          const fullUrl = `http://localhost:8000${att.url}`;
                                          return (
                                            <span key={attIdx} className="table-att-link">
                                              {isImg ? (
                                                <span 
                                                  className="att-thumbnail-trigger"
                                                  onClick={() => setActivePreviewImage(fullUrl)}
                                                  title="Click to view screenshot"
                                                >
                                                  🖼️ {att.name.length > 10 ? att.name.substring(0, 8) + '...' : att.name}
                                                </span>
                                              ) : (
                                                <a href={fullUrl} target="_blank" rel="noopener noreferrer">
                                                  📄 {att.name.length > 10 ? att.name.substring(0, 8) + '...' : att.name}
                                                </a>
                                              )}
                                            </span>
                                          );
                                        })}
                                      </div>
                                    ) : '-'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      );
                    })()}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Tab: Monthly Summary */}
          {activeTab === 'options' && optionsSubTab === 'monthly_summary' && (
            <div className="panel-vertical">
              <div className="monthly-stacked-container">
                <h2>🗂️ Stacked Monthly Performance Journals</h2>
                <p className="block-desc">Aggregated metrics, equity progression trendlines, and detailed audits per month.</p>
                
                {(() => {
                  const monthsGroup = {};
                  closedTrades.forEach(t => {
                    const dt = new Date(t.timestamp);
                    const mKey = dt.toLocaleString('default', { month: 'long', year: 'numeric' });
                    if (!monthsGroup[mKey]) {
                      monthsGroup[mKey] = [];
                    }
                    monthsGroup[mKey].push(t);
                  });
                  
                  const sortedMonthKeys = Object.keys(monthsGroup).sort((a, b) => {
                    return new Date(b) - new Date(a);
                  });
                  
                  if (sortedMonthKeys.length === 0) {
                    return <p className="text-muted">No monthly trading records available.</p>;
                  }
                  
                  return sortedMonthKeys.map((monthKey, idx) => {
                    const monthTrades = monthsGroup[monthKey];
                    const monthPnl = monthTrades.reduce((sum, t) => sum + (t.details?.pnl || 0), 0);
                    const monthWins = monthTrades.filter(t => (t.details?.pnl || 0) > 0);
                    const monthWinRate = monthTrades.length > 0 ? (monthWins.length / monthTrades.length) * 100 : 0;
                    
                    const monthWinsPnl = monthWins.reduce((sum, t) => sum + (t.details?.pnl || 0), 0);
                    const monthAvgGain = monthWins.length > 0 ? monthWinsPnl / monthWins.length : 0;
                    
                    return (
                      <div key={idx} className="monthly-stacked-card">
                        <div className="monthly-card-header">
                          <div className="month-title-wrap">
                            <h3>{monthKey}</h3>
                            <span className="month-trades-count">{monthTrades.length} trades closed</span>
                          </div>
                          
                          <button 
                            className="month-view-details-btn"
                            onClick={() => {
                              setSelectedLogMonth(monthKey);
                              setActiveTab('trades');
                            }}
                          >
                            Go to Ledger ➔
                          </button>
                        </div>
                        
                        <div className="monthly-card-body">
                          {/* Mini KPIs */}
                          <div className="monthly-card-kpis">
                            <div className="mini-kpi-block">
                              <span className="mini-kpi-lbl">NET PROFIT</span>
                              <strong className={`mini-kpi-val ${monthPnl >= 0 ? 'txt-profit' : 'txt-loss'}`}>
                                {monthPnl >= 0 ? '+' : ''}${monthPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </strong>
                              <span className="mini-kpi-sub">
                                {monthPnl >= 0 ? '🟢 Over average' : '🔴 Under average'}
                              </span>
                            </div>
                            
                            <div className="mini-kpi-block">
                              <span className="mini-kpi-lbl">WIN RATE</span>
                              <strong className="mini-kpi-val txt-profit">
                                {monthWinRate.toFixed(1)}%
                              </strong>
                              <span className="mini-kpi-sub">
                                {monthWinRate >= 50 ? '🟢 Over average (50%)' : '🔴 Under average'}
                              </span>
                            </div>
                            
                            <div className="mini-kpi-block">
                              <span className="mini-kpi-lbl">AVG WIN</span>
                              <strong className="mini-kpi-val txt-profit">
                                +${monthAvgGain.toFixed(0)}
                              </strong>
                              <span className="mini-kpi-sub">Per winning trade</span>
                            </div>
                          </div>
                          
                          {/* Mini Equity Curve */}
                          <div className="monthly-card-chart-wrap">
                            <div className="chart-legend-mini">
                              <span>📈 Monthly Equity Trend</span>
                              <span className="legend-pnl-color">■ Profit / Loss</span>
                            </div>
                            <div className="mini-chart-container">
                              {renderMiniMonthChart(monthTrades, monthPnl)}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
            </div>
          )}

          {/* Tab 5: Weekly Review */}
          {activeTab === 'options' && optionsSubTab === 'weekly' && (
            <div className="panel-grid">
              <div className="grid-col-2">
                <div className="dashboard-block">
                  <h2>🗓️ Publish Weekly Review & Audit Report</h2>
                  <p className="block-desc">Formulate performance summaries and markdown templates</p>
                  
                  <form onSubmit={handleWeeklyReviewSubmit} className="weekly-review-form">
                    <div className="form-row">
                      <div className="form-group">
                        <label>Weekly Net P&L ($)</label>
                        <input 
                          type="number" 
                          step="0.01" 
                          value={wkPnl} 
                          onChange={(e) => setWkPnl(e.target.value)} 
                          required 
                        />
                      </div>
                      <div className="form-group">
                        <label>Discipline Score (1 - 10)</label>
                        <input 
                          type="number" 
                          min="1" 
                          max="10" 
                          value={wkRating} 
                          onChange={(e) => setWkRating(e.target.value)} 
                          required 
                        />
                      </div>
                    </div>
                    <div className="form-group">
                      <label>Trading Mistakes Made</label>
                      <textarea 
                        value={wkMistakes} 
                        onChange={(e) => setWkMistakes(e.target.value)} 
                        rows="3"
                        placeholder="E.g. Flipped NVDA calls before VWAP exit target, overtraded during morning chop."
                      />
                    </div>
                    <div className="form-group">
                      <label>Learnings & Continuous Improvement</label>
                      <textarea 
                        value={wkLearnings} 
                        onChange={(e) => setWkLearnings(e.target.value)} 
                        rows="3"
                        placeholder="E.g. Keep options position sizes small. Let the mathematical strategy play out."
                      />
                    </div>
                    <button type="submit" className="form-submit-btn">Publish Weekly review Markdown Report</button>
                  </form>
                </div>
              </div>

              <div className="grid-sidebar">
                <div className="dashboard-block">
                  <h2>📖 View Past Weekly Reports</h2>
                  <p className="block-desc">Review chronological review templates</p>
                  
                  {weekly.length === 0 ? (
                    <p className="text-muted">No weekly reports published yet.</p>
                  ) : (
                    <div className="weekly-preview-container">
                      <select 
                        value={selectedReview || ''} 
                        onChange={(e) => handleReviewSelectChange(e.target.value)}
                        className="weekly-select"
                      >
                        {weekly.map((w, idx) => (
                          <option key={idx} value={w.filename}>{w.filename}</option>
                        ))}
                      </select>

                      <div className="weekly-review-markdown-box">
                        <pre>{selectedReviewContent}</pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Tab 6: Systematic Trading Pipeline */}
          {activeTab === 'systematic' && (
            <WhiteLightPanel
              state={state}
              systematicStatus={systematicStatus}
              onRefreshState={fetchData}
              onRefreshStatus={fetchSystematicStatus}
              ingestTicker={ingestTicker}
              setIngestTicker={setIngestTicker}
              ingestLoading={ingestLoading}
              handleIngestSubmit={handleIngestSubmit}
              signalTicker={signalTicker}
              setSignalTicker={setSignalTicker}
              signalLoading={signalLoading}
              handleGenerateSignal={handleGenerateSignal}
              executingLoading={executingLoading}
              handleExecuteSignal={handleExecuteSignal}
              fetchSystematicStatus={fetchSystematicStatus}
            />
          )}

          {/* Tab 7: Alpaca Migration */}
          {activeTab === 'alpaca' && (
            <AlpacaPanel
              state={state}
              systematicStatus={systematicStatus}
              onRefreshState={fetchData}
              onRefreshStatus={fetchSystematicStatus}
              ingestTicker={ingestTicker}
              setIngestTicker={setIngestTicker}
              ingestLoading={ingestLoading}
              handleIngestSubmit={handleIngestSubmit}
              signalTicker={signalTicker}
              setSignalTicker={setSignalTicker}
              signalLoading={signalLoading}
              handleGenerateSignal={handleGenerateSignal}
              executingLoading={executingLoading}
              handleExecuteSignal={handleExecuteSignal}
              fetchSystematicStatus={fetchSystematicStatus}
            />
          )}

          {/* Tab 8: Options Trading (Dual-Agent Intraday) */}
          {activeTab === 'options_trading' && (
            <OptionsTradingPanel API_BASE={API_BASE} />
          )}

          {/* Tab 9: Shadow Cortex Decision Engine */}
          {activeTab === 'shadow_cortex' && (
            <ShadowCortexPanel API_BASE={API_BASE} />
          )}

          {/* Tab 10: Whitelight + Shadow Cortex Integrated Master Tab */}
          {activeTab === 'whitelight_cortex' && (
            <WhitelightCortexIntegratedPanel 
              API_BASE={API_BASE}
              state={state}
              trades={trades}
              positions={positions}
              systematicStatus={systematicStatus}
            />
          )}
        </div>
      </main>
      {/* Screenshot Preview Modal */}
      {activePreviewImage && (
        <div className="modal-overlay" onClick={() => setActivePreviewImage(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close-btn" onClick={() => setActivePreviewImage(null)}>×</button>
            <img src={activePreviewImage} alt="Attachment Screenshot Preview" className="modal-image-preview" />
          </div>
        </div>
      )}

      {/* Upload & Drag Drop Modal */}
      {isUploadModalOpen && (
        <div className="kinfo-modal-overlay" onClick={() => { if (!tUploading) { setIsUploadModalOpen(false); setModalFiles([]); } }}>
          <div className="kinfo-modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {tTickerInput.trim() === '' ? '📁 Auto-Import Trades from Screenshot' : '📎 Attach Statements & Screenshots'}
              </h3>
              <button 
                type="button" 
                className="modal-close-x" 
                onClick={() => { setIsUploadModalOpen(false); setModalFiles([]); }}
                disabled={tUploading}
              >
                ×
              </button>
            </div>
            
            <div className="modal-body">
              <div 
                className={`dropzone-area ${isDragging ? 'dragging' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={async (e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  const files = Array.from(e.dataTransfer.files);
                  setModalFiles(prev => [...prev, ...files]);
                }}
                onClick={() => document.getElementById('modal-file-picker').click()}
              >
                <input 
                  id="modal-file-picker"
                  type="file" 
                  multiple 
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const files = Array.from(e.target.files);
                    setModalFiles(prev => [...prev, ...files]);
                  }}
                  disabled={tUploading}
                />
                <div className="dropzone-hint-icon">📂</div>
                <p className="dropzone-text-primary">
                  {tTickerInput.trim() === '' 
                    ? 'Drag & drop transaction screenshot here, or ' 
                    : 'Drag & drop files here, or '}
                  <span>browse</span>
                </p>
                <p className="dropzone-text-secondary">Supports PNG, JPEG, SVG, PDF, CSV, TXT</p>
              </div>

              {modalFiles.length > 0 && (
                <div className="modal-files-list">
                  <h4>Selected Files ({modalFiles.length})</h4>
                  <div className="files-scroll-wrap">
                    {modalFiles.map((file, idx) => (
                      <div key={idx} className="modal-file-row">
                        <span className="file-icon-pill">📄</span>
                        <span className="file-name-text" title={file.name}>
                          {file.name.length > 25 ? file.name.substring(0, 22) + '...' : file.name}
                        </span>
                        <span className="file-size-text">({(file.size / 1024).toFixed(1)} KB)</span>
                        <button 
                          type="button" 
                          className="file-remove-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setModalFiles(prev => prev.filter((_, i) => i !== idx));
                          }}
                          disabled={tUploading}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {tUploading && (
                <div className="modal-uploading-indicator">
                  <span className="spinner-icon">🔄</span> 
                  {tTickerInput.trim() === '' ? 'Processing screenshot & importing trades...' : 'Uploading screenshots and publishing trade...'}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button 
                type="button" 
                className="modal-btn-secondary"
                onClick={() => { setIsUploadModalOpen(false); setModalFiles([]); }}
                disabled={tUploading}
              >
                Cancel
              </button>
              
              {tTickerInput.trim() !== '' && (
                <button 
                  type="button" 
                  className="modal-btn-skip"
                  onClick={async () => {
                    setIsUploadModalOpen(false);
                    await submitTrade([]);
                  }}
                  disabled={tUploading}
                >
                  Skip & Publish
                </button>
              )}

              {tTickerInput.trim() === '' ? (
                <button 
                  type="button" 
                  className="modal-btn-primary"
                  onClick={handleModalImportAndSubmit}
                  disabled={tUploading || modalFiles.length === 0}
                >
                  Upload & Import
                </button>
              ) : (
                <button 
                  type="button" 
                  className="modal-btn-primary"
                  onClick={handleModalUploadAndSubmit}
                  disabled={tUploading || modalFiles.length === 0}
                >
                  Upload & Publish
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
