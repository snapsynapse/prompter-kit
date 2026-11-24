# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.4 | Best-effort security review |
| 1.0.0 to 1.0.3 | No; upgrade to 1.0.4, which fixes browser-origin attacks on the local GUI |
| < 1.0 | No |

PrompterKit 1.0.x is feature-complete and in maintenance mode. No feature
development or Camera Hub compatibility tracking is planned. Security reports
against 1.0.x may be reviewed and addressed as maintainer capacity allows.

## Reporting a vulnerability

Please report security issues privately via GitHub Security Advisories:

https://github.com/snapsynapse/prompter-kit/security/advisories/new

Do not open a public issue for security reports.

There is no guaranteed response, fix, or remediation timeline. A private report
is welcome but does not create a commitment to issue a patch. Forks may provide
continued support; assess their provenance independently.

## Scope

PrompterKit writes to the Camera Hub data directory on the local machine
and produces backup zip archives. In-scope reports include:

- Path traversal or zip-slip during `restore`
- Arbitrary file write outside the Camera Hub data directory
- Corruption of `AppSettings.json` that is not recoverable
- Code execution triggered by a crafted `.txt`, `.md`, or backup zip
- Remote code execution via the local web GUI (Flask app)
- A web page reaching the local web GUI from the browser, for example through
  DNS rebinding or cross-site request forgery
- Script injection in the local web GUI through a script name or backup zip

Out of scope:

- Issues requiring the attacker to already have write access to the
  Camera Hub data directory
- Vulnerabilities in Elgato Camera Hub itself
- Denial of service against a local-only server bound to `127.0.0.1`
