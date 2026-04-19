# Roadmap

## Near-term

- [ ] Upload social preview image (1280x640) on GitHub repo settings
- [ ] Build landing page with `/canonical-spec-page`
- [ ] Set `homepageUrl` on repo once landing page is live
- [ ] Publish distribution content (dev.to, blog, LinkedIn) via `/promo-orchestrator`

## GUI -- web UI (recommended next feature)

A local web server opened in the browser. No installation beyond Python + Flask.
Single command: `python3 elgato_prompter_tools_gui.py`

- [ ] Flask routes wrapping existing import/export/list functions
- [ ] Script list table with GUID, friendly name, index
- [ ] Import form with drag-and-drop file input and name/index fields
- [ ] Single-script export by name or GUID
- [ ] Export-all to a chosen directory
- [ ] Status and error feedback in UI
- [ ] Auto-open browser on launch

## GUI -- double-click app (longer term)

A standalone installable app requiring no Python. Users download and run it like any other Mac or Windows application.

- [ ] Bundle with PyInstaller (single-file or single-folder output)
- [ ] macOS: code-sign and notarize with Apple Developer account (required for Gatekeeper)
- [ ] Windows: optional code-signing to avoid SmartScreen warnings
- [ ] CI build matrix: macOS arm64, macOS x86_64, Windows x86_64
- [ ] GitHub Release assets for each platform
- [ ] Auto-update mechanism or release notification
