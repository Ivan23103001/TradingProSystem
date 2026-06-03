const path = require("path");
const BASE_DIR = "/root/TradingProSystem"; // Ajustar a la ruta real en tu VPS

module.exports = {
  apps: [
    {
      name: "tps-backend",
      script: path.join(BASE_DIR, ".venv/bin/uvicorn"),
      args: "backend.main:app --host 0.0.0.0 --port 8000",
      cwd: BASE_DIR,
      interpreter: "none",
      env_file: path.join(BASE_DIR, ".env"),
      env: {
        PYTHONPATH: BASE_DIR
      }
    },
    {
      name: "tps-worker",
      script: "bot_worker.py",
      cwd: BASE_DIR,
      interpreter: path.join(BASE_DIR, ".venv/bin/python"),
      env_file: path.join(BASE_DIR, ".env"),
      env: {
        PYTHONPATH: BASE_DIR
      }
    }
  ]
};