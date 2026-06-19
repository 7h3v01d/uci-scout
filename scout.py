#!/usr/bin/env python3
"""
 ██████╗██████╗ ███████╗███████╗██████╗
██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗
██║     ██████╔╝█████╗  █████╗  ██████╔╝
██║     ██╔══██╗██╔══╝  ██╔══╝  ██╔═══╝
╚██████╗██║  ██║███████╗███████╗██║
 ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝

UCI Scout
==================================
Crawls a target Python project to discover all API entry points, HTTP routes,
CLI commands, callable interfaces, and event hooks that can be mapped to UCI
capabilities. Outputs a compatibility report and generates a UCI manifest scaffold.

Usage
-----
    python scout.py <target_path>
    python scout.py <target_path> --json
    python scout.py <target_path> --scaffold
    python scout.py <target_path> --scaffold --out manifest_scout.json
    python scout.py <target_path> --full

Flags
-----
    --json       Emit machine-readable JSON report to stdout
    --scaffold   Generate a UCI manifest scaffold from discovered entry points
    --out FILE   Write scaffold to FILE instead of stdout
    --full       Run all analysis passes and emit report + scaffold
    --depth N    Max directory recursion depth (default: 8)
    --quiet      Suppress progress output
"""

from __future__ import annotations

import sys
import os
import ast
import re
import json
import argparse
import importlib.util
from dataclasses import dataclass, field, asdict
from typing import Any
from pathlib import Path


# ─────────────────────────────────────────────────────────────────
# Version
# ─────────────────────────────────────────────────────────────────

SCOUT_VERSION = "0.1.0"
UCI_TARGET_VERSION = "0.1"

# ─────────────────────────────────────────────────────────────────
# Discovery result types
# ─────────────────────────────────────────────────────────────────

@dataclass
class EntryPoint:
    """A single discovered callable entry point in the target program."""
    kind: str           # http_route | cli_command | public_function | class_method |
                        # fastapi_route | flask_route | django_view | event_hook |
                        # rpc_handler | websocket | scheduler | uci_action
    name: str           # Canonical name (e.g. "create_note" or "POST /api/notes")
    module: str         # Python module path (e.g. "app.routes.notes")
    file: str           # Relative file path
    line: int           # Line number
    description: str = ""
    params: list[str] = field(default_factory=list)
    return_hint: str = ""
    decorators: list[str] = field(default_factory=list)
    http_method: str = ""    # GET | POST | PUT | DELETE | PATCH | WS
    http_path: str = ""      # /api/notes/{id}
    is_async: bool = False
    risk_guess: str = "low"  # low | medium | high — heuristic
    uci_category: str = ""   # mapped UCI capability category
    uci_execution_mode: str = "sync"
    confidence: str = "high" # high | medium | low — detection confidence

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CrawlResult:
    """Full result of crawling a target directory."""
    target_path: str
    scout_version: str = SCOUT_VERSION
    uci_target_version: str = UCI_TARGET_VERSION

    # Discovery stats
    files_scanned: int = 0
    python_files: int = 0
    config_files_found: list[str] = field(default_factory=list)

    # Framework detections
    frameworks: list[str] = field(default_factory=list)   # fastapi, flask, django, typer, click, etc.
    has_existing_uci: bool = False

    # Entry points by category
    http_routes: list[EntryPoint] = field(default_factory=list)
    cli_commands: list[EntryPoint] = field(default_factory=list)
    public_functions: list[EntryPoint] = field(default_factory=list)
    class_methods: list[EntryPoint] = field(default_factory=list)
    event_hooks: list[EntryPoint] = field(default_factory=list)
    rpc_handlers: list[EntryPoint] = field(default_factory=list)
    websocket_handlers: list[EntryPoint] = field(default_factory=list)
    scheduler_tasks: list[EntryPoint] = field(default_factory=list)

    # Warnings and notes
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # UCI compatibility score (0–100)
    uci_compatibility_score: int = 0
    uci_compatibility_notes: list[str] = field(default_factory=list)

    @property
    def all_entry_points(self) -> list[EntryPoint]:
        return (
            self.http_routes +
            self.cli_commands +
            self.public_functions +
            self.class_methods +
            self.event_hooks +
            self.rpc_handlers +
            self.websocket_handlers +
            self.scheduler_tasks
        )

    @property
    def total_entry_points(self) -> int:
        return len(self.all_entry_points)

    def to_dict(self) -> dict:
        return {
            "scout_version": self.scout_version,
            "uci_target_version": self.uci_target_version,
            "target_path": self.target_path,
            "files_scanned": self.files_scanned,
            "python_files": self.python_files,
            "config_files_found": self.config_files_found,
            "frameworks": self.frameworks,
            "has_existing_uci": self.has_existing_uci,
            "uci_compatibility_score": self.uci_compatibility_score,
            "uci_compatibility_notes": self.uci_compatibility_notes,
            "warnings": self.warnings,
            "notes": self.notes,
            "summary": {
                "total_entry_points": self.total_entry_points,
                "http_routes": len(self.http_routes),
                "cli_commands": len(self.cli_commands),
                "public_functions": len(self.public_functions),
                "class_methods": len(self.class_methods),
                "event_hooks": len(self.event_hooks),
                "rpc_handlers": len(self.rpc_handlers),
                "websocket_handlers": len(self.websocket_handlers),
                "scheduler_tasks": len(self.scheduler_tasks),
            },
            "entry_points": {
                "http_routes": [e.to_dict() for e in self.http_routes],
                "cli_commands": [e.to_dict() for e in self.cli_commands],
                "public_functions": [e.to_dict() for e in self.public_functions],
                "class_methods": [e.to_dict() for e in self.class_methods],
                "event_hooks": [e.to_dict() for e in self.event_hooks],
                "rpc_handlers": [e.to_dict() for e in self.rpc_handlers],
                "websocket_handlers": [e.to_dict() for e in self.websocket_handlers],
                "scheduler_tasks": [e.to_dict() for e in self.scheduler_tasks],
            },
        }


# ─────────────────────────────────────────────────────────────────
# Heuristics helpers
# ─────────────────────────────────────────────────────────────────

# Map common decorator / function name patterns to UCI capability categories.
# Keywords are matched as whole tokens (split on _ and spaces) to avoid
# substring collisions like "log" matching "login" or "record" matching "audio".
_UCI_CATEGORY_MAP: list[tuple[list[str], str]] = [
    (["search", "find", "get", "fetch", "list", "query", "read", "retrieve", "lookup"], "retrieval"),
    (["delete", "remove", "purge", "clear", "reset", "drop", "destroy"], "storage"),
    (["save", "store", "write", "insert", "create", "add", "put", "upload", "persist"], "storage"),
    (["generate", "produce", "render", "build", "draft", "compose", "synthesize"], "generation"),
    (["analyze", "analyse", "classify", "detect", "evaluate", "score", "compare", "audit"], "analysis"),
    (["transform", "convert", "encode", "decode", "parse", "format", "translate", "process"], "transformation"),
    (["send", "email", "notify", "message", "publish", "broadcast", "push", "alert", "webhook"], "communication"),
    (["run", "execute", "invoke", "spawn", "launch", "start", "trigger", "dispatch", "call"], "execution"),
    (["policy", "govern", "permit", "deny", "approve", "authorize", "validate", "enforce"], "governance"),
    (["monitor", "watch", "health", "status", "metrics", "logging", "trace", "observe", "report"], "monitoring"),
    (["image", "video", "vision", "ocr", "screenshot", "photo", "visual"], "vision"),
    (["audio", "speech", "tts", "stt", "transcribe", "voice", "recording"], "audio"),
    (["login", "auth", "token", "user", "identity", "session", "register", "profile"], "identity"),
    (["request", "http", "socket", "connect", "download", "scrape", "ping"], "network"),
    (["encrypt", "decrypt", "hash", "sign", "verify", "secure", "certificate"], "security"),
]

def _tokenize(name: str) -> set[str]:
    """Split a name into underscore/space tokens for whole-word keyword matching."""
    import re
    return set(re.split(r'[_\s]+', name.lower()))

_RISK_HIGH_PATTERNS = [
    "delete", "remove", "drop", "destroy", "purge", "wipe", "overwrite",
    "execute", "run", "spawn", "shell", "subprocess", "os.system",
    "send_email", "send_sms", "payment", "charge", "refund", "transfer",
    "admin", "root", "sudo", "privilege",
    "password", "secret", "private_key", "credential",
]

_RISK_MEDIUM_PATTERNS = [
    "write", "update", "modify", "patch", "create", "insert",
    "upload", "publish", "broadcast", "notify",
    "login", "auth", "register",
    "download", "fetch_url", "request",
]

def _guess_risk(name: str, params: list[str]) -> str:
    n = name.lower()
    for p in _RISK_HIGH_PATTERNS:
        if p in n:
            return "high"
    for p in _RISK_MEDIUM_PATTERNS:
        if p in n:
            return "medium"
    return "low"

def _guess_uci_category(name: str, decorators: list[str]) -> str:
    # Tokenise the name for whole-word matching (avoids "log" matching "login")
    name_tokens = _tokenize(name)
    # Also do substring match on decorator strings (they contain path/method info)
    deco_str = " ".join(decorators).lower()
    for keywords, category in _UCI_CATEGORY_MAP:
        for kw in keywords:
            if kw in name_tokens or kw in deco_str:
                return category
    return "utility"

def _guess_execution_mode(is_async: bool, decorators: list[str], name: str) -> str:
    deco_str = " ".join(decorators).lower()
    if "websocket" in deco_str or "ws" in name.lower():
        return "streaming"
    if "scheduled" in deco_str or "cron" in deco_str or "periodic" in name.lower():
        return "scheduled"
    if "event" in deco_str or "on_" in name.lower() or "handle_" in name.lower():
        return "event_driven"
    if is_async:
        return "async"
    return "sync"

def _extract_params(func_def: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    params = []
    args = func_def.args
    all_args = list(args.args) + list(args.posonlyargs) + list(args.kwonlyargs)
    for arg in all_args:
        if arg.arg in ("self", "cls", "request", "req", "response", "resp"):
            continue
        hint = ""
        if arg.annotation:
            try:
                hint = ast.unparse(arg.annotation)
            except Exception:
                pass
        params.append(f"{arg.arg}: {hint}" if hint else arg.arg)
    if args.vararg:
        params.append(f"*{args.vararg.arg}")
    if args.kwarg:
        params.append(f"**{args.kwarg.arg}")
    return params

def _extract_return_hint(func_def: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if func_def.returns:
        try:
            return ast.unparse(func_def.returns)
        except Exception:
            return ""
    return ""

def _decorator_names(func_def: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names = []
    for deco in func_def.decorator_list:
        try:
            names.append(ast.unparse(deco))
        except Exception:
            pass
    return names

def _is_public(name: str) -> bool:
    return not name.startswith("_")

def _first_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str:
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
        doc = node.body[0].value.value.strip()
        return doc.split("\n")[0][:120]
    return ""


# ─────────────────────────────────────────────────────────────────
# Framework detectors (file-level patterns)
# ─────────────────────────────────────────────────────────────────

_FRAMEWORK_SIGNATURES: dict[str, list[str]] = {
    "fastapi":   ["from fastapi", "import fastapi", "FastAPI(", "APIRouter("],
    "flask":     ["from flask", "import flask", "Flask(__name__", "@app.route"],
    "django":    ["from django", "import django", "urlpatterns", "views.py"],
    "starlette": ["from starlette", "import starlette"],
    "aiohttp":   ["from aiohttp", "import aiohttp"],
    "tornado":   ["from tornado", "import tornado"],
    "sanic":     ["from sanic", "import sanic"],
    "litestar":  ["from litestar", "import litestar"],
    "typer":     ["import typer", "from typer", "typer.Typer"],
    "click":     ["import click", "from click", "@click.command", "@click.group"],
    "argparse":  ["import argparse", "ArgumentParser("],
    "grpc":      ["import grpc", "from grpc", "grpc.server"],
    "celery":    ["from celery", "import celery", "Celery(", "@app.task"],
    "apscheduler": ["from apscheduler", "import apscheduler", "BlockingScheduler", "AsyncIOScheduler"],
    "pyqt6":     ["from PyQt6", "import PyQt6", "QApplication"],
    "pyqt5":     ["from PyQt5", "import PyQt5"],
    "sqlalchemy":["from sqlalchemy", "import sqlalchemy", "Session(", "engine ="],
    "uci":       ["from uci", "import uci", "UCIProvider", "UCIManifest", "uci_manifest_version"],
}

def _detect_frameworks(source: str) -> list[str]:
    found = []
    for fw, sigs in _FRAMEWORK_SIGNATURES.items():
        if any(sig in source for sig in sigs):
            found.append(fw)
    return found


# ─────────────────────────────────────────────────────────────────
# AST-based entry point extractors
# ─────────────────────────────────────────────────────────────────

_HTTP_METHOD_DECOS = {
    "get": "GET", "post": "POST", "put": "PUT",
    "delete": "DELETE", "patch": "PATCH", "options": "OPTIONS", "head": "HEAD",
    "route": "ANY",
}
_WS_DECOS = {"websocket", "ws", "on_message", "on_connect"}


def _parse_http_route_from_decorator(deco_str: str) -> tuple[str, str]:
    """Try to extract HTTP method and path from a decorator string like '@app.get("/users/{id}")'."""
    m = re.match(r".*\.(get|post|put|delete|patch|options|head|route)\s*\(\s*['\"]([^'\"]+)['\"]", deco_str, re.I)
    if m:
        return _HTTP_METHOD_DECOS.get(m.group(1).lower(), "ANY"), m.group(2)
    m = re.match(r".*\.(websocket)\s*\(\s*['\"]([^'\"]+)['\"]", deco_str, re.I)
    if m:
        return "WS", m.group(2)
    return "", ""


def _extract_entry_points_from_ast(
    tree: ast.Module,
    file_rel: str,
    module_path: str,
    frameworks: list[str],
) -> list[EntryPoint]:
    results: list[EntryPoint] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        func_name = node.name
        decos = _decorator_names(node)
        deco_lower = " ".join(decos).lower()
        params = _extract_params(node)
        ret = _extract_return_hint(node)
        desc = _first_docstring(node)
        is_async = isinstance(node, ast.AsyncFunctionDef)
        line = node.lineno

        # ── FastAPI / Flask / Starlette HTTP routes ──────────────────
        is_http = False
        http_method, http_path = "", ""
        for deco in decos:
            method, path = _parse_http_route_from_decorator(deco)
            if method == "WS":
                ep = EntryPoint(
                    kind="websocket",
                    name=func_name,
                    module=module_path,
                    file=file_rel,
                    line=line,
                    description=desc,
                    params=params,
                    return_hint=ret,
                    decorators=decos,
                    http_method="WS",
                    http_path=path,
                    is_async=is_async,
                    risk_guess="medium",
                    uci_category="network",
                    uci_execution_mode="streaming",
                    confidence="high",
                )
                results.append(ep)
                is_http = True
                break
            if method:
                ep = EntryPoint(
                    kind="http_route",
                    name=f"{method} {path}  ({func_name})",
                    module=module_path,
                    file=file_rel,
                    line=line,
                    description=desc,
                    params=params,
                    return_hint=ret,
                    decorators=decos,
                    http_method=method,
                    http_path=path,
                    is_async=is_async,
                    risk_guess=_guess_risk(func_name, params),
                    uci_category=_guess_uci_category(func_name, decos),
                    uci_execution_mode=_guess_execution_mode(is_async, decos, func_name),
                    confidence="high",
                )
                results.append(ep)
                is_http = True
                break
        if is_http:
            continue

        # ── Click / Typer CLI commands ────────────────────────────────
        if any(kw in deco_lower for kw in ["click.command", "click.group", "command()", "group()",
                                            "app.command", "typer.command", "app.callback"]):
            ep = EntryPoint(
                kind="cli_command",
                name=func_name,
                module=module_path,
                file=file_rel,
                line=line,
                description=desc,
                params=params,
                return_hint=ret,
                decorators=decos,
                is_async=is_async,
                risk_guess=_guess_risk(func_name, params),
                uci_category=_guess_uci_category(func_name, decos),
                uci_execution_mode=_guess_execution_mode(is_async, decos, func_name),
                confidence="high",
            )
            results.append(ep)
            continue

        # ── Celery tasks ──────────────────────────────────────────────
        if any(kw in deco_lower for kw in ["app.task", "celery.task", "shared_task", ".task("]):
            ep = EntryPoint(
                kind="scheduler_task",
                name=func_name,
                module=module_path,
                file=file_rel,
                line=line,
                description=desc,
                params=params,
                return_hint=ret,
                decorators=decos,
                is_async=is_async,
                risk_guess=_guess_risk(func_name, params),
                uci_category=_guess_uci_category(func_name, decos),
                uci_execution_mode="scheduled",
                confidence="high",
            )
            results.append(ep)
            continue

        # ── APScheduler jobs ─────────────────────────────────────────
        if any(kw in deco_lower for kw in ["scheduler", "scheduled_job", "cron", "interval"]):
            ep = EntryPoint(
                kind="scheduler_task",
                name=func_name,
                module=module_path,
                file=file_rel,
                line=line,
                description=desc,
                params=params,
                return_hint=ret,
                decorators=decos,
                is_async=is_async,
                risk_guess=_guess_risk(func_name, params),
                uci_category="monitoring",
                uci_execution_mode="scheduled",
                confidence="medium",
            )
            results.append(ep)
            continue

        # ── Event hooks / signal handlers ─────────────────────────────
        if (func_name.startswith("on_") or func_name.startswith("handle_")
                or any(kw in deco_lower for kw in ["event", "signal", "hook", ".on(", ".listen("])):
            ep = EntryPoint(
                kind="event_hook",
                name=func_name,
                module=module_path,
                file=file_rel,
                line=line,
                description=desc,
                params=params,
                return_hint=ret,
                decorators=decos,
                is_async=is_async,
                risk_guess=_guess_risk(func_name, params),
                uci_category=_guess_uci_category(func_name, decos),
                uci_execution_mode="event_driven",
                confidence="medium",
            )
            results.append(ep)
            continue

        # ── gRPC service handlers ─────────────────────────────────────
        if any(kw in deco_lower for kw in ["grpc", "rpc", "servicer"]):
            ep = EntryPoint(
                kind="rpc_handler",
                name=func_name,
                module=module_path,
                file=file_rel,
                line=line,
                description=desc,
                params=params,
                return_hint=ret,
                decorators=decos,
                is_async=is_async,
                risk_guess=_guess_risk(func_name, params),
                uci_category=_guess_uci_category(func_name, decos),
                uci_execution_mode=_guess_execution_mode(is_async, decos, func_name),
                confidence="medium",
            )
            results.append(ep)
            continue

        # ── Public functions (top-level only, not inside classes) ─────
        # (We check parent context below in the class-aware pass; here we
        #  only catch module-level public functions that weren't decorated.)
        # We do a lightweight check: if the function is inside a class,
        # skip here — handled in the class pass.
        # Note: ast.walk does not give parent context; we mark these later.

    # ── Class method pass (public methods of public classes) ─────────
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_public(node.name):
            continue
        class_decos = _decorator_names(node)
        class_desc = _first_docstring(node)

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_public(item.name):
                continue
            if item.name in ("__init__", "__str__", "__repr__", "__eq__",
                             "__hash__", "__len__", "__iter__", "__next__",
                             "__enter__", "__exit__", "__del__"):
                continue

            decos = _decorator_names(item)
            deco_lower = " ".join(decos).lower()
            params = _extract_params(item)
            ret = _extract_return_hint(item)
            desc = _first_docstring(item)
            is_async = isinstance(item, ast.AsyncFunctionDef)

            # Skip if this was already caught as http route
            already = any(
                e.file == file_rel and e.line == item.lineno
                for e in results
            )
            if already:
                continue

            ep = EntryPoint(
                kind="class_method",
                name=f"{node.name}.{item.name}",
                module=module_path,
                file=file_rel,
                line=item.lineno,
                description=desc or class_desc,
                params=params,
                return_hint=ret,
                decorators=decos,
                is_async=is_async,
                risk_guess=_guess_risk(item.name, params),
                uci_category=_guess_uci_category(item.name, decos),
                uci_execution_mode=_guess_execution_mode(is_async, decos, item.name),
                confidence="medium",
            )
            results.append(ep)

    # ── Module-level public functions (not in any class) ─────────────
    class_method_lines = {e.line for e in results if e.kind == "class_method"}
    existing_lines = {e.line for e in results}

    for node in tree.body:  # Only top-level nodes
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _is_public(node.name):
            continue
        if node.lineno in existing_lines:
            continue

        decos = _decorator_names(node)
        params = _extract_params(node)
        ret = _extract_return_hint(node)
        desc = _first_docstring(node)
        is_async = isinstance(node, ast.AsyncFunctionDef)

        ep = EntryPoint(
            kind="public_function",
            name=node.name,
            module=module_path,
            file=file_rel,
            line=node.lineno,
            description=desc,
            params=params,
            return_hint=ret,
            decorators=decos,
            is_async=is_async,
            risk_guess=_guess_risk(node.name, params),
            uci_category=_guess_uci_category(node.name, decos),
            uci_execution_mode=_guess_execution_mode(is_async, decos, node.name),
            confidence="medium",
        )
        results.append(ep)

    return results


# ─────────────────────────────────────────────────────────────────
# Directory crawler
# ─────────────────────────────────────────────────────────────────

_SKIP_DIRS = {
    "__pycache__", ".git", ".hg", ".svn", "node_modules", ".venv", "venv",
    "env", ".env", "dist", "build", "*.egg-info", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "htmlcov", ".tox", "site-packages",
}

_CONFIG_FILES = {
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "Pipfile", "Pipfile.lock", "poetry.lock",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    "openapi.json", "openapi.yaml", "swagger.json", "swagger.yaml",
    ".env.example", "config.py", "settings.py", "config.yaml", "config.yml",
    "uci_manifest.json", "manifest.json",
}


class ScoutCrawler:
    """
    Crawls a Python project directory, extracting all discoverable
    entry points and producing a CrawlResult.
    """

    def __init__(
        self,
        target_path: str,
        max_depth: int = 8,
        quiet: bool = False,
    ) -> None:
        self.target = Path(target_path).resolve()
        self.max_depth = max_depth
        self.quiet = quiet
        self._all_frameworks: set[str] = set()

    def _log(self, msg: str) -> None:
        if not self.quiet:
            print(f"  [scout] {msg}", file=sys.stderr)

    def crawl(self) -> CrawlResult:
        result = CrawlResult(target_path=str(self.target))

        if not self.target.exists():
            result.warnings.append(f"Target path does not exist: {self.target}")
            return result

        self._log(f"Crawling: {self.target}")

        all_py_files: list[Path] = []
        all_eps: list[EntryPoint] = []

        for root, dirs, files in os.walk(self.target):
            root_path = Path(root)
            depth = len(root_path.relative_to(self.target).parts)
            if depth > self.max_depth:
                dirs.clear()
                continue

            # Prune skipped dirs
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.endswith(".egg-info")]

            result.files_scanned += len(files)

            for fname in files:
                fpath = root_path / fname

                # Config/manifest detection
                if fname in _CONFIG_FILES:
                    rel = str(fpath.relative_to(self.target))
                    result.config_files_found.append(rel)

                if not fname.endswith(".py"):
                    continue

                all_py_files.append(fpath)
                result.python_files += 1

                rel_path = str(fpath.relative_to(self.target))
                module_path = rel_path.replace(os.sep, ".").removesuffix(".py")

                try:
                    source = fpath.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    result.warnings.append(f"Could not read {rel_path}: {e}")
                    continue

                # Framework detection
                fws = _detect_frameworks(source)
                self._all_frameworks.update(fws)

                # UCI detection
                if "uci" in fws or "UCIProvider" in source or "uci_manifest_version" in source:
                    result.has_existing_uci = True

                # AST parse
                try:
                    tree = ast.parse(source, filename=str(fpath))
                except SyntaxError as e:
                    result.warnings.append(f"Syntax error in {rel_path}: {e}")
                    continue

                eps = _extract_entry_points_from_ast(tree, rel_path, module_path, list(self._all_frameworks))
                all_eps.extend(eps)

                if eps:
                    self._log(f"  {rel_path}: {len(eps)} entry point(s)")

        result.frameworks = sorted(self._all_frameworks)

        # Categorise entry points
        for ep in all_eps:
            if ep.kind == "http_route":
                result.http_routes.append(ep)
            elif ep.kind == "cli_command":
                result.cli_commands.append(ep)
            elif ep.kind == "class_method":
                result.class_methods.append(ep)
            elif ep.kind == "event_hook":
                result.event_hooks.append(ep)
            elif ep.kind in ("rpc_handler",):
                result.rpc_handlers.append(ep)
            elif ep.kind == "websocket":
                result.websocket_handlers.append(ep)
            elif ep.kind == "scheduler_task":
                result.scheduler_tasks.append(ep)
            else:
                result.public_functions.append(ep)

        # Score UCI compatibility
        result.uci_compatibility_score, result.uci_compatibility_notes = self._score_compatibility(result)

        self._log(
            f"Done. {result.total_entry_points} entry points across "
            f"{result.python_files} Python files."
        )
        return result

    def _score_compatibility(self, r: CrawlResult) -> tuple[int, list[str]]:
        score = 0
        notes = []

        if r.total_entry_points > 0:
            score += 30
            notes.append(f"✓ {r.total_entry_points} discoverable entry points found")
        else:
            notes.append("✗ No entry points found — UCI manifest would be empty")
            return 0, notes

        if r.http_routes:
            score += 20
            notes.append(f"✓ {len(r.http_routes)} HTTP routes — map directly to UCI actions over HTTP transport")

        if r.cli_commands:
            score += 15
            notes.append(f"✓ {len(r.cli_commands)} CLI commands — can be wrapped as UCI actions via IPC/local transport")

        if r.public_functions or r.class_methods:
            score += 10
            notes.append(f"✓ {len(r.public_functions) + len(r.class_methods)} callable functions/methods — candidate UCI actions")

        if r.has_existing_uci:
            score += 15
            notes.append("✓ Existing UCI integration detected — partial or full compatibility already present")

        if r.websocket_handlers:
            score += 5
            notes.append(f"✓ {len(r.websocket_handlers)} WebSocket handlers — map to streaming UCI actions")

        if r.scheduler_tasks:
            score += 5
            notes.append(f"✓ {len(r.scheduler_tasks)} scheduler tasks — map to scheduled UCI actions")

        if "fastapi" in r.frameworks or "flask" in r.frameworks or "starlette" in r.frameworks:
            score = min(score + 10, 100)
            notes.append("✓ REST framework detected — UCI HTTP transport layer can be added with minimal changes")

        if "openapi.json" in r.config_files_found or "openapi.yaml" in r.config_files_found:
            score = min(score + 5, 100)
            notes.append("✓ OpenAPI spec found — can be used to enrich UCI action schemas")

        score = min(score, 100)
        return score, notes


# ─────────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scout",
        description="UCI Scout — discovers entry points and generates UCI manifest scaffolds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("target", help="Path to the target project directory or file")
    p.add_argument("--json", action="store_true", help="Emit JSON report to stdout")
    p.add_argument("--scaffold", action="store_true", help="Generate UCI manifest scaffold")
    p.add_argument("--out", metavar="FILE", help="Write scaffold to FILE (default: stdout)")
    p.add_argument("--full", action="store_true", help="Report + scaffold in one pass")
    p.add_argument("--depth", type=int, default=8, metavar="N", help="Max crawl depth (default: 8)")
    p.add_argument("--quiet", action="store_true", help="Suppress progress output")
    p.add_argument("--version", action="version", version=f"scout {SCOUT_VERSION}")
    return p


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    crawler = ScoutCrawler(
        target_path=args.target,
        max_depth=args.depth,
        quiet=args.quiet,
    )
    result = crawler.crawl()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return

    if args.full or (not args.scaffold and not args.json):
        # Default: print the terminal report
        from scout_report import render_report
        render_report(result)

    if args.scaffold or args.full:
        from scout_manifest import generate_scaffold
        scaffold = generate_scaffold(result)
        out_str = json.dumps(scaffold, indent=2)
        if args.out:
            Path(args.out).write_text(out_str, encoding="utf-8")
            print(f"\n  [scout] Scaffold written to: {args.out}")
        else:
            print("\n" + "─" * 60)
            print("  UCI MANIFEST SCAFFOLD")
            print("─" * 60)
            print(out_str)


if __name__ == "__main__":
    main()
