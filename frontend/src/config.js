// src/config.js
// ─────────────────────────────────────────────────────────────────
//  Satu-satunya tempat untuk konfigurasi URL backend.
//
//  Dev lokal    → buat file .env.local berisi: VITE_API_URL=http://localhost:8001
//  Production   → set VITE_API_URL di Vercel/Netlify dashboard
//                 contoh: https://apex-api.namadomain.com
//
//  Kalau VITE_API_URL kosong (misal di HF Spaces dimana FE & BE satu domain),
//  semua fetch akan pakai path relatif → otomatis ke domain yang sama.
// ─────────────────────────────────────────────────────────────────

export const API = import.meta.env.VITE_API_URL || '';

// WebSocket URL — otomatis konversi http→ws, https→wss
export const WS_URL = API
  ? API.replace(/^http/, 'ws')
  : (typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
      : '');