import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createSeriesMarkers,
} from "lightweight-charts";
import { API_BASE } from "../apiConfig";

interface TradingChartProps {
  ticker: string;
  interval: string;
  period: string;
}

export default function TradingChart({ ticker, interval, period }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    setLoading(true);
    setError(null);

    let chart: any = null;

    const fetchDataAndRender = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/chart-data?ticker=${ticker}&interval=${interval}&period=${period}`
        );
        if (!response.ok) {
          throw new Error(`Error en API: ${response.statusText}`);
        }
        const data = await response.json();

        if (!data.candles || data.candles.length === 0) {
          throw new Error("No hay suficientes datos de velas.");
        }

        // Clean up the container first
        if (containerRef.current) {
          containerRef.current.innerHTML = "";
        }

        // Create Chart
        chart = createChart(containerRef.current!, {
          layout: {
            background: { type: ColorType.Solid, color: "#0B0E14" },
            textColor: "#94A3B8",
            fontSize: 11,
            fontFamily: "JetBrains Mono, monospace",
          },
          grid: {
            vertLines: { color: "#1E293B" },
            horzLines: { color: "#1E293B" },
          },
          crosshair: { mode: CrosshairMode.Normal },
          rightPriceScale: { borderColor: "#334155" },
          timeScale: {
            borderColor: "#334155",
            timeVisible: true,
            secondsVisible: false,
          },
          width: containerRef.current!.clientWidth || 600,
          height: 480,
        });

        // Candlesticks Series
        const candleSeries = chart.addSeries(CandlestickSeries, {
          upColor: "#10B981",
          downColor: "#EF4444",
          borderVisible: false,
          wickUpColor: "#10B981",
          wickDownColor: "#EF4444",
        });
        candleSeries.setData(
          data.candles.map((c: any) => ({
            time: c.time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }))
        );

        // Volume Histogram
        const volSeries = chart.addSeries(HistogramSeries, {
          priceFormat: { type: "volume" },
          priceScaleId: "", // overlay volume
        });
        volSeries.priceScale().applyOptions({
          scaleMargins: { top: 0.8, bottom: 0 },
        });
        volSeries.setData(
          data.candles.map((c: any) => ({
            time: c.time,
            value: c.volume,
            color: c.vol_color,
          }))
        );

        // EMA Trend Lines
        if (data.ema20 && data.ema20.length > 0) {
          const ema20Line = chart.addSeries(LineSeries, {
            color: "#F59E0B",
            lineWidth: 1.5,
            title: "EMA 20",
          });
          ema20Line.setData(data.ema20);
        }

        if (data.ema50 && data.ema50.length > 0) {
          const ema50Line = chart.addSeries(LineSeries, {
            color: "#8B5CF6",
            lineWidth: 1.2,
            title: "EMA 50",
          });
          ema50Line.setData(data.ema50);
        }

        if (data.ema200 && data.ema200.length > 0) {
          const ema200Line = chart.addSeries(LineSeries, {
            color: "#3B82F6",
            lineWidth: 1.0,
            title: "EMA 200",
          });
          ema200Line.setData(data.ema200);
        }

        // Sweeps Markers
        if (data.markers && data.markers.length > 0) {
          createSeriesMarkers(candleSeries, data.markers);
        }

        // Bullish Order Block Price Line
        if (data.bullish_ob > 0) {
          candleSeries.createPriceLine({
            price: data.bullish_ob,
            color: "rgba(16, 185, 129, 0.6)",
            lineWidth: 1.5,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "Zona Compra (OB)",
          });
        }

        // Bearish Order Block Price Line
        if (data.bearish_ob > 0) {
          candleSeries.createPriceLine({
            price: data.bearish_ob,
            color: "rgba(239, 68, 68, 0.6)",
            lineWidth: 1.5,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "Zona Venta (OB)",
          });
        }

        chart.timeScale().fitContent();
        setLoading(false);
      } catch (err: any) {
        console.error(err);
        setError(err.message || "Error al cargar los datos del gráfico.");
        setLoading(false);
      }
    };

    fetchDataAndRender();

    const handleResize = () => {
      if (chart && containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (chart) {
        chart.remove();
      }
    };
  }, [ticker, interval, period]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: "480px" }}>
      {loading && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(11, 14, 20, 0.8)",
            color: "var(--cyan)",
            fontSize: "14px",
            fontWeight: "bold",
            zIndex: 10,
            fontFamily: "monospace",
          }}
        >
          🔄 CARGANDO DATOS HISTÓRICOS...
        </div>
      )}
      {error && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(11, 14, 20, 0.95)",
            color: "var(--red)",
            padding: "20px",
            textAlign: "center",
            zIndex: 10,
          }}
        >
          <span style={{ fontSize: "24px", marginBottom: "10px" }}>⚠️</span>
          <p style={{ fontWeight: "bold" }}>{error}</p>
          <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "8px" }}>
            Intenta cambiar el intervalo o período en el Centro de Control.
          </p>
        </div>
      )}
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
}
