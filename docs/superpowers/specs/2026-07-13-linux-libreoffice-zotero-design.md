# Linux LibreOffice Zotero Integration Design

## Goal

Extend the existing dynamic DOCX citation workflow to Linux without changing the validated macOS behavior. The Linux implementation must convert `{{zotero:ITEMKEY}}` placeholders into refreshable Zotero citation fields, persist them to DOCX, and verify the resulting citation and bibliography field counts.

## Repository And Branch

- Repository: `pjl-takeoff/cli-anything-zotero`
- Linux checkout: `/home/loong/projects/cli-anything-zotero`
- Development branch: `codex/linux-libreoffice`
- Baseline: `codex/background-libreoffice` at `50c271d`

The generic Zotero DOCX capability remains in this repository. Downstream research agents consume it through the CLI instead of copying LibreOffice control logic into their own codebases.

## Boundaries

The existing cross-platform core remains responsible for placeholder parsing, Zotero item lookup, bridge execution, DOCX preparation, citation inspection, and final validation. Platform adapters are responsible only for opening the prepared DOCX, making it available to Zotero's LibreOffice integration, warming up the integration when required, saving the active document, and closing temporary processes.

The first Linux release does not directly synthesize Zotero OOXML fields, automate a Wayland desktop, or change the macOS AppleScript path. Static CSL output remains a separate fallback and is not a substitute for a failed dynamic conversion.

## Linux Runtime

The supported Linux execution environment is Ubuntu 24.04 with:

- Zotero Desktop and the Zotero CLI Bridge plugin;
- LibreOffice and the Zotero LibreOffice integration;
- Java runtime required by the LibreOffice integration;
- Xvfb for an isolated display session;
- Python UNO bindings for deterministic document save and close operations.

The caller starts the CLI inside an Xvfb session. Zotero and LibreOffice inherit the same display. LibreOffice opens the prepared DOCX as a real active document, Zotero performs placeholder conversion through its integration API, and a UNO helper stores the converted document back to the same DOCX path.

## Platform Interface

Linux support is exposed through the same internal operations already used by macOS:

1. `open_document(path)` launches LibreOffice with an explicit UNO socket.
2. `prime_active_document(path)` confirms that the document is available through UNO.
3. `warm_up_zotero_connection(path)` retries the Zotero integration only when the bridge reports an uninitialized listener.
4. `save_document(path)` invokes UNO `store()` and confirms that the file modification time advances.
5. `close_document(path)` closes only the document and processes started by the current conversion.

Platform selection is internal. Existing CLI arguments and JSON output remain compatible.

## Validation

Unit tests run without Zotero or LibreOffice and must verify command construction, Linux dispatch, timeout behavior, save-result reporting, and preservation of the macOS path. A Linux integration test uses a fixture DOCX with one citation placeholder and one bibliography placeholder. It passes only when inspection reports one Zotero citation field and one Zotero bibliography field after the file is closed and reopened.

The full acceptance test uses the same command surface intended for downstream agents. A failure to persist fields is fatal; the tool must never silently replace dynamic fields with static text.

## Agent Integration

The antigen research agent will call `zotero-cli docx insert-citations` as a subprocess or service boundary. Its document pipeline supplies Zotero item keys, a CSL style, locale, and an output path. The agent receives structured JSON containing field counts, output location, and readiness status. This keeps Zotero Desktop and LibreOffice outside the scientific reasoning process and allows static export to remain an explicit fallback mode.

## Success Criteria

- Existing macOS tests remain green.
- Linux unit tests fail before implementation and pass afterward.
- `zotero-cli docx doctor` reports the Linux runtime ready.
- A Linux fixture produces refreshable citation and bibliography fields.
- `inspect-citations` confirms expected field counts after the output is saved and reopened.
- The Linux branch is pushed independently; the macOS baseline branch is unchanged.
