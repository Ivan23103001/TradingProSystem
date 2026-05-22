module.exports = {
  apps: [
    {
      name: "tps-backend",
      script: "./.venv/bin/uvicorn",
      args: "backend.main:app --host 127.0.0.1 --port 8000",
      cwd: "./",
      interpreter: "none",
      env: {
        PYTHONPATH: ".",
        ALLOWED_ORIGINS: "http://localhost:3000,http://localhost:5173"
      }
    },
    {
      name: "tps-worker",
      script: "bot_worker.py",
      cwd: "./",
      interpreter: "./.venv/bin/python",
      env: {
        PYTHONPATH: "."
      }
    }
  ]
};
