# HAZEWAVE — Harness-executed REA 6.0.0 + Iris 0.4.1 (research fixture bridge)

**State:** draft development candidate; real end-to-end CI runner executed, **existing Codespace still not attested**.
**Authority:** HAZEWAVE_HARNESS. **Agents:** subordinate and limited to first-party fixtures.
**Parent PRs:** REA6 #30, audiovisual lab #31, Iris #32, capability evidence #33, provider conformance #34, this bridge #35.

## Verified difference from an inert tool registry

This implementation does not merely show an npm package or MCP catalog. It has
an actual, version-checked **HarnessRouteDecision -> HarnessAuthorization ->
subprocess tool execution -> verified evidence -> private receipt**.

Admitted tools:

- `harness_rea_owned_js`: executes pinned REA 6.0.0 to analyze the harmless
  first-party `tests/fixtures/rea6-javascript-owned` application, verifies
  REA Evidence ID and nonempty application module graph and exact source-tree
  digest. No JavaScript execution, non-owned files or native Ghidra assumption.
- `harness_iris_owned_page`: executes pinned Iris 0.4.1 with a Chromium-family
  browser against **only** `tests/fixtures/iris-proof.html`, validates PNG
  structure, CRC, dimensions, screenshot SHA256 and local receipt. CLI cannot
  select another URL and the gateway accepts no URL/path argument.

The stdio MCP facade `hazewave.harness_research_mcp` implements
`initialize`, `tools/list`, `tools/call`; it exposes only the two tool
names. Tool calls accept precisely `task_id` and at most two calls per server
instance; a request trying to inject a URL, path, provider ID or shell command
fails before any tool launch. It does **not** register the raw upstream REA/Iris
MCP with every coding agent, so it cannot bypass the Harness research scope.

`python -m hazewave.harness_research_execution` also supports one-shot
operator-triggered execution. Both commands verify the exact clean worktree SHA
and keep receipts `0600` outside Git. Subprocess environments are restricted
to basic HOME/PATH/localization/browser variables; they do not inherit API
keys, GitHub access headers, Telegram tokens, SSH agents or npm credentials.

The output is **OBSERVATION_ONLY**, `production_approved=false`,
`capability_plane_measured_ready=false`,
`owner_signed_external_target=false` and
`agent_mcp_session_connected=false`. The scope is an operator-owned fixture
bootstrap, **NOT** an arbitrary signed target grant.

## What was proven on a disposable GitHub worker

- The exact published REA 6.0.0 npm package was installed in an isolated prefix
  and its executable analyzed a first-party source app through the actual
  Harness-routed subprocess entrypoint.
- The exact official Iris 0.4.1 Linux musl archive SHA-256 was verified, and the
  executable took a real Chromium screenshot of the first-party HTML fixture.
- An independent MCP client initialized the local Harness façade, enumerated
  its two tools, refused an external URL override and invoked both tools via
  `tools/call`, producing two locally private SHA-bound receipts.
- The GitHub runner requires a dedicated `--no-sandbox` Chromium wrapper
  for that offline synthetic fixture. **Never transfer that weakening to the
  existing Codespace or a real public page.**

The CI runner is not the owner's Codespace, and the MCP client used there is
not an existing Hermes/Agent Office/Codex session. Do not say
`CODESPACE_INSTALL=PASS` or `OWNER_AGENT_MCP_CONNECTED=PASS` from these tests.

## Deployment on the ONE existing Codespace

Use only `hazewave-zero-cost-4jxp45676rq6279xx`. Work must open the
**existing** machine terminal via its authorized browser/computer-use workflow.
The GitHub repository connector alone does not provide interactive shell
execution. Do not create another Codespace, increase compute size or overwrite
the active worktree. The original stock Colibri is untouched.

```bash
set -euo pipefail
cd /workspaces/Hazewave-
test "$CODESPACE_NAME" = "hazewave-zero-cost-4jxp45676rq6279xx"
git status --short
git fetch --no-tags origin refs/heads/work/harness-live-research-execution-v1
SHA="$(git rev-parse FETCH_HEAD)"
REMOTE_SHA="$(git ls-remote origin refs/heads/work/harness-live-research-execution-v1 | awk 'NR==1 {print $1}')"
test "$SHA" = "$REMOTE_SHA"
WT="$HOME/.local/share/hazewave/harness-research-bridge-${SHA:0:12}"
test ! -e "$WT"
git worktree add --detach "$WT" "$SHA"
cd "$WT"
export HAZEWAVE_RESEARCH_EXPECTED_SHA="$SHA"
bash scripts/codespaces/harness-live-research-bridge.sh --preflight
bash scripts/codespaces/harness-live-research-bridge.sh --prove
```

The preflight is fail-closed on wrong Codespace ID, dirty worktree, remote
identity or moved branch SHA, absent pinned REA/Iris binaries or Chromium, and
insufficient 4GiB free RAM/4GiB free disk. No downloads. Run the exact
**preexisting** approved REA6 and Iris installers from their respective parent
PRs if dependencies are missing, then repeat the preflight. Do not install
Hopper/IDA, proprietary drivers or paid services. If no existing terminal
is accessible, report `CODESPACE_SHELL_UNAVAILABLE` instead of fake PASS.

After both real proofs pass, the local Harness research MCP can be started by:

```bash
bash scripts/codespaces/harness-live-research-bridge.sh --mcp
```

This STDIO mode is for a client whose **exact command and arguments were
reviewed and approved**. Register only this limited wrapper, not raw `iris mcp`
or raw `rea mcp`. Restart/reconnect the chosen client and verify its
`tools/list` then a controlled `tools/call` against the first-party
fixtures. A tool launched from a Codespace terminal is not automatically
available in a pre-existing agent process. No automatic registration was done
by this PR.

## Real sites and external native applications — current hard boundary

**Not enabled.** An Iris URL string allowlist is not a network sandbox:
redirects, subresource requests, service workers, WebSockets, credentials,
DNS and browser profiles must be isolated too. Playwright's
`browserContext.route()` can intercept requests but may miss traffic mediated
by service workers unless disabled; it must be paired with effective
operating-system-level egress controls, fresh ephemeral browser profiles,
nonprivileged execution, and an enforced deny-by-default origin policy.
The upstream Iris binary does not itself provide a Harness-proof egress
boundary just because its CLI was given an approved URL.

Authoritative technical sources:
- https://playwright.dev/docs/network
- https://playwright.dev/docs/service-workers
- https://chromedevtools.github.io/devtools-protocol/tot/Fetch/
- https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- https://morluto.github.io/rea/get-started/
- https://github.com/brijr/iris

Likewise, REA Ghidra native analysis requires the separately prepared
`scripts/codespaces/rea6-provider-conformance.sh --native`, a compiled
first-party ELF and verified direct Evidence with real provider startup.
JavaScript graph success must not be generalized to managed .NET, Ghidra,
Electron runtime observation or Frida instrumentation.

## Next measurement gates

1. Owner workstation `--preflight` and `--prove` on exact SHA, stdout/stderr
   and file hashes preserved privately, stock Colibri health checked read-only.
2. Local MCP `tools/list` plus the two `tools/call` operations inside the
   **actual existing agent client**, not a disposable probe.
3. Minimum ten Iris calls in a persistent test MCP session and repeated REA
   static and native fixture operations, reporting cold-start, p50/p95,
   CPU/RAM, unexpected networking and failure rates, independently checked.
4. External sites only after independently reviewed browser network egress
   isolation and owner-signed exact-target grants; no global crawler.
5. Promote a capability to `MEASURED_READY` only after owner-controlled
   signed host/artifact evidence and coverage-plane checks; human artistic
   approval remains separate.

**No merge, branch reset, production publication, stock restart, external
models or autonomous network install is authorized by this runbook.**
