import React, { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, LineSeries, HistogramSeries, ColorType, CrosshairMode } from 'lightweight-charts';

// Fungsi kalkulasi EMA
const calculateEMA = (data, p) => {
  if (!data || data.length < p) return [];
  const k = 2 / (p + 1);
  let ema = [{ time: data[0].time, value: data[0].close }];
  for(let i=1; i<data.length; i++) {
    ema.push({ time: data[i].time, value: data[i].close * k + ema[i-1].value * (1-k) });
  }
  return ema;
};

export default function PriceChart({ data, settings, liveCandle, tf }) {
  const chartContainerRef = useRef(null);
  
  // ─── PERBAIKAN: Deklarasi Ref yang tadi terlewat ───
  const chartInstanceRef = useRef(null); 
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);

  useEffect(() => {
    if (!data?.length || !chartContainerRef.current) return;

    // Inisialisasi Chart
    const chart = createChart(chartContainerRef.current, {
      layout: { 
        background: { type: ColorType.Solid, color: 'transparent' }, 
        textColor: '#64748B', 
        fontSize: 12,
        fontFamily: 'var(--mono)',
        attributionLogo: false
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#ffffff', width: 1, style: 2, labelBackgroundColor: '#18181B' },
        horzLine: { color: '#ffffff', width: 1, style: 2, labelBackgroundColor: '#18181B' },
      },
      grid: { 
        vertLines: { color: 'rgba(255, 255, 255, 0.03)' }, // Sangat samar
        horzLines: { color: 'rgba(255, 255, 255, 0.03)' }, 
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
      localization: {
        timeFormatter: (time) => {
          // 1. PENANGANAN INTRADAY (Angka Detik Unix)
          if (typeof time === 'number') {
             const date = new Date(time * 1000);
             // Format: "20 Feb, 14:30"
             return date.toLocaleString('en-GB', {
               day: '2-digit', month: 'short',
               hour: '2-digit', minute: '2-digit'
             });
          }
          
          // 2. PENANGANAN HARIAN (1D - Format String 'YYYY-MM-DD')
          if (typeof time === 'string') {
             // Pecah string "2026-02-20"
             const [year, month, day] = time.split('-');
             const date = new Date(year, month - 1, day); // Bulan di JS dimulai dari 0
             
             // Format: "Fri, 20 Feb '26"
             return date.toLocaleDateString('en-GB', {
                weekday: 'short', 
                day: '2-digit', 
                month: 'short', 
                year: '2-digit'
             }).replace(',', ''); // Hapus koma bawaan browser jika ada
          }
          
          return time; // Fallback aman
        }
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

    // Simpan instance chart ke Ref agar bisa diakses efek lain
    chartInstanceRef.current = chart;

    // 1. BUAT CANDLE SERIES
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10B981', 
      downColor: '#F43F5E', 
      borderVisible: false,
      wickUpColor: '#10B981', 
      wickDownColor: '#F43F5E',
    });
    candleSeries.setData(data);
    candleSeriesRef.current = candleSeries;

    // 2. TAMBAHKAN INDIKATOR EMA
    if (settings.showEma1) {
      chart.addSeries(LineSeries, { color: '#3B82F6', lineWidth: 2, priceLineVisible: false, crosshairMarkerVisible: false })
           .setData(calculateEMA(data, settings.ema1));
    }
    if (settings.showEma2) {
      chart.addSeries(LineSeries, { color: '#F97316', lineWidth: 2, priceLineVisible: false, crosshairMarkerVisible: false })
           .setData(calculateEMA(data, settings.ema2));
    }
    
    // 3. BUAT VOLUME SERIES
    if (settings.showVol) {
      const volumeSeries = chart.addSeries(HistogramSeries, { 
        color: '#E2E8F0', 
        priceFormat: { type: 'volume' }, 
        priceScaleId: '' 
      });
      volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
      volumeSeries.setData(data.map(d => ({
        time: d.time, 
        value: d.volume, 
        color: d.close >= d.open ? 'rgba(16, 185, 129, 0.5)' : 'rgba(244, 63, 94, 0.5)'
      })));
      volumeSeriesRef.current = volumeSeries;
    } else {
      volumeSeriesRef.current = null;
    }

    chart.timeScale().fitContent();

    // RESIZE OBSERVER
    const resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });

    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [data, settings]); 

  // ─── EFEK KHUSUS UNTUK LIVE UPDATE ───
  useEffect(() => {
    // Pastikan semua referensi dan data historis sudah siap
    if (!liveCandle || !candleSeriesRef.current || !data || data.length === 0) return;

    // Bikin salinan dari liveCandle agar kita bisa memodifikasi time-nya
    const currentLive = { ...liveCandle };
    const lastHistorical = data[data.length - 1];

    // THE HACK: Jika waktu dari WebSocket "mundur" atau lebih kecil dari 
    // data historis terakhir, paksa waktunya menjadi sama dengan data historis.
    if (currentLive.time < lastHistorical.time) {
        currentLive.time = lastHistorical.time;
    }

    try {
      // 1. Update batang lilin terakhir
      candleSeriesRef.current.update(currentLive);

      // 2. Update batang volume terakhir
      if (volumeSeriesRef.current) {
        volumeSeriesRef.current.update({
          time: currentLive.time,
          value: currentLive.volume,
          color: currentLive.close >= currentLive.open ? 'rgba(16, 185, 129, 0.5)' : 'rgba(244, 63, 94, 0.5)'
        });
      }
    } catch (err) {
      // Sekarang error ini hampir mustahil terjadi, tapi kalau pun terjadi,
      // kita diamkan saja agar tidak menuh-menuhin console log.
    }
  }, [liveCandle, data]); // Pastikan 'data' masuk ke dependency array

  return (
    <div 
      ref={chartContainerRef} 
      className="w-full relative overflow-hidden" 
      style={{ touchAction: 'none', height: '100%', minHeight: '480px' }} 
    />
  );
}