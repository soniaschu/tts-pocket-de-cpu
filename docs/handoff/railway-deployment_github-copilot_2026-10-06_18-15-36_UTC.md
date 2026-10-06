# Handoff: Railway-Deployment für Pocket TTS

> **Erstellt von:** GitHub Copilot  
> **Erstellt am:** 2026-10-06 18:15:36 UTC  
> **Repository:** `soniaschu/tts-pocket-de-cpu`  
> **Branch:** `main`  
> **Stand:** `ebd99a2` (`Fix Railway landing startup and auth`)

## Kurzstatus

Die Railway-Konfiguration für Landing/Admin, Spokenword und Raven ist auf `main` vorhanden und gepusht. Alle drei Dockerfiles wurden vom Repository-Root erfolgreich gebaut. Python-/Shell-Syntax, Railway-JSON und Compose-Konfiguration wurden geprüft; der Landing-HTTP-Smoke-Test bestätigt Healthcheck und Admin-Schutz. Ein Railway-Projekt wurde aus dieser Umgebung nicht angelegt oder live deployed: die Railway-CLI ist nicht installiert und es gibt keinen Railway-Projektzugriff.

**Deploy-Status:** bereit für manuelle Railway-Service-Konfiguration. Öffentliche TTS-Endpunkte sind wegen der fehlenden Bearer-Prüfung noch nicht für untrusted Internet-Traffic freizugeben.

## Commits

- `d321299` – `docker` nach `main` gemergt.
- `ec134f8` – Remote-main-Integration.
- `ebd99a2` – Landing-Start- und Auth-Fix, auf `upstream/main` gepusht.

Der Arbeitsbaum war nach dem Push sauber.

## Railway-Services

Alle drei Services müssen denselben GitHub-Repository-Root als Build-Kontext verwenden. In Railway pro Service unter Settings die passende Config-as-code-Datei auswählen:

| Railway-Service | Config-Datei | Dockerfile | Volume-Mount | Healthcheck |
| --- | --- | --- | --- | --- |
| `landing` | `railway/landing.json` | `docker/Dockerfile.landing` | `/german` | `/health` |
| `spokenword` | `railway/spokenword.json` | `docker/Dockerfile.spokenword` | `/models` | `/health` |
| `raven` | `railway/raven.json` | `docker/Dockerfile.raven` | `/models` | `/health` |

`model-voice-assets` ist nur der lokale Compose-Sidecar und wird nicht als Railway-Service deployt. Railway-Volumes sind pro Service eigenständig; daher laden Spokenword und Raven den Hugging-Face-Bucket je einmal in ihr eigenes persistentes `/models`-Volume. Der erste Start kann aufgrund der Modellgröße mehrere Minuten dauern.

## Service-Variablen

**Landing**

- `POCKET_TTS_RAILWAY=1`
- `STATE_DIR=/german`
- `ADMIN_USERNAME=<gewünschter Adminname>`
- `ADMIN_PASSWORD=<starkes Railway-Secret, nicht change-me>`
- `PORT` nicht setzen: Railway stellt den Port bereit.

Landing beendet den Start mit Fehler, wenn `ADMIN_PASSWORD` fehlt oder noch `change-me` ist. Das Dashboard kann Railway-Container nicht mit `docker compose` steuern; Restart/Deploy erfolgt im Railway-Dashboard.

**Spokenword**

- `POCKET_TTS_RAILWAY=1`
- `HF_BUCKET_ID=eysho-it/pocket-tts-models`
- `HF_TOKEN` nur, falls der Bucket privat ist
- Optional: `OMP_NUM_THREADS`
- `PORT` nicht festlegen.

**Raven**

- `POCKET_TTS_RAILWAY=1`
- `HF_BUCKET_ID=eysho-it/pocket-tts-models`
- `HF_TOKEN` nur, falls der Bucket privat ist
- Optional: `RAVEN_THREADS`
- `PORT` nicht festlegen.

Eigene öffentliche Domains nur für Dienste vergeben, die wirklich extern erreichbar sein müssen. Die Modell-Volumes müssen auch nach einem Restart am selben Pfad (`/models`) montiert bleiben.

## Verifizierte Prüfungen

- `docker build -f docker/Dockerfile.landing -t pocket-tts-landing:railway-preflight .` – erfolgreich.
- `docker build -f docker/Dockerfile.spokenword -t pocket-tts-spokenword:railway-preflight .` – erfolgreich.
- `docker build -f docker/Dockerfile.raven -t pocket-tts-raven:railway-preflight .` – erfolgreich, einschließlich nativer C++-Build.
- `python3 -m py_compile docker/landing_server.py docker/serve_spokenword.py docker/sync_hf_bucket.py` – erfolgreich.
- `sh -n docker/entrypoint-raven.sh docker/entrypoint-spokenword.sh` – erfolgreich.
- `python3 -m json.tool` für `railway/*.json` – erfolgreich.
- `docker compose config --quiet` – erfolgreich.
- `black --check docker/landing_server.py` – erfolgreich.
- Landing-Smoke-Test: Default-Passwort im Railway-Modus wird abgewiesen; mit gesetztem Admin-Secret liefert `/health` HTTP 200; `/api/keys` ohne Basic Auth liefert HTTP 401.

Diese Prüfungen sind lokale Build-/Smoke-Tests, kein Railway-Live-Deploy.

## Sicherheitsblocker vor öffentlicher API-Nutzung

Landing kann API-Keys erzeugen, aber die TTS-Runtimes prüfen diese Keys derzeit nicht:

- `require_service_key()` in `docker/landing_server.py` ist nicht an eine API-Route angeschlossen.
- Spokenword akzeptiert aktuell seine `/tts`-Anfrage ohne diese servicegebundene Bearer-Prüfung.
- Raven hat derzeit keine Bearer-Key-Prüfung im HTTP-Server.
- Die vorhandene Key-Datei `german/api_keys.json` wird im Klartext gespeichert.

Daher TTS-Domains vorerst privat/intern halten oder Zugriff per Railway-Netzwerk-/Edge-Policy einschränken. Nächster Sicherheits-PR: serverseitiges TTS-Gateway/Auth-Middleware für beide Services, Key-Hashing und Rotation; danach Auth-Tests mit gültigem, ungültigem und widerrufenem Token.

## Nächste Schritte

1. Railway-Projekt mit dem GitHub-Repository verbinden und Branch `main` auswählen.
2. Die drei Services mit den obigen Config-Dateien und Root-Build-Kontext anlegen.
3. Volumes und Service-Variablen setzen; beim Landing ein starkes Admin-Secret verwenden.
4. Erst Landing und danach Spokenword/Raven deployen; die TTS-Healthchecks können bis zu 300 Sekunden benötigen.
5. Logs und `/health` je Service prüfen; bei Modell-Downloadfehlern Bucket-Zugriff, Volume-Schreibrechte und `HF_TOKEN` kontrollieren.
6. Vor öffentlichen TTS-Domains den oben genannten Bearer-Auth-Blocker beseitigen.

Die geplante agentische Coding-IDE/A2A-Orchestrierung ist in diesem Handoff nicht als implementiert enthalten; aktuell dokumentiert und vorbereitet ist der deploybare Pocket-TTS-Stack.
