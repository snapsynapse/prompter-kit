# Roadmap

## Near-term

- [ ] Upload social preview image (1280x640) on GitHub repo settings
- [ ] Build landing page with `/canonical-spec-page`
- [ ] Set `homepageUrl` on repo once landing page is live
- [ ] Publish distribution content (dev.to, blog, LinkedIn) via `/promo-orchestrator`

## CLI -- missing CRUD operations

Common pain points confirmed across user forums and competing tools. Small-effort, high-value.

- [ ] `delete` command: remove a script by name or GUID from Texts/ and AppSettings.json
- [ ] `rename` command: update friendlyName in an existing script JSON
- [ ] `reindex` command: bulk-set index values to reorder the full script library
- [ ] `edit` command: open an existing script's chapters in `$EDITOR`

## CLI -- backup and restore

No native backup path exists in Camera Hub. Users have no way to recover scripts after
a reinstall or migration without this tool.

- [ ] `backup` command: export all scripts + AppSettings.json to a timestamped zip archive
- [ ] `restore` command: import from a backup zip, merging or replacing the library

## CLI -- Camera Hub lifecycle

Every import and export requires the user to manually quit Camera Hub first. A wrapper
that handles this automatically removes the most common friction point.

- [ ] `camerahub stop`: quit Camera Hub gracefully (macOS: `osascript`; Windows: `taskkill`)
- [ ] `camerahub start`: relaunch Camera Hub
- [ ] `--restart` flag on `import`: auto-stop before write, auto-start after

## CLI -- LLM script generation

Draft a Prompter script from bullet points or a topic using a local or API-backed LLM.
Low priority -- useful for creators who script from outlines.

- [ ] `generate` command: takes a prompt or outline file, outputs a chapter-per-line script
- [ ] Model-agnostic: support OpenAI-compatible endpoints and local models (Ollama)

## Ecosystem -- evaluate merge with brendancol/elgato_prompter_text_cli

[brendancol/elgato_prompter_text_cli](https://github.com/brendancol/elgato_prompter_text_cli)
is an independent tool solving overlapping problems. Evaluate before duplicating effort.

- [ ] Audit feature overlap and gaps between the two projects
- [ ] Reach out to brendancol about co-maintaining or upstreaming shared improvements
- [ ] Decide: absorb useful patterns (Camera Hub restart, `del` logic) or propose a merge

## GUI -- web UI

A local web server opened in the browser. No installation beyond Python + Flask.
Single command: `python3 elgato_prompter_tools_gui.py`

- [ ] Flask routes wrapping existing import/export/list functions
- [ ] Script list table with GUID, friendly name, index
- [ ] Import form with drag-and-drop file input and name/index fields
- [ ] Single-script export by name or GUID
- [ ] Export-all to a chosen directory
- [ ] Delete and rename from UI
- [ ] Status and error feedback in UI
- [ ] Auto-open browser on launch

## GUI -- double-click app (longer term)

A standalone installable app requiring no Python. Users download and run it like any
other Mac or Windows application.

- [ ] Bundle with PyInstaller (single-file or single-folder output)
- [ ] macOS: code-sign and notarize with Apple Developer account (required for Gatekeeper)
- [ ] Windows: optional code-signing to avoid SmartScreen warnings
- [ ] CI build matrix: macOS arm64, macOS x86_64, Windows x86_64
- [ ] GitHub Release assets for each platform
- [ ] Auto-update mechanism or release notification
