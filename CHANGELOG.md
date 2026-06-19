# Changelog

All notable changes to UCI Scout will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2025-06-19

Initial public release.

### Added
- AST-based entry point crawler — detects HTTP routes, CLI commands, WebSocket handlers, Celery/APScheduler tasks, event hooks, gRPC handlers, public functions, and class methods
- Framework detection for 18 frameworks: FastAPI, Flask, Starlette, Sanic, Litestar, aiohttp, Tornado, Click, Typer, Celery, APScheduler, gRPC, SQLAlchemy, PyQt5, PyQt6, Django, argparse, UCI
- UCI compatibility scoring (0–100) with per-signal breakdown
- Terminal report renderer with ANSI colour output (`scout_report.py`)
- UCI manifest scaffold generator (`scout_manifest.py`) — produces `UCIManifest` JSON with inferred execution modes, risk levels, input/output schema stubs, transport block, and governance defaults
- PyQt6 desktop GUI (`scout_gui.py`) — score ring, entry point explorer, scaffold viewer, JSON report, scan log
- 177-test suite covering all heuristics, AST extraction, crawler integration, scoring, scaffold generation, and edge cases
- `--json`, `--scaffold`, `--full`, `--depth`, `--quiet` CLI flags
- Zero external dependencies for CLI — Python 3.10+ stdlib only
