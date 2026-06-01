module.exports = {
  apps: [
    {
      name: "tps-backend",
      script: "./.venv/bin/uvicorn",
      args: "backend.main:app --host 0.0.0.0 --port 8000",
      cwd: "./",
      interpreter: "none",
      env: {
        PYTHONPATH: "."
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
