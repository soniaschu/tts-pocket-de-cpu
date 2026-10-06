> **Model:** Kilo (MiniMax-M3) · **Erstellt:** 2026-10-06 16:47 UTC

# Plan: Agentische Coding-IDE

## Ziel

Eine Coding-IDE bauen, in der einzelne oder mehrere Agents gemeinsam an einem Workspace arbeiten. Die Oberfläche zeigt den aktuellen Arbeitskontext und passt aufgabenbezogene Panels während der Arbeit dynamisch an. GenUI ist die Rendering-Schicht; ein eigener Orchestrator verantwortet A2A-Kommunikation, Agenten, Skills, Codeänderungen und Freigaben.

Pocket TTS ist die Sprachausgabe der IDE, nicht der Agenten-Orchestrator:

- **Einzelagent:** Eine Antwort eines einzelnen Agents wird als einzelne TTS-Ausgabe gesprochen.
- **Mehrere Agents:** Der Orchestrator führt die Beiträge als geordnete Debatte zusammen und gibt sie über Spokenword mit einer Stimme pro Agent aus.
- Spokenword erzeugt Audio und kennt keine Debattenlogik. Turn-Reihenfolge, Sprecher, Transkript, Abbruch und Wiederholung verwaltet der Orchestrator.

## Architektur

### 1. IDE-Frontend

- Stabiler Arbeitsbereich mit Projekt-/Dateibaum, Editor, Diff, Terminal, Aufgabenstatus und Agentenübersicht.
- GenUI-Oberfläche für dynamische, aufgabenbezogene Formulare, Pläne, Reviews und Statuspanels.
- GenuiChat für Chat und Konversationsverlauf, wo dessen integrierte UX passt.
- GenuiRenderer für von der Anwendung kontrollierte, gestreamte Schema-Updates.
- Zentrale IDE-Zustände wie Workspace, aktive Aufgabe, Agentenstatus und Freigaben bleiben im App-Store/Backend. Der Renderer-State ist laut SDK-Doku nur beim Initialisieren eingemischt und daher kein Live-Store.

### 2. Agenten-Orchestrator

Eigener Backend-Dienst mit einer stabilen API für Frontend und Agentenadapter:

- A2A-Agenten auffinden und ihre Fähigkeiten/Identität erfassen.
- Aufgaben verteilen, Status und Ereignisse streamen sowie Abbruch, Timeout und Fehler verwalten.
- Ergebnisse, geänderte Dateien, Tests und Herkunft pro Agent protokollieren.
- Debattenabläufe koordinieren und Sprecherturns deterministisch ordnen.
- Credentials serverseitig verwalten; das Frontend erhält keine Provider-Schlüssel.

Die GenUI-Dokumentation beschreibt OpenAI-kompatibles Streaming, MCP und UI-Rendering, jedoch keine fertige A2A-Laufzeit. A2A ist deshalb eine eigene Integrationsschicht und darf nicht als SDK-Funktion vorausgesetzt werden.

### 3. Skills und Agentenkontext

- Skills als versionierte `SKILL.md`-Fähigkeiten katalogisieren.
- Benötigte Skills passend zur Aufgabe auswählen und nur den zuständigen Agents bereitstellen.
- Skill-ID und Version, Agent, Aufgabe und verwendete Werkzeuge im Laufprotokoll festhalten.
- Skill-Kontext von tatsächlichen Ausführungsrechten trennen; ein Skill gewährt nicht automatisch Shell-, Netzwerk- oder Schreibzugriff.

Die SDK-Dokumentation enthält keinen Skill-Katalog oder automatischen Skill-Loader; diese Funktionen gehören zum Orchestrator.

### 4. Dynamische GenUI-Oberfläche

- UI-Schemas über den Renderer inkrementell ausgeben, während Agents planen oder arbeiten.
- Fragile Felder wie `componentName`, `JSFunction`, Expressions und erforderliche Optionslisten mit `requiredCompleteFieldSelectors` puffern.
- Vor jedem Rendern Schemaform, Material-Whitelist und zulässige Actions validieren.
- Änderungen im Workspace- und Aufgabenzustand über den App-Store synchronisieren, nicht über eine nachträgliche Änderung des initialen Renderer-State.
- Fester IDE-Rahmen und explizite Freigaben bleiben außerhalb generierter Schemas.

### 5. Coding- und Review-Loop

1. Planner zerlegt den Auftrag in überprüfbare Schritte und benötigte Fähigkeiten.
2. Orchestrator weist Teilaufgaben geeigneten Agents zu.
3. Agents analysieren und bearbeiten Dateien in isolierten Worktrees/Branches.
4. Reviewer-Agents prüfen Änderungen und Tests unabhängig.
5. IDE zeigt Diffs, Testergebnisse, Herkunft und Konflikte.
6. Nutzer gibt Änderungen frei; erst danach werden sie angewendet oder zusammengeführt.

### 6. Sprache und Debatten

- Einzelagentenantworten werden als einzelne TTS-Ausgabe gesprochen.
- Bei mehreren Agents erstellt der Orchestrator eine Turn-Liste mit Agent, Text und Voice-ID.
- Spokenword erhält die Turns nacheinander, damit Sprecherwechsel und Reihenfolge erhalten bleiben.
- UI zeigt parallel das Texttranskript, den aktiven Sprecher und Audiostatus; Nutzer kann pausieren, abbrechen und einzelne Beiträge erneut abspielen.
- Bestehende Endpunkte: Raven `POST /v1/audio/speech` liefert OpenAI-kompatibles WAV; Spokenword `POST /tts` nimmt Multipart-Text sowie optional eine Voice-Quelle an und streamt WAV. Stimmenzuordnung und Routing werden konfigurierbar gehalten.

## Sicherheit und Betrieb

- Agenten erhalten minimale, auf Workspace und Aufgabe begrenzte Rechte.
- Shell-Kommandos, Dateischreibvorgänge, Netzwerkzugriffe und Merge/Apply benötigen explizite Policies und passende Freigaben.
- Generierte Schema-Inhalte werden als nicht vertrauenswürdig behandelt. Keine ungeprüfte Ausführung von `JSFunction`, CSS, Links oder beliebigem Code.
- Actions sind eng allowlisted und serverseitig erneut autorisiert.
- A2A-Identität, Payload-Größen, Timeouts, Rate Limits und Audit-Logs absichern.
- Compose- und Railway-Konfigurationen trennen Frontend, Orchestrator, Agentenadapter und TTS-Dienste; Secrets kommen aus Laufzeit-Umgebungsvariablen/Secret Stores.

## Umsetzungsphasen

1. **Verträge festlegen:** A2A-Agenten/Provider, Authentifizierung, erste Skills, Sandbox, Freigaberegeln und TTS-Voice-Mapping spezifizieren.
2. **IDE-Shell:** Vue-App unter `tts-pocket-de-cpu/webui` mit Workspace-Shell und statischem Demo-Zustand aufbauen; SDK-Checkout und dessen vorhandene ungetrackte Dateien unangetastet lassen.
3. **GenUI-Integration:** SDK-Materialien, Chat/Renderer, Schema-Validierung, Live-Updates, Custom Actions und Abbruch integrieren.
4. **Orchestrator-MVP:** Task-/Event-API, Agentenadapter, Laufstatus und persistentes Audit-Protokoll implementieren.
5. **Skills und isolierte Änderungen:** `SKILL.md`-Katalog, Auswahlregeln, Worktrees, Diffs und menschliche Freigabe anschließen.
6. **Mehragenten-Debatte und Spokenword:** Turn-Plan, Stimmenzuordnung, serielle Sprachwiedergabe, Transkript, Pause/Abbruch/Wiederholung ergänzen.
7. **Deployment und Härtung:** Compose/Railway, Auth, Rechte, Fehlerwiederherstellung, Monitoring und Ende-zu-Ende-Tests.

## Abnahmekriterien

- Ein einzelner Agent kann eine Aufgabe bearbeiten; UI zeigt Fortschritt, Diff und Testergebnis, und eine einzelne Antwort kann gesprochen werden.
- Mehrere Agents können Teilaufgaben parallel bearbeiten und anschließend eine nachvollziehbare, geordnete Debatte führen; Spokenword spricht die Turns mit passenden Stimmen.
- Laufende GenUI-Schema-Updates verändern nur das dafür vorgesehene UI-Panel und brechen bei unvollständigen JSON-Fragmenten nicht.
- Agentenlauf, verwendete Skills/Versionen, Änderungen, Tests und Freigaben sind nachvollziehbar.
- Nicht erlaubte Actions, Schreibzugriffe und Befehle werden serverseitig blockiert; kein ungeprüfter Agenten-Code wird ausgeführt.
- Abbruch, Timeout, TTS-Ausfall und Agentenfehler lassen die IDE bedienbar und den Laufstatus verständlich.

## SDK-Dokumentationsgrundlage

Geprüft wurden insbesondere GenUI Quick Start, Chat-/Renderer-/ConfigProvider- und Core-APIs, Schema-Protokoll, Server-Usage, Code-Generator, Materialien sowie Beispiele zu Streaming, Custom Fetch, Actions, Custom Components, Verlauf, Thinking-Prozess, Renderer-State und gepufferten Feldern. Die SDK-Doku beschreibt MCP, aber keine A2A-Orchestrierung, Skill-Verwaltung oder Coding-Sandbox; diese Punkte sind eigene Produktarbeit.
