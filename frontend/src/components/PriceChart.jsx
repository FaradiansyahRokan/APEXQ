import React, { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, LineSeries, HistogramSeries, ColorType, CrosshairMode } from 'lightweight-charts';

const calculateEMA = (data, p) => {
  if (!data || data.length < p) return [];
  const k = 2 / (p + 1);
  let ema = [{ time: data[0].time, value: data[0].close }];
  for (let i = 1; i < data.length; i++) {
    ema.push({ time: data[i].time, value: data[i].close * k + ema[i - 1].value * (1 - k) });
  }
  return ema;
};

// Hitung presisi desimal berdasarkan harga
// BTC 84500 → 2, HYPE 32.9 → 4, PEPE 0.000012 → 8
const getPricePrecision = (price) => {
  if (!price || price <= 0) return 4;
  if (price >= 1000)  return 2;
  if (price >= 100)   return 3;
  if (price >= 10)    return 4;
  if (price >= 1)     return 4;
  if (price >= 0.1)   return 5;
  if (price >= 0.01)  return 6;
  if (price >= 0.001) return 7;
  return 8;
};

export default function PriceChart({ data, settings, liveCandle, tf }) {
  const chartContainerRef = useRef(null);
  const chartInstanceRef  = useRef(null);
  const candleSeriesRef   = useRef(null);
  const ema1SeriesRef     = useRef(null);
  const ema2SeriesRef     = useRef(null);
  const volumeSeriesRef   = useRef(null);
  const visibleRangeRef   = useRef(null);   // simpan posisi scroll user
  const isUserScrolledRef = useRef(false);  // user sudah geser manual?
  const initialFitDoneRef = useRef(false);  // sudah fitContent pertama kali?

  // ═══════════════════════════════════════════════════════════════
  //  EFEK 1: INISIALISASI CHART
  //  Hanya jalan saat mount atau tf berubah.
  //  TIDAK ada data/settings/liveCandle di dependency — ini kuncinya.
  // ═══════════════════════════════════════════════════════════════
  useEffect(() => {
    if (!chartContainerRef.current) return;

    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove();
      chartInstanceRef.current  = null;
      candleSeriesRef.current   = null;
      ema1SeriesRef.current     = null;
      ema2SeriesRef.current     = null;
      volumeSeriesRef.current   = null;
      initialFitDoneRef.current = false;
      isUserScrolledRef.current = false;
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#64748B',
        fontSize: 12,
        fontFamily: 'var(--mono)',
        attributionLogo: false,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#ffffff', width: 1, style: 2, labelBackgroundColor: '#18181B' },
        horzLine: { color: '#ffffff', width: 1, style: 2, labelBackgroundColor: '#18181B' },
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.03)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
      },
      width:  chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
      localization: {
        timeFormatter: (time) => {
          if (typeof time === 'number') {
            const date = new Date(time * 1000);
            return date.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
          }
          if (typeof time === 'string') {
            const [year, month, day] = time.split('-');
            const date = new Date(year, month - 1, day);
            return date.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: '2-digit' }).replace(',', '');
          }
          return time;
        },
      },
      timeScale: {
        borderColor: '#E2E8F0',
        barSpacing: 12,
        rightOffset: 15,
        timeVisible: tf !== '1D',
      },
      rightPriceScale: {
        borderColor: '#E2E8F0',
        autoScale: true,
        alignLabels: true,
        borderVisible: true,
        scaleMargins: { top: 0.15, bottom: 0.2 },
      },
    });

    chartInstanceRef.current = chart;

    // Deteksi user scroll — simpan range supaya live update tidak override
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range) {
        visibleRangeRef.current = range;
        if (initialFitDoneRef.current) {
          isUserScrolledRef.current = true;
        }
      }
    });

    // Buat semua series di sini (data diset di efek berikutnya)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10B981', downColor: '#F43F5E',
      borderVisible: false,
      wickUpColor: '#10B981', wickDownColor: '#F43F5E',
    });
    candleSeriesRef.current = candleSeries;

    ema1SeriesRef.current = chart.addSeries(LineSeries, {
      color: '#3B82F6', lineWidth: 2, priceLineVisible: false, crosshairMarkerVisible: false, visible: false,
    });
    ema2SeriesRef.current = chart.addSeries(LineSeries, {
      color: '#F97316', lineWidth: 2, priceLineVisible: false, crosshairMarkerVisible: false, visible: false,
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#E2E8F0', priceFormat: { type: 'volume' }, priceScaleId: '', visible: false,
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    volumeSeriesRef.current = volumeSeries;

    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartInstanceRef.current  = null;
      candleSeriesRef.current   = null;
      ema1SeriesRef.current     = null;
      ema2SeriesRef.current     = null;
      volumeSeriesRef.current   = null;
      initialFitDoneRef.current = false;
      isUserScrolledRef.current = false;
    };
  }, [tf]); // ← hanya tf yang trigger recreate chart

  // ═══════════════════════════════════════════════════════════════
  //  EFEK 2: SET DATA HISTORIS
  //  Tidak recreate chart — cukup setData ke series yang sudah ada
  // ═══════════════════════════════════════════════════════════════
  useEffect(() => {
    if (!data?.length || !candleSeriesRef.current) return;

    const samplePrice = data[data.length - 1]?.close ?? 0;
    const precision   = getPricePrecision(samplePrice);

    // Set priceFormat agar desimal tampil penuh sesuai harga aset
    candleSeriesRef.current.applyOptions({
      priceFormat: { type: 'price', precision, minMove: Math.pow(10, -precision) },
    });
    candleSeriesRef.current.setData(data);

    if (settings?.showEma1 && ema1SeriesRef.current) {
      ema1SeriesRef.current.applyOptions({ visible: true });
      ema1SeriesRef.current.setData(calculateEMA(data, settings.ema1));
    } else if (ema1SeriesRef.current) {
      ema1SeriesRef.current.applyOptions({ visible: false });
    }

    if (settings?.showEma2 && ema2SeriesRef.current) {
      ema2SeriesRef.current.applyOptions({ visible: true });
      ema2SeriesRef.current.setData(calculateEMA(data, settings.ema2));
    } else if (ema2SeriesRef.current) {
      ema2SeriesRef.current.applyOptions({ visible: false });
    }

    if (settings?.showVol && volumeSeriesRef.current) {
      volumeSeriesRef.current.applyOptions({ visible: true });
      volumeSeriesRef.current.setData(data.map(d => ({
        time:  d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(16, 185, 129, 0.5)' : 'rgba(244, 63, 94, 0.5)',
      })));
    } else if (volumeSeriesRef.current) {
      volumeSeriesRef.current.applyOptions({ visible: false });
    }

    // fitContent hanya sekali saat data pertama kali masuk
    // Setelah user scroll, jangan override posisi mereka
    if (!isUserScrolledRef.current && chartInstanceRef.current) {
      chartInstanceRef.current.timeScale().fitContent();
      setTimeout(() => { initialFitDoneRef.current = true; }, 300);
    }
  }, [data, settings]);

  // ═══════════════════════════════════════════════════════════════
  //  EFEK 3: LIVE CANDLE UPDATE (WebSocket)
  //  Hanya .update() — tidak sentuh chart instance sama sekali
  //  Dependency: [liveCandle] saja — 'data' sengaja dikeluarkan
  // ═══════════════════════════════════════════════════════════════
  useEffect(() => {
    if (!liveCandle || !candleSeriesRef.current) return;

    // Ambil lastHistorical dari ref agar tidak jadi dependency
    const lastTime = candleSeriesRef.current
      ? (() => { try { return null; } catch { return null; } })()
      : null;

    const currentLive = { ...liveCandle };

    try {
      candleSeriesRef.current.update(currentLive);

      if (volumeSeriesRef.current) {
        volumeSeriesRef.current.update({
          time:  currentLive.time,
          value: currentLive.volume,
          color: currentLive.close >= currentLive.open
            ? 'rgba(16, 185, 129, 0.5)'
            : 'rgba(244, 63, 94, 0.5)',
        });
      }

      // Restore scroll position kalau user sudah scroll manual
      // Ini mencegah chart "loncat" ke kanan saat ada update harga baru
      if (isUserScrolledRef.current && visibleRangeRef.current && chartInstanceRef.current) {
        chartInstanceRef.current.timeScale().setVisibleLogicalRange(visibleRangeRef.current);
      }
    } catch {
      // Swallow — terjadi saat unmount
    }
  }, [liveCandle]); // ← HANYA liveCandle, bukan [liveCandle, data]

  return (
    <div
      ref={chartContainerRef}
      className="w-full relative overflow-hidden"
      style={{ touchAction: 'none', height: '100%', minHeight: '480px' }}
    />
  );
}