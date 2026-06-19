"""
scout_report.py — Terminal Report Renderer
==========================================
Renders the CrawlResult as a rich, colour-coded terminal report.
No external dependencies — uses only ANSI escape codes.
"""

from __future__ import annotations

import sys
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scout import CrawlResult, EntryPoint


# ─────────────────────────────────────────────────────────────────
# ANSI colours (Windows-safe)
# ─────────────────────────────────────────────────────────────────

if sys.platform == "win32":
    import ctypes
    _k32 = ctypes.windll.kernel32
    _h = _k32.GetStdHandle(-11)
    _m = ctypes.c_ulong()
    if _k32.GetConsoleMode(_h, ctypes.byref(_m)):
        _k32.SetConsoleMode(_h, _m.value | 0x0004)

_NO_COLOUR = not sys.stdout.isatty() or os.environ.get("NO_COLOR")

def _c(code: str, text: str) -> str:
    if _NO_COLOUR:
        return text
    return f"\033[{code}m{text}\033[0m"

def cyan(t: str) -> str:    return _c("36", t)
def green(t: str) -> str:   return _c("32", t)
def yellow(t: str) -> str:  return _c("33", t)
def red(t: str) -> str:     return _c("31", t)
def bold(t: str) -> str:    return _c("1", t)
def dim(t: str) -> str:     return _c("2", t)
def magenta(t: str) -> str: return _c("35", t)
def blue(t: str) -> str:    return _c("34", t)


# ─────────────────────────────────────────────────────────────────
# Score bar
# ─────────────────────────────────────────────────────────────────

def _score_bar(score: int, width: int = 30) -> str:
    filled = round(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    if score >= 70:
        coloured = green(bar)
    elif score >= 40:
        coloured = yellow(bar)
    else:
        coloured = red(bar)
    return f"[{coloured}] {bold(str(score))}/100"


# ─────────────────────────────────────────────────────────────────
# Entry point table
# ─────────────────────────────────────────────────────────────────

_KIND_LABELS: dict[str, str] = {
    "http_route":      "HTTP  ",
    "cli_command":     "CLI   ",
    "public_function": "FUNC  ",
    "class_method":    "METHOD",
    "event_hook":      "EVENT ",
    "rpc_handler":     "RPC   ",
    "websocket":       "WS    ",
    "scheduler_task":  "SCHED ",
}

_RISK_COLOUR = {
    "low":    green,
    "medium": yellow,
    "high":   red,
}

def _kind_colour(kind: str) -> str:
    label = _KIND_LABELS.get(kind, kind[:6].upper().ljust(6))
    if kind == "http_route":     return cyan(label)
    if kind == "cli_command":    return magenta(label)
    if kind == "websocket":      return blue(label)
    if kind == "scheduler_task": return yellow(label)
    if kind == "event_hook":     return _c("35", label)
    return dim(label)


def _render_ep_section(
    title: str,
    eps: list["EntryPoint"],
    limit: int = 50,
) -> None:
    if not eps:
        return
    print()
    print(bold(f"  ┌─ {title} ({len(eps)}) " + "─" * max(0, 52 - len(title) - len(str(len(eps))))))
    for ep in eps[:limit]:
        risk_fn = _RISK_COLOUR.get(ep.risk_guess, dim)
        risk_str = risk_fn(f"[{ep.risk_guess:6}]")
        cat = dim(f"[{ep.uci_category or 'utility':14}]")
        name = bold(ep.name[:55]) if len(ep.name) <= 55 else bold(ep.name[:52] + "…")
        loc = dim(f"{ep.file}:{ep.line}")
        print(f"  │  {_kind_colour(ep.kind)}  {risk_str} {cat}  {name}")
        if ep.description:
            print(f"  │           {dim(ep.description[:80])}")
        if ep.params:
            p_str = ", ".join(ep.params[:6])
            if len(ep.params) > 6:
                p_str += f", …+{len(ep.params)-6}"
            print(f"  │           {dim('params: ')}{dim(p_str)}")
        print(f"  │           {dim('at')} {loc}")
    if len(eps) > limit:
        print(f"  │  {dim(f'... and {len(eps)-limit} more (use --json for full list)')}")
    print(f"  └{'─' * 60}")


# ─────────────────────────────────────────────────────────────────
# Main report renderer
# ─────────────────────────────────────────────────────────────────

def render_report(result: "CrawlResult") -> None:
    print()
    print(bold(cyan("  ██████╗██████╗ ███████╗███████╗██████╗ ")))
    print(bold(cyan(" ██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗")))
    print(bold(cyan(" ██║     ██████╔╝█████╗  █████╗  ██████╔╝")))
    print(bold(cyan(" ██║     ██╔══██╗██╔══╝  ██╔══╝  ██╔═══╝ ")))
    print(bold(cyan(" ╚██████╗██║  ██║███████╗███████╗██║      ")))
    print(bold(cyan("  ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝      ")))
    print(f"  {dim('UCI Scout')}  {dim('v' + result.scout_version)}")
    print()

    # ── Target summary ───────────────────────────────────────────
    print(bold("  TARGET"))
    print(f"    Path:          {result.target_path}")
    print(f"    Files scanned: {result.files_scanned}")
    print(f"    Python files:  {result.python_files}")

    if result.frameworks:
        fw_str = "  ".join(result.frameworks)
        print(f"    Frameworks:    {cyan(fw_str)}")
    else:
        print(f"    Frameworks:    {dim('none detected')}")

    if result.config_files_found:
        print(f"    Config files:  {dim(', '.join(result.config_files_found[:5]))}")

    if result.has_existing_uci:
        print(f"    UCI:           {green('✓ Existing UCI integration detected')}")
    else:
        print(f"    UCI:           {dim('not yet integrated')}")

    # ── Entry point summary ──────────────────────────────────────
    print()
    print(bold("  ENTRY POINTS DISCOVERED"))
    total = result.total_entry_points
    print(f"    Total:         {bold(str(total))}")
    if result.http_routes:
        print(f"    HTTP routes:   {cyan(str(len(result.http_routes)))}")
    if result.cli_commands:
        print(f"    CLI commands:  {magenta(str(len(result.cli_commands)))}")
    if result.public_functions:
        print(f"    Functions:     {str(len(result.public_functions))}")
    if result.class_methods:
        print(f"    Class methods: {str(len(result.class_methods))}")
    if result.event_hooks:
        print(f"    Event hooks:   {str(len(result.event_hooks))}")
    if result.rpc_handlers:
        print(f"    RPC handlers:  {str(len(result.rpc_handlers))}")
    if result.websocket_handlers:
        print(f"    WebSockets:    {blue(str(len(result.websocket_handlers)))}")
    if result.scheduler_tasks:
        print(f"    Scheduled:     {yellow(str(len(result.scheduler_tasks)))}")

    # ── UCI compatibility score ──────────────────────────────────
    print()
    print(bold("  UCI COMPATIBILITY"))
    print(f"    Score:  {_score_bar(result.uci_compatibility_score)}")
    print()
    for note in result.uci_compatibility_notes:
        icon = green("✓") if note.startswith("✓") else red("✗")
        body = note[2:].strip()
        print(f"    {icon}  {body}")

    # ── Detailed entry point sections ────────────────────────────
    _render_ep_section("HTTP Routes", result.http_routes)
    _render_ep_section("CLI Commands", result.cli_commands)
    _render_ep_section("WebSocket Handlers", result.websocket_handlers)
    _render_ep_section("Scheduled / Async Tasks", result.scheduler_tasks)
    _render_ep_section("Event Hooks", result.event_hooks)
    _render_ep_section("RPC Handlers", result.rpc_handlers)
    _render_ep_section("Public Functions", result.public_functions, limit=20)
    _render_ep_section("Class Methods", result.class_methods, limit=20)

    # ── Warnings ─────────────────────────────────────────────────
    if result.warnings:
        print()
        print(bold(yellow("  WARNINGS")))
        for w in result.warnings:
            print(f"    {yellow('⚠')}  {w}")

    # ── Next steps ───────────────────────────────────────────────
    print()
    print(bold("  NEXT STEPS"))
    if total == 0:
        print(f"    {red('No entry points found.')} Ensure the target path contains Python source files.")
    else:
        score = result.uci_compatibility_score
        if score >= 70:
            print(f"    {green('Good fit!')} Run with {cyan('--scaffold')} to generate a UCI manifest scaffold.")
        elif score >= 40:
            print(f"    {yellow('Moderate fit.')} Review the entry points above, then run {cyan('--scaffold')}.")
        else:
            print(f"    {red('Low UCI coverage.')} The target may need adapter wrappers before UCI integration.")

        if not result.has_existing_uci:
            print(f"    Install UCI Python SDK and extend the scaffold to create a full UCI provider.")
        else:
            print(f"    UCI already present — UCI Scout scaffold may complement existing manifest.")

    print()
    print(dim("  Run with --json for machine-readable output."))
    print(dim("  Run with --scaffold to produce a UCI manifest scaffold."))
    print(dim("  Run with --full for report + scaffold in one pass."))
    print()
