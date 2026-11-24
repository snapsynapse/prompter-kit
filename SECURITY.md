# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.4 | No; final release, unmaintained since the archive |
| 1.0.0 to 1.0.3 | No; use 1.0.4, which fixes browser-origin attacks on the local GUI |
| < 1.0 | No |

The repository was archived on 2026-11-24 and is read-only. No version
receives security fixes, and no further releases will ship. If you rely on
PrompterKit, use 1.0.4 or a maintained fork.

## Reporting a vulnerability

GitHub takes no new issues on an archived repository, and its documentation
does not say whether private vulnerability reports still reach one. Either way,
no fix will ship from this repository. Do not post vulnerability details in
public places that point at this project.

Forks may provide continued support; assess their provenance independently.
The scope below records what the project treated as a vulnerability.

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
