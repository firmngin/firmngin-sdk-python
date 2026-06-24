# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project skeleton, `pyproject.toml`, CI scaffold.
- `PLAN.md` — full design and phase plan.
- `keys.json.example` — config template.

## [0.1.0] — TBD

### Added
- Phase 1: `ClientConfig`, `KeysConfig` (load from `keys.json` / env), `paths.py`, `payloads.py`, `exceptions.py`.
- Phase 2: AES-128/256-GCM E2EE (packet format: `nonce[12] || ciphertext || tag[16]`).
- Phase 3: file-backed persistent offline publish queue, no database dependency.
- Phase 4: `aiomqtt` async client with TLS, mTLS, fingerprint pin, exponential backoff reconnect, LWT.
- Phase 5: `FirmnginClient` orchestrator with typed callbacks, `BatchEntityBuilder`, `LocationUpdateBuilder`, `ActiveSession` context manager.
- Phase 7: Image upload via `httpx` async multipart.
- Phase 8: NTP sync on connect.
- Phase 9: README, examples, MkDocs.
- Phase 10: `mypy --strict`, `ruff`, ≥90% coverage on core, `pip-audit`, `bandit`.

[Unreleased]: https://github.com/firmngin/firmngin-sdk-python/compare/HEAD
[0.1.0]: https://github.com/firmngin/firmngin-sdk-python/releases/tag/v0.1.0
