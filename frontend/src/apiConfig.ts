export const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : ""; // En producción, Nginx redirigirá dinámicamente usando rutas relativas
