"""
scout_manifest.py — UCI Manifest Scaffold Generator
=====================================================
Takes a CrawlResult and produces a valid UCI v0.1 manifest scaffold
with one capability per logical group of entry points and one action
per discovered entry point (up to a reasonable limit per capability).

The scaffold is not a final manifest — it is a starting point that
the developer finishes by filling in descriptions, tightening schemas,
and adjusting governance settings.
"""

from __future__ import annotations

import re
import uuid
import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scout import CrawlResult, EntryPoint


# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

_MAX_ACTIONS_PER_CAPABILITY = 20   # keep manifests readable
_MAX_PUBLIC_FUNCS = 30             # cap public_function + class_method noise


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert a free-form name to a valid UCI action_id / capability_id."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9_ ]", " ", s)
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"_+", "_", s)
    return s[:64] or "unnamed"


def _risk_to_confirmation(risk: str) -> str:
    return {
        "high":   "required",
        "medium": "recommended",
        "low":    "none",
    }.get(risk, "none")


def _risk_to_min_trust(risk: str) -> str:
    return {
        "high":   "trusted",
        "medium": "trusted",
        "low":    "trusted",
    }.get(risk, "trusted")


def _ep_to_action(ep: "EntryPoint") -> dict:
    """Convert a single EntryPoint to a UCI action dict."""
    # Build input schema stub from params
    props: dict[str, dict] = {}
    for p in ep.params:
        if ":" in p:
            param_name, hint = p.split(":", 1)
            param_name = param_name.strip().lstrip("*")
            hint = hint.strip()
            # Map Python type hints to JSON schema types
            jtype = _hint_to_json_type(hint)
            props[param_name] = {"type": jtype, "description": f""}
        elif p.strip():
            pname = p.strip().lstrip("*")
            if pname:
                props[pname] = {"type": "string", "description": ""}

    input_schema: dict = {}
    if props:
        input_schema = {
            "type": "object",
            "properties": props,
            "required": [k for k in props if not k.startswith("**")],
        }

    # Output schema stub
    output_schema: dict = {}
    if ep.return_hint:
        jtype = _hint_to_json_type(ep.return_hint)
        output_schema = {"type": jtype, "description": f"Return value: {ep.return_hint}"}

    action_id = _slugify(ep.name)

    return {
        "action_id":   action_id,
        "description": ep.description or f"TODO: describe {ep.name}",
        "execution": {
            "mode":                 ep.uci_execution_mode,
            "timeout_ms":          30000 if ep.uci_execution_mode == "async" else 10000,
            "idempotent":          ep.risk_guess == "low" and ep.kind in ("http_route", "public_function"),
            "side_effects":        ep.risk_guess in ("medium", "high"),
            "rollback_supported":  False,
            "requires_confirmation": ep.risk_guess == "high",
        },
        "risk": {
            "level":       ep.risk_guess,
            "categories":  _risk_to_categories(ep),
            "description": f"Heuristic risk assessment for {ep.name}. Review and adjust.",
        },
        "permissions": {
            "required_permissions":  [],
            "operator_confirmation": _risk_to_confirmation(ep.risk_guess),
            "minimum_trust_state":   _risk_to_min_trust(ep.risk_guess),
        },
        "input_schema":  input_schema,
        "output_schema": output_schema,
        "errors": [
            {
                "code":      "INTERNAL_ERROR",
                "message":   "An unexpected error occurred.",
                "retryable": True,
            }
        ],
        "_scout_meta": {
            "source_file":  ep.file,
            "source_line":  ep.line,
            "source_kind":  ep.kind,
            "confidence":   ep.confidence,
            "http_method":  ep.http_method,
            "http_path":    ep.http_path,
        },
    }


def _hint_to_json_type(hint: str) -> str:
    hint = hint.strip().lower()
    if hint in ("str", "string"):           return "string"
    if hint in ("int", "integer"):          return "integer"
    if hint in ("float", "number"):         return "number"
    if hint in ("bool", "boolean"):         return "boolean"
    if hint.startswith(("list", "tuple")):  return "array"
    if hint.startswith("dict"):             return "object"
    if hint in ("none", "nonetype"):        return "null"
    return "string"  # conservative fallback


def _risk_to_categories(ep: "EntryPoint") -> list[str]:
    cats: list[str] = []
    name = (ep.name + " " + ep.kind).lower()
    if any(kw in name for kw in ["delete", "remove", "drop", "destroy", "purge"]):
        cats.append("destructive")
        cats.append("irreversible")
    if any(kw in name for kw in ["write", "create", "update", "insert", "save", "store"]):
        cats.append("state_modifying")
    if ep.kind == "http_route" and ep.http_method in ("POST", "PUT", "DELETE", "PATCH"):
        cats.append("state_modifying")
    if any(kw in name for kw in ["file", "path", "disk", "read_file", "write_file"]):
        cats.append("filesystem_access")
    if any(kw in name for kw in ["email", "send", "notify", "webhook", "http", "request"]):
        cats.append("external_communication")
    if any(kw in name for kw in ["password", "token", "secret", "auth", "credential"]):
        cats.append("sensitive_data_access")
    if ep.kind in ("scheduler_task",):
        cats.append("operator_visible")
    if ep.uci_execution_mode in ("async", "streaming"):
        pass
    if not cats:
        cats.append("read_only")
    return list(set(cats))


# ─────────────────────────────────────────────────────────────────
# Capability grouping
# ─────────────────────────────────────────────────────────────────

def _group_eps_into_capabilities(result: "CrawlResult") -> list[dict]:
    """
    Groups discovered entry points into UCI capabilities.

    Grouping strategy:
      - HTTP routes → one capability per distinct path prefix, or one 'api' capability
      - CLI commands → one 'cli' capability
      - WebSocket handlers → one 'realtime' capability
      - Scheduler tasks → one 'background_tasks' capability
      - Event hooks → one 'event_handling' capability
      - RPC handlers → one 'rpc' capability
      - Public functions / class methods → one capability per module (or merged)
    """
    capabilities: list[dict] = []
    added_action_ids: set[str] = set()

    def _make_capability(
        cap_id: str,
        label: str,
        category: str,
        eps: list["EntryPoint"],
        description: str = "",
    ) -> dict | None:
        if not eps:
            return None
        actions = []
        for ep in eps[:_MAX_ACTIONS_PER_CAPABILITY]:
            action = _ep_to_action(ep)
            aid = action["action_id"]
            # Deduplicate action IDs within this capability
            if aid in added_action_ids:
                aid = f"{aid}_{ep.line}"
                action["action_id"] = aid
            added_action_ids.add(aid)
            actions.append(action)
        return {
            "capability_id": cap_id,
            "version": "1.0",
            "category": category,
            "description": description or f"TODO: describe {label}",
            "tags": [],
            "actions": actions,
        }

    # ── HTTP routes → group by path prefix ───────────────────────
    if result.http_routes:
        # Try to group by first path segment
        prefix_groups: dict[str, list["EntryPoint"]] = {}
        for ep in result.http_routes:
            parts = ep.http_path.strip("/").split("/")
            prefix = parts[0] if parts else "api"
            prefix = prefix or "api"
            prefix_groups.setdefault(prefix, []).append(ep)

        if len(prefix_groups) <= 6:
            for prefix, eps in prefix_groups.items():
                cap = _make_capability(
                    cap_id=f"http_{_slugify(prefix)}",
                    label=f"HTTP /{prefix}",
                    category=eps[0].uci_category if eps else "retrieval",
                    eps=eps,
                    description=f"HTTP endpoints under /{prefix}",
                )
                if cap:
                    capabilities.append(cap)
        else:
            # Too many prefixes — collapse into one capability
            cap = _make_capability(
                cap_id="http_api",
                label="HTTP API",
                category="retrieval",
                eps=result.http_routes,
                description="HTTP API endpoints",
            )
            if cap:
                capabilities.append(cap)

    # ── CLI commands ──────────────────────────────────────────────
    if result.cli_commands:
        cap = _make_capability(
            cap_id="cli_interface",
            label="CLI Interface",
            category="execution",
            eps=result.cli_commands,
            description="Command-line interface entry points",
        )
        if cap:
            capabilities.append(cap)

    # ── WebSocket handlers ────────────────────────────────────────
    if result.websocket_handlers:
        cap = _make_capability(
            cap_id="realtime_streams",
            label="Realtime Streams",
            category="network",
            eps=result.websocket_handlers,
            description="WebSocket and streaming connection handlers",
        )
        if cap:
            capabilities.append(cap)

    # ── Scheduler tasks ───────────────────────────────────────────
    if result.scheduler_tasks:
        cap = _make_capability(
            cap_id="background_tasks",
            label="Background Tasks",
            category="execution",
            eps=result.scheduler_tasks,
            description="Scheduled and background task entry points",
        )
        if cap:
            capabilities.append(cap)

    # ── Event hooks ───────────────────────────────────────────────
    if result.event_hooks:
        cap = _make_capability(
            cap_id="event_handling",
            label="Event Handling",
            category="monitoring",
            eps=result.event_hooks,
            description="Event hook and signal handler entry points",
        )
        if cap:
            capabilities.append(cap)

    # ── RPC handlers ──────────────────────────────────────────────
    if result.rpc_handlers:
        cap = _make_capability(
            cap_id="rpc_interface",
            label="RPC Interface",
            category="execution",
            eps=result.rpc_handlers,
            description="Remote procedure call handler entry points",
        )
        if cap:
            capabilities.append(cap)

    # ── Public functions / class methods ──────────────────────────
    # Group by module (top-level package)
    func_eps = (result.public_functions + result.class_methods)[:_MAX_PUBLIC_FUNCS]
    if func_eps:
        module_groups: dict[str, list["EntryPoint"]] = {}
        for ep in func_eps:
            parts = ep.module.split(".")
            top = parts[0] if parts else "core"
            module_groups.setdefault(top, []).append(ep)

        if len(module_groups) <= 8:
            for mod, eps in module_groups.items():
                cat = eps[0].uci_category if eps else "utility"
                cap = _make_capability(
                    cap_id=f"{_slugify(mod)}_functions",
                    label=f"{mod} functions",
                    category=cat,
                    eps=eps,
                    description=f"Callable functions from {mod} module",
                )
                if cap:
                    capabilities.append(cap)
        else:
            cap = _make_capability(
                cap_id="core_functions",
                label="Core Functions",
                category="utility",
                eps=func_eps,
                description="Core callable functions discovered by UCI Scout",
            )
            if cap:
                capabilities.append(cap)

    # Ensure at least one capability exists
    if not capabilities:
        capabilities.append({
            "capability_id": "placeholder",
            "version": "1.0",
            "category": "utility",
            "description": "TODO: No entry points discovered. Add capabilities manually.",
            "tags": [],
            "actions": [
                {
                    "action_id": "ping",
                    "description": "Basic health check action.",
                    "execution": {
                        "mode": "sync",
                        "timeout_ms": 1000,
                        "idempotent": True,
                        "side_effects": False,
                        "rollback_supported": False,
                        "requires_confirmation": False,
                    },
                    "risk": {"level": "none", "categories": ["read_only"], "description": ""},
                    "permissions": {
                        "required_permissions": [],
                        "operator_confirmation": "none",
                        "minimum_trust_state": "trusted",
                    },
                    "input_schema": {},
                    "output_schema": {"type": "object"},
                    "errors": [],
                }
            ],
        })

    return capabilities


# ─────────────────────────────────────────────────────────────────
# Transport inference
# ─────────────────────────────────────────────────────────────────

def _infer_transports(result: "CrawlResult") -> list[dict]:
    transports: list[dict] = []

    if any(fw in result.frameworks for fw in ("fastapi", "flask", "starlette", "aiohttp", "sanic", "litestar", "tornado")):
        transports.append({
            "transport_id": "http_primary",
            "type": "http",
            "endpoint": "http://localhost:8000",
            "security": {},
            "options": {"content_type": "application/json"},
        })

    if "grpc" in result.frameworks:
        transports.append({
            "transport_id": "grpc_primary",
            "type": "grpc",
            "endpoint": "localhost:50051",
            "security": {},
            "options": {},
        })

    if result.websocket_handlers:
        transports.append({
            "transport_id": "ws_primary",
            "type": "websocket",
            "endpoint": "ws://localhost:8000/ws",
            "security": {},
            "options": {},
        })

    if result.cli_commands and not transports:
        transports.append({
            "transport_id": "ipc_local",
            "type": "ipc",
            "endpoint": "local://cli",
            "security": {},
            "options": {},
        })

    if not transports:
        transports.append({
            "transport_id": "local_default",
            "type": "ipc",
            "endpoint": "local://default",
            "security": {},
            "options": {},
        })

    return transports


# ─────────────────────────────────────────────────────────────────
# Main scaffold generator
# ─────────────────────────────────────────────────────────────────

def generate_scaffold(result: "CrawlResult") -> dict:
    """
    Generate a UCI v0.1 manifest scaffold from a CrawlResult.
    The scaffold is a valid (or near-valid) manifest that the developer
    can fill in and register with the UCI SDK.
    """
    target_name = result.target_path.rstrip("/\\").split("/")[-1].split("\\")[-1]
    node_id = _slugify(target_name) or "my_node"
    instance_id = f"{node_id}_{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.utcnow().isoformat() + "Z"

    capabilities = _group_eps_into_capabilities(result)
    transports = _infer_transports(result)

    # Determine if any actions are high risk
    has_high_risk = any(
        action.get("risk", {}).get("level") == "high"
        for cap in capabilities
        for action in cap.get("actions", [])
    )

    scaffold = {
        "_scout": {
            "generator": "uci-scout",
            "generator_version": result.scout_version,
            "generated_at": now,
            "target_path": result.target_path,
            "uci_compatibility_score": result.uci_compatibility_score,
            "frameworks_detected": result.frameworks,
            "total_entry_points_found": result.total_entry_points,
            "note": (
                "This is a UCI Scout-generated scaffold. Review all TODO fields, "
                "adjust governance settings, tighten input/output schemas, "
                "and remove _scout_meta and _scout blocks before production use."
            ),
        },
        "uci_manifest_version": "0.1",
        "node": {
            "node_id":      node_id,
            "instance_id":  instance_id,
            "display_name": f"TODO: {target_name} (display name)",
            "node_type":    _infer_node_type(result),
            "version":      "0.1.0",
            "vendor":       "TODO: your name or organisation",
            "description":  f"TODO: describe what {target_name} does",
        },
        "capabilities": capabilities,
        "transports": transports,
        "governance": {
            "requires_policy_check":        True,
            "audit_required":               True,
            "operator_authority_required":  has_high_risk,
            "default_action_policy":        "deny",
            "sandbox_required":             False,
            "allow_remote_execution":       bool(result.http_routes),
            "signed_invocations_required":  False,
        },
        "health": {
            "health_endpoint":   "",
            "check_interval_ms": 30000,
            "timeout_ms":        5000,
            "expose_metrics":    False,
            "expose_uptime":     True,
        },
        "compatibility": {
            "supported_manifest_versions": ["0.1"],
        },
        "compliance": {
            "profile": "minimal",
        },
        "audit": {
            "audit_enabled": True,
        },
        "extensions": {},
        "metadata": {
            "scout_generated": True,
            "source_frameworks": result.frameworks,
        },
    }

    return scaffold


def _infer_node_type(result: "CrawlResult") -> str:
    fws = set(result.frameworks)
    if any(fw in fws for fw in ("fastapi", "flask", "starlette", "aiohttp", "litestar", "tornado", "sanic")):
        return "service"
    if any(fw in fws for fw in ("typer", "click", "argparse")):
        return "application"
    if "grpc" in fws:
        return "service"
    if "celery" in fws or "apscheduler" in fws:
        return "daemon"
    if any(fw in fws for fw in ("pyqt5", "pyqt6")):
        return "application"
    if result.cli_commands and not result.http_routes:
        return "application"
    return "service"
