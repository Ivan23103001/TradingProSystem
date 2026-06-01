// En desarrollo usa localhost:8000; en produccin toma VITE_API_URL del build
export const API_BASE = (import.meta as any).env?.VITE_API_URL || "http://localhost:8000";

// API Key compartida con el backend (mismo valor que bot_config.json.api_key o TRADING_API_KEY)
export const API_KEY = (import.meta as any).env?.VITE_API_KEY || "";