# Hazewave — Capability Evidence Plane V1

**Status:** development draft, not deployed to existing Codespace.
**Authority:** `HAZEWAVE_HARNESS`; all output is **read-only and advisory**.
**Owner-controlled target:** existing `hazewave-zero-cost-4jxp45676rq6279xx`, never another Codespace.
**Scope:** REA6 software forensics, Iris browser camera, HAZE sound and WAVE visual/media work.

## Why this exists

The Harness currently recognizes over 100 capability names, but a valid domain route
does not imply an installed executable, a loaded MCP tool, successfully executed
fixture, honest benchmark, signed exact-target grant, or permission to publish.
We must not repeat the false equation “repository integrated = operational”.

The plane distinguishes:

| Step | What it proves | What it does not prove |
|---|---|---|
| `DECLARED` | manifest names a provider and exact Harness capability | present/installed |
| `UNAVAILABLE` | executable discovery failed | upstream is broken |
| `PRESENT_UNPROVEN` | executable path observed on inspected host | correct version, usable functionality |
| `CI_FIXTURE_PROVEN` | short-lived signed record came from different CI host | Codespace readiness |
| `FIXTURE_PROVEN` | valid signed scoped fixture record exists on this host | production acceptance |
| `STALE` | SHA/host/bin hash/date mismatch | eligible to route |
| `MEASURED_READY` | signed exact host/SHA/tool/artifact, observed list+call, reproducible measurement (>=3 samples), free cost | human production authorization or continued health |
| `BLOCKED` | invalid manifest/signature/cost/trust input | automatic bypass |

As of the initial CI check there are **zero operationally ready providers**: this is the
correct result without owner-signed host-specific reproducible evidence. Existing GitHub
runner success is historically useful **but is not Codespace runtime evidence**.

## Approved read-only inventory

In an existing, reviewed Hazewave checkout or isolated worktree (do not switch/reset
the checkout in use):

```bash
PYTHONPATH=src python3 -m hazewave.capability_plane inventory \
  --host-id "${CODESPACE_NAME:?Codespace identity required}" \
  --repo-sha "$(git rev-parse HEAD)"
```

No downloads, no installations, no network, no agent invocation. Candidate binaries
are discovered via PATH plus known version-pinned isolated Iris/REA/scene-detector
locations. The inventory includes explicit totals: mapped vs unmapped Harness
capabilities, present-but-unproven, CI-verified but not local, route-eligible, and
percentages. Unknown cost always denies automatic selection.

## Signed runtime proof ingestion

For a real capability proof, an independent owner/Harness verifier must inspect the
raw local tool trace, binaries and fixture results, then produce a signed
`HazewaveCapabilityRuntimeEvidence/v1` JSON record:

- Exact `tool_id`, Harness `capability_id`, `domain` and version
- Correct host identity, exact repo SHA and installed tool binary SHA256
- `stage`: INSTALL/EXPOSED/EXECUTED/BENCHMARKED (using exact enum
  `INSTALLED`, `EXPOSED`, `EXECUTED`, `BENCHMARKED`)
- Actual `tools/list` and `tools/call` or equivalent instrumented adapter calls
- Actual fixture SHA256, result, and SHA256 of preserved owner-only raw evidence log
- Benchmark with sample count, defined quality score, cost USD, risk score, p50 and p95
- Issue/expiry timestamps: maximum 6 hours, always checked again during selection
- An explicit `production_approved=false` field

Sign **outside** the Codespace with the owner-controlled private SSH key, OpenSSH
namespace `hazewave-capability-proof`. Keep the exact allowed public signer file
owner-controlled, mode 0600; never generate owner keys in CI or grant a tool
the right to sign its own promotion.

Store `evidence.json`, `evidence.json.sig`, `evidence.json.log` and the
owner public trust file outside Git. Logs can contain private URLs, paths or
media details, so never attach them to a public PR or send them to provider plugins.
Verification uses `ssh-keygen -Y verify`, checks the raw log hash, file ownership,
mode 0600, host, digest, package version and expiry. Only reviewed signatures are
trusted. A signed claim does not automatically prove the accuracy of the log's
measurements: review and independent test are still required.

```bash
PYTHONPATH=src python3 -m hazewave.capability_plane inventory \
  --host-id "${CODESPACE_NAME:?}" \
  --repo-sha "$(git rev-parse HEAD)" \
  --signer-trust "$HOME/.config/hazewave/reverse-engineering/allowed_signers" \
  --evidence "/private/owner-controlled/evidence.json"

PYTHONPATH=src python3 -m hazewave.capability_plane select \
  --host-id "${CODESPACE_NAME:?}" \
  --repo-sha "$(git rev-parse HEAD)" \
  --signer-trust "$HOME/.config/hazewave/reverse-engineering/allowed_signers" \
  --evidence "/private/owner-controlled/evidence.json" \
  --capability web.visual_regression --domain WAVE
```

`select` is **an advisory comparison**, never an execution token. The existing
Harness task authorization and a real owner-signed exact-target grant remain separately
mandatory. The generated decision cannot alter `BR_OWNER_V1`, bypass review,
register arbitrary `iris mcp` URLs, restart Reflex/Colibri, install paid tools,
merge branches or publish releases.

## Choosing professional tools

Selection only considers owner-signed real-host reproducible evidence of the
specific capability and freely admitted cost. It ranks *observed* normalized
quality (descending), risk score (ascending), and p95 latency (ascending).
Metrics are not made up from tool names or star counts. Unknown costs, missing
benchmarks, one-off screenshots, unsigned JSON and cross-domain capabilities are
excluded. Separate models and reference media must have proper rights.

For long audiovisual benchmarks, use a dedicated reviewed worktree and a separate
resource/owner-review gate. Measure audio quality, video/animation fidelity,
render consistency, stems, optical flow and timing using appropriate tools.
Neither REA decompilation nor Iris screenshots prove artistic excellence.

## Acceptance plan

1. Test in CI that unknown tools stay unavailable, the declared list does not
   imply readiness, and CI receipts never become Codespace receipts.
2. Execute actual isolated installer/preflight/doctor/fixtures on the existing
   Codespace only; preserve stock. Audit actual MCP agent `tools/list`.
3. Independently review raw trace and sign exact scoped facts. Repeat at least
   3 randomized paired runs for any benchmark.
4. Analyze coverage gaps, then build *one validated capability at a time*.
5. Maintain separate human quality signoff and security review; production
   remains fail-closed.
