// API_BASE dinámico: prioriza VITE_API_URL del build, luego la IP pública de producción,
// finalmente localhost para desarrollo local.
const _env_api = (import.meta as any).env?.VITE_API_URL;
export const API_BASE = _env_api && _env_api.trim() !== ""
  ? _env_api
  : "";

// API Key compartida con el backend (mismo valor que bot_config.json.api_key o TRADING_API_KEY)
export const API_KEY = (import.meta as any).env?.VITE_API_KEY || "";

// Helper: fetch con autenticación automática (X-API-Key header)
export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers || {});
  if (API_KEY) {
    headers.set("X-API-Key", API_KEY);
  }
  return fetch(url, { ...options, headers });
}