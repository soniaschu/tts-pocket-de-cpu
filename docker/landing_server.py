import base64
import json
import os
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE_DIR = Path(os.environ.get("STATE_DIR", "/german"))
PORT = int(os.environ.get("PORT", "8088"))
COMPOSE_FILE = os.environ.get("COMPOSE_FILE", "compose.yaml")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")
RAILWAY_DEPLOYMENT = os.environ.get("POCKET_TTS_RAILWAY", "0") == "1"
API_KEYS_FILE = STATE_DIR / "api_keys.json"


def run_compose(action: str) -> dict:
    if RAILWAY_DEPLOYMENT:
        return {
            "ok": False,
            "error": "Manage Railway services from the Railway dashboard.",
        }

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
    if not API_KEYS_FILE.exists():
        return []
    try:
        data = json.loads(API_KEYS_FILE.read_text())
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("keys", [])
    except json.JSONDecodeError:
        pass
    return []


def write_api_keys(keys: list[dict]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    API_KEYS_FILE.write_text(json.dumps(keys, indent=2) + "\n")


def require_dashboard_auth(handler: BaseHTTPRequestHandler) -> bool:
    if not ADMIN_PASSWORD or ADMIN_PASSWORD == "change-me":
        return not RAILWAY_DEPLOYMENT

    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False

    encoded = auth_header.split(" ", 1)[1]
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return False

    username, _, password = decoded.partition(":")
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def require_service_key(service_name: str, handler: BaseHTTPRequestHandler) -> bool:
    if not service_name:
        return True
    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False

    token = auth_header.split(" ", 1)[1].strip()
    keys = {
        item.get("key")
        for item in read_api_keys()
        if item.get("service") == service_name
    }
    return token in keys


def create_api_key(service: str) -> dict:
    service_name = (service or "spokenword").strip().lower()
    key_data = {
        "service": service_name,
        "key": secrets.token_urlsafe(24),
        "created_at": __import__("datetime")
        .datetime.utcnow()
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    status_label = (
        "Ready"
        if status_name == "ready"
        else "Downloading" if status_name == "downloading" else "Waiting"
    )
    app_links = """
        <div class="actions buttons-row">
            <a href="http://localhost:8000" target="_blank" rel="noreferrer">Open Spokenword</a>
            <a href="http://localhost:8080" target="_blank" rel="noreferrer">Open Raven</a>
            <button class="admin-btn" data-action="start">Start stack</button>
            <button class="admin-btn" data-action="restart">Restart stack</button>
            <button class="admin-btn danger" data-action="stop">Stop stack</button>
        </div>
    """
    if RAILWAY_DEPLOYMENT:
        app_links = """
        <div class="actions buttons-row muted">
          <span>Railway services are managed from the Railway dashboard.</span>
        </div>
      """
    elif status_name != "ready":
        app_links = """
            <div class="actions buttons-row muted">
                <span>Waiting for the model sidecar to finish syncing.</span>
                <button class="admin-btn" data-action="start">Start stack</button>
                <button class="admin-btn" data-action="restart">Restart stack</button>
                <button class="admin-btn danger" data-action="stop">Stop stack</button>
            </div>
        """

    key_rows = (
        "".join(
            "<li><strong>{service}</strong>: <code>{key}</code> <span class='tiny'>{created_at}</span></li>".format(
                service=item.get("service", "service"),
                key=item.get("key", ""),
                created_at=item.get("created_at", ""),
            )
            for item in read_api_keys()
        )
        or "<li class='tiny'>No API keys created yet.</li>"
    )

    template = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Pocket TTS Control Center</title>
      <style>
        :root {
          --bg: #07111f;
          --bg-soft: #0d1b2d;
          --panel: rgba(15, 23, 42, 0.82);
          --panel-strong: rgba(17, 24, 39, 0.96);
          --line: rgba(148, 163, 184, 0.22);
          --accent: #7dd3fc;
          --accent-strong: #38bdf8;
          --success: #34d399;
          --warning: #fbbf24;
          --text: #e2e8f0;
          --muted: #94a3b8;
          --danger: #f87171;
          --shadow: rgba(15, 23, 42, 0.45);
        }
        * { box-sizing: border-box; }
        html, body { margin: 0; padding: 0; }
        body {
          background: radial-gradient(circle at top, #11263d 0%, var(--bg) 32%, #040b15 100%);
          color: var(--text);
          font-family: Inter, "Segoe UI", sans-serif;
          min-height: 100vh;
          display: flex;
          justify-content: center;
          padding: 32px 24px;
        }
        .shell {
          width: min(1180px, 100%);
          display: flex;
          flex-direction: column;
          gap: 24px;
        }
        .hero {
          background: linear-gradient(135deg, rgba(18, 34, 58, 0.95), rgba(10, 17, 28, 0.95));
          border: 1px solid var(--line);
          border-radius: 24px;
          box-shadow: 0 20px 50px var(--shadow);
          padding: 28px 24px;
        }
        .topbar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          flex-wrap: wrap;
        }
        .brand {
          display: flex;
          align-items: center;
          gap: 14px;
        }
        .brand-mark {
          width: 42px;
          height: 42px;
          border-radius: 14px;
          background: linear-gradient(135deg, var(--accent), #7c3aed);
          box-shadow: 0 12px 20px rgba(125, 211, 252, 0.35);
          display: grid;
          place-items: center;
          font-weight: 800;
          color: #04111f;
        }
        h1 {
          margin: 0;
          font-size: clamp(2rem, 3vw, 3rem);
          letter-spacing: -0.05em;
        }
        .subtitle {
          color: var(--muted);
          font-size: 1rem;
          margin-top: 8px;
        }
        .status-pill {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          background: rgba(52, 211, 153, 0.12);
          border: 1px solid rgba(52, 211, 153, 0.35);
          color: #b9f7d8;
          border-radius: 999px;
          padding: 8px 14px;
          font-weight: 700;
        }
        .status-pill.waiting {
          background: rgba(251, 191, 36, 0.12);
          border-color: rgba(251, 191, 36, 0.35);
          color: #fde68a;
        }
        .status-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: currentColor;
          display: block;
        }
        .metrics {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 18px;
          margin-top: 26px;
        }
        .card {
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid var(--line);
          border-radius: 18px;
          padding: 18px 20px;
        }
        .label {
          font-size: 0.72rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: var(--muted);
        }
        .value {
          margin-top: 14px;
          font-size: clamp(1.8rem, 2.3vw, 2.6rem);
          font-weight: 800;
          letter-spacing: -0.05em;
        }
        .muted { color: var(--muted); }
        .section {
          background: rgba(15, 23, 42, 0.75);
          border: 1px solid var(--line);
          border-radius: 22px;
          box-shadow: 0 18px 40px var(--shadow);
          padding: 22px 20px;
        }
        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 18px;
          flex-wrap: wrap;
          margin-bottom: 18px;
        }
        .section-title {
          margin: 0;
          font-size: 1.2rem;
        }
        .actions { display: flex; gap: 12px; flex-wrap: wrap; }
        .admin-btn, .action-link {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: none;
          border-radius: 12px;
          padding: 11px 16px;
          text-decoration: none;
          font-weight: 700;
          cursor: pointer;
          transition: transform 0.15s ease;
        }
        .admin-btn:hover, .action-link:hover { transform: translateY(-1px); }
        .action-link {
          background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(125, 211, 252, 0.14));
          border: 1px solid rgba(125, 211, 252, 0.38);
          color: var(--text);
        }
        .admin-btn.primary {
          background: linear-gradient(135deg, var(--accent-strong), var(--accent));
          color: #04111f;
        }
        .admin-btn.warning {
          background: linear-gradient(135deg, #f59e0b, #fbbf24);
          color: #1f1300;
        }
        .admin-btn.danger {
          background: linear-gradient(135deg, #fda4af, #fb7185);
          color: #1b0910;
        }
        .panel-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: 18px;
        }
        .mini-card {
          background: rgba(2, 6, 23, 0.26);
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 18px;
          padding: 18px;
        }
        .mini-card h3 {
          margin: 0 0 8px;
          font-size: 1rem;
        }
        .mini-card p {
          margin: 0;
          color: var(--muted);
          line-height: 1.5;
        }
        form {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          margin-top: 12px;
        }
        select, button, code {
          font: inherit;
        }
        select {
          background: rgba(15, 23, 42, 0.8);
          color: var(--text);
          border: 1px solid rgba(148, 163, 184, 0.28);
          border-radius: 10px;
          padding: 10px 12px;
          min-width: 180px;
        }
        ul {
          list-style: none;
          padding: 0;
          margin: 16px 0 0;
        }
        li {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
          padding: 10px 0;
          border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        }
        .key-name {
          font-weight: 700;
          text-transform: capitalize;
        }
        code {
          display: inline-block;
          background: rgba(148,163,184,0.08);
          border-radius: 8px;
          padding: 4px 8px;
          color: var(--text);
          max-width: 100%;
          overflow-wrap: anywhere;
        }
        .tiny { font-size: 0.8rem; color: var(--muted); }
        @media (max-width: 720px) {
          body { padding: 18px 14px; }
          .section, .hero { padding: 18px 16px; }
        }
      </style>
    </head>
    <body>
      <div class="shell">
        <header class="hero">
          <div class="topbar">
            <div class="brand">
              <div class="brand-mark">T</div>
              <div>
                <h1>Pocket TTS</h1>
                <div class="subtitle">Sidecar sync, voice download, and remote model control</div>
              </div>
            </div>
            <div class="status-pill __STATUS_CLASS__"><span class="status-dot"></span> __STATUS_LABEL__</div>
          </div>

          <div class="metrics">
            <div class="card">
              <div class="label">System status</div>
              <div class="value">__STATUS_LABEL__</div>
            </div>
            <div class="card">
              <div class="label">Bucket</div>
              <div class="value muted">__BUCKET__</div>
            </div>
            <div class="card">
              <div class="label">Models</div>
              <div class="value">__MODEL_FILES__</div>
            </div>
            <div class="card">
              <div class="label">Voices</div>
              <div class="value">__VOICE_FILES__</div>
            </div>
            <div class="card">
              <div class="label">Downloaded files</div>
              <div class="value">__DOWNLOADED__</div>
            </div>
            <div class="card">
              <div class="label">Updated</div>
              <div class="value muted">__UPDATED_AT__</div>
            </div>
          </div>
        </header>

        <section class="section">
          <div class="section-header">
            <h2 class="section-title">Runtime controls</h2>
          </div>
          <div class="actions">
            __APP_LINKS__
          </div>
        </section>

        <section class="section">
          <div class="section-header">
            <h2 class="section-title">Service overview</h2>
          </div>
          <div class="panel-grid">
            <div class="mini-card">
              <h3>Spokenword</h3>
              <p>German TTS runtime with local model and voice assets loaded from the synced bucket.</p>
            </div>
            <div class="mini-card">
              <h3>Raven</h3>
              <p>OpenAI-compatible voice endpoint for browser and remote client integrations.</p>
            </div>
            <div class="mini-card">
              <h3>Admin</h3>
              <p>Create bearer keys for remote access and control stack lifecycle from the dashboard.</p>
            </div>
          </div>
        </section>

        <section class="section">
          <div class="section-header">
            <h2 class="section-title">Remote API key manager</h2>
          </div>
          <p class="tiny">Create bearer tokens for the TTS services and attach them as <code>Authorization: Bearer &lt;key&gt;</code> in remote clients.</p>
          <form id="keyForm">
            <select id="service" name="service">
              <option value="spokenword">spokenword</option>
              <option value="raven">raven</option>
            </select>
            <button type="submit" class="admin-btn primary">Generate API key</button>
          </form>
          <ul id="keyList">
            __KEY_ROWS__
          </ul>
        </section>
      </div>
      <script>
        async function refresh() {
          try {
            const response = await fetch('/api/status');
            const data = await response.json();
            if (data.status === 'ready') {
              window.location.reload();
            }
          } catch (error) {}
        }
        async function refreshKeys() {
          const response = await fetch('/api/keys');
          const payload = await response.json();
          const list = document.getElementById('keyList');
          if (!list) return;
          list.innerHTML = payload.keys.length ? payload.keys.map((item) =>
            '<li><span class="key-name">' + item.service + '</span><code>' + item.key + '</code><span class="tiny">' + item.created_at + '</span></li>'
          ).join('') : '<li class="tiny">No API keys created yet.</li>';
        }
        document.querySelectorAll('.admin-btn').forEach((button) => {
          if (button.type === 'submit') return;
          button.addEventListener('click', async () => {
            const action = button.dataset.action;
            const response = await fetch('/api/' + action, { method: 'POST' });
            const payload = await response.json();
            if (payload.ok) {
              setTimeout(() => window.location.reload(), 800);
            } else {
              alert('Action failed: ' + (payload.stderr || payload.error || 'unknown error'));
            }
          });
        });
        document.getElementById('keyForm')?.addEventListener('submit', async (event) => {
          event.preventDefault();
          const service = document.getElementById('service').value;
          const response = await fetch('/api/key/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service })
          });
          const payload = await response.json();
          if (payload.ok) {
            await refreshKeys();
            alert('API key created for ' + payload.service + ': ' + payload.key);
          } else {
            alert('Key creation failed: ' + (payload.error || 'unknown error'));
          }
        });
        setInterval(refresh, 5000);
      </script>
    </body>
    </html>
    """
    rendered = template
    replacements = {
        "__STATUS_LABEL__": status_label,
        "__STATUS_CLASS__": "" if status_name == "ready" else "waiting",
        "__BUCKET__": status.get("bucket", "eysho-it/pocket-tts-models"),
        "__MODEL_FILES__": str(model_files),
        "__VOICE_FILES__": str(voice_files),
        "__DOWNLOADED__": str(downloaded),
        "__UPDATED_AT__": str(status.get("updated_at") or "waiting"),
        "__APP_LINKS__": app_links,
        "__KEY_ROWS__": key_rows,
    }
    for key, value in replacements.items():
        rendered = rendered.replace(key, str(value))
    return rendered


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"status": "ok", "admin": ADMIN_USERNAME}).encode()
            )
            return

        if self.path == "/api/keys" and not require_dashboard_auth(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Pocket TTS dashboard"')
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
            return

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

        if not require_dashboard_auth(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Pocket TTS dashboard"')
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(render_page(read_status()).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b""

        if not require_dashboard_auth(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Pocket TTS dashboard"')
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
            return

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
    if RAILWAY_DEPLOYMENT and (not ADMIN_PASSWORD or ADMIN_PASSWORD == "change-me"):
        raise SystemExit("Set a non-default ADMIN_PASSWORD for Railway deployments.")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), StatusHandler)
    print(f"Landing page serving on http://0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
