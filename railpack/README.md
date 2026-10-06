# Railpack configs

This directory contains project-specific Railpack overlays for the Python services in this repo.

> Important: `--config-file` is resolved relative to the target app directory. The working pattern is to run the command from the service directory and point it back to this folder.

## Landing admin service

Use the Docker app directory as the build context:

```bash
cd /workspaces/pocket-tts-models/tts-pocket-de-cpu/docker
railpack plan --config-file ../railpack/landing.json .
railpack build --config-file ../railpack/landing.json . --name pocket-tts-landing
```

## Spokenword runtime

Use the spokenword app directory as the build context:

```bash
cd /workspaces/pocket-tts-models/tts-pocket-de-cpu/pocket-tts-spokenword
railpack plan --config-file ../railpack/spokenword.json .
railpack build --config-file ../railpack/spokenword.json . --name pocket-tts-spokenword
```

The overlays keep the generated detection logic, but add the repo-specific runtime dependencies and start commands required by this stack.
