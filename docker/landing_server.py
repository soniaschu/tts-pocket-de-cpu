import json
import os
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE_DIR = Path(os.environ.get("STATE_DIR", "/german"))
PORT = int(os.environ.get("PORT", "8088"))
COMPOSE_FILE = os.environ.get("COMPOSE_FILE", "compose.yaml")


def run_compose(action: str) -> dict:
    try:
        subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, action],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return {"ok": True, "action": action}
    except subprocess.CalledProcessError as error:
        return {
            "ok": False,
            "action": action,
            "stdout": error.stdout,
            "stderr": error.stderr,
            "returncode": error.returncode,
        }


def read_api_keys() -> list[dict]:
    key_file = STATE_DIR / "api_keys.json"
    if not key_file.exists():
        return []
    try:
        data = json.loads(key_file.read_text())
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("keys", [])
    except json.JSONDecodeError:
        pass
    return []


def write_api_keys(keys: list[dict]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "api_keys.json").write_text(json.dumps(keys, indent=2) + "\n")


def create_api_key(service: str) -> dict:
    service_name = (service or "spokenword").strip().lower()
    key_data = {
        "service": service_name,
        "key": secrets.token_urlsafe(24),
        "created_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    keys = read_api_keys()
    keys.append(key_data)
    write_api_keys(keys)
    return key_data


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
        <div class="actions buttons-row">
            <a href="http://localhost:8000" target="_blank" rel="noreferrer">Open Spokenword</a>
            <a href="http://localhost:8080" target="_blank" rel="noreferrer">Open Raven</a>
            <button class="admin-btn" data-action="start">Start stack</button>
            <button class="admin-btn" data-action="restart">Restart stack</button>
            <button class="admin-btn danger" data-action="stop">Stop stack</button>
        </div>
    """
    if status_name != "ready":
        app_links = """
            <div class="actions buttons-row muted">
                <span>Waiting for the model sidecar to finish syncing.</span>
                <button class="admin-btn" data-action="start">Start stack</button>
                <button class="admin-btn" data-action="restart">Restart stack</button>
                <button class="admin-btn danger" data-action="stop">Stop stack</button>
            </div>
        """

    key_rows = "".join(
        f"<li><strong>{item.get('service', 'service')}</strong>: <code>{item.get('key', '')}</code> <span class='tiny'>{item.get('created_at', '')}</span></li>"
        for item in read_api_keys()
    ) or "<li class='tiny'>No API keys created yet.</li>"

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
        .buttons-row {{ align-items: center; }}
        .actions a, .admin-btn {{
          display: inline-block;
          padding: 12px 16px;
          background: linear-gradient(135deg, var(--accent-2), var(--accent));
          color: #081321;
          text-decoration: none;
          border-radius: 10px;
          font-weight: 700;
          border: none;
          cursor: pointer;
          font-size: 0.95rem;
        }}
        .admin-btn.danger {{
          background: linear-gradient(135deg, #fca5a5, #f87171);
        }}
        .actions.muted span {{
          color: var(--muted);
          padding: 12px 14px;
          border-radius: 10px;
          background: rgba(148, 163, 184, 0.08);
          border: 1px solid rgba(148, 163, 184, 0.14);
        }}
        .panel {{
          margin-top: 22px;
          background: rgba(18, 27, 45, 0.92);
          border: 1px solid rgba(148, 163, 184, 0.2);
          border-radius: 18px;
          padding: 20px;
        }}
        form {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
        select, button, code {{ font: inherit; }}
        select {{
          background: #111827;
          color: var(--text);
          border: 1px solid rgba(148, 163, 184, 0.3);
          border-radius: 10px;
          padding: 10px 12px;
        }}
        .tiny {{ font-size: 0.8rem; color: var(--muted); }}
        ul {{ list-style: none; padding-left: 0; margin: 16px 0 0; }}
        li {{ padding: 8px 0; border-bottom: 1px solid rgba(148,163,184,0.1); }}
        code {{ background: rgba(148,163,184,0.08); padding: 4px 8px; border-radius: 6px; display: inline-block; max-width: 100%; overflow-wrap: anywhere; }}
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

        <div class="panel">
          <h2>Remote API key manager</h2>
          <p class="tiny">Create bearer tokens for the TTS services and use them as <code>Authorization: Bearer &lt;key&gt;</code> in remote clients.</p>
          <form id="keyForm">
            <select id="service" name="service">
              <option value="spokenword">spokenword</option>
              <option value="raven">raven</option>
            </select>
            <button type="submit" class="admin-btn">Generate API key</button>
          </form>
          <ul id="keyList">
            {key_rows}
          </ul>
        </div>
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
        async function refreshKeys() {{
          const response = await fetch('/api/keys');
          const payload = await response.json();
          const list = document.getElementById('keyList');
          if (!list) return;
          list.innerHTML = payload.keys.length ? payload.keys.map((item) => `
            <li><strong>${{item.service}}</strong>: <code>${{item.key}}</code> <span class='tiny'>${{item.created_at}}</span></li>
          `).join('') : '<li class="tiny">No API keys created yet.</li>';
        }
        document.querySelectorAll('.admin-btn').forEach((button) => {{
          if (button.type === 'submit') return;
          button.addEventListener('click', async () => {{
            const action = button.dataset.action;
            const response = await fetch('/api/' + action, {{ method: 'POST' }});
            const payload = await response.json();
            if (payload.ok) {{
              setTimeout(() => window.location.reload(), 800);
            }} else {{
              alert('Action failed: ' + (payload.stderr || payload.error || 'unknown error'));
            }}
          }});
        }});
        document.getElementById('keyForm')?.addEventListener('submit', async (event) => {{
          event.preventDefault();
          const service = document.getElementById('service').value;
          const response = await fetch('/api/key/create', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ service }})
          }});
          const payload = await response.json();
          if (payload.ok) {{
            await refreshKeys();
            alert('API key created for ' + payload.service + ': ' + payload.key);
          } else {{
            alert('Key creation failed: ' + (payload.error || 'unknown error'));
          }}
        }});
        setInterval(refresh, 5000);
      </script>
    </body>
    </html>
    """


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/keys":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"keys": read_api_keys()}).encode())
            return
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

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b""

        if self.path == "/api/start":
            result = run_compose("up --build -d")
        elif self.path == "/api/restart":
            result = run_compose("up --build -d --force-recreate")
        elif self.path == "/api/stop":
            result = run_compose("down")
        elif self.path == "/api/key/create":
            try:
                payload = json.loads(raw_body.decode() or "{}")
            except json.JSONDecodeError:
                payload = {}
            created = create_api_key(payload.get("service", "spokenword"))
            result = {"ok": True, **created}
        else:
            result = {"ok": False, "error": "unknown action"}

        self.send_response(200 if result.get("ok") else 500)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def log_message(self, format, *args):
        return


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), StatusHandler)
    print(f"Landing page serving on http://0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
