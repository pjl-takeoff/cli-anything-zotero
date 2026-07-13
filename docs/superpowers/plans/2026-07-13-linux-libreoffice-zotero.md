# Linux LibreOffice Zotero Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested Linux platform adapter that persists dynamic Zotero citation fields in LibreOffice DOCX files.

**Architecture:** Preserve the current Zotero bridge and DOCX validation flow. Add a small Linux LibreOffice controller that launches a socket-enabled LibreOffice process and uses a system-Python UNO helper to confirm, save, and close the target document; dispatch to it only on Linux.

**Tech Stack:** Python 3.11+, pytest, LibreOffice UNO, Zotero Desktop, Zotero CLI Bridge, Xvfb.

---

### Task 1: Freeze Linux Platform Contracts

**Files:**
- Create: `cli_anything/zotero/core/libreoffice_linux.py`
- Modify: `cli_anything/zotero/tests/test_core.py`

- [ ] Add failing tests for Linux open, prime, save, and close dispatch. The tests must assert the exact socket-enabled LibreOffice command and structured result fields without launching external applications.
- [ ] Run `uv run --with-editable . --with pytest pytest -q cli_anything/zotero/tests/test_core.py -k linux_libreoffice` and confirm failures identify missing Linux functions.
- [ ] Add the minimal controller API and command builder required by the tests.
- [ ] Rerun the focused tests and the complete test suite.
- [ ] Commit with `test: define Linux LibreOffice controller contract`.

### Task 2: Implement UNO Document Persistence

**Files:**
- Create: `cli_anything/zotero/core/libreoffice_uno_helper.py`
- Modify: `cli_anything/zotero/core/libreoffice_linux.py`
- Modify: `cli_anything/zotero/tests/test_core.py`

- [ ] Add failing tests for UNO helper invocation, target-document matching, timeout reporting, and nonzero subprocess exit handling.
- [ ] Verify the tests fail because persistence is not implemented.
- [ ] Implement `wait`, `store`, and `close` operations in the UNO helper. Match the target by normalized file URL and emit one JSON object to stdout.
- [ ] Implement the controller subprocess wrapper using `/usr/bin/python3` by default and an environment override for tests.
- [ ] Rerun focused and full tests.
- [ ] Commit with `feat: persist Linux LibreOffice documents through UNO`.

### Task 3: Wire Linux Dispatch Into Zoterify

**Files:**
- Modify: `cli_anything/zotero/core/docx_zoterify.py`
- Modify: `cli_anything/zotero/tests/test_core.py`

- [ ] Add failing tests showing that Linux uses the new controller while Darwin still uses the existing AppleScript implementation.
- [ ] Verify the Linux dispatch tests fail for the expected missing behavior.
- [ ] Route `_open_in_libreoffice`, `_prime_libreoffice_active_document`, `_warm_up_libreoffice_zotero_connection`, and `_save_active_libreoffice_document` through the Linux controller when `sys.platform.startswith("linux")`.
- [ ] Preserve all existing return keys consumed by `zoterify_document`.
- [ ] Rerun the complete unit suite.
- [ ] Commit with `feat: add Linux LibreOffice zoterify backend`.

### Task 4: Bootstrap And Diagnose Hasee

**Files:**
- Modify: `cli_anything/zotero/README.md`
- Modify: `cli_anything/zotero/core/docx.py`
- Modify: `cli_anything/zotero/tests/test_core.py`

- [ ] Install user-local `uv`, LibreOffice, Python UNO bindings, Java, Xvfb, and Zotero Desktop on `hasee`.
- [ ] Install the editable CLI, CLI Bridge plugin, and Zotero LibreOffice integration.
- [ ] Add a failing doctor test for Linux runtime guidance when Xvfb or UNO is absent.
- [ ] Extend doctor output with Linux-specific dependency and invocation guidance.
- [ ] Run `zotero-cli --json docx doctor` and retain the structured output as test evidence outside Git.
- [ ] Commit with `docs: add Linux dynamic citation setup`.

### Task 5: Run Linux End-To-End Acceptance

**Files:**
- Create: `cli_anything/zotero/tests/fixtures/linux_dynamic_placeholder.docx`
- Modify: `cli_anything/zotero/tests/test_full_e2e.py`

- [ ] Add an opt-in integration test guarded by `ZOTERO_LINUX_E2E=1`; it must require one citation field and one bibliography field after reopening the output.
- [ ] Run the test before final wiring and record the expected persistence failure.
- [ ] Run the complete conversion inside Xvfb and fix only defects exposed by the integration test.
- [ ] Inspect the output with `zotero-cli --json docx inspect-citations` and require `citation=1`, `bibliography=1`.
- [ ] Render the fixture DOCX and confirm the citation and bibliography are visible without layout corruption.
- [ ] Commit with `test: verify Linux Zotero DOCX conversion end to end`.

### Task 6: Final Regression And Delivery

**Files:**
- Modify only files required by failures found during regression.

- [ ] Run `uv run --with-editable . --with pytest pytest -q`.
- [ ] Run the Linux opt-in integration test in Xvfb.
- [ ] Run `git diff --check` and confirm the working tree is clean after committing.
- [ ] Push only `codex/linux-libreoffice` to `origin`.
- [ ] Verify `codex/background-libreoffice` still points to `50c271d`.
