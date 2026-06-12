# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | Yes (security fixes only) |
| < 1.0 | No |

PrompterKit 1.0.x is feature-complete and in maintenance mode. No feature
development is planned, but security reports against 1.0.x are still
reviewed and fixed.

## Reporting a vulnerability

Please report security issues privately via GitHub Security Advisories:

https://github.com/snapsynapse/prompter-kit/security/advisories/new

Do not open a public issue for security reports.

Expect an initial response within 7 days. If the report is confirmed, a
fix and coordinated disclosure will be scheduled from there.

## Scope

PrompterKit writes to the Camera Hub data directory on the local machine
and produces backup zip archives. In-scope reports include:

- Path traversal or zip-slip during `restore`
- Arbitrary file write outside the Camera Hub data directory
- Corruption of `AppSettings.json` that is not recoverable
- Code execution triggered by a crafted `.txt`, `.md`, or backup zip
- Remote code execution via the local web GUI (Flask app)

Out of scope:

- Issues requiring the attacker to already have write access to the
  Camera Hub data directory
- Vulnerabilities in Elgato Camera Hub itself
- Denial of service against a local-only server bound to `127.0.0.1`
