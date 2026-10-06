# Umsetzungsplan: A2A Coding-IDE mit GenUI und Spokenword

> **Erstellt von:** GitHub Copilot
> **Modellkennung:** GitHub Copilot
> **Erstellt am:** 2026-10-06 16:49:34 UTC

## 1. Produktziel

Eine Coding-IDE im Pocket-TTS-Projekt, in der ein Agent allein oder mehrere Agents gemeinsam Aufgaben planen, Code ändern, prüfen und miteinander debattieren können. Die IDE zeigt ihren festen Arbeitsbereich zuverlässig an; GenUI ergänzt ihn durch dynamische, auf die laufende Aufgabe abgestimmte Panels. Änderungen an Dateien und UI werden als nachvollziehbare Ereignisse dargestellt.

Pocket TTS ist die Audio-Ausgabe dieser Anwendung. Ein einzelner Agent kann eine einzelne Antwort sprechen. Bei mehreren Agents steuert der Orchestrator die Reihenfolge ihrer Beiträge und lässt Spokenword die Debatte mit einer Stimme pro Agent ausgeben.

## 2. Architekturentscheidungen

### Frontend

- Eigenständige Vue-3-Anwendung; als Produkt-App einen separaten Workspace `a2a-ide/` neben `webui-sdk/` anlegen. Das SDK-Repository bleibt Referenz und wird nicht mit Produktcode vermischt.
- Fester IDE-Rahmen: Workspace-Dateibaum, Editor, Diff, Aufgaben-/Teststatus und Agentenübersicht.
- GenUI `GenuiConfigProvider` und `GenuiRenderer` für freigegebene, aufgabenspezifische Pläne, Agentenstatus, Debattenbeiträge und Formulare einsetzen.
- `GenuiChat` für Chat und Gesprächsverlauf dort nutzen, wo die eingebaute Chat-UX genügt.
- Laufenden Workspace- und Aufgabenstatus im Frontend-Store/Backend führen. Renderer-`state` wird laut SDK beim Initialisieren eingemischt und ist kein Ersatz für laufenden Anwendungszustand.

### Admin- und Betriebskonsole

- Einen separat geschützten Admin-Bereich für Dienststatus, Modell-/Voice-Assets, API-Keys und Laufzeitkonfiguration bereitstellen.
- Status mindestens für Model-Sync, Spokenword, Raven, IDE-Orchestrator und TTS-Gateway anzeigen; Healthchecks, Ports, letzter Sync, Modell-/Voice-Anzahl und verständliche Fehler aufführen.
- API-Keys für die logischen Dienste `spokenword` und `raven` erstellen, widerrufen und rotieren. Rohschlüssel nur beim Erstellen einmal zeigen; im persistenten Store nur Hashes speichern.
- Modellquelle/Bucket, Revision und verfügbare Modelle anzeigen; Modellwechsel nur auf verifizierte Assets erlauben und danach betroffene Dienste kontrolliert neu starten.
- Stimmen aus synchronisierten Voice-Dateien als Auswahl anbieten. Freie Dateipfade aus UI/Agenten nicht akzeptieren.
- Ports und externe Service-URLs als Deployment-Konfiguration anzeigen. Änderungen, die Bind-Ports oder geladene Modelle betreffen, als Neustart-/Redeploy-Schritt behandeln und vor Übernahme bestätigen.
- Beim Start zwingend eindeutige Admin-Zugangsdaten verlangen. Der bestehende `change-me`-Fallback und ein dadurch offener Admin-Zugriff dürfen nicht in die produktive Konfiguration gelangen.
- Compose-Aktionen wie `docker compose up/down` nur lokal unterstützen. Railway-Services innerhalb der App nicht so behandeln, als hätten sie den lokalen Docker-Daemon; dort kontrollierte Railway-Deployment-/Restart-Aktionen oder externe Neu-Deploys verwenden.

### Orchestrator und Agenten

- Eigenständiger Backend-Dienst mit Agentenadaptern und A2A-Aufgaben-/Ereignismodell.
- Agentenidentität, Fähigkeiten, Task-Lifecycle, Ergebnisse, geänderte Dateien, Herkunft, Abbruch, Timeout und Fehler protokollieren.
- Planung und Coding getrennt behandeln: Planner erstellt einen begrenzten Plan; Ausführungs-Agents bearbeiten isolierte Worktrees; Reviewer prüfen Diffs und Tests.
- Mehragenten-Debatten als explizite, begrenzte Runden mit Rollen, Turn-Reihenfolge, Abbruchbedingung und menschlicher Entscheidung modellieren.
- Keine A2A-Funktion des GenUI-SDK voraussetzen: Die SDK-Dokumentation deckt OpenAI-kompatibles Streaming, MCP und GenUI-Rendering ab, nicht die A2A-Orchestrierung.

### Skills

- Skills aus versionierten `SKILL.md`-Dateien katalogisieren und anhand der Aufgabe gezielt auswählen.
- Dem Agenten zunächst nur Skill-Metadaten geben; konkrete Skill-Inhalte bei Bedarf laden.
- Jede Ausführung mit Skill-ID/Version, Agent, Task und verwendeten Tools protokollieren.
- Skills sind Anweisungen, keine Berechtigungen: Dateizugriff, Shell, Netzwerk und externe Tools werden separat serverseitig autorisiert.

### GenUI und dynamische Oberfläche

- Agenten-/Orchestrator-Ereignisse lösen neue, validierte GenUI-Schema-Versionen aus. `GenuiRenderer` aktualisiert nur die dafür vorgesehenen Panels, ohne vollständigen Seitenreload.
- `PatternExtractor`/`DeltaPatcher` und `requiredCompleteFieldSelectors` nutzen, wo partielles Schema-Streaming eingesetzt wird.
- Eigene IDE-Materialien mit enger Komponenten-Whitelist bereitstellen.
- Keine generierten `JSFunction`- oder `JSExpression`-Felder unkontrolliert ausführen. Änderungen an Editorlayout, Aktionen und Codezugriff laufen durch registrierte Komponenten, geprüfte Actions und Backend-Policies.
- Editor, Dateisystem und Terminal sind keine frei generierten UI-Komponenten: GenUI darf deren kontrollierte Ansichten aktualisieren, aber nicht eigenständig Berechtigungen ändern.

## 3. Dienstgrenzen und Audio

### Audio-Routing

- Einzelagentenantwort: Orchestrator sendet den Antworttext über den konfigurierten TTS-Pfad und gibt Audio/Status an die IDE zurück.
- Mehrere Agents: Orchestrator erstellt geordnete Turns `{ taskId, agentId, role, voiceId, text }` und spricht sie nacheinander über Spokenword. Der Debattenverlauf bleibt zugleich als Text lesbar.
- UI erhält Sprecher-, Text-, Audio- und Fehlerereignisse; Abbruch und Wiederholung wirken auf den betreffenden Turn.
- TTS- und Agentenfehler dürfen die Textdebatte nicht blockieren.

### Im Repository verifizierte Endpunkte

- **Spokenword:** `POST /tts`, Multipart-Form mit `text` und optional `voice_url` oder `voice_wav`; Antwort `audio/wav` als Stream.
- **Raven:** `POST /v1/audio/speech`, OpenAI-kompatibles JSON mit `input`, `voice` und `response_format`; WAV-Ausgabe. Raven bietet außerdem `POST /tts` für PCM-Streaming.
- Die vorliegende Spokenword-Route ist kein `/v1/audio/speech`-JSON-Endpunkt. Für Browserzugriffe CORS, Authentifizierung und Deployment-Origin prüfen; bevorzugt ruft ein serverseitiger TTS-Proxy die internen Services auf.
- Stimmenverzeichnis und Voice-IDs vor dem Voice-Picker gegen die tatsächlich synchronisierten Assets prüfen. Keine Dateipfade aus Agentenantworten direkt als Voice-Quelle akzeptieren.

### OpenAI-kompatibles Gateway und Authentifizierung

- Einen öffentlichen, authentifizierten TTS-Einstieg `POST /v1/audio/speech` bereitstellen. Er akzeptiert OpenAI-kompatible Felder (`model`, `input`, `voice`, `response_format`) und Bearer-Keys.
- Raven nativ ansprechen; für Spokenword die JSON-Anfrage serverseitig in dessen Multipart-`/tts`-Vertrag übersetzen. Damit bleiben beide logischen Services für Clients über denselben kompatiblen Vertrag nutzbar.
- Keys je logischem Dienst (`spokenword`/`raven`) durchsetzen, nicht nur im Dashboard anzeigen oder erzeugen. Ungültige/widerrufene Keys mit `401` ablehnen; Nutzung, Rate Limits und Rotation protokollieren.
- Provider-/Admin-Geheimnisse nie an Browser oder Agents ausliefern. Die IDE verwendet einen autorisierten Backend-Proxy; TTS-Container bleiben intern erreichbar.
- Bestehende Schlüssel in `german/api_keys.json` sind derzeit Klartext. Migration auf gehashte Schlüssel mit Rotation und sauberem Umgang mit Alt-Keys als eigener Schritt.

## 4. Backend-API für die IDE

Erster interner API-Entwurf, vor Implementierung an bestehende Services anzupassen:

- `GET /api/agents` – registrierte Agents und Fähigkeiten.
- `GET /api/skills` – Skill-Metadaten und Versionen.
- `POST /api/tasks` – Coding-Aufgabe mit Workspace, Modus `single` oder `debate` und Policy anlegen.
- `GET /api/tasks/:id/events` – Status, Plan, Agenten-Turns, Schema-Updates, Diff-/Testereignisse und Fehler streamen.
- `POST /api/tasks/:id/cancel` – Task und laufende Agenten-/TTS-Aufrufe abbrechen.
- `GET /api/workspaces/:id/diff` – Änderungen mit Agent-/Task-Herkunft abrufen.
- `POST /api/workspaces/:id/apply` – freigegebene Änderung anwenden oder mergen.
- `POST /api/tts/speech` – autorisierte TTS-Proxy-Route für einzelne Agentenantworten.
- `GET /api/admin/status` – Health, Service-Ports, Sync-Zeitpunkt sowie verfügbare Modell-/Voice-Assets.
- `GET/PATCH /api/admin/config` – validierte Service-URLs, öffentliche Ports, Modell-/Bucket-Auswahl und Default-Voice lesen/ändern; Änderungen mit Neustartbedarf explizit kennzeichnen.
- `GET/POST/DELETE /api/admin/keys` – servicegebundene Keys erstellen, einmalig ausgeben, widerrufen/rotieren und Metadaten anzeigen.
- `POST /v1/audio/speech` – OpenAI-kompatibler, Bearer-geschützter Gateway-Endpunkt mit Adapter zu Raven oder Spokenword.

Alle schreibenden oder ausführenden Endpunkte prüfen Workspace-Rechte, Task-Zustand und Freigabe serverseitig.
Admin-Endpunkte prüfen zusätzlich Admin-Authentifizierung und CSRF-Schutz; API-Keys werden nie über normale Statusabfragen erneut im Klartext ausgegeben.

## 5. Coding-Workflow

1. Nutzer wählt Workspace und formuliert Ziel sowie Grenzen.
2. Orchestrator ermittelt passende Agents und Skills; UI zeigt den vorgeschlagenen Plan und wartet bei Bedarf auf Freigabe.
3. Ein Agent arbeitet allein oder mehrere Agents erhalten abgegrenzte Teilaufgaben in isolierten Worktrees.
4. Ereignisse aktualisieren Agentenliste, Plan, Dateibaum und passende GenUI-Panels.
5. Reviewer prüfen Änderungen und führen definierte Tests aus.
6. IDE zeigt Diff, Testergebnisse und Herkunft. Änderungen werden erst nach Nutzerfreigabe angewendet oder gemergt.
7. Bei Debatte werden Beiträge geordnet angezeigt und optional nacheinander mit Spokenword gesprochen.

## 6. Sicherheit, Daten und Zuverlässigkeit

- Provider- und TTS-Zugangsdaten ausschließlich serverseitig verwalten; nie in Browser-Storage oder generierte Schemas schreiben.
- Agenten in isolierten Worktrees mit minimalen Workspace-Rechten ausführen.
- Terminalkommandos, Netzwerkzugriffe, Schreiboperationen und Apply/Merge über explizite Allowlist/Policy und Freigaben begrenzen.
- A2A-Identität, Inputgröße, Timeouts, Rate Limits, Abbruch und Audit-Logs implementieren.
- UI-Schemas auf Protokoll, Whitelist, Größenlimits und erlaubte Actions validieren; CSS, Links und Eventhandler einschränken.
- Agentenfehler, Konflikte oder ausgefallenes TTS führen zu sichtbarem Fehlerstatus und lassen den Text-/Editor-Workflow bedienbar.

## 7. Umsetzung in überprüfbaren Phasen

### Phase 0: Verträge und Bestandsaufnahme

- Package- und Laufzeitgrenzen zwischen `webui-sdk`, IDE und Backend festlegen.
- Zuerst unterstützte A2A-Agents, Identitäts-/Authentifizierungsmodell, Skill-Schema, Sandbox und Freigaberegeln festlegen.
- Spokenword-Voice-Assets sowie reale Netzwerk-/Auth-Anforderungen der drei Services testen.
- Ergebnis: Architekturentscheidungen, API-Vertrag, Threat-Model und Testmatrix.

### Phase 1: Statischer IDE-Prototyp

- `a2a-ide/` mit Frontend, Backend-Grundgerüst und lokalen Start-Scripts einrichten.
- IDE-Rahmen mit Testdaten auf Desktop und schmalem Viewport implementieren.
- Ergebnis: navigierbare Oberfläche ohne echte Agenten, TTS oder Dateischreibzugriffe.

### Phase 2: GenUI-Renderer und Materials

- `GenuiConfigProvider`, `GenuiRenderer`, Materialien und registrierte IDE-Komponenten integrieren.
- Einen simulierten SSE-Schema-Stream inklusive unvollständiger JSON-Fragmente und Abbruch anzeigen.
- Validator, Whitelist und Custom Actions vor dem Anschluss echter Agents testen.
- Ergebnis: live aktualisierte, begrenzte Agenten-/Plan-Panels ohne Reload.

### Phase 3: Einzelagenten-Task

- Ein A2A-Adapter und Task-/Event-Lifecycle implementieren.
- Zunächst nur lesende Workspace-Analyse und Plan-Ausgabe; danach isolierte Dateiänderung mit Diff und expliziter Apply-Freigabe.
- Einzelantwort optional über TTS sprechen lassen.
- Ergebnis: vollständiger, auditierbarer Single-Agent-Workflow.

### Phase 4: Skills, Sandbox und Reviewer

- `SKILL.md`-Katalog, Auswahl, Versionsprotokoll und minimale Agenten-Toolrechte anschließen.
- Worktree, Dateizugriff, Testausführung, Review-Agent, Konfliktbehandlung und Freigabe testen.
- Ergebnis: überprüfbare Codeänderung mit Skills und kontrollierter Ausführung.

### Phase 5: Mehragenten-Debatte und Spokenword

- Rollen-/Turn-Protokoll, Max-Runden, Abbruch- und Abschlussbedingungen implementieren.
- Debattenbeiträge mit Agentenidentität und Voice-ID im UI darstellen.
- Turns über Spokenword sequenziell erzeugen und abspielen; TTS-Ausfall, Cancel, Replay und Stimme pro Agent abdecken.
- Ergebnis: nachvollziehbare Textdebatte mit synchronisierter, optionaler Mehrstimmenausgabe.

### Phase 6: API-Gateway und Admin-Konsole

- OpenAI-kompatibles `/v1/audio/speech`-Gateway implementieren und zu Raven bzw. Spokenword routen; Bearer-Authentifizierung tatsächlich vor jedem Request prüfen.
- Key-Verwaltung mit Erstellen, einmaliger Anzeige, Widerruf/Rotation, Hash-Speicherung und Migration der vorhandenen Klartext-Keys umsetzen.
- Admin-Oberfläche für Admin-Zugang, Healthchecks, Ports, Modell-/Bucket-Konfiguration, Sync-Status und Voice-Auswahl bauen.
- Modell-/Portänderungen validieren, Neustartbedarf anzeigen und kontrollierte lokale bzw. Railway-Aktionen unterscheiden.
- Ergebnis: beide TTS-Dienste über dokumentierte, geschützte Client-Verträge verwaltbar.

### Phase 7: Deployment und Betriebsreife

- Compose für lokale Entwicklung und einzelne Railpack-/Railway-Services für Frontend, Orchestrator, Gateway, Spokenword, Raven und Model-Sync abstimmen.
- Öffentliche und interne Ports eindeutig konfigurieren: lokal derzeit Landing `8088`, Spokenword `8000`, Raven `8080`; Produktions-Ports aus Railway-`PORT`/Service-URLs beziehen, nicht fest im Frontend verdrahten.
- Persistente Volumes/Stores für heruntergeladene Modelle und Voices, Admin-/Key-Metadaten, Task-Audit und Workspace-Artefakte definieren. Große Modell-Assets nicht bei jedem Neustart neu herunterladen.
- Railway-Secrets für Admin-Zugang, Provider- und HF-Zugangsdaten konfigurieren; Healthchecks, internes Routing, TLS, Logs, Ressourcenlimits und Startabhängigkeiten dokumentieren.
- Änderungen von Port oder Modellrevision brauchen je nach Dienst einen kontrollierten Restart/Redeploy; UI zeigt laufenden, ausstehenden oder fehlgeschlagenen Konfigurationswechsel.
- Build-, Integrations- und End-to-End-Tests samt Dokumentation ergänzen.
- Ergebnis: reproduzierbarer lokaler Betrieb und dokumentierbarer Railway-Deploy.

## 8. Abnahmekriterien

- Einzelagent: Aufgabe starten, Fortschritt sehen, Änderung als Diff prüfen, Tests sehen und erst nach Freigabe anwenden.
- Mehragentenmodus: Agents parallelisierte Teilaufgaben geben lassen und eine geordnete, nachvollziehbare Debatte führen.
- Oberfläche: Gestreamte GenUI-Updates verändern nur freigegebene Panels und überstehen partielle/fehlerhafte Schemafragmente kontrolliert.
- Skills: Nur aufgabenrelevante, versionierte Skills an Agents geben und im Laufprotokoll nachweisen.
- Audio: Einzelagentenantwort sprechen; Mehragenten-Turns mit passenden Stimmen ohne Überlappung ausgeben; Text bleibt bei Audiofehlern verfügbar.
- API/Admin: Beide logischen TTS-Dienste akzeptieren gültige servicegebundene Bearer-Keys über den OpenAI-kompatiblen Gateway-Vertrag; ungültige und widerrufene Keys werden abgelehnt. Admin kann Keys widerrufen sowie Ports, Modelle und Voices verwalten.
- Konfiguration: Modell-/Portänderungen werden validiert, persistiert und mit dem erforderlichen Restart/Redeploy-Status angezeigt; Produktionsbetrieb startet nicht mit Default-Admin-Zugangsdaten.
- Deployment: Compose lokal und Railway mit internen Service-URLs, persistenten Model-/Voice-Assets, Secrets und Healthchecks funktionieren ohne feste Frontend-URLs.
- Sicherheit: Nicht erlaubte Befehle/Actions/Schreibzugriffe serverseitig blockieren; Agenten-Code nicht ungeprüft ausführen.
- Betrieb: Abbruch, Timeout, Agentenfehler, Merge-Konflikt und TTS-Ausfall erzeugen verständlichen Status und lassen die IDE bedienbar.

## 9. Nicht-Ziele des ersten MVP

- Vollwertiger Ersatz für VS Code oder beliebige IDE-Erweiterungen.
- Autonomes Merge/Deploy ohne menschliche Freigabe.
- Freie Ausführung beliebiger Skills oder generierten JavaScript-Codes.
- Gleichzeitige Audioausgabe mehrerer Sprecher.
- Behauptung, GenUI implementiere A2A oder Spokenword orchestriere Debatten.
