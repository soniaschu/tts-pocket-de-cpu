import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE_DIR = Path(os.environ.get("STATE_DIR", "/german"))
PORT = int(os.environ.get("PORT", "8088"))


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob("*") if _.is_file())


def read_status() -> dict:
    status_file = STATE_DIR / "status.json"
    if not status_file.exists():
        return {
            "status": "waiting",
            "bucket": os.environ.get("HF_BUCKET_ID", "eysho-it/pocket-tts-models"),
            "downloaded_files": 0,
            "model_files": count_files(STATE_DIR / "models"),
            "voice_files": count_files(STATE_DIR / "voices"),
            "updated_at": None,
        }

    try:
        return json.loads(status_file.read_text())
    except json.JSONDecodeError:
        return {
            "status": "waiting",
            "bucket": os.environ.get("HF_BUCKET_ID", "eysho-it/pocket-tts-models"),
            "downloaded_files": 0,
            "model_files": count_files(STATE_DIR / "models"),
            "voice_files": count_files(STATE_DIR / "voices"),
            "updated_at": None,
        }


def render_page(status: dict) -> str:
    model_files = int(status.get("model_files", 0))
    voice_files = int(status.get("voice_files", 0))
    downloaded = int(status.get("downloaded_files", 0))
    status_name = status.get("status", "waiting")
    status_label = "Ready" if status_name == "ready" else "Downloading" if status_name == "downloading" else "Waiting"
    app_links = """
        <div class="actions">
            <a href="http://localhost:8000" target="_blank" rel="noreferrer">Open Spokenword</a>
            <a href="http://localhost:8080" target="_blank" rel="noreferrer">Open Raven</a>
        </div>
    """
    if status_name != "ready":
        app_links = """
            <div class="actions muted">
                <span>Waiting for the model sidecar to finish syncing.</span>
            </div>
        """

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Pocket TTS Status</title>
      <style>
        :root {{
          --bg: #0b1020;
          --panel: #121b2d;
          --panel-alt: #18263f;
          --accent: #6ee7b7;
          --accent-2: #60a5fa;
          --warning: #fbbf24;
          --text: #e5eefb;
          --muted: #a7b7d6;
          --danger: #fca5a5;
          --shadow: rgba(15, 23, 42, 0.45);
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          font-family: Arial, sans-serif;
          background: radial-gradient(circle at top, #16213d 0%, var(--bg) 35%, #090d17 100%);
          color: var(--text);
          min-height: 100vh;
          display: grid;
          place-items: center;
        }}
        .shell {{
          width: min(960px, calc(100vw - 32px));
          padding: 32px 20px 42px;
        }}
        h1 {{ margin: 0 0 12px; font-size: clamp(2rem, 4vw, 3rem); }}
        .subtitle {{ color: var(--muted); margin-bottom: 24px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }}
        .card {{
          background: rgba(18, 27, 45, 0.92);
          border: 1px solid rgba(148, 163, 184, 0.2);
          border-radius: 18px;
          padding: 18px 20px;
          box-shadow: 0 18px 40px var(--shadow);
        }}
        .label {{
          display: block;
          font-size: 0.75rem;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--muted);
        }}
        .value {{
          display: block;
          margin-top: 12px;
          font-size: clamp(1.7rem, 3vw, 2.5rem);
          font-weight: 700;
        }}
        .status-badge {{
          display: inline-block;
          padding: 6px 12px;
          border-radius: 999px;
          background: rgba(110, 231, 183, 0.15);
          border: 1px solid rgba(110, 231, 183, 0.5);
          color: var(--accent);
          font-weight: 600;
          margin-top: 4px;
        }}
        .muted {{ color: var(--muted); }}
        .actions {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 26px; }}
        .actions a {{
          display: inline-block;
          padding: 12px 16px;
          background: linear-gradient(135deg, var(--accent-2), var(--accent));
          color: #081321;
          text-decoration: none;
          border-radius: 10px;
          font-weight: 700;
        }}
        .actions.muted span {{
          color: var(--muted);
          padding: 12px 14px;
          border-radius: 10px;
          background: rgba(148, 163, 184, 0.08);
          border: 1px solid rgba(148, 163, 184, 0.14);
        }}
      </style>
    </head>
    <body>
      <div class="shell">
        <h1>Pocket TTS</h1>
        <div class="subtitle">Model sidecar status, downloaded assets and voice sync</div>

        <div class="grid">
          <div class="card">
            <span class="label">System status</span>
            <span class="value"><span class="status-badge">{status_label}</span></span>
          </div>
          <div class="card">
            <span class="label">Bucket</span>
            <span class="value">{status.get('bucket', 'eysho-it/pocket-tts-models')}</span>
          </div>
          <div class="card">
            <span class="label">Models</span>
            <span class="value">{model_files}</span>
          </div>
          <div class="card">
            <span class="label">Voices</span>
            <span class="value">{voice_files}</span>
          </div>
          <div class="card">
            <span class="label">Downloaded files</span>
            <span class="value">{downloaded}</span>
          </div>
          <div class="card">
            <span class="label">Updated</span>
            <span class="value muted">{status.get('updated_at') or 'waiting'}</span>
          </div>
        </div>

        {app_links}
      </div>
      <script>
        async function refresh() {{
          try {{
            const response = await fetch('/api/status');
            const data = await response.json();
            if (data.status === 'ready') {{
              window.location.reload();
            }}
          }} catch (error) {{}}
        }}
        setInterval(refresh, 5000);
      </script>
    </body>
    </html>
    """


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(read_status()).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(render_page(read_status()).encode())

    def log_message(self, format, *args):
        return


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), StatusHandler)
    print(f"Landing page serving on http://0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
