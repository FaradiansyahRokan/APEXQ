import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, LineStyle, AreaSeries } from 'lightweight-charts';

// ─── TANGKAP PROP 'tf' DI SINI ───
export default function MarketOverview({ data, openPrice, isMini = false, color, tf = '1D' }) {
  const chartContainerRef = useRef();

  useEffect(() => {
    if (!data?.length || !chartContainerRef.current) return;

    const processedData = isMini 
      ? data.map((item, index) => ({ time: index, value: item.value }))
      : data;

    const chart = createChart(chartContainerRef.current, {
      localization: {
        timeFormatter: (time) => {
          if (isMini) return '';
          
          if (typeof time === 'number') {
            const date = new Date(time * 1000);
            
            // ─── ALAT PELACAK ───
            console.log(`[TF: ${tf}] Menerima Unix: ${time} | Dikonversi jadi: ${date.toISOString()}`);
            
            if (tf === '1D') {
              return date.toLocaleTimeString('en-GB', { 
                timeZone: 'Asia/Jakarta', 
                hour: '2-digit', minute: '2-digit' 
              });
            } else if (tf === '1W') {
              return date.toLocaleString('en-GB', { 
                timeZone: 'Asia/Jakarta',
                weekday: 'short', hour: '2-digit', minute: '2-digit' 
              });
            } else if (tf === '1M') {
              return date.toLocaleString('en-GB', { 
                timeZone: 'Asia/Jakarta',
                day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' 
              });
            }
          }
          
          if (typeof time === 'string') {
             const [year, month] = time.split('-');
             const date = new Date(year, month - 1);
             return date.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });
          }
          return time;
        }
      },
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: isMini ? 'transparent' : '#888888',
        fontSize: 11,
        fontFamily: 'var(--mono)',
        attributionLogo: false
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false }, 
      },
      handleScroll: false,
      handleScale: false,
      timeScale: { 
        visible: !isMini, 
        borderVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
        timeVisible: tf === '1D' || tf === '1W', 
        
        // ─── INI DIA OBATNYA: TICK MARK FORMATTER ───
        // Mengubah tulisan jam statis di sumbu X bagian bawah
        tickMarkFormatter: (time, tickMarkType, locale) => {
          const date = new Date(time * 1000);
          
          if (tf === '1D') {
            return date.toLocaleTimeString('en-GB', { 
              timeZone: 'Asia/Jakarta', 
              hour: '2-digit', minute: '2-digit' 
            });
          } else if (tf === '1W') {
             return date.toLocaleString('en-GB', { 
              timeZone: 'Asia/Jakarta',
              weekday: 'short', hour: '2-digit' // Sengaja hilangkan menit biar gak kepanjangan
            });
          } else if (tf === '1M') {
             return date.toLocaleDateString('en-GB', { 
              timeZone: 'Asia/Jakarta',
              day: '2-digit', month: 'short' 
            });
          } else {
             // Untuk 1Y (Format awalnya string, lightweight-charts merubahnya jadi object)
             // Jika tf === '1Y', `time` yang dikirim dari Python adalah string YYYY-MM-DD
             // Lightweight-charts akan mem-parsingnya. Kita kembalikan format amannya:
             if (typeof time === 'object' && time.year) {
                 const d = new Date(time.year, time.month - 1, time.day);
                 return d.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });
             }
             return String(time); 
          }
        },
      },
      rightPriceScale: { 
        visible: !isMini, 
        borderVisible: false,
        autoScale: true,
        scaleMargins: isMini ? { top: 0.05, bottom: 0.05 } : { top: 0.1, bottom: 0.1 },
      },
      crosshair: { visible: !isMini },
    });

    const lastValue = processedData[processedData.length - 1].value;
    const isBull = openPrice ? lastValue >= openPrice : true;
    const mainColor = color || (isBull ? '#16A34A' : '#DC2626');

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: mainColor,
      topColor: mainColor + '44',
      bottomColor: mainColor + '00',
      lineWidth: isMini ? 2.5 : 3, 
      priceLineVisible: false,
      lastValueVisible: false, 
    });

    areaSeries.setData(processedData);

    if (!isMini && openPrice) {
      areaSeries.createPriceLine({
        price: parseFloat(openPrice),
        color: '#111111',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'OPEN',
      });
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
        chart.timeScale().fitContent();
      }
    };

    window.addEventListener('resize', handleResize);
    const timer = setTimeout(() => chart.timeScale().fitContent(), 100);

    return () => {
      window.removeEventListener('resize', handleResize);
      clearTimeout(timer);
      chart.remove();
    };
  }, [data, openPrice, isMini, color, tf]); // <-- PENTING: Jangan lupa masukin tf ke dependency!

  return (
    <div 
      ref={chartContainerRef} 
      style={{ width: '100%', height: '100%', position: 'relative' }} 
    />
  );
}