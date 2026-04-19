# Roadmap

## GUI -- double-click app (longer term)

A standalone installable app requiring no Python. Users download and run it like any
other Mac or Windows application.

- [ ] Bundle with PyInstaller (single-file or single-folder output)
- [ ] macOS: code-sign and notarize with Apple Developer account (required for Gatekeeper)
- [ ] Windows: optional code-signing to avoid SmartScreen warnings
- [ ] CI build matrix: macOS arm64, macOS x86_64, Windows x86_64
- [ ] GitHub Release assets for each platform
- [ ] Auto-update mechanism or release notification
