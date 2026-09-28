// PM2 process definition for the Yo-B backend.
//
// Usage (from the backend/ folder):
//   pm2 start deploy/ecosystem.config.js
//   pm2 save                # so it survives a reboot (after `pm2 startup` once)
//
// Runs deploy/start.sh, which resolves the venv and execs wsgi.py (the Flask app
// served by waitress, a production-grade pure-Python WSGI server) — the same wrapper
// update.sh relies on, so there's exactly one place this logic lives.
module.exports = {
  apps: [
    {
      name: "yo-b-backend",
      script: "./deploy/start.sh",
      interpreter: "bash",
      cwd: __dirname + "/..",
      env: {
        YO_B_HOST: "127.0.0.1",
        YO_B_PORT: "5000",
        // Turn on the optional online-translation fallback (off by default) with:
        // YO_B_ONLINE_TRANSLATION: "true",
        // YO_B_ONLINE_TRANSLATION_TIMEOUT: "4",
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 2000,
      out_file: "./deploy/logs/out.log",
      error_file: "./deploy/logs/error.log",
      time: true,
    },
  ],
};
