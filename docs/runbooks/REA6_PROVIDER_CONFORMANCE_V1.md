# REA 6.0.0 — Native and Application Provider Conformance

**Status:** draft, non-production. This workflow is a **route-by-route investigation**, not a blanket REA readiness certificate.
**Authority:** `HAZEWAVE_HARNESS`. **Host:** existing `hazewave-zero-cost-4jxp45676rq6279xx` only.
**Source:** exact upstream open-source `morluto/rea` release `rea-agents@6.0.0`.

## What the REA tools actually cover

| Route | Tool | First-party proof | Status required for real use |
|---|---|---|---|
| Native ELF/PE | REA + Ghidra 12.1.4 | compile owned ELF with `cc -O0 -g`, query `main` via `rea function ... --provider ghidra --json`, validate direct Evidence bound to target SHA | Ghidra-only doctor + actual tool call + independent host receipts |
| Static JS/Electron graph | `rea analyze-javascript-application` | analyze self-contained owned JS directory and check nonempty module graph/Evidence | exact source artifact identity, sample tests on host |
| Managed .NET | `rea inspect-managed-artifact` | reject a deliberately invalid PE/CLI fixture (NEGATIVE ONLY) | source-owned real managed assembly metadata/CIL fixture, per-field facts |
| Rizin | version-pinned standalone binary | no native-provider equivalence assumed | qualify its actual supported operations independently |
| Frida | version-pinned dynamic instrumentation | **NOT EXECUTED** in CI | separate explicit owner scope and sandbox/permission review; no attachment to stock |
| Browser/Electron runtime | specialized REA runtime observations | NOT EXECUTED in CI | isolated browser, redirect/request policy, signed target, resource guard |

Ghidra is the admitted open-source **native analysis provider**. Rizin and Frida
are auxiliary tools, not implicit interchangeable substitutes for Ghidra.
Proprietary Hopper/IDA fallback is not permitted. Source and behavior recovery
do **not** imply perfect original-source reconstruction.

## Operational procedure — existing Codespace only

No automatic installs, branch switches, new machines, paid services,
mass tool-agent registration or restarts. Use a detached worktree tied to the
reviewed exact SHA. Confirm host identity, resource budget, clean worktree,
published 6.0.0 package and Ghidra license before action. Use the REA6
side-by-side installation already prepared in PR #30, not BR-no-GTA binaries.

```bash
export HAZEWAVE_REA6_EXPECTED_SHA="$(git rev-parse HEAD)"
bash scripts/codespaces/rea6-provider-conformance.sh --preflight

# Native-only: Ghidra scoped health, owned ELF, real function query,
# exact-bound Evidence verification. Does NOT need Frida/Rizin to PASS.
bash scripts/codespaces/rea6-provider-conformance.sh --native

# JS application: owned package and two modules, graph Evidence.
bash scripts/codespaces/rea6-provider-conformance.sh --javascript

# Negative control ONLY, not proof of positive .NET analysis capability.
bash scripts/codespaces/rea6-provider-conformance.sh --managed-negative
```

Preflight never starts REA, mutates the host or creates a fixture. Mode runs
create private receipts under the isolated REA6 doctor route directory. The
native function probe uses the explicitly selected `ghidra` provider and
rejects evidence without a source digest and direct observation. JS analysis
does not require a native provider or browser: it is static artifact inspection,
not live Electron runtime observation. Existing global `rea` and old 4.1.0
installers remain untouched.

## CI scope and no false PASS

The disposable GitHub Actions runner installs published
`rea-agents@6.0.0` separately, analyzes Hazewave-owned JS source, validates
the recovered application module graph and checks that a bogus `.dll`
is rejected by `inspect-managed-artifact`.

Those proofs do not attest Ghidra being operational in the owner's Codespace,
positive .NET analysis, Frida instrumentation, Rizin equivalence, a connected
agent MCP session or production rights.

The capability-plane's signed host-bound evidence must be issued only after
independent review of raw logs and the actual tool digest; CI success cannot
be rebound to the Codespace. In addition, the real signed *target grant*
remains mandatory for every non-fixture reverse-engineering study.

## Next graduation gates

1. **Ghidra:** host-scoped doctor, real owned ELF/PE fixture and at least three
   repeat observations with source/tool SHA and resource numbers.
2. **Managed:** compile a tiny original .NET assembly and prove metadata,
   CIL and native-boundary tool behavior before enabling that route.
3. **JS/Electron:** validate bundled/ASAR graph, static observation and
   runtime CDP as distinct measured capabilities; browser must be isolated.
4. **Rizin/Frida:** qualify per operation, host and grant, not automatically.
5. **Agent connection:** after independent review of permissions, enumerate
   exact MCP tools in the actual agent session and run one signed controlled call.
6. **Harness promotion:** capability evidence plane must mark each operation,
   not just tool names, and fail closed on unknown cost, missing or stale proof.
   Publication/merge requires separate owner decision.
