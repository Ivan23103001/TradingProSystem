import { useEffect, useState, useCallback } from "react";
import TradingChart from "./TradingChart";
import { ErrorBoundary } from "./ErrorBoundary";
import { API_BASE, API_KEY } from "../apiConfig";

interface DashboardData {
  price: string;
  change: string;
  rsi: string;
  atr: string;
  ml_pred: string;
  ml_label: string;
  ml_winrate: string;
  ml_weight: string;
  kelly_size: string;
  score: number;
  signal_text: string;
  volume_imbalance: string;
  volume_scenario: string;
  kill_switch_label: string;
  ticker: string;
  reasoning_lines: string[];
}

interface MarketMapItem {
  ticker: string;
  price: string;
  change: string;
  score: string;
  emoji: string;
  color: string;
}

interface PortfolioData {
  connected: boolean;
  buying_power: string;
  equity: string;
  status: string;
  positions: Array<{
    symbol: string;
    qty: string;
    price: string;
    pnl: string;
    pnl_pct: string;
    side: string;
  }>;
  error?: string;
}

interface TradeHistoryItem {
  id: number;
  fecha: string;
  ticker: string;
  tipo: string;
  precio: string;
  cantidad: string;
  score: number;
  pnl: string;
}

interface SystemStatusData {
  market_open: boolean;
  market_msg: string;
  scanner_active: boolean;
  autobot_active: boolean;
  positions_count: string;
  kill_switch_daily: string;
  kill_switch_weekly: string;
  ai_adaptative_label: string;
  cache_label: string;
  worker_uptime: string;
  worker_connected: boolean;
  is_retraining?: boolean;
  broker_degraded?: boolean;
}

interface ScannerResult {
  ticker: string;
  price: string;
  score: number;
  signal: string;
  ia: string;
}

const DEFAULT_STATE: DashboardData = {
  price: "$298.64",
  change: "+0.01%",
  rsi: "58",
  atr: "$0.94",
  ml_pred: "11%",
  ml_label: "PESIMISTA",
  ml_winrate: "50%",
  ml_weight: "40%",
  kelly_size: "7.5%",
  score: 47,
  signal_text: "ESPERAR",
  volume_imbalance: "Sin Imbalance",
  volume_scenario: "Fase 2: Estándar | 🤖 ML: PESIMISTA",
  kill_switch_label: "Normal",
  ticker: "SPY",
  reasoning_lines: ["[00:00:00] Calibrando consola de decisión central..."]
};

export default function Dashboard() {
  // Core selected states
  const [ticker, setTicker] = useState("SPY");
  const [interval, setInterval] = useState("15m");
  const [period, setPeriod] = useState("5d");

  // UI state
  const [data, setData] = useState<DashboardData>(DEFAULT_STATE);
  const [connected, setConnected] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState("portfolio");
  const [scoreAnim, setScoreAnim] = useState(0);

  // Content states
  const [marketMap, setMarketMap] = useState<MarketMapItem[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [tradeHistory, setTradeHistory] = useState<TradeHistoryItem[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatusData | null>(null);
  const [scannerResults, setScannerResults] = useState<ScannerResult[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);

  // Control Center form states
  const [configWatchlist, setConfigWatchlist] = useState("");
  const [configInterval, setConfigInterval] = useState("15m");
  const [configPeriod, setConfigPeriod] = useState("5d");
  const [configAutoScan, setConfigAutoScan] = useState(false);
  const [configAutoTrade, setConfigAutoTrade] = useState(false);
  const [configTradeAmount, setConfigTradeAmount] = useState(100.0);
  const [configStopLoss, setConfigStopLoss] = useState(8.0);
  const [configTakeProfit, setConfigTakeProfit] = useState(15.0);
  const [configUseAtr, setConfigUseAtr] = useState(true);
  const [configKellyFraction, setConfigKellyFraction] = useState(0.5);
  const [configDirectionMode, setConfigDirectionMode] = useState("BOTH");
  const [configLongAmount, setConfigLongAmount] = useState(100.0);
  const [configShortAmount, setConfigShortAmount] = useState(50.0);
  const [configLongMaxPrice, setConfigLongMaxPrice] = useState(0.0);
  const [configShortMinPrice, setConfigShortMinPrice] = useState(0.0);
  const [savingConfig, setSavingConfig] = useState(false);

  // Animate score bar (no resetea scoreAnim a 0 innecesariamente)
  useEffect(() => {
    const t = setTimeout(() => setScoreAnim(data.score), 200);
    return () => clearTimeout(t);
  }, [data.score]);

  // Load Main Dashboard data (useCallback para evitar recreación en cada render)
  const loadDashboardData = useCallback(() => {
    fetch(`${API_BASE}/api/dashboard-state?ticker=${ticker}&interval=${interval}&period=${period}`)
      .then((r) => r.json())
      .then((json) => {
        if (!json.error) {
          setData(json);
          setConnected(true);
        } else {
          setConnected(false);
        }
      })
      .catch(() => setConnected(false));
  }, [ticker, interval, period]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Refresh Market Map (useCallback para estabilidad de dependencias)
  const loadMarketMap = useCallback(() => {
    fetch(`${API_BASE}/api/market-map?interval=${interval}&period=${period}`)
      .then((r) => r.json())
      .then((json) => {
        if (Array.isArray(json)) setMarketMap(json);
      })
      .catch(() => {});
  }, [interval, period]);

  useEffect(() => {
    loadMarketMap();
  }, [loadMarketMap]);

  // Load Tab Content dynamically
  useEffect(() => {
    if (activeTab === "portfolio") {
      fetch(`${API_BASE}/api/portfolio`)
        .then((r) => r.json())
        .then((json) => setPortfolio(json))
        .catch(() => setPortfolio(null));
    } else if (activeTab === "history") {
      fetch(`${API_BASE}/api/trade-history`)
        .then((r) => r.json())
        .then((json) => {
          if (Array.isArray(json)) setTradeHistory(json);
        })
        .catch(() => setTradeHistory([]));
    } else if (activeTab === "status") {
      fetch(`${API_BASE}/api/system-status`)
        .then((r) => r.json())
        .then((json) => setSystemStatus(json))
        .catch(() => setSystemStatus(null));
    }
  }, [activeTab, ticker]);

  // Fetch config on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/config`)
      .then((r) => r.json())
      .then((c) => {
        setConfigWatchlist(c.tickers || "");
        setConfigInterval(c.interval || "15m");
        setConfigPeriod(c.period || "5d");
        setConfigAutoScan(c.auto_scan || false);
        setConfigAutoTrade(c.auto_trade || false);
        setConfigTradeAmount(c.trade_amount || 100.0);
        setConfigStopLoss(c.stop_loss_pct || 8.0);
        setConfigTakeProfit(c.take_profit_pct || 15.0);
        setConfigUseAtr(c.use_atr_sl !== undefined ? c.use_atr_sl : true);
        setConfigKellyFraction(c.kelly_fraction || 0.5);
        setConfigDirectionMode(c.direction_mode || "BOTH");
        setConfigLongAmount(c.long_amount || 100.0);
        setConfigShortAmount(c.short_amount || 50.0);
        setConfigLongMaxPrice(c.long_max_price || 0.0);
        setConfigShortMinPrice(c.short_min_price || 0.0);
      })
      .catch(() => {});
  }, []);

  // Run Global Scanner
  const runGlobalScan = async () => {
    setScanning(true);
    setScanProgress(20);
    try {
      const resp = await fetch(`${API_BASE}/api/run-scanner?interval=${interval}&period=${period}`, {
        method: "POST"
      });
      setScanProgress(70);
      const json = await resp.json();
      setScanProgress(100);
      if (Array.isArray(json)) {
        setScannerResults(json);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setTimeout(() => {
        setScanning(false);
        setScanProgress(0);
      }, 500);
    }
  };

  // Save Settings from Control Panel
  const saveConfiguration = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingConfig(true);
    try {
      const payload = {
        tickers: configWatchlist,
        interval: configInterval,
        period: configPeriod,
        auto_scan: configAutoScan,
        auto_trade: configAutoTrade,
        trade_amount: Number(configTradeAmount),
        stop_loss_pct: Number(configStopLoss),
        take_profit_pct: Number(configTakeProfit),
        use_atr_sl: configUseAtr,
        kelly_fraction: Number(configKellyFraction),
        direction_mode: configDirectionMode,
        long_amount: Number(configLongAmount),
        short_amount: Number(configShortAmount),
        long_max_price: Number(configLongMaxPrice),
        short_min_price: Number(configShortMinPrice)
      };

      const resp = await fetch(`${API_BASE}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        alert("Configuración centralizada guardada exitosamente.");
        // Sync outer timeframes if changed in config
        setInterval(configInterval);
        setPeriod(configPeriod);
        loadMarketMap();
        loadDashboardData();
      }
    } catch {
      alert("Error guardando la configuración.");
    } finally {
      setSavingConfig(false);
    }
  };

  const isPositive = data.change?.startsWith("+") ?? false;
  const isBuy = data.signal_text === "COMPRAR";
  const isSell = data.signal_text === "VENDER";

  let signalClass = "wait";
  let signalEmoji = "⏸️";
  if (isBuy) {
    signalClass = "buy";
    signalEmoji = "🟢";
  } else if (isSell) {
    signalClass = "sell";
    signalEmoji = "🔴";
  }

  let scoreClass = "neutral";
  if (data.score >= 60) scoreClass = "bull";
  else if (data.score <= 40) scoreClass = "bear";

  return (
    <div className="dashboard">
      {/* ── Header ─────────────────────────────────────────── */}
      <header className="header">
        <div className="header-brand">
          <div className="header-icon">🛡️</div>
          <div>
            <div className="header-title">
              TradingProSystem <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: "normal" }}>v5.0 · Adaptive AI</span>
            </div>
            <div className="header-sub">SMC · Volume Imbalances · Ensamble RF+GB · Kill Switches · Kelly Dinámico</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          {/* Timeframe shortcuts */}
          <div className="timeframe-bar" style={{ display: "flex", gap: "4px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "8px", padding: "3px" }}>
            {["1m", "5m", "15m", "1h", "1d"].map((tf) => (
              <button
                key={tf}
                onClick={() => setInterval(tf)}
                style={{
                  background: interval === tf ? "var(--bg-hover)" : "none",
                  border: "none",
                  color: interval === tf ? "var(--cyan)" : "var(--text-muted)",
                  padding: "4px 8px",
                  fontSize: "11px",
                  borderRadius: "5px",
                  cursor: "pointer",
                  fontWeight: interval === tf ? "bold" : "normal"
                }}
              >
                {tf}
              </button>
            ))}
          </div>
          <div className="status-badge">
            <span className={`status-dot ${connected ? "live" : ""}`} />
            {connected ? "API Conectada · " + ticker : "Demo Mode · " + ticker}
          </div>
        </div>
      </header>

      {/* ── KPI Row ────────────────────────────────────────── */}
      <div className="kpi-row">
        <div className="kpi-card">
          <div className="kpi-label">Precio Actual</div>
          <div className="kpi-value">{data.price}</div>
          <div className="kpi-sub">{ticker} en vivo</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Cambio 24h</div>
          <div className={`kpi-value ${isPositive ? "green" : "red"}`}>{data.change}</div>
          <div className="kpi-sub">vs cierre anterior</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">RSI (14)</div>
          <div className="kpi-value">{data.rsi}</div>
          <div className="kpi-sub">momentum local</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">ATR Volatilidad</div>
          <div className="kpi-value">{data.atr}</div>
          <div className="kpi-sub">análisis de rango</div>
        </div>
      </div>

      {/* ── Heatmap (Market Map) ──────────────────────────── */}
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "14px", padding: "12px 16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div style={{ fontSize: "11px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}>🗺️ Mapa del Mercado</div>
          <div style={{ fontSize: "10px", color: "var(--text-dim)" }}>Haz clic en un activo para cargar su análisis y gráfico</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: "8px" }}>
          {marketMap.map((item) => (
            <button
              key={item.ticker}
              onClick={() => setTicker(item.ticker)}
              style={{
                background: ticker === item.ticker ? "var(--bg-hover)" : "rgba(255,255,255,0.02)",
                border: ticker === item.ticker ? "1px solid var(--cyan)" : "1px solid var(--border)",
                borderRadius: "8px",
                padding: "8px 10px",
                color: "var(--text-main)",
                cursor: "pointer",
                textAlign: "left",
                display: "flex",
                flexDirection: "column",
                gap: "2px",
                transition: "all 0.2s"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}>
                <span style={{ fontWeight: "bold", fontSize: "12px" }}>{item.emoji} {item.ticker}</span>
                <span style={{ fontSize: "10px", padding: "1px 5px", borderRadius: "100px", background: item.color === "green" ? "rgba(16,185,129,0.12)" : item.color === "red" ? "rgba(239,68,68,0.12)" : "rgba(255,255,255,0.05)", color: item.color === "green" ? "var(--green)" : item.color === "red" ? "var(--red)" : "var(--text-muted)" }}>
                  {item.score}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", width: "100%", fontSize: "11px", fontFamily: "monospace", marginTop: "2px" }}>
                <span>{item.price}</span>
                <span style={{ color: (item.change?.startsWith("+") ?? false) ? "var(--green)" : "var(--red)" }}>{item.change}</span>
              </div>
            </button>
          ))}
          {marketMap.length === 0 && (
            <div style={{ gridColumn: "1/-1", textAlign: "center", padding: "12px", color: "var(--text-muted)", fontSize: "12px" }}>
              {configWatchlist.trim() === "" ? "La Watchlist está vacía. Añade activos en el Panel." : "Cargando mapa de activos de la Watchlist..."}
            </div>
          )}
        </div>
      </div>

      {/* ── Main Grid ──────────────────────────────────────── */}
      <div className="main-grid" style={{ gridTemplateColumns: `${isSidebarCollapsed ? "0px" : "340px"} 1fr 280px` }}>
        
        {/* Collapsible Left Sidebar */}

        {/* Chart Panel & Console */}
        <aside className="control-sidebar" style={{ 
          width: isSidebarCollapsed ? "0px" : "340px",
          opacity: isSidebarCollapsed ? 0 : 1,
          transition: "all 0.3s ease",
          background: "var(--bg-card)",
          borderLeft: "1px solid var(--border)",
          padding: "16px",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "16px"
        }}>
              <h3 style={{ fontSize: "14px", fontWeight: "bold", marginBottom: "16px" }}>⚡ PRO TERMINAL — Panel de Control Central</h3>
              
              <form onSubmit={saveConfiguration} style={{ display: "grid", gridTemplateColumns: "1fr", gap: "16px" }}>
                
                {/* Watchlist & Sizing */}
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>📋 Activos de la Watchlist (separados por coma)</label>
                    <textarea
                      value={configWatchlist}
                      onChange={(e) => setConfigWatchlist(e.target.value)}
                      style={{ width: "100%", height: "60px", background: "#05080E", border: "1px solid var(--border-lit)", borderRadius: "8px", padding: "8px", color: "var(--text-main)", fontSize: "12px", fontFamily: "monospace", resize: "none" }}
                    />
                    {configWatchlist.trim() !== "" && (() => {
                      const tickers = configWatchlist.split(",").map(t => t.trim().toUpperCase()).filter(t => t !== "");
                      const invalid = tickers.filter(t => !/^[A-Z0-9.\-]{1,10}$/.test(t));
                      return invalid.length > 0 ? (
                        <div style={{ color: "var(--red)", fontSize: "10px", marginTop: "4px", fontFamily: "monospace" }}>
                          ⚠️ Tickers inválidos: {invalid.join(", ")} (deben ser 1-10 caracteres: A-Z, 0-9, ., -)
                        </div>
                      ) : null;
                    })()}
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>⏱️ Intervalo Velas</label>
                      <select
                        value={configInterval}
                        onChange={(e) => {
                          setConfigInterval(e.target.value);
                          setInterval(e.target.value);
                        }}
                        style={{ width: "100%", background: "#05080E", border: "1px solid var(--border-lit)", borderRadius: "8px", padding: "8px", color: "var(--text-main)", fontSize: "12px" }}
                      >
                        <option value="1m">1 Minuto</option>
                        <option value="5m">5 Minutos</option>
                        <option value="15m">15 Minutos</option>
                        <option value="1h">1 Hora</option>
                        <option value="1d">1 Día</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>⏱️ Período Historial</label>
                      <select
                        value={configPeriod}
                        onChange={(e) => {
                          setConfigPeriod(e.target.value);
                          setPeriod(e.target.value);
                        }}
                        style={{ width: "100%", background: "#05080E", border: "1px solid var(--border-lit)", borderRadius: "8px", padding: "8px", color: "var(--text-main)", fontSize: "12px" }}
                      >
                        <option value="1d">1 Día</option>
                        <option value="5d">5 Días</option>
                        <option value="1mo">1 Mes</option>
                        <option value="6mo">6 Meses</option>
                        <option value="1y">1 Año</option>
                      </select>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginTop: "4px" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={configAutoScan}
                        onChange={(e) => setConfigAutoScan(e.target.checked)}
                      />
                      Activar Auto-Scanner
                    </label>
                    <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={configAutoTrade}
                        onChange={(e) => setConfigAutoTrade(e.target.checked)}
                      />
                      Activar Auto-Trading Bot
                    </label>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>💰 Monto Operación Base ($ USD)</label>
                    <input
                      type="number"
                      value={configTradeAmount}
                      onChange={(e) => setConfigTradeAmount(Number(e.target.value))}
                      style={{ width: "100%", background: "#05080E", border: "1px solid var(--border-lit)", borderRadius: "8px", padding: "8px", color: "var(--text-main)", fontSize: "12px" }}
                    />
                  </div>
                </div>

                {/* Risk Control */}
                <div style={{ display: "flex", flexDirection: "column", gap: "10px", background: "rgba(255,255,255,0.01)", border: "1px solid rgba(255,255,255,0.03)", borderRadius: "8px", padding: "12px" }}>
                  <div style={{ fontSize: "11px", fontWeight: "bold", color: "var(--cyan)", textTransform: "uppercase" }}>🛡️ Control de Riesgo y Operación</div>
                  
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)" }}>Stop Loss % ({configStopLoss}%)</label>
                      <input
                        type="range"
                        min="1" max="25"
                        value={configStopLoss}
                        onChange={(e) => setConfigStopLoss(Number(e.target.value))}
                        style={{ width: "100%" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)" }}>Take Profit % ({configTakeProfit}%)</label>
                      <input
                        type="range"
                        min="2" max="50"
                        value={configTakeProfit}
                        onChange={(e) => setConfigTakeProfit(Number(e.target.value))}
                        style={{ width: "100%" }}
                      />
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", alignItems: "center" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={configUseAtr}
                        onChange={(e) => setConfigUseAtr(e.target.checked)}
                      />
                      ATR SL Dinámico
                    </label>
                    <div>
                      <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)" }}>Fracción Kelly ({configKellyFraction})</label>
                      <input
                        type="range"
                        min="0.1" max="1" step="0.1"
                        value={configKellyFraction}
                        onChange={(e) => setConfigKellyFraction(Number(e.target.value))}
                        style={{ width: "100%" }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)", marginBottom: "4px" }}>Dirección Permitida</label>
                    <div style={{ display: "flex", gap: "12px" }}>
                      {["LONG_ONLY", "SHORT_ONLY", "BOTH"].map((m) => (
                        <label key={m} style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", cursor: "pointer" }}>
                          <input
                            type="radio"
                            name="direction_mode"
                            value={m}
                            checked={configDirectionMode === m}
                            onChange={(e) => setConfigDirectionMode(e.target.value)}
                          />
                          {m}
                        </label>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)" }}>📈 Monto LONG ($)</label>
                      <input
                        type="number"
                        value={configLongAmount}
                        onChange={(e) => setConfigLongAmount(Number(e.target.value))}
                        style={{ width: "100%", background: "#05080E", border: "1px solid var(--border-lit)", borderRadius: "6px", padding: "6px", color: "var(--text-main)", fontSize: "11px" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)" }}>📉 Monto SHORT ($)</label>
                      <input
                        type="number"
                        value={configShortAmount}
                        onChange={(e) => setConfigShortAmount(Number(e.target.value))}
                        style={{ width: "100%", background: "#05080E", border: "1px solid var(--border-lit)", borderRadius: "6px", padding: "6px", color: "var(--text-main)", fontSize: "11px" }}
                      />
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)" }}>Precio Máx LONG</label>
                      <input
                        type="number"
                        value={configLongMaxPrice}
                        onChange={(e) => setConfigLongMaxPrice(Number(e.target.value))}
                        style={{ width: "100%", background: "#05080E", border: "1px solid var(--border-lit)", borderRadius: "6px", padding: "6px", color: "var(--text-main)", fontSize: "11px" }}
                        placeholder="0 = Sin Límite"
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "10px", color: "var(--text-muted)" }}>Precio Mín SHORT</label>
                      <input
                        type="number"
                        value={configShortMinPrice}
                        onChange={(e) => setConfigShortMinPrice(Number(e.target.value))}
                        style={{ width: "100%", background: "#05080E", border: "1px solid var(--border-lit)", borderRadius: "6px", padding: "6px", color: "var(--text-main)", fontSize: "11px" }}
                        placeholder="0 = Sin Límite"
                      />
                    </div>
                  </div>
                </div>

                <div style={{ gridColumn: "1/-1", display: "flex", justifyContent: "flex-end", marginTop: "10px" }}>
                  <button
                    type="submit"
                    disabled={savingConfig}
                    style={{
                      background: "var(--cyan)",
                      border: "none",
                      color: "#000",
                      fontWeight: "bold",
                      padding: "10px 20px",
                      borderRadius: "8px",
                      cursor: savingConfig ? "not-allowed" : "pointer",
                      fontSize: "12px"
                    }}
                  >
                    {savingConfig ? "Guardando..." : "💾 Guardar Configuración Central"}
                  </button>
                </div>
              </form>
        </aside>
        <section className="chart-panel" style={{ position: "relative" }}>
          
          {/* Collapse toggle button */}
          <button
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            style={{
              position: "absolute",
              left: "10px",
              top: "14px",
              zIndex: 10,
              background: "var(--bg-hover)",
              border: "1px solid var(--border-lit)",
              color: "var(--text-main)",
              borderRadius: "6px",
              padding: "4px 8px",
              fontSize: "11px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px"
            }}
            title={isSidebarCollapsed ? "Mostrar panel" : "Esconder panel"}
          >
            {isSidebarCollapsed ? "▶ Mostrar Panel" : "◀ Ocultar Panel"}
          </button>

          {/* Chart Header */}
          <div className="chart-header" style={{ paddingLeft: isSidebarCollapsed ? "130px" : "130px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="chart-ticker" style={{ color: "var(--cyan)" }}>{ticker}</span>
              <span className="chart-period">· {interval} ({period})</span>
              
              <div className="legend" style={{ marginLeft: 16, display: "flex", gap: "10px" }}>
                <span className="legend-item" style={{ fontSize: "10px", display: "flex", alignItems: "center", gap: "4px" }}>
                  <span className="legend-line" style={{ background: "#F59E0B", width: "10px", height: "2px", display: "inline-block" }} /> EMA 20
                </span>
                <span className="legend-item" style={{ fontSize: "10px", display: "flex", alignItems: "center", gap: "4px" }}>
                  <span className="legend-line" style={{ background: "#8B5CF6", width: "10px", height: "2px", display: "inline-block" }} /> EMA 50
                </span>
                <span className="legend-item" style={{ fontSize: "10px", display: "flex", alignItems: "center", gap: "4px" }}>
                  <span className="legend-line" style={{ background: "#3B82F6", width: "10px", height: "2px", display: "inline-block" }} /> EMA 200
                </span>
              </div>
            </div>
            <span className={`chart-price-badge ${isPositive ? "green" : "red"}`}>
              {data.price} &nbsp; {data.change}
            </span>
          </div>

          {/* Chart Canvas */}
          <div className="chart-body">
            <ErrorBoundary>
              <TradingChart ticker={ticker} interval={interval} period={period} />
            </ErrorBoundary>
          </div>

          {/* Real-time reasoning console */}
          <div style={{ 
            background: "#05080E", 
            borderTop: "1px solid var(--border)", 
            padding: "12px 18px", 
            fontFamily: "monospace",
            fontSize: "11px"
          }}>
            <div style={{ color: "var(--text-muted)", fontWeight: "bold", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
              🧠 Consola de decisión en tiempo real
            </div>
            <div style={{ 
              maxHeight: "100px", 
              overflowY: "auto", 
              display: "flex", 
              flexDirection: "column",
              gap: "4px",
              color: "#38BDF8"
            }}>
              {data.reasoning_lines.map((line, i) => (
                <div key={i} style={{ 
                  lineHeight: "1.4",
                  borderLeft: "2px solid #1E293B",
                  paddingLeft: "8px",
                  color: line.includes("✅") || line.includes("COMPRAR") ? "var(--green)" : line.includes("⚠️") || line.includes("VENDER") || line.includes("🚨") ? "var(--red)" : "#38BDF8"
                }}>
                  {line}
                </div>
              ))}
            </div>
          </div>
        </section>
        <aside className="sidebar" style={{ 
          width: "280px", 
          overflow: "hidden", 
          transition: "all 0.3s ease",
          opacity: 1
        }}>
          {/* IA Ensamble */}
          <div className="card">
            <div className="card-header"><span className="card-icon">🤖</span> IA Ensamble</div>
            <div className="card-value-big">{data.ml_pred}</div>
            <div className={`tag ${data.ml_label === "OPTIMISTA" ? "green" : data.ml_label === "PESIMISTA" ? "red" : "amber"}`}>
              {data.ml_label === "OPTIMISTA" ? "▲" : data.ml_label === "PESIMISTA" ? "▼" : "◆"} {data.ml_label}
            </div>
            <div style={{ display: "flex", gap: "10px", marginTop: "8px", fontSize: "10px", color: "var(--text-muted)" }}>
              <span>WinRate: <b style={{ color: "var(--cyan)" }}>{data.ml_winrate}</b></span>
              <span>Peso IA: <b style={{ color: "var(--violet)" }}>{data.ml_weight}</b></span>
            </div>
          </div>

          {/* Kelly Sizing */}
          <div className="card">
            <div className="card-header"><span className="card-icon">💼</span> Kelly Sizing</div>
            <div className="card-value-big" style={{ color: "var(--cyan)" }}>{data.kelly_size}</div>
            <div className="card-sub">del capital disponible</div>
          </div>

          {/* Score Global */}
          <div className="card">
            <div className="card-header"><span className="card-icon">📊</span> Score Global</div>
            <div className="card-value-big">
              {data.score}
              <span style={{ fontSize: 16, color: "var(--text-muted)", fontWeight: 400 }}>/100</span>
            </div>
            <div className="score-bar-bg">
              <div className={`score-bar-fill ${scoreClass}`} style={{ width: `${scoreAnim}%` }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
              <span style={{ fontSize: 10, color: "var(--text-dim)" }}>🔴 Vender</span>
              <span style={{ fontSize: 10, color: "var(--text-dim)" }}>🟢 Comprar</span>
            </div>
          </div>

          {/* Señal Sistema */}
          <div className={`signal-card ${signalClass}`}>
            <div className="card-header"><span className="card-icon">🛡️</span> Señal Sistema</div>
            <div className={`signal-text ${signalClass}`}>{signalEmoji} {data.signal_text}</div>
          </div>
        </aside>
        {/* Right Sidebar - Control Center */}
      </div>

      {/* ── Tabs Section ──────────────────────────────────── */}
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "14px", overflow: "hidden", marginTop: "16px" }}>
        
        {/* Tab Selection */}
        <div style={{ 
          display: "flex", 
          borderBottom: "1px solid var(--border)", 
          background: "rgba(255,255,255,0.01)",
          overflowX: "auto"
        }}>
          {[
            { id: "portfolio", label: "📊 Portafolio Vivo" },
            { id: "history", label: "📜 Historial de Trades" },
            { id: "scanner", label: "🔬 Scanner Global" },
            { id: "status", label: "🔗 Estado del Sistema" }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: "14px 20px",
                background: activeTab === tab.id ? "var(--bg-hover)" : "none",
                border: "none",
                borderBottom: activeTab === tab.id ? "2px solid var(--cyan)" : "none",
                color: activeTab === tab.id ? "var(--text-main)" : "var(--text-muted)",
                fontSize: "12px",
                fontWeight: "bold",
                cursor: "pointer",
                transition: "all 0.2s"
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Contents */}
        <div style={{ padding: "20px" }}>
          
          {/* TAB: Live Portfolio */}
          {activeTab === "portfolio" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "14px", fontWeight: "bold" }}>Posiciones Abiertas en Alpaca</h3>
                {portfolio && portfolio.connected && (
                  <div style={{ display: "flex", gap: "24px" }}>
                    <div><span style={{ color: "var(--text-muted)", fontSize: "11px" }}>Capital Total:</span> <b style={{ fontSize: "14px" }}>{portfolio.equity}</b></div>
                    <div><span style={{ color: "var(--text-muted)", fontSize: "11px" }}>Poder Compra:</span> <b style={{ fontSize: "14px" }}>{portfolio.buying_power}</b></div>
                    <div><span style={{ color: "var(--text-muted)", fontSize: "11px" }}>Broker Status:</span> <b style={{ fontSize: "14px", color: "var(--green)" }}>{portfolio.status.toUpperCase()}</b></div>
                  </div>
                )}
              </div>

              {portfolio && portfolio.connected ? (
                portfolio.positions && portfolio.positions.length > 0 ? (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-muted)", textTransform: "uppercase", fontSize: "10px" }}>
                        <th style={{ padding: "10px" }}>Activo</th>
                        <th style={{ padding: "10px" }}>Dirección</th>
                        <th style={{ padding: "10px" }}>Cantidad</th>
                        <th style={{ padding: "10px" }}>Precio Actual</th>
                        <th style={{ padding: "10px" }}>PnL No Realizado</th>
                        <th style={{ padding: "10px" }}>% PnL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portfolio.positions.map((pos) => (
                        <tr key={pos.symbol} style={{ borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
                          <td style={{ padding: "10px" }}>
                            <button
                              onClick={() => setTicker(pos.symbol)}
                              style={{ background: "none", border: "none", color: "var(--cyan)", fontWeight: "bold", cursor: "pointer", textDecoration: "underline", padding: 0 }}
                            >
                              {pos.symbol}
                            </button>
                          </td>
                          <td style={{ padding: "10px" }}>
                            <span style={{ padding: "2px 8px", borderRadius: "100px", background: pos.side === "LONG" ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.12)", color: pos.side === "LONG" ? "var(--green)" : "var(--red)", fontSize: "10px", fontWeight: "bold" }}>
                              {pos.side}
                            </span>
                          </td>
                          <td style={{ padding: "10px", fontFamily: "monospace" }}>{pos.qty}</td>
                          <td style={{ padding: "10px", fontFamily: "monospace" }}>{pos.price}</td>
                          <td style={{ padding: "10px", fontFamily: "monospace", color: (pos.pnl?.startsWith("+") ?? false) ? "var(--green)" : "var(--red)", fontWeight: "bold" }}>{pos.pnl}</td>
                          <td style={{ padding: "10px", fontFamily: "monospace", color: (pos.pnl_pct?.startsWith("+") ?? false) ? "var(--green)" : "var(--red)", fontWeight: "bold" }}>{pos.pnl_pct}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                    📭 No hay posiciones abiertas actualmente.
                  </div>
                )
              ) : (
                <div style={{ textAlign: "center", padding: "30px", color: "var(--red)" }}>
                  ⚠️ {portfolio?.error || "Desconectado de Alpaca. Ingrese credenciales válidas en su archivo .env."}
                </div>
              )}
            </div>
          )}

          {/* TAB: Trade History */}
          {activeTab === "history" && (
            <div>
              <h3 style={{ fontSize: "14px", fontWeight: "bold", marginBottom: "16px" }}>Historial de Operaciones Realizadas</h3>
              
              {tradeHistory.length > 0 ? (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-muted)", textTransform: "uppercase", fontSize: "10px" }}>
                      <th style={{ padding: "10px" }}>Fecha / Hora</th>
                      <th style={{ padding: "10px" }}>Activo</th>
                      <th style={{ padding: "10px" }}>Acción</th>
                      <th style={{ padding: "10px" }}>Precio Entrada</th>
                      <th style={{ padding: "10px" }}>Cantidad</th>
                      <th style={{ padding: "10px" }}>Score</th>
                      <th style={{ padding: "10px" }}>PnL Cerrado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tradeHistory.map((trade) => (
                      <tr key={trade.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
                        <td style={{ padding: "10px", color: "var(--text-muted)" }}>{trade.fecha}</td>
                        <td style={{ padding: "10px" }}>
                          <button
                            onClick={() => setTicker(trade.ticker)}
                            style={{ background: "none", border: "none", color: "var(--cyan)", fontWeight: "bold", cursor: "pointer", textDecoration: "underline", padding: 0 }}
                          >
                            {trade.ticker}
                          </button>
                        </td>
                        <td style={{ padding: "10px" }}>
                          <span style={{ padding: "2px 8px", borderRadius: "100px", background: trade.tipo.includes("BUY") || trade.tipo.includes("LONG") ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.12)", color: trade.tipo.includes("BUY") || trade.tipo.includes("LONG") ? "var(--green)" : "var(--red)", fontSize: "10px", fontWeight: "bold" }}>
                            {trade.tipo}
                          </span>
                        </td>
                        <td style={{ padding: "10px", fontFamily: "monospace" }}>{trade.precio}</td>
                        <td style={{ padding: "10px", fontFamily: "monospace" }}>{trade.cantidad}</td>
                        <td style={{ padding: "10px" }}>
                          <span style={{ color: trade.score >= 65 ? "var(--green)" : trade.score <= 35 ? "var(--red)" : "var(--text-muted)", fontWeight: "bold" }}>
                            {trade.score}
                          </span>
                        </td>
                        <td style={{ 
                          padding: "10px", 
                          fontFamily: "monospace", 
                          color: trade.pnl === "N/A" || !trade.pnl ? "var(--text-muted)" : (trade.pnl?.startsWith("-") ?? false) ? "var(--red)" : "var(--green)",
                          fontWeight: "bold" 
                        }}>
                          {trade.pnl || "Abierta / En Curso"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                  📜 Aún no hay operaciones registradas en `trade_history.db`.
                </div>
              )}
            </div>
          )}

          {/* TAB: Global Scanner */}
          {activeTab === "scanner" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <div>
                  <h3 style={{ fontSize: "14px", fontWeight: "bold" }}>Scanner del Portafolio Watchlist</h3>
                  <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>Busca señales de compra/venta institucionales en toda la watchlist.</p>
                </div>
                <button
                  onClick={runGlobalScan}
                  disabled={scanning}
                  style={{
                    background: "linear-gradient(135deg, var(--green), var(--cyan))",
                    border: "none",
                    color: "#000",
                    fontWeight: "bold",
                    padding: "8px 16px",
                    borderRadius: "8px",
                    cursor: scanning ? "not-allowed" : "pointer",
                    fontSize: "12px"
                  }}
                >
                  {scanning ? "🔍 Escaneando..." : "◆ Iniciar Escaneo"}
                </button>
              </div>

              {scanning && (
                <div style={{ marginBottom: "16px" }}>
                  <div style={{ height: "4px", background: "var(--bg-hover)", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ height: "100%", background: "var(--cyan)", width: `${scanProgress}%`, transition: "width 0.2s" }} />
                  </div>
                </div>
              )}

              {scannerResults.length > 0 ? (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-muted)", textTransform: "uppercase", fontSize: "10px" }}>
                      <th style={{ padding: "10px" }}>Activo</th>
                      <th style={{ padding: "10px" }}>Precio</th>
                      <th style={{ padding: "10px" }}>Score Global</th>
                      <th style={{ padding: "10px" }}>Dirección Señal</th>
                      <th style={{ padding: "10px" }}>Modelo ML Bias</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scannerResults.map((res) => (
                      <tr key={res.ticker} style={{ borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
                        <td style={{ padding: "10px" }}>
                          <button
                            onClick={() => setTicker(res.ticker)}
                            style={{ background: "none", border: "none", color: "var(--cyan)", fontWeight: "bold", cursor: "pointer", textDecoration: "underline", padding: 0 }}
                          >
                            {res.ticker}
                          </button>
                        </td>
                        <td style={{ padding: "10px", fontFamily: "monospace" }}>{res.price}</td>
                        <td style={{ padding: "10px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span style={{ fontWeight: "bold", minWidth: "24px" }}>{res.score}</span>
                            <div style={{ width: "80px", height: "4px", background: "var(--bg-hover)", borderRadius: "4px", overflow: "hidden" }}>
                              <div style={{ 
                                height: "100%", 
                                width: `${res.score}%`, 
                                background: res.score >= 65 ? "var(--green)" : res.score <= 35 ? "var(--red)" : "var(--amber)"
                              }} />
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: "10px" }}>
                          <span style={{ 
                            padding: "2px 8px", 
                            borderRadius: "100px", 
                            background: res.signal.includes("COMPRAR") ? "rgba(16,185,129,0.12)" : res.signal.includes("VENDER") ? "rgba(239,68,68,0.12)" : "rgba(255,255,255,0.05)", 
                            color: res.signal.includes("COMPRAR") ? "var(--green)" : res.signal.includes("VENDER") ? "var(--red)" : "var(--text-muted)",
                            fontSize: "10px", 
                            fontWeight: "bold" 
                          }}>
                            {res.signal}
                          </span>
                        </td>
                        <td style={{ padding: "10px", fontFamily: "monospace" }}>
                          {res.ia}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                  🔬 Pulsa "Iniciar Escaneo" para analizar la watchlist en tiempo real.
                </div>
              )}
            </div>
          )}


          {/* TAB: System Status */}
          {activeTab === "status" && (
            <div>
              <h3 style={{ fontSize: "14px", fontWeight: "bold", marginBottom: "16px" }}>Estado Operativo de Trading Pro System</h3>
              
              {systemStatus ? (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
                  
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Mercado SPY</span>
                      <b style={{ color: systemStatus.market_open ? "var(--green)" : "var(--red)" }}>
                        {systemStatus.market_open ? "🟢 ABIERTO" : "🔴 CERRADO"} ({systemStatus.market_msg})
                      </b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Auto-Scanner</span>
                      <b>{systemStatus.scanner_active ? "🟢 ACTIVO" : "⚪ INACTIVO"}</b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Auto-Bot Executer</span>
                      <b>{systemStatus.autobot_active ? "🟢 EJECUTANDO" : "⚪ APAGADO"}</b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Cupo Posiciones Abiertas</span>
                      <b>{systemStatus.positions_count}</b>
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Circuit Breaker Diario (Kill Switch)</span>
                      <b style={{ color: systemStatus.kill_switch_daily.includes("ACTIVO") ? "var(--red)" : "var(--green)" }}>{systemStatus.kill_switch_daily}</b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Cuarentena Semanal (Kill Switch)</span>
                      <b style={{ color: systemStatus.kill_switch_weekly.includes("ACTIVO") ? "var(--red)" : "var(--green)" }}>{systemStatus.kill_switch_weekly}</b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Win-Rate IA &amp; Peso</span>
                      <b>{systemStatus.ai_adaptative_label}</b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Memoria Caché Universal</span>
                      <b style={{ fontSize: "11px" }}>{systemStatus.cache_label}</b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Estado Worker Background</span>
                      <b style={{ color: systemStatus.worker_connected ? "var(--green)" : "var(--red)" }}>
                        {systemStatus.worker_connected ? `🟢 Conectado (${systemStatus.worker_uptime})` : "🔴 Desconectado (Ejecutar python bot_worker.py)"}
                      </b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Broker Alpaca API</span>
                      <b style={{ color: systemStatus.broker_degraded ? "var(--red)" : "var(--green)" }}>
                        {systemStatus.broker_degraded ? "🔴 DEGRADADO (Rate Limits / Timeouts)" : "🟢 Operativo"}
                      </b>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Modelo ML Background</span>
                      <b style={{ color: systemStatus.is_retraining ? "var(--amber)" : "var(--green)" }}>
                        {systemStatus.is_retraining ? "🔄 Optimizando Modelos..." : "✅ Actualizado"}
                      </b>
                    </div>
                  </div>

                  {/* Critical Banners */}
                  {systemStatus.broker_degraded && (
                    <div style={{
                      marginTop: "16px",
                      padding: "12px 16px",
                      background: "rgba(239,68,68,0.1)",
                      border: "1px solid rgba(239,68,68,0.25)",
                      borderRadius: "8px",
                      color: "var(--red)",
                      fontSize: "12px",
                      fontWeight: "bold",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px"
                    }}>
                      <span style={{ fontSize: "16px" }}>🚨</span>
                      Alpaca Markets API Degradada — el bot está aplicando Exponential Backoff. Las órdenes se reintentarán automáticamente.
                    </div>
                  )}
                  {systemStatus.is_retraining && (
                    <div style={{
                      marginTop: "12px",
                      padding: "12px 16px",
                      background: "rgba(245,158,11,0.1)",
                      border: "1px solid rgba(245,158,11,0.25)",
                      borderRadius: "8px",
                      color: "var(--amber)",
                      fontSize: "12px",
                      fontWeight: "bold",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px"
                    }}>
                      <span style={{ fontSize: "16px" }}>🧠</span>
                      Reentrenamiento ML en curso — el sistema sigue escaneando y protegiendo posiciones sin interrupción.
                    </div>
                  )}

                </div>
              ) : (
                <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)" }}>
                  Cargando estado del sistema...
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
