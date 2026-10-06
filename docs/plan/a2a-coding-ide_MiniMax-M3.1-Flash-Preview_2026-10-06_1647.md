> **Model:** `minimax-coding-plan/MiniMax-M3.1-Flash-Preview` · **Erstellt:** 2026-10-06 16:47 UTC

# A2A Coding-IDE mit lebender GenUI und Spokenword-TTS

## Prompt (verbessert)

> Baue auf `tts-pocket-de-cpu/webui-sdk` (OpenTiny GenUI SDK) eine Coding-IDE, in der mehrere Agenten direkt miteinander (Agent-to-Agent) arbeiten und debattieren können. Die UI passt sich live an, was gerade codiert wird — angetrieben vom Stream-Schema-Renderer (keine Seiten-Reloads). Agenten finden über das vorhandene `.agents/skills/`-Format automatisch die Skills, die sie gerade brauchen. Das Spokenword-TTS (`localhost:8000`, bearer, OpenAI-kompatibel) liefert die Stimme: ein einzelner Agent spricht seinen Stream, oder mehrere Agenten sprechen abwechselnd ihre Debatten-Turns (verschiedene `voices/*.wav`). Während der Planung rendert der GenUI-Renderer das Debate-Panel / Plan-Card / File-Tree / Editor / Diff-Layout direkt mit, sobald sich Schema-State ändert.

## Architektur-Überblick

```
┌─────────────────────────── Browser (Vue 3 + GenuiRenderer) ───────────────────────────┐
│  GenuiChat · DeltaPatcher · WebAudio Queue · Panel-Layout (vom LLM geliefert) ───────┤
└────────────┬───────────────────────────────────────────┬───────────────────────────────┘
             │ SSE Schema-Stream                       │ WebSocket Turns + Audio-Chunks
┌─────────────▼─────────────────────┐  ┌──────────────────▼────────────────────────────┐
│  genui-sdk-server (:4000)       │  │  a2a-orchestrator (Node)                       │
│  OpenAI-Chat → schemaJson-Stream│◄─┤  single · debate · turn-protocol · router       │
└─────────────┬────────────────────┘  └──────┬───────────────┬───────────────────────┘
              │                              │               │
              │ LLM-Call                     │ Skill-Inject  │ TTS-Bridge
              ▼                              ▼               ▼
       ┌──────────────┐             ┌──────────────────┐ ┌────────────────────────┐
       │  LLM (OSS)   │             │ .agents/skills/  │ │ pocket-tts-spokenword  │
       │              │             │ + a2a-ide/skills/│ │ :8000  (Bearer, /v1/   │
       │              │             │ + IDE materials  │ │  audio/speech)         │
       └──────────────┘             └──────────────────┘ └────────────────────────┘
```

## Mapping Anforderung → vorhandene Assets

| Anforderung | Asset im Repo (Pfad) |
|---|---|
| UI passt sich live ans Coden an | `webui-sdk/projects/tiny-schema-renderer/` + `webui-sdk/packages/core/src/delta-patcher/` + `stream-pattern-extractor/` |
| Schema-getriebenes Rendering | `webui-sdk/docs/src/schema/protocol.md` (`Page`/`Node`/`state`/`methods`/`condition`/`loop`) |
| Server streamt strukturierte UI | `webui-sdk/packages/server/` + `packages/chat-completions/` |
| Material-Whitelist für UI-Komponenten | `webui-sdk/packages/materials/vue-element-plus/` (Vorlage für IDE-Material) |
| Skills automatisch verfügbar | `webui-sdk/.agents/skills/<name>/SKILL.md` + `webui-sdk/packages/skill-generator/` |
| TTS-Backend | `tts-pocket-de-cpu/pocket-tts-spokenword/` (Port 8000, Bearer, OpenAI-kompatibel), `german/voices/*.wav` |
| Raven-Fallback TTS | `tts-pocket-de-cpu/pocket-tts-raven/` (Port 8080) |
| Admin/Status | `tts-pocket-de-cpu/docker/landing_server.py` (Port 8088) |

## Verzeichnis-Layout

```
tts-pocket-de-cpu/
└── a2a-ide/                                 # neuer Subworkspace
    ├── package.json                         # pnpm, hängt am webui-sdk-Workspace
    ├── pnpm-workspace.yaml                  # bindet ../webui-sdk/packages/* mit ein
    ├── apps/
    │   └── ide-web/                         # Vite + Vue 3 + GenuiChat + TinyRobot
    │       └── src/
    │           ├── App.vue                  # Layout-Container
    │           ├── main.ts
    │           ├── panels/
    │           │   ├── DebatePanel.vue
    │           │   ├── PlanCard.vue
    │           │   ├── SkillPicker.vue
    │           │   ├── FileTree.vue
    │           │   ├── CodeEditor.vue
    │           │   ├── DiffView.vue
    │           │   ├── Terminal.vue
    │           │   └── AgentVoiceBadge.vue
    │           ├── renderer.ts              # GenuiRenderer + DeltaPatcher Wrapper
    │           └── audio/
    │                       queue.ts            # WebAudio playback queue
    │                       └── voices.ts    # Mapping agentId → wav in german/voices/
    ├── packages/
    │   ├── a2a-orchestrator/
    │   │   └── src/
    │   │       ├── single.ts                # 1 Agent, normaler Coding-Loop
    │   │       ├── debate.ts                # N Agenten, Planning-Debatte
    │   │       ├── turn-protocol.ts         # { agentId, role, voice, text, schemaPatch, skillRefs }
    │   │       ├── router.ts                # nächster Sprecher (Planner→Critic→Impl→Reviewer)
    │   │       └── layout-agent.ts          # erzeugt IDE-Layout-Schema nach Code-Events
    │   ├── tts-bridge/
    │   │   └── src/
    │   │       ├── spokenword.ts            # OpenAI-kompatibler /v1/audio/speech Aufruf
    │   │       ├── chunker.ts               # Sentence-Chunker für Stream-Sprache
    │   │       └── player.ts                # AudioQueue, overlap-frei
    │   ├── skills-loader/
    │   │   └── src/
    │   │       ├── scan.ts                  # .agents/skills/* + a2a-ide/skills/* scannen
    │   │       ├── inject.ts                # kompakter Index in System-Prompt
    │   │       └── generate.ts              # Wrapper für skill-generator CLI
    │   └── ide-materials/                   # Material-Whitelist für IDE-UI
    │       └── src/
    │           ├── materials.ts             # materialsMeta mit wrapperComponent
    │           └── components/
    │               ├── FileTree.vue
    │               ├── CodeEditor.vue
    │               ├── DiffView.vue
    │               ├── AgentCard.vue
    │               ├── DebateTurn.vue
    │               ├── PlanCard.vue
    │               ├── SkillCard.vue
    │               └── AgentVoiceBadge.vue
    └── skills/                              # werden zur Laufzeit gescannt
        ├── a2a-debate/SKILL.md
        ├── code-editor/SKILL.md
        ├── spokenword-tts/SKILL.md
        ├── layout-agent/SKILL.md
        └── skills-index.json
```

## Phasen

### Phase 1 — Foundation (Workspace anlegen)
- `a2a-ide/` als pnpm-Subworkspace mit `pnpm-workspace.yaml`, der `../webui-sdk/packages/*` als Quell-Pakete einbindet (kein Neupublish nötig).
- `package.json` mit Scripts `dev`, `dev:server`, `dev:ide`, `skills:sync`, `build`.
- Erste Abhängigkeiten: `@opentiny/genui-sdk-core`, `@opentiny/genui-sdk-vue`, `@opentiny/genui-sdk-server`, `@opentiny/genui-sdk-chat-completions`, `ai`.

### Phase 2 — IDE-Materials
- Eigene Material-Whitelist `ide-materials` mit den IDE-Komponenten (`FileTree`, `CodeEditor`, `DiffView`, `AgentCard`, `DebateTurn`, `PlanCard`, `SkillCard`, `AgentVoiceBadge`).
- `materials.ts` exportiert `materialsMeta` analog `vue-element-plus/meta`. Der LLM kann nur diese Komponenten ins Schema setzen.
- Wrapper-Komponente als Root.

### Phase 3 — A2A-Orchestrator
- `single.ts`: ein Agent, Tool-Loop (read/write/edit/run), schreibt `schemaJson` → Server → Renderer patcht IDE.
- `debate.ts`: N Agenten mit Rollen **Planner, Critic, Implementer, Reviewer**. Rundenbasiert, Stop bei Konsens oder Max-Turns. Jeder Turn erzeugt zusätzlich ein **kleines UI-Schema** (Debate-Panel), das in Echtzeit ins Live-Layout gepatcht wird.
- `turn-protocol.ts`: Hülle `{ agentId, role, voice, text, schemaPatch, skillRefs }`.
- `router.ts`: wählt nächsten Sprecher (Unsicherheits-/Reife-/Rollen-Heuristik).
- `layout-agent.ts`: bei Datei-Events (write/edit/test-result) ein **kleiner, schneller LLM-Call** → neues `Page`-Schema → `DeltaPatcher` patcht das IDE-Layout ohne Reload.

### Phase 4 — GenUI-Server-Anbindung
- `@opentiny/genui-sdk-server` mit `ide-materials` starten (Port 4000).
- OpenAI-Chat-Completions-kompatibel, antwortet mit `streamObject` → Stream-Schema → Browser-`GenuiRenderer`.
- Konfiguration über `BASE_URL` + `API_KEY` (OpenAI-kompatibler Provider, OSS-tauglich).

### Phase 5 — Skills-Loader
- Scannt `a2a-ide/skills/` und `webui-sdk/.agents/skills/` zur Laufzeit.
- Injiziert kompakten Skill-Index (analog `skill-generator/reference/components.md`) in den System-Prompt. Detail-Links werden on-demand geladen.
- `pnpm skills:sync` ruft `genui-sdk-skill-generator` gegen `ide-materials` auf → erzeugt `a2a-ide/skills/code-editor/SKILL.md` automatisch.
- Vier handgeschriebene Skills: `a2a-debate`, `code-editor`, `spokenword-tts`, `layout-agent`.

### Phase 6 — TTS-Bridge (Spokenword)
- Endpunkt `http://localhost:8000/v1/audio/speech` mit Bearer aus `german/api_keys.json` (siehe `tts-pocket-de-cpu/README.md`).
- `chunker.ts` teilt Agent-Text-Deltas am Satzende.
- `spokenword.ts` ruft TTS pro Chunk auf, liefert `audio/mpeg` zurück.
- `player.ts` (Browser): `AudioContext`-Queue, overlap-frei, pro Agent eigene Stimme aus `german/voices/` (z. B. `de_voice_<n>.wav`). Bei Debate wechselt die Stimme automatisch pro Sprecher.
- Raven-Fallback (Port 8080) als Backup konfigurierbar.

### Phase 7 — Live-IDE-Layout
- Sobald ein Agent eine Datei schreibt/ändert: Event an `layout-agent`.
- `layout-agent` erzeugt ein neues `Page`-Schema für die IDE (Tabs, Split-Views, Diff-Panels).
- `GenuiRenderer` + `DeltaPatcher` patchen das bestehende DOM, kein F5.
- Schema-Constraints verhindern Sprünge: `requiredCompleteFieldSelectors` analog `docs/inner-docs/GENERATIVE_UI.md`.

### Phase 8 — Live-Demo
- `pnpm dev` startet parallel: GenUI-Server :4000, A2A-Orchestrator, Vite :5173.
- Browser öffnet IDE, spricht „Plane Feature X mit mir".
- Sichtbar: zwei Agenten debattieren abwechselnd hörbar (Spokenword), das IDE-Layout wächst live mit (File-Tree, Plan-Card, Code-Editor, Diff-View).

### Phase 9 — Tests + Docs + i18n
- Vitest für `a2a-orchestrator` (single + debate + router), `tts-bridge` (chunker), `skills-loader` (scan/inject), `ide-materials` (Schema-Konformität gegen `docs/src/schema/protocol.md`).
- Doku unter `a2a-ide/docs/` mit deutschem + englischem Spiegel gemäß `webui-sdk/docs/I18N.md`.
- Neue Komponenten-Index-Datei `reference/components.md` (auto) + handgeschriebene Ergänzungen pro Skill.

## Wichtige Designentscheidungen

1. **Kein neuer Renderer.** Wir nutzen `tiny-schema-renderer` + `DeltaPatcher` aus `webui-sdk` unverändert — Schema-Konformität nach `docs/src/schema/protocol.md` ist Pflicht.
2. **Material-Whitelist erzwingt Disziplin.** `ide-materials` ist die einzige Quelle der Wahrheit dafür, was der LLM rendern darf.
3. **Layout-Agent ist klein und schnell.** Er bekommt nur das IDE-Inventar + das Delta-Event und gibt ein Page-Schema zurück. Kein Wissen über Fachlichkeit.
4. **Skills sind reine Markdown-Dateien.** Format exakt wie `webui-sdk/.agents/skills/<name>/SKILL.md` mit YAML-Frontmatter (`name`, `description`). Auto-Generation via `genui-sdk-skill-generator`.
5. **TTS streamsynchron.** Pro Satz ein Chunk → TTS. Audio-Queue im Browser garantiert Reihenfolge und Sprecherwechsel ohne Übersprechen.
6. **Bearer-Token wiederverwendet.** `german/api_keys.json` ist Single-Source-of-Truth (siehe `tts-pocket-de-cpu/README.md` § Remote API keys).

## Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| LLM halluziniert Komponenten außerhalb der Whitelist | Validator in `ide-materials` wirft vor Renderer-Apply, fällt auf leeres `DebatePanel` zurück |
| Stream-Schema mit unvollständigen Feldern (z. B. abgeschnittene Funktionen) | `requiredCompleteFieldSelectors` + `repairJson` wie in `docs/inner-docs/generative-ui-delay-update.md` |
| TTS-Latenz zerstört Debatte-Feeling | `chunker.ts` bricht an Satzgrenzen, `player.ts` prefetched nächsten Satz während aktueller läuft |
| Mehrere Agenten reden gleichzeitig | `router.ts` serialisiert; `player.ts` hat Single-Lock-Lock pro `agentId` |
| Skills veralten bei Material-Update | `pnpm skills:sync` regeneriert; `skills-loader` validiert zur Laufzeit |
| Token-Kosten bei Layout-Agent | Layout-Agent bekommt nur Delta-Event + aktuellen Page-Schema-Auszug, max. ~500 Output-Tokens |

## Nächste konkrete Aktion

1. `a2a-ide/` anlegen (Phase 1).
2. `ide-materials` Gerüst (Phase 2).
3. Erste Demo: `DebatePanel.vue` rendert live aus einem Schema-Stream.