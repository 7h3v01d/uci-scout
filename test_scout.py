#!/usr/bin/env python3
"""
test_scout.py — UCI Scout Test Suite
=================================
Comprehensive tests for all UCI Scout components. Each test writes real Python
fixture files to a temp directory so the AST crawler runs against actual code,
giving deterministic expected outcomes.

Run with:
    python test_scout.py
    python test_scout.py -v          # verbose per-test output
    python test_scout.py TestHeuristics  # run one class
"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# ── Allow import from the same directory ─────────────────────────
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scout import (
    ScoutCrawler,
    CrawlResult,
    EntryPoint,
    _guess_risk,
    _guess_uci_category,
    _guess_execution_mode,
    _detect_frameworks,
    _extract_params,
    _extract_return_hint,
    _decorator_names,
    _is_public,
    _first_docstring,
    _parse_http_route_from_decorator,
    _extract_entry_points_from_ast,
)
from scout_manifest import generate_scaffold, _slugify, _hint_to_json_type


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _parse(src: str) -> ast.Module:
    """Parse a source string into an AST module."""
    return ast.parse(textwrap.dedent(src))


def _write_project(files: dict[str, str]) -> Path:
    """
    Create a temporary directory with the given file tree.
    files is a dict of relative_path -> source_content.
    Returns the project root Path.
    """
    tmp = tempfile.mkdtemp(prefix="scout_test_")
    root = Path(tmp)
    for rel, content in files.items():
        fpath = root / rel
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(textwrap.dedent(content), encoding="utf-8")
    return root


def _crawl(files: dict[str, str], depth: int = 8) -> CrawlResult:
    """Write a project and crawl it, returning the CrawlResult."""
    root = _write_project(files)
    crawler = ScoutCrawler(str(root), max_depth=depth, quiet=True)
    return crawler.crawl()


def _ep_names(eps: list[EntryPoint]) -> list[str]:
    return [e.name for e in eps]


# ─────────────────────────────────────────────────────────────────
# 1. Heuristic unit tests
# ─────────────────────────────────────────────────────────────────

class TestGuessRisk(unittest.TestCase):

    def test_low_risk_plain_name(self):
        self.assertEqual(_guess_risk("get_report", []), "low")

    def test_low_risk_fetch(self):
        self.assertEqual(_guess_risk("fetch_data", []), "low")

    def test_medium_risk_write(self):
        self.assertEqual(_guess_risk("write_record", []), "medium")

    def test_medium_risk_create(self):
        self.assertEqual(_guess_risk("create_user", []), "medium")

    def test_medium_risk_update(self):
        self.assertEqual(_guess_risk("update_settings", []), "medium")

    def test_medium_risk_notify(self):
        self.assertEqual(_guess_risk("notify_user", []), "medium")

    def test_high_risk_delete(self):
        self.assertEqual(_guess_risk("delete_account", []), "high")

    def test_high_risk_drop(self):
        self.assertEqual(_guess_risk("drop_table", []), "high")

    def test_high_risk_execute(self):
        self.assertEqual(_guess_risk("execute_query", []), "high")

    def test_high_risk_purge(self):
        self.assertEqual(_guess_risk("purge_old_records", []), "high")

    def test_high_risk_admin(self):
        self.assertEqual(_guess_risk("admin_reset", []), "high")

    def test_high_risk_transfer(self):
        self.assertEqual(_guess_risk("transfer_funds", []), "high")

    def test_high_risk_password(self):
        self.assertEqual(_guess_risk("set_password", []), "high")

    def test_high_takes_priority_over_medium(self):
        # "remove" is high, "create" is medium — high wins because high patterns checked first
        self.assertEqual(_guess_risk("remove_and_create", []), "high")

    def test_case_insensitive(self):
        self.assertEqual(_guess_risk("DELETE_USER", []), "high")

    def test_mixed_case_medium(self):
        self.assertEqual(_guess_risk("CreateOrder", []), "medium")


class TestGuessUciCategory(unittest.TestCase):

    def test_get_is_retrieval(self):
        self.assertEqual(_guess_uci_category("get_user", []), "retrieval")

    def test_fetch_is_retrieval(self):
        self.assertEqual(_guess_uci_category("fetch_records", []), "retrieval")

    def test_list_is_retrieval(self):
        self.assertEqual(_guess_uci_category("list_items", []), "retrieval")

    def test_create_is_storage(self):
        self.assertEqual(_guess_uci_category("create_document", []), "storage")

    def test_save_is_storage(self):
        self.assertEqual(_guess_uci_category("save_config", []), "storage")

    def test_delete_is_storage(self):
        self.assertEqual(_guess_uci_category("delete_record", []), "storage")

    def test_generate_is_generation(self):
        self.assertEqual(_guess_uci_category("generate_report", []), "generation")

    def test_analyse_is_analysis(self):
        self.assertEqual(_guess_uci_category("analyse_data", []), "analysis")

    def test_send_is_communication(self):
        self.assertEqual(_guess_uci_category("send_invoice", []), "communication")

    def test_notify_is_communication(self):
        self.assertEqual(_guess_uci_category("notify_users", []), "communication")

    def test_execute_is_execution(self):
        self.assertEqual(_guess_uci_category("execute_task", []), "execution")

    def test_validate_is_governance(self):
        self.assertEqual(_guess_uci_category("validate_policy", []), "governance")

    def test_monitor_is_monitoring(self):
        self.assertEqual(_guess_uci_category("monitor_health", []), "monitoring")

    def test_login_is_identity(self):
        self.assertEqual(_guess_uci_category("login_user", []), "identity")

    def test_hash_is_security(self):
        self.assertEqual(_guess_uci_category("hash_password", []), "security")

    def test_unknown_is_utility(self):
        self.assertEqual(_guess_uci_category("frobnicate", []), "utility")

    def test_decorator_contributes(self):
        # category inferred from decorator keyword even if name is generic
        self.assertEqual(_guess_uci_category("handler", ["@app.get('/items')"]), "retrieval")


class TestGuessExecutionMode(unittest.TestCase):

    def test_sync_plain(self):
        self.assertEqual(_guess_execution_mode(False, [], "do_thing"), "sync")

    def test_async_function(self):
        self.assertEqual(_guess_execution_mode(True, [], "do_thing"), "async")

    def test_websocket_decorator(self):
        self.assertEqual(_guess_execution_mode(True, ["@app.websocket('/ws')"], "ws_handler"), "streaming")

    def test_ws_in_name(self):
        self.assertEqual(_guess_execution_mode(False, [], "ws_connect"), "streaming")

    def test_scheduled_decorator(self):
        self.assertEqual(_guess_execution_mode(False, ["@scheduler.scheduled_job('cron')"], "job"), "scheduled")

    def test_cron_in_decorator(self):
        self.assertEqual(_guess_execution_mode(False, ["@cron('0 * * * *')"], "hourly"), "scheduled")

    def test_periodic_in_name(self):
        self.assertEqual(_guess_execution_mode(False, [], "periodic_cleanup"), "scheduled")

    def test_on_prefix_is_event_driven(self):
        self.assertEqual(_guess_execution_mode(False, [], "on_startup"), "event_driven")

    def test_handle_prefix_is_event_driven(self):
        self.assertEqual(_guess_execution_mode(False, [], "handle_message"), "event_driven")

    def test_event_decorator(self):
        self.assertEqual(_guess_execution_mode(False, ["@event"], "process"), "event_driven")


# ─────────────────────────────────────────────────────────────────
# 2. Framework detection
# ─────────────────────────────────────────────────────────────────

class TestDetectFrameworks(unittest.TestCase):

    def test_fastapi_detected(self):
        src = "from fastapi import FastAPI\napp = FastAPI()"
        self.assertIn("fastapi", _detect_frameworks(src))

    def test_flask_detected(self):
        src = "from flask import Flask\napp = Flask(__name__)"
        self.assertIn("flask", _detect_frameworks(src))

    def test_click_detected(self):
        src = "import click\n@click.command()\ndef run(): pass"
        self.assertIn("click", _detect_frameworks(src))

    def test_typer_detected(self):
        src = "import typer\napp = typer.Typer()"
        self.assertIn("typer", _detect_frameworks(src))

    def test_celery_detected(self):
        src = "from celery import Celery\napp = Celery('tasks')"
        self.assertIn("celery", _detect_frameworks(src))

    def test_sqlalchemy_detected(self):
        src = "from sqlalchemy import create_engine\nengine = create_engine(url)"
        self.assertIn("sqlalchemy", _detect_frameworks(src))

    def test_uci_detected(self):
        src = "from uci.sdk.provider import UCIProvider"
        self.assertIn("uci", _detect_frameworks(src))

    def test_pyqt6_detected(self):
        src = "from PyQt6.QtWidgets import QApplication"
        self.assertIn("pyqt6", _detect_frameworks(src))

    def test_no_framework_empty(self):
        self.assertEqual(_detect_frameworks("x = 1"), [])

    def test_multiple_frameworks(self):
        src = "from fastapi import FastAPI\nfrom sqlalchemy import Session"
        detected = _detect_frameworks(src)
        self.assertIn("fastapi", detected)
        self.assertIn("sqlalchemy", detected)

    def test_grpc_detected(self):
        src = "import grpc\nserver = grpc.server()"
        self.assertIn("grpc", _detect_frameworks(src))


# ─────────────────────────────────────────────────────────────────
# 3. AST helpers
# ─────────────────────────────────────────────────────────────────

class TestAstHelpers(unittest.TestCase):

    def _func(self, src: str):
        tree = _parse(src)
        return tree.body[0]

    def test_is_public_true(self):
        self.assertTrue(_is_public("get_user"))

    def test_is_public_false_single_underscore(self):
        self.assertFalse(_is_public("_internal"))

    def test_is_public_false_double_underscore(self):
        self.assertFalse(_is_public("__private"))

    def test_extract_params_basic(self):
        f = self._func("def fn(name: str, age: int): pass")
        self.assertEqual(_extract_params(f), ["name: str", "age: int"])

    def test_extract_params_skips_self(self):
        f = self._func("def fn(self, name: str): pass")
        self.assertEqual(_extract_params(f), ["name: str"])

    def test_extract_params_skips_request(self):
        f = self._func("def fn(request, body: dict): pass")
        self.assertEqual(_extract_params(f), ["body: dict"])

    def test_extract_params_no_hints(self):
        f = self._func("def fn(a, b, c): pass")
        self.assertEqual(_extract_params(f), ["a", "b", "c"])

    def test_extract_params_vararg(self):
        f = self._func("def fn(*args): pass")
        self.assertIn("*args", _extract_params(f))

    def test_extract_params_kwargs(self):
        f = self._func("def fn(**kwargs): pass")
        self.assertIn("**kwargs", _extract_params(f))

    def test_extract_return_hint(self):
        f = self._func("def fn() -> str: pass")
        self.assertEqual(_extract_return_hint(f), "str")

    def test_extract_return_hint_none(self):
        f = self._func("def fn(): pass")
        self.assertEqual(_extract_return_hint(f), "")

    def test_extract_return_hint_complex(self):
        f = self._func("def fn() -> dict[str, int]: pass")
        self.assertEqual(_extract_return_hint(f), "dict[str, int]")

    def test_decorator_names_simple(self):
        f = self._func("@app.get('/items')\ndef fn(): pass")
        decos = _decorator_names(f)
        self.assertEqual(len(decos), 1)
        self.assertIn("app.get", decos[0])

    def test_decorator_names_multiple(self):
        f = self._func("@login_required\n@cache(60)\ndef fn(): pass")
        decos = _decorator_names(f)
        self.assertEqual(len(decos), 2)

    def test_first_docstring_present(self):
        f = self._func('def fn():\n    """This is the docstring."""\n    pass')
        self.assertEqual(_first_docstring(f), "This is the docstring.")

    def test_first_docstring_multiline_returns_first_line(self):
        f = self._func('def fn():\n    """First line.\n    Second line.\n    """\n    pass')
        self.assertEqual(_first_docstring(f), "First line.")

    def test_first_docstring_absent(self):
        f = self._func("def fn():\n    x = 1")
        self.assertEqual(_first_docstring(f), "")


class TestParseHttpRouteFromDecorator(unittest.TestCase):

    def test_get_route(self):
        method, path = _parse_http_route_from_decorator("app.get('/items')")
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/items")

    def test_post_route(self):
        method, path = _parse_http_route_from_decorator("router.post('/users')")
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/users")

    def test_delete_route(self):
        method, path = _parse_http_route_from_decorator("app.delete('/items/{id}')")
        self.assertEqual(method, "DELETE")
        self.assertEqual(path, "/items/{id}")

    def test_put_route(self):
        method, path = _parse_http_route_from_decorator("app.put('/config')")
        self.assertEqual(method, "PUT")
        self.assertEqual(path, "/config")

    def test_patch_route(self):
        method, path = _parse_http_route_from_decorator("app.patch('/user/{id}')")
        self.assertEqual(method, "PATCH")
        self.assertEqual(path, "/user/{id}")

    def test_websocket_route(self):
        method, path = _parse_http_route_from_decorator("app.websocket('/ws')")
        self.assertEqual(method, "WS")
        self.assertEqual(path, "/ws")

    def test_double_quoted_path(self):
        method, path = _parse_http_route_from_decorator('app.get("/items")')
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/items")

    def test_not_a_route(self):
        method, path = _parse_http_route_from_decorator("@login_required")
        self.assertEqual(method, "")
        self.assertEqual(path, "")

    def test_case_insensitive_method(self):
        method, path = _parse_http_route_from_decorator("app.GET('/upper')")
        self.assertEqual(method, "GET")

    def test_nested_path_params(self):
        method, path = _parse_http_route_from_decorator("app.get('/orgs/{org_id}/repos/{repo_id}')")
        self.assertEqual(path, "/orgs/{org_id}/repos/{repo_id}")


# ─────────────────────────────────────────────────────────────────
# 4. AST entry point extraction (single-file)
# ─────────────────────────────────────────────────────────────────

class TestExtractEntryPointsFromAst(unittest.TestCase):

    def _extract(self, src: str, file: str = "app.py", mod: str = "app") -> list[EntryPoint]:
        tree = _parse(src)
        return _extract_entry_points_from_ast(tree, file, mod, [])

    # ── HTTP routes ───────────────────────────────────────────────

    def test_fastapi_get_route(self):
        eps = self._extract("""
            from fastapi import FastAPI
            app = FastAPI()

            @app.get('/users')
            async def list_users():
                pass
        """)
        routes = [e for e in eps if e.kind == "http_route"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].http_method, "GET")
        self.assertEqual(routes[0].http_path, "/users")
        self.assertIn("list_users", routes[0].name)
        self.assertTrue(routes[0].is_async)

    def test_fastapi_post_route(self):
        eps = self._extract("""
            @router.post('/items')
            async def create_item(name: str, qty: int):
                pass
        """)
        routes = [e for e in eps if e.kind == "http_route"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].http_method, "POST")
        self.assertEqual(routes[0].http_path, "/items")
        self.assertIn("name: str", routes[0].params)
        self.assertIn("qty: int", routes[0].params)

    def test_delete_route_is_high_risk(self):
        eps = self._extract("""
            @app.delete('/users/{id}')
            async def delete_user(id: int):
                pass
        """)
        routes = [e for e in eps if e.kind == "http_route"]
        self.assertEqual(routes[0].risk_guess, "high")

    def test_websocket_route(self):
        eps = self._extract("""
            @app.websocket('/ws')
            async def ws_handler():
                pass
        """)
        ws = [e for e in eps if e.kind == "websocket"]
        self.assertEqual(len(ws), 1)
        self.assertEqual(ws[0].http_method, "WS")
        self.assertEqual(ws[0].uci_execution_mode, "streaming")

    def test_multiple_routes(self):
        eps = self._extract("""
            @app.get('/a')
            def get_a(): pass

            @app.post('/b')
            def post_b(): pass

            @app.delete('/c')
            def del_c(): pass
        """)
        routes = [e for e in eps if e.kind == "http_route"]
        self.assertEqual(len(routes), 3)
        methods = {r.http_method for r in routes}
        self.assertEqual(methods, {"GET", "POST", "DELETE"})

    def test_route_docstring_captured(self):
        eps = self._extract("""
            @app.get('/ping')
            def ping():
                \"\"\"Health check endpoint.\"\"\"
                return {"status": "ok"}
        """)
        routes = [e for e in eps if e.kind == "http_route"]
        self.assertEqual(routes[0].description, "Health check endpoint.")

    def test_route_return_hint_captured(self):
        eps = self._extract("""
            @app.get('/items')
            async def list_items() -> list[dict]:
                pass
        """)
        routes = [e for e in eps if e.kind == "http_route"]
        self.assertEqual(routes[0].return_hint, "list[dict]")

    # ── CLI commands ──────────────────────────────────────────────

    def test_click_command(self):
        eps = self._extract("""
            import click

            @click.command()
            def run(host: str, port: int):
                pass
        """)
        cmds = [e for e in eps if e.kind == "cli_command"]
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0].name, "run")

    def test_typer_command(self):
        eps = self._extract("""
            import typer
            app = typer.Typer()

            @app.command()
            def deploy(env: str):
                pass
        """)
        cmds = [e for e in eps if e.kind == "cli_command"]
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0].name, "deploy")

    def test_click_group(self):
        eps = self._extract("""
            @click.group()
            def cli():
                pass
        """)
        cmds = [e for e in eps if e.kind == "cli_command"]
        self.assertEqual(len(cmds), 1)

    # ── Scheduler tasks ───────────────────────────────────────────

    def test_celery_task(self):
        eps = self._extract("""
            @app.task
            def send_report():
                pass
        """)
        tasks = [e for e in eps if e.kind == "scheduler_task"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].name, "send_report")
        self.assertEqual(tasks[0].uci_execution_mode, "scheduled")

    def test_shared_task(self):
        eps = self._extract("""
            @shared_task
            def cleanup():
                pass
        """)
        tasks = [e for e in eps if e.kind == "scheduler_task"]
        self.assertEqual(len(tasks), 1)

    def test_apscheduler_cron(self):
        eps = self._extract("""
            @scheduler.scheduled_job('cron', hour=0)
            def nightly_job():
                pass
        """)
        tasks = [e for e in eps if e.kind == "scheduler_task"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].uci_execution_mode, "scheduled")

    # ── Event hooks ───────────────────────────────────────────────

    def test_on_prefix_event(self):
        eps = self._extract("""
            def on_startup():
                pass
        """)
        hooks = [e for e in eps if e.kind == "event_hook"]
        self.assertEqual(len(hooks), 1)
        self.assertEqual(hooks[0].name, "on_startup")
        self.assertEqual(hooks[0].uci_execution_mode, "event_driven")

    def test_handle_prefix_event(self):
        eps = self._extract("""
            def handle_payment_received(amount: float):
                pass
        """)
        hooks = [e for e in eps if e.kind == "event_hook"]
        self.assertEqual(len(hooks), 1)

    def test_event_decorator(self):
        eps = self._extract("""
            @event
            def user_registered(user_id: int):
                pass
        """)
        hooks = [e for e in eps if e.kind == "event_hook"]
        self.assertEqual(len(hooks), 1)

    # ── Public functions ──────────────────────────────────────────

    def test_public_function_detected(self):
        eps = self._extract("""
            def calculate_gst(amount: float) -> float:
                \"\"\"Calculate GST on amount.\"\"\"
                return amount * 0.1
        """)
        funcs = [e for e in eps if e.kind == "public_function"]
        self.assertEqual(len(funcs), 1)
        self.assertEqual(funcs[0].name, "calculate_gst")
        self.assertEqual(funcs[0].return_hint, "float")
        self.assertIn("amount: float", funcs[0].params)

    def test_private_function_excluded(self):
        eps = self._extract("""
            def _internal_helper():
                pass

            def public_one():
                pass
        """)
        names = _ep_names(eps)
        self.assertIn("public_one", names)
        self.assertNotIn("_internal_helper", names)

    def test_dunder_function_excluded(self):
        eps = self._extract("""
            def __main__():
                pass

            def run():
                pass
        """)
        names = _ep_names(eps)
        self.assertIn("run", names)
        self.assertNotIn("__main__", names)

    def test_async_public_function(self):
        eps = self._extract("""
            async def fetch_data(url: str) -> dict:
                pass
        """)
        funcs = [e for e in eps if e.kind == "public_function"]
        self.assertEqual(len(funcs), 1)
        self.assertTrue(funcs[0].is_async)
        self.assertEqual(funcs[0].uci_execution_mode, "async")

    # ── Class methods ─────────────────────────────────────────────

    def test_class_method_detected(self):
        eps = self._extract("""
            class UserService:
                def create(self, name: str, email: str) -> dict:
                    \"\"\"Create a new user.\"\"\"
                    pass

                def delete(self, user_id: int) -> None:
                    pass
        """)
        methods = [e for e in eps if e.kind == "class_method"]
        names = _ep_names(methods)
        self.assertIn("UserService.create", names)
        self.assertIn("UserService.delete", names)

    def test_class_private_method_excluded(self):
        eps = self._extract("""
            class Svc:
                def public_method(self): pass
                def _private_method(self): pass
        """)
        names = _ep_names([e for e in eps if e.kind == "class_method"])
        self.assertIn("Svc.public_method", names)
        self.assertNotIn("Svc._private_method", names)

    def test_dunder_methods_excluded(self):
        eps = self._extract("""
            class Thing:
                def __init__(self): pass
                def __str__(self): pass
                def __repr__(self): pass
                def do_work(self): pass
        """)
        names = _ep_names([e for e in eps if e.kind == "class_method"])
        self.assertIn("Thing.do_work", names)
        self.assertNotIn("Thing.__init__", names)

    def test_private_class_excluded(self):
        eps = self._extract("""
            class _InternalThing:
                def method(self): pass
        """)
        methods = [e for e in eps if e.kind == "class_method"]
        self.assertEqual(len(methods), 0)

    def test_class_method_params_exclude_self(self):
        eps = self._extract("""
            class Svc:
                def create(self, name: str, qty: int) -> None:
                    pass
        """)
        methods = [e for e in eps if e.kind == "class_method"]
        self.assertIn("name: str", methods[0].params)
        self.assertIn("qty: int", methods[0].params)
        self.assertNotIn("self", methods[0].params)

    def test_class_method_risk_inherited(self):
        eps = self._extract("""
            class DataService:
                def delete_all(self) -> None:
                    pass
        """)
        methods = [e for e in eps if e.kind == "class_method"]
        self.assertEqual(methods[0].risk_guess, "high")

    # ── HTTP route NOT double-counted as class method ─────────────

    def test_http_route_in_class_not_double_counted(self):
        eps = self._extract("""
            class Router:
                @app.get('/items')
                async def list_items(self): pass
        """)
        http = [e for e in eps if e.kind == "http_route"]
        method = [e for e in eps if e.kind == "class_method"]
        self.assertEqual(len(http), 1)
        self.assertEqual(len(method), 0)

    # ── No entries on syntax error ────────────────────────────────

    def test_empty_file_produces_no_eps(self):
        eps = self._extract("")
        self.assertEqual(eps, [])

    def test_file_with_only_imports_produces_no_eps(self):
        eps = self._extract("""
            import os
            import sys
            from pathlib import Path
        """)
        self.assertEqual(eps, [])


# ─────────────────────────────────────────────────────────────────
# 5. Full crawler integration tests
# ─────────────────────────────────────────────────────────────────

class TestCrawlerIntegration(unittest.TestCase):

    def test_empty_directory(self):
        result = _crawl({"placeholder.txt": "not python"})
        self.assertEqual(result.python_files, 0)
        self.assertEqual(result.total_entry_points, 0)
        self.assertEqual(result.uci_compatibility_score, 0)

    def test_single_fastapi_file(self):
        result = _crawl({"main.py": """
            from fastapi import FastAPI
            app = FastAPI()

            @app.get('/users')
            async def list_users(): pass

            @app.post('/users')
            async def create_user(name: str): pass

            @app.delete('/users/{id}')
            async def delete_user(id: int): pass
        """})
        self.assertEqual(result.python_files, 1)
        self.assertEqual(len(result.http_routes), 3)
        self.assertIn("fastapi", result.frameworks)

    def test_fastapi_score_above_50(self):
        # 3 HTTP routes + FastAPI framework = 30 + 20 + 10 = 60
        result = _crawl({"main.py": """
            from fastapi import FastAPI
            app = FastAPI()

            @app.get('/a')
            def a(): pass

            @app.get('/b')
            def b(): pass

            @app.post('/c')
            def c(): pass
        """})
        self.assertGreater(result.uci_compatibility_score, 50)

    def test_fastapi_plus_cli_score_above_70(self):
        # Routes + CLI commands + FastAPI + callables pushes above 70
        result = _crawl({"main.py": """
            from fastapi import FastAPI
            import click
            app = FastAPI()

            @app.get('/a')
            def a(): pass
            @app.post('/b')
            def b(): pass

            @click.command()
            def migrate(): pass

            def helper_func(): pass
        """})
        self.assertGreater(result.uci_compatibility_score, 70)

    def test_click_cli_detected(self):
        result = _crawl({"cli.py": """
            import click

            @click.command()
            def run(host: str): pass

            @click.command()
            def deploy(env: str): pass
        """})
        self.assertEqual(len(result.cli_commands), 2)
        self.assertIn("click", result.frameworks)

    def test_celery_tasks_detected(self):
        result = _crawl({"tasks.py": """
            from celery import Celery
            app = Celery()

            @app.task
            def send_email(): pass

            @app.task
            def process_payment(): pass
        """})
        self.assertEqual(len(result.scheduler_tasks), 2)
        self.assertIn("celery", result.frameworks)

    def test_websocket_handler_detected(self):
        result = _crawl({"ws.py": """
            @app.websocket('/ws')
            async def ws_endpoint(): pass
        """})
        self.assertEqual(len(result.websocket_handlers), 1)

    def test_event_hooks_detected(self):
        result = _crawl({"events.py": """
            def on_startup(): pass
            def on_shutdown(): pass
            def handle_error(exc): pass
        """})
        self.assertEqual(len(result.event_hooks), 3)

    def test_uci_existing_detected(self):
        result = _crawl({"provider.py": """
            from uci.sdk.provider import UCIProvider

            class MyProvider(UCIProvider):
                pass
        """})
        self.assertTrue(result.has_existing_uci)
        self.assertIn("uci", result.frameworks)

    def test_multi_file_project(self):
        result = _crawl({
            "routes/users.py": """
                @app.get('/users')
                async def list_users(): pass

                @app.post('/users')
                async def create_user(): pass
            """,
            "routes/items.py": """
                @app.get('/items')
                async def list_items(): pass
            """,
            "services/user.py": """
                class UserService:
                    def create(self, name: str): pass
                    def delete(self, id: int): pass
            """,
            "cli.py": """
                import click

                @click.command()
                def migrate(): pass
            """,
        })
        self.assertEqual(result.python_files, 4)
        self.assertEqual(len(result.http_routes), 3)
        self.assertEqual(len(result.cli_commands), 1)
        self.assertEqual(len(result.class_methods), 2)

    def test_skip_dirs_respected(self):
        result = _crawl({
            "main.py": "@app.get('/a')\ndef a(): pass",
            "__pycache__/cached.py": "@app.get('/b')\ndef b(): pass",
            ".venv/lib/routes.py": "@app.get('/c')\ndef c(): pass",
        })
        # Only main.py should be scanned
        self.assertEqual(result.python_files, 1)
        self.assertEqual(len(result.http_routes), 1)

    def test_syntax_error_in_file_produces_warning(self):
        result = _crawl({
            "bad.py": "def broken(: pass",
            "good.py": "def fine(): pass",
        })
        self.assertTrue(any("bad.py" in w or "Syntax" in w for w in result.warnings))
        # good.py still processed
        self.assertGreater(result.python_files, 0)

    def test_config_files_detected(self):
        result = _crawl({
            "main.py": "def run(): pass",
            "requirements.txt": "fastapi\nsqlalchemy",
            "pyproject.toml": "[tool.poetry]",
        })
        config_names = [Path(f).name for f in result.config_files_found]
        self.assertIn("requirements.txt", config_names)
        self.assertIn("pyproject.toml", config_names)

    def test_depth_limit_respected(self):
        result = _crawl({
            "a/b/c/d/e/f/g/h/deep.py": "@app.get('/deep')\ndef deep(): pass",
            "shallow.py": "@app.get('/shallow')\ndef shallow(): pass",
        }, depth=3)
        names = _ep_names(result.all_entry_points)
        # deep.py is 8 levels in, should not be reached at depth=3
        self.assertNotIn("GET /deep  (deep)", names)
        # shallow.py is at root, should be found
        http_names = _ep_names(result.http_routes)
        self.assertTrue(any("shallow" in n for n in http_names))

    def test_nonexistent_path_produces_warning(self):
        crawler = ScoutCrawler("/this/does/not/exist/at/all", quiet=True)
        result = crawler.crawl()
        self.assertTrue(any("not exist" in w.lower() or "does not exist" in w for w in result.warnings))
        self.assertEqual(result.total_entry_points, 0)

    def test_to_dict_structure(self):
        result = _crawl({"main.py": """
            from fastapi import FastAPI
            app = FastAPI()

            @app.get('/ping')
            def ping(): pass
        """})
        d = result.to_dict()
        self.assertIn("scout_version", d)
        self.assertIn("uci_target_version", d)
        self.assertIn("frameworks", d)
        self.assertIn("summary", d)
        self.assertIn("entry_points", d)
        self.assertIn("http_routes", d["entry_points"])
        self.assertEqual(d["summary"]["http_routes"], 1)


# ─────────────────────────────────────────────────────────────────
# 6. UCI compatibility scoring
# ─────────────────────────────────────────────────────────────────

class TestCompatibilityScoring(unittest.TestCase):

    def test_empty_project_scores_zero(self):
        result = _crawl({"empty.py": ""})
        self.assertEqual(result.uci_compatibility_score, 0)

    def test_http_routes_boost_score(self):
        result_with = _crawl({"r.py": """
            from fastapi import FastAPI
            @app.get('/a')
            def a(): pass
        """})
        result_without = _crawl({"f.py": "def something(): pass"})
        self.assertGreater(
            result_with.uci_compatibility_score,
            result_without.uci_compatibility_score
        )

    def test_existing_uci_boosts_score(self):
        base = _crawl({"a.py": "@app.get('/x')\ndef x(): pass"})
        uci = _crawl({"a.py": """
            from uci import UCIProvider
            @app.get('/x')
            def x(): pass
        """})
        self.assertGreater(uci.uci_compatibility_score, base.uci_compatibility_score)

    def test_score_capped_at_100(self):
        result = _crawl({"main.py": """
            from fastapi import FastAPI
            from uci import UCIProvider
            app = FastAPI()

            @app.get('/a')
            def a(): pass
            @app.get('/b')
            def b(): pass
            @app.get('/c')
            def c(): pass
            @app.post('/d')
            def d(): pass
            @app.websocket('/ws')
            async def ws(): pass

            @app.task
            def task1(): pass
        """})
        self.assertLessEqual(result.uci_compatibility_score, 100)

    def test_score_notes_are_not_empty_when_eps_exist(self):
        result = _crawl({"a.py": "def do_thing(): pass"})
        self.assertGreater(len(result.uci_compatibility_notes), 0)

    def test_fastapi_rest_note_present(self):
        result = _crawl({"a.py": """
            from fastapi import FastAPI
            @app.get('/items')
            def items(): pass
        """})
        all_notes = " ".join(result.uci_compatibility_notes).lower()
        self.assertTrue(
            "rest" in all_notes or "http" in all_notes or "fastapi" in all_notes or "transport" in all_notes
        )


# ─────────────────────────────────────────────────────────────────
# 7. Manifest scaffold generation
# ─────────────────────────────────────────────────────────────────

class TestManifestScaffold(unittest.TestCase):

    def _scaffold(self, files: dict[str, str]) -> dict:
        result = _crawl(files)
        return generate_scaffold(result)

    def test_scaffold_has_required_top_level_keys(self):
        s = self._scaffold({"a.py": "def run(): pass"})
        for key in ("uci_manifest_version", "node", "capabilities", "transports", "governance"):
            self.assertIn(key, s)

    def test_uci_manifest_version(self):
        s = self._scaffold({"a.py": "def run(): pass"})
        self.assertEqual(s["uci_manifest_version"], "0.1")

    def test_node_id_derived_from_path(self):
        root = _write_project({"main.py": "def run(): pass"})
        # Directory name used as node_id
        crawler = ScoutCrawler(str(root), quiet=True)
        result = crawler.crawl()
        scaffold = generate_scaffold(result)
        # node_id should be slugified from the dir name
        self.assertIsInstance(scaffold["node"]["node_id"], str)
        self.assertTrue(len(scaffold["node"]["node_id"]) > 0)

    def test_http_routes_produce_capability(self):
        s = self._scaffold({"main.py": """
            @app.get('/users')
            def list_users(): pass

            @app.post('/users')
            def create_user(name: str): pass
        """})
        caps = s["capabilities"]
        all_action_ids = [a["action_id"] for c in caps for a in c["actions"]]
        self.assertTrue(len(all_action_ids) >= 2)

    def test_action_has_required_fields(self):
        s = self._scaffold({"a.py": """
            @app.get('/ping')
            def ping(): pass
        """})
        action = s["capabilities"][0]["actions"][0]
        for field in ("action_id", "description", "execution", "risk", "permissions"):
            self.assertIn(field, action)

    def test_action_execution_mode_sync(self):
        s = self._scaffold({"a.py": "def compute(x: int) -> int: pass"})
        action = s["capabilities"][0]["actions"][0]
        self.assertEqual(action["execution"]["mode"], "sync")

    def test_action_execution_mode_async(self):
        s = self._scaffold({"a.py": "async def fetch(url: str): pass"})
        action = s["capabilities"][0]["actions"][0]
        self.assertEqual(action["execution"]["mode"], "async")

    def test_high_risk_action_requires_confirmation(self):
        s = self._scaffold({"a.py": "def delete_everything(): pass"})
        action = s["capabilities"][0]["actions"][0]
        self.assertEqual(action["risk"]["level"], "high")
        self.assertEqual(action["permissions"]["operator_confirmation"], "required")

    def test_low_risk_action_no_confirmation(self):
        s = self._scaffold({"a.py": "def get_report(): pass"})
        action = s["capabilities"][0]["actions"][0]
        self.assertEqual(action["risk"]["level"], "low")
        self.assertEqual(action["permissions"]["operator_confirmation"], "none")

    def test_input_schema_has_params(self):
        s = self._scaffold({"a.py": """
            def process(name: str, count: int) -> bool:
                pass
        """})
        action = s["capabilities"][0]["actions"][0]
        props = action.get("input_schema", {}).get("properties", {})
        self.assertIn("name", props)
        self.assertIn("count", props)

    def test_fastapi_produces_http_transport(self):
        s = self._scaffold({"a.py": """
            from fastapi import FastAPI
            @app.get('/x')
            def x(): pass
        """})
        transport_types = [t["type"] for t in s["transports"]]
        self.assertIn("http", transport_types)

    def test_cli_only_produces_ipc_transport(self):
        s = self._scaffold({"a.py": """
            import click

            @click.command()
            def run(): pass
        """})
        transport_types = [t["type"] for t in s["transports"]]
        self.assertTrue(any(t in ("ipc", "local") for t in transport_types))

    def test_governance_default_deny(self):
        s = self._scaffold({"a.py": "def run(): pass"})
        self.assertEqual(s["governance"]["default_action_policy"], "deny")

    def test_node_type_service_for_fastapi(self):
        s = self._scaffold({"a.py": """
            from fastapi import FastAPI
            @app.get('/x')
            def x(): pass
        """})
        self.assertEqual(s["node"]["node_type"], "service")

    def test_node_type_application_for_pyqt6(self):
        s = self._scaffold({"a.py": """
            from PyQt6.QtWidgets import QApplication
            def run(): pass
        """})
        self.assertEqual(s["node"]["node_type"], "application")

    def test_node_type_daemon_for_celery(self):
        s = self._scaffold({"a.py": """
            from celery import Celery
            @app.task
            def job(): pass
        """})
        self.assertEqual(s["node"]["node_type"], "daemon")

    def test_scout_meta_in_action(self):
        s = self._scaffold({"a.py": "def run(): pass"})
        action = s["capabilities"][0]["actions"][0]
        self.assertIn("_scout_meta", action)
        self.assertIn("source_file", action["_scout_meta"])
        self.assertIn("source_line", action["_scout_meta"])

    def test_placeholder_when_no_entry_points(self):
        s = self._scaffold({"empty.py": ""})
        self.assertEqual(len(s["capabilities"]), 1)
        self.assertEqual(s["capabilities"][0]["capability_id"], "placeholder")

    def test_scaffold_serialisable_to_json(self):
        s = self._scaffold({"a.py": """
            from fastapi import FastAPI
            @app.get('/x')
            def x(): pass
            @app.post('/y')
            def y(name: str): pass
        """})
        # Should not raise
        out = json.dumps(s, indent=2)
        self.assertGreater(len(out), 100)


class TestSlugify(unittest.TestCase):

    def test_basic(self):
        self.assertEqual(_slugify("create_user"), "create_user")

    def test_spaces_become_underscores(self):
        self.assertEqual(_slugify("create user"), "create_user")

    def test_special_chars_removed(self):
        self.assertEqual(_slugify("GET /users/{id}"), "get_users_id")

    def test_leading_trailing_stripped(self):
        self.assertEqual(_slugify("  hello  "), "hello")

    def test_empty_returns_unnamed(self):
        self.assertEqual(_slugify(""), "unnamed")

    def test_truncated_at_64(self):
        long = "a" * 100
        self.assertEqual(len(_slugify(long)), 64)


class TestHintToJsonType(unittest.TestCase):

    def test_str(self):
        self.assertEqual(_hint_to_json_type("str"), "string")

    def test_int(self):
        self.assertEqual(_hint_to_json_type("int"), "integer")

    def test_float(self):
        self.assertEqual(_hint_to_json_type("float"), "number")

    def test_bool(self):
        self.assertEqual(_hint_to_json_type("bool"), "boolean")

    def test_list(self):
        self.assertEqual(_hint_to_json_type("list[str]"), "array")

    def test_dict(self):
        self.assertEqual(_hint_to_json_type("dict[str, int]"), "object")

    def test_none(self):
        self.assertEqual(_hint_to_json_type("None"), "null")

    def test_unknown_defaults_to_string(self):
        self.assertEqual(_hint_to_json_type("MyCustomType"), "string")


# ─────────────────────────────────────────────────────────────────
# 8. CrawlResult data model
# ─────────────────────────────────────────────────────────────────

class TestCrawlResult(unittest.TestCase):

    def _make_ep(self, kind: str = "public_function", name: str = "fn") -> EntryPoint:
        return EntryPoint(kind=kind, name=name, module="mod", file="f.py", line=1)

    def test_all_entry_points_aggregates_all_lists(self):
        r = CrawlResult(target_path="/x")
        r.http_routes    = [self._make_ep("http_route", "r1")]
        r.cli_commands   = [self._make_ep("cli_command", "c1")]
        r.public_functions = [self._make_ep("public_function", "f1")]
        r.class_methods  = [self._make_ep("class_method", "m1")]
        r.event_hooks    = [self._make_ep("event_hook", "e1")]
        r.scheduler_tasks = [self._make_ep("scheduler_task", "s1")]
        self.assertEqual(r.total_entry_points, 6)
        names = _ep_names(r.all_entry_points)
        for n in ("r1", "c1", "f1", "m1", "e1", "s1"):
            self.assertIn(n, names)

    def test_total_entry_points_zero_on_fresh(self):
        r = CrawlResult(target_path="/x")
        self.assertEqual(r.total_entry_points, 0)

    def test_to_dict_summary_counts_match_lists(self):
        r = CrawlResult(target_path="/x")
        r.http_routes = [self._make_ep("http_route")] * 3
        r.cli_commands = [self._make_ep("cli_command")] * 2
        d = r.to_dict()
        self.assertEqual(d["summary"]["http_routes"], 3)
        self.assertEqual(d["summary"]["cli_commands"], 2)
        self.assertEqual(d["summary"]["total_entry_points"], 5)

    def test_entry_point_to_dict_has_all_fields(self):
        ep = EntryPoint(
            kind="http_route",
            name="GET /test  (test_fn)",
            module="routes.test",
            file="routes/test.py",
            line=42,
            description="Test endpoint",
            params=["id: int"],
            return_hint="dict",
            decorators=["@app.get('/test')"],
            http_method="GET",
            http_path="/test",
            is_async=True,
            risk_guess="low",
            uci_category="retrieval",
            uci_execution_mode="async",
            confidence="high",
        )
        d = ep.to_dict()
        self.assertEqual(d["kind"], "http_route")
        self.assertEqual(d["http_method"], "GET")
        self.assertEqual(d["http_path"], "/test")
        self.assertEqual(d["risk_guess"], "low")
        self.assertEqual(d["uci_category"], "retrieval")
        self.assertTrue(d["is_async"])
        self.assertEqual(d["line"], 42)


# ─────────────────────────────────────────────────────────────────
# 9. Edge cases and regression tests
# ─────────────────────────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_file_with_only_class_no_methods(self):
        result = _crawl({"a.py": "class Empty:\n    pass"})
        self.assertEqual(result.total_entry_points, 0)

    def test_nested_classes_not_double_counted(self):
        result = _crawl({"a.py": """
            class Outer:
                class Inner:
                    def method(self): pass
                def outer_method(self): pass
        """})
        # Should not crash; outer_method should be found
        names = _ep_names(result.class_methods)
        self.assertTrue(any("outer_method" in n for n in names))

    def test_function_named_on_not_mistaken_for_event(self):
        # "on" alone isn't a prefix, must be "on_"
        result = _crawl({"a.py": "def once(): pass\ndef ongoing(): pass"})
        hooks = result.event_hooks
        names = _ep_names(hooks)
        # "once" and "ongoing" don't start with "on_"
        self.assertNotIn("once", names)
        self.assertNotIn("ongoing", names)

    def test_deeply_nested_route_in_subpackage(self):
        result = _crawl({
            "api/v2/users/routes.py": """
                @router.get('/v2/users')
                async def list_v2_users(): pass
            """
        })
        self.assertEqual(len(result.http_routes), 1)
        self.assertEqual(result.http_routes[0].http_path, "/v2/users")

    def test_multiple_decorators_on_one_function(self):
        result = _crawl({"a.py": """
            @requires_auth
            @app.get('/secure')
            def secure_endpoint(): pass
        """})
        routes = result.http_routes
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].http_method, "GET")

    def test_unicode_in_source_handled(self):
        result = _crawl({"a.py": '# coding: utf-8\ndef grüßen(): pass\ndef hello(): pass'})
        # Should not crash; hello() should be found
        names = _ep_names(result.public_functions)
        self.assertTrue(any("hello" in n for n in names))

    def test_large_class_doesnt_crash(self):
        methods = "\n".join(f"    def method_{i}(self): pass" for i in range(50))
        result = _crawl({"a.py": f"class Big:\n{methods}"})
        self.assertGreaterEqual(len(result.class_methods), 10)

    def test_openapi_config_detected(self):
        result = _crawl({
            "main.py": "def run(): pass",
            "openapi.json": '{"openapi": "3.0.0"}',
        })
        config_names = [Path(f).name for f in result.config_files_found]
        self.assertIn("openapi.json", config_names)


# ─────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────

def _count_tests() -> tuple[int, list[type]]:
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    return suite.countTestCases(), [
        TestGuessRisk, TestGuessUciCategory, TestGuessExecutionMode,
        TestDetectFrameworks, TestAstHelpers, TestParseHttpRouteFromDecorator,
        TestExtractEntryPointsFromAst, TestCrawlerIntegration,
        TestCompatibilityScoring, TestManifestScaffold,
        TestSlugify, TestHintToJsonType, TestCrawlResult, TestEdgeCases,
    ]


if __name__ == "__main__":
    total, classes = _count_tests()

    print(f"\n{'═' * 62}")
    print(f"  UCI Scout Test Suite  ·  {total} tests across {len(classes)} classes")
    print(f"{'═' * 62}\n")

    # Parse args — support class filtering and -v
    verbose = "-v" in sys.argv
    filter_class = next((a for a in sys.argv[1:] if not a.startswith("-")), None)

    if filter_class:
        matched = [c for c in classes if c.__name__ == filter_class]
        if not matched:
            print(f"No test class named '{filter_class}'. Available:")
            for c in classes:
                print(f"  {c.__name__}")
            sys.exit(1)
        suite = unittest.TestLoader().loadTestsFromTestCase(matched[0])
        print(f"  Running: {filter_class}\n")
    else:
        suite = unittest.TestSuite()
        for cls in classes:
            suite.addTests(unittest.TestLoader().loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(
        verbosity=2 if verbose else 1,
        stream=sys.stdout,
        descriptions=True,
    )
    result = runner.run(suite)

    print(f"\n{'─' * 62}")
    if result.wasSuccessful():
        print(f"  ✓  All {result.testsRun} tests passed.")
    else:
        print(f"  ✗  {len(result.failures)} failure(s), {len(result.errors)} error(s) "
              f"from {result.testsRun} tests.")
    print(f"{'─' * 62}\n")

    sys.exit(0 if result.wasSuccessful() else 1)
