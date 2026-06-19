<div align="center">

```
   ███████╗ ██████╗ ██████╗ ██╗   ██╗████████╗
   ██╔════╝██╔════╝██╔═══██╗██║   ██║╚══██╔══╝
 ███████╗██║     ██║   ██║██║   ██║   ██║
 ╚════██║██║     ██║   ██║██║   ██║   ██║
 ███████║╚██████╗╚██████╔╝╚██████╔╝   ██║
 ╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝
```

**UCI Scout** — Make your Python app callable by AI agents in under an hour

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green?style=flat-square)](LICENSE)
[![UCI Protocol](https://img.shields.io/badge/UCI-v0.1-00B4D8?style=flat-square)](https://github.com/uci-protocol)
[![Tests](https://img.shields.io/badge/tests-177%20passing-3FB950?style=flat-square)](test_scout.py)
[![No dependencies](https://img.shields.io/badge/dependencies-none-lightgrey?style=flat-square)]()

</div>

---

UCI Scout crawls your Python project, discovers every API and entry point an AI agent could use, scores how ready your code is for [UCI (Universal Capability Interface)](https://github.com/7h3v01d/uci-protocol) integration, and generates a manifest scaffold to get you started — without touching a single line of your existing code.

```bash
python scout.py /your/project --full
```

```
  ENTRY POINTS DISCOVERED
    Total:         67
    HTTP routes:   23   ← FastAPI routes, auto-detected
    CLI commands:   4   ← Click/Typer commands
    Functions:     18   ← Public callables
    Class methods: 22   ← Service layer methods

  UCI COMPATIBILITY
    Score:  [████████████████████░░░░░░░░░░] 72/100

    ✓  23 HTTP routes — map directly to UCI actions over HTTP transport
    ✓  REST framework detected — UCI transport layer addable with minimal changes
    ✓  4 CLI commands — wrap as UCI actions via IPC transport
```

---

## What is UCI?

[UCI (Universal Capability Interface)](https://github.com/7h3v01d/uci-protocol) is an open protocol that lets AI agents discover and safely invoke capabilities in your software — with built-in governance, risk controls, and audit trails. Think of it as a typed, governed API contract between your app and any AI agent that wants to use it.

UCI Scout is the fastest way to find out what a UCI integration would look like for *your* project, before you write any integration code.

---

## Install

No pip install required for the CLI. Just clone and run.

```bash
git clone https://github.com/7h3v01d/uci-scout
cd uci-scout
python scout.py --help
```

For the desktop GUI:

```bash
pip install PyQt6
python scout_gui.py
```

**Requirements:** Python 3.10+, stdlib only (CLI) · PyQt6 (GUI only)

---

## Usage

```bash
# Scan a project and see the full report
python scout.py /path/to/project

# Save a UCI manifest scaffold
python scout.py /path/to/project --scaffold --out uci_manifest.json

# Machine-readable JSON output (for CI or other tools)
python scout.py /path/to/project --json

# Report + scaffold in one pass
python scout.py /path/to/project --full
```

| Flag | Description |
|---|---|
| `--scaffold` | Generate UCI manifest scaffold |
| `--out FILE` | Write scaffold to `FILE` |
| `--json` | Machine-readable JSON report |
| `--full` | Report + scaffold together |
| `--depth N` | Max directory recursion depth (default: 8) |
| `--quiet` | Suppress per-file progress output |

---

## What Scout detects

Scout uses pure static AST analysis — it never imports or executes your code.

| Entry point | Detection |
|---|---|
| FastAPI / Flask / Starlette routes | `@app.get(...)`, `@router.post(...)` decorators |
| Sanic / Litestar / aiohttp / Tornado | Same decorator pattern |
| Click / Typer CLI commands | `@click.command()`, `@app.command()` |
| WebSocket handlers | `.websocket(...)` decorator |
| Celery / APScheduler tasks | `@app.task`, `@shared_task`, cron patterns |
| Event hooks | `on_*` / `handle_*` names, `@event` decorator |
| gRPC handlers | `grpc` / `servicer` patterns |
| Public functions | Module-level callables |
| Class methods | Public methods on public classes |
| Existing UCI | `UCIProvider`, `UCIManifest` anywhere in source |

---

## The UCI compatibility score

Scout scores how naturally your project maps to UCI on a 0–100 scale:

| Score | What it means |
|---|---|
| 70–100 | Great fit — generate the scaffold and start wiring |
| 40–69 | Moderate fit — some adapter work likely needed |
| 0–39 | Low coverage — target may need wrapping first |

---

## From Scout scan to UCI provider: 5 steps

```
1.  python scout.py /myproject --full
    See your entry points and compatibility score.

2.  python scout.py /myproject --scaffold --out uci_manifest.json
    Generate the manifest scaffold.

3.  Edit uci_manifest.json
    Fill in the TODO fields. Adjust risk levels and governance.

4.  pip install uci-python
    Install the UCI Python SDK.

5.  Subclass UCIProvider, register your action handlers.
    python uci_validate.py uci_manifest.json
    Ship it.
```

---

## Desktop GUI

A full PyQt6 desktop GUI ships alongside the CLI.

```bash
pip install PyQt6
python scout_gui.py
```

**Features:**
- UCI compatibility score ring (colour-coded green / amber / red)
- Sortable entry points table with live text filter, type and risk dropdowns
- Click any entry point to see params, return type, file location, UCI category
- Generated scaffold with JSON syntax highlighting, copy and save buttons
- Scan log streaming progress in real time on a background thread
- Remembers your last project path between sessions

---

## What Scout generates

The `--scaffold` flag outputs a ready-to-edit `UCIManifest` JSON. For every discovered entry point, Scout writes a full UCI action with:

- **`execution.mode`** — inferred: `sync` / `async` / `streaming` / `scheduled` / `event_driven`
- **`risk.level`** — `low` / `medium` / `high` from name heuristics
- **`risk.categories`** — `read_only`, `state_modifying`, `destructive`, `external_communication`, etc.
- **`permissions.operator_confirmation`** — `none` / `recommended` / `required` based on risk
- **`input_schema`** — JSON Schema stub built from Python type hints
- **`output_schema`** — stub from return type hint
- **`_scout_meta`** — source file and line number for easy navigation

Governance defaults are fail-closed: `default_action_policy: deny`.

<details>
<summary>Example scaffold output (click to expand)</summary>

```json
{
  "uci_manifest_version": "0.1",
  "node": {
    "node_id": "my-service",
    "node_type": "service",
    "version": "0.1.0",
    "description": "TODO: describe what my-service does"
  },
  "capabilities": [
    {
      "capability_id": "http_users",
      "category": "retrieval",
      "actions": [
        {
          "action_id": "get_users_list_users",
          "description": "TODO: describe this action",
          "execution": {
            "mode": "async",
            "timeout_ms": 10000,
            "idempotent": true,
            "side_effects": false
          },
          "risk": {
            "level": "low",
            "categories": ["read_only"]
          },
          "permissions": {
            "operator_confirmation": "none",
            "minimum_trust_state": "trusted"
          },
          "input_schema": {},
          "output_schema": {},
          "_scout_meta": {
            "source_file": "routes/users.py",
            "source_line": 18,
            "http_method": "GET",
            "http_path": "/users"
          }
        }
      ]
    }
  ],
  "governance": {
    "default_action_policy": "deny",
    "audit_required": true
  }
}
```

</details>

---

## Design principles

**Non-invasive.** Scout reads but never writes to your project. No decorators, no imports, no SDK required in the target.

**Zero target dependencies.** The CLI runs on Python 3.10+ stdlib. Drop it anywhere.

**Heuristic, not authoritative.** Risk levels and capability groupings are best-effort — you always review before deploying.

**Fail-closed by default.** Generated manifests set `default_action_policy: deny`. You opt in to permissions explicitly.

---

## Limitations

- Python only in v0.1 — TypeScript / Go analysers on the roadmap
- Static analysis only — routes registered dynamically at runtime won't be detected
- `argparse` CLIs are detected as a framework but individual subcommands aren't extracted

---

## Roadmap

- [ ] TypeScript / Node.js support
- [ ] OpenAPI spec ingestion to enrich action schemas
- [ ] `--ci` flag — non-zero exit when score falls below a threshold
- [ ] Interactive mode — confirm / rename each action before scaffold output
- [ ] Diff mode — compare a new scan against an existing UCI manifest
- [ ] Badge generator — add a UCI Scout score badge to your own README

---

## Contributing

Issues and PRs welcome. Run the test suite before submitting:

```bash
python test_scout.py
# ✓  All 177 tests passed.
```

Tests use real fixture files written to a temp directory — no mocks of the AST or filesystem.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

<div align="center">

Built by Leon Priest · companion tool for [UCI Protocol v0.1](https://github.com/7h3v01d/uci-protocol)

*If UCI Scout saved you time, consider starring the repo — it helps other developers find it.*

</div>
