// Fungsi hitung EMA (Exponential Moving Average)
export const calculateEMA = (data, period) => {
  const k = 2 / (period + 1);
  let emaData = [];
  let prevEma = data[0].close;

  data.forEach((item, i) => {
    const emaValue = item.close * k + prevEma * (1 - k);
    emaData.push({ time: item.time, value: emaValue });
    prevEma = emaValue;
  });
  return emaData;
};

// Fungsi hitung RSI
export const calculateRSI = (data, period = 14) => {
  let rsiData = [];
  delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1+rs))
  // (Data dikirim ke chart khusus RSI di bawah)
  return rsiData;
};