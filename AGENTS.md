# Agent instructions

## Rules

Read `RULES.md` from `fairPath/fairpath-rules` before starting any ticket or implementation. Every change in this repo follows it.

- With the rules repo cloned next to this one: `../fairpath-rules/RULES.md`
- Otherwise: `gh api repos/fairPath/fairpath-rules/contents/RULES.md -H "Accept: application/vnd.github.raw"`

The rules repo is private. If neither works, ask the developer for access before writing code.

## Required reuse

Always reuse the files below for their listed responsibilities. Import or extend the existing implementation in its owning file. Do not copy the implementation or create a parallel file that serves the same purpose.

| File | Required reuse |
| --- | --- |
| `src/errors.py` | Use `ErrorEnvelope`, `ExtractionError`, `error_response`, and `retry_after_headers` for shared error responses, extraction failures, and retry headers. |
| `tests/conftest.py` | Use the existing shared pytest fixtures, `FakeLLM`, `make_pdf`, and synthetic resume data. Add new shared test fixtures here. |
| `src/ai_errors.py` | Use `AiErrorRoute`, `AiRequestError`, and `call_ai` for AI route error handling and provider failure classification. |

### Compatibility when extending shared files

- Preserve existing behavior for every caller, including function signatures, response shapes, error codes, and retry behavior.
- Make new parameters optional for existing callers. Use defaults that preserve the previous behavior when a parameter is omitted, sent as JSON `null`, or passed as Python `None`. Account for clients that omit `undefined` values during serialization.
- Verify existing callers and add regression coverage for omitted and explicit null values when introducing a parameter. Exercise affected API flows and check that downstream callers and pages continue to work without unhandled errors.

## Done

Done means `pytest` passes, after `pip install -r requirements-dev.txt`.
