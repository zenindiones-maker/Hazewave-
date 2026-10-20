# HAZEWAVE — Iris visual camera, verified deployment contract

**Status:** draft candidate; installed and demonstrated on ephemeral GitHub Actions runner only. The existing Hazewave Codespace has not been accessed in this chat.

**Upstream:** [brijr/iris](https://github.com/brijr/iris), `v0.4.1`, Rust CLI/MCP, MIT.
**Pinned asset:** Linux x86_64 musl `iris-x86_64-unknown-linux-musl.tar.gz`, SHA256 `aa6073ba255c0bcf09364a5503cbd4794791b832e5934a52b169a455d66101c7` from the GitHub official release API.
**Runtime dependency:** installed Chromium-family browser; this installer never makes a paid service, a second Codespace or a global Chromium/browser install.

## Why Iris and when not to use it

Iris gives WAVE a measured screenshot of a website render. It is not software reverse-engineering (REA 6.0.0 + Ghidra remains that lane), audio (HAZE), graphics frame debugging, DOM accessibility or an automated artistic judge. A screenshot is only a first observation in a visual engineering investigation: compare color/typography, breakpoints, WebGL render, layout, animation timing, visual regressions and human editorial judgment with task-appropriate analyzers.

## Execute on the one existing Hazewave Codespace

Use **only** `hazewave-zero-cost-4jxp45676rq6279xx`. Open an existing shell, refresh remote `work/iris-visual-observability-v1`, verify exact HEAD and create one isolated detached worktree without switching the current branch. The installer requires `HAZEWAVE_IRIS_EXPECTED_SHA` equal to that worktree's HEAD. Check the remote branch HEAD just before proceeding; a SHA mismatch blocks execution. Never create another machine.

```bash
cd /absolute/path/to/existing/reviewed/iris-worktree
export HAZEWAVE_IRIS_EXPECTED_SHA="$(git rev-parse HEAD)"
bash scripts/codespaces/install-iris-open-tool.sh --preflight
bash scripts/codespaces/install-iris-open-tool.sh --install
bash scripts/codespaces/install-iris-open-tool.sh --doctor
bash scripts/codespaces/install-iris-open-tool.sh --smoke
bash scripts/codespaces/install-iris-open-tool.sh --mcp-smoke
```

Each mode is separately invoked and fail-closed. `--install` downloads the official archive, verifies SHA256 and safe archive structure, and installs the binary under `~/.local/share/hazewave/iris/v0.4.1/bin/iris` only. There is no `curl|sh`, `sudo`, global path replacement, repository merge or stock restart. `--smoke` renders only a repo-owned `file://` HTML fixture and writes a local 0600 receipt under `~/.local/state/hazewave/iris/receipts`. `--mcp-smoke` verifies an ephemeral `iris mcp` process, its sole `capture` tool, and an inline PNG on the same first-party fixture.

**Do not infer that a parent Codex/Hermes/other agent has loaded the MCP tool.** No global registration occurs. The standalone Iris MCP service accepts arbitrary URL requests, so enabling it in a production coding agent without an enforcing task-scoped/redirect-safe authorization gateway would be a security regression. Implement and review that gateway before live registration.

**Browser CI caveat:** the ephemeral GitHub runner needs a `--no-sandbox` Chromium wrapper when sandboxed browser startup fails; only its generated local fixture is loaded. This workaround MUST NOT be silently copied into the owner Codespace or reused for untrusted external URLs.

## Evidence states

- `IRIS_BINARY_INSTALLED`: proves exact release archive digest/binary execution on the named host.
- `IRIS_CLI_CAPTURE`: screenshot PNG CRC, bytes, viewport dimensions, source digest and output receipt.
- `IRIS_MCP_PROCESS_FIXTURE`: isolated upstream tools/list + tools/call + inline PNG, **not** live agent connection.
- `IRIS_HARNESS_LIVE_EXECUTION`: explicit qualified task authorization, redirect-safe URL policy, actual agent tool enumeration, human approval boundaries (currently **NOT_PROVEN**).
- `STOCK_HEALTH`, `CODESPACE_RESOURCE_BUDGET`, `PRODUCTION_APPROVED`: separately assessed; CI does not prove these.

Do not upload screenshots of private owner sites or application sessions, credentials, console history or target media to public GitHub artifacts. Follow the screenshot's content license and preserve approved WAVE research scope. All findings must remain evidence-only until independent visual/editorial review.
