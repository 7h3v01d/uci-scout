# Contributing to UCI Scout

Thanks for your interest. Contributions are welcome — bug reports, feature requests, and PRs alike.

## Getting started

```bash
git clone https://github.com/7h3v01d/uci-scout
cd uci-scout
python test_scout.py   # make sure everything passes before you change anything
```

No pip installs needed for the CLI or tests — pure Python 3.10+ stdlib.

For the GUI:
```bash
pip install PyQt6
python scout_gui.py
```

## Running tests

```bash
python test_scout.py          # all 177 tests
python test_scout.py -v       # verbose output
python test_scout.py TestCrawlerIntegration   # single class
```

Tests write real Python fixture files to a temp directory and run the actual AST crawler against them. No mocking of the filesystem or AST. Please keep it that way — new tests should follow the same pattern.

## Where things live

```
scout.py           Core crawler, CLI, AST analysis, CrawlResult model
scout_report.py    ANSI terminal report renderer
scout_manifest.py  UCI manifest scaffold generator
scout_gui.py       PyQt6 desktop GUI
test_scout.py      Full test suite
```

## Adding a new framework detector

Framework detection lives in `_FRAMEWORK_SIGNATURES` in `scout.py`. To add a new framework:

1. Add an entry to `_FRAMEWORK_SIGNATURES` with import/usage patterns
2. If the framework uses decorators, add decorator patterns to the relevant section in `_extract_entry_points_from_ast`
3. Add tests in `TestDetectFrameworks` and `TestExtractEntryPointsFromAst`

## Adding a new entry point kind

1. Add detection logic in `_extract_entry_points_from_ast`
2. Add a categorisation branch in `CreepCrawler.crawl()` that routes it to the right list on `CrawlResult`
3. Update `KIND_LABEL` and `KIND_COLOUR` in `scout_gui.py`
4. Add tests

## Pull request checklist

- [ ] All 177 existing tests still pass
- [ ] New behaviour is covered by tests
- [ ] No new external dependencies introduced (CLI must stay stdlib-only)
- [ ] `scout_gui.py` changes tested with `QT_QPA_PLATFORM=offscreen` at minimum

## Reporting bugs

Open an issue with:
- The command you ran
- The Python version (`python --version`)
- The target project's framework(s) if known
- The full output or error

## Feature requests

Open an issue describing the use case, not just the feature. "I want X" is less useful than "when I try to Y, I can't because Z."
