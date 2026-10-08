---
name: hazewave-iris-camera
description: Governed first-party site screenshot observation for WAVE using Iris 0.4.1; never replaces the REA software forensics layer, creative evaluation or owner approval.
---

# WAVE Iris — visual evidence camera (development candidate)

**Upstream:** brijr/iris, MIT, official v0.4.1 sha256-pinned Linux release. **Authority:** HAZEWAVE_HARNESS. **Domain:** WAVE only. **Agent execution authority:** NONE.

Iris produces a screenshot of an already authorized first-party webpage. It does not inspect React source, reconstruct layouts, evaluate art direction, audit accessibility, perform interactions or independently fix a website. Its optional stdio MCP tool named `capture` is one tool, not a general browser/automation service.

## Before every capture

1. Determine if the reviewed first-party fixture is the target. Default admission is **only** `tests/fixtures/iris-proof.html` inside the verified Hazewave worktree. A development preview requires a precise separately authorized loopback origin; no arbitrary public URL, private address, intranet, credentials or private media.
2. Verify installed Iris version `0.4.1`, upstream asset digest, browser identity, resource budget, and whether the current machine is the **existing Codespace**, not a disposable CI runner.
3. For CLI installation and fixture test use `scripts/codespaces/install-iris-open-tool.sh --preflight`, `--install`, `--doctor` and `--smoke` in that sequence from an isolated clean worktree.
4. Verify the screenshot PNG CRC structure, source identity, SHA256, nonzero dimensions, and private 0600 evidence receipt. Keep pixels and any page state local by default.
5. Interpret pixel observations alongside CSS/layout/DOM, computed styles, browser performance, mobile breakpoints, accessibility checks and independent human art-direction review. One image cannot prove an immersive Hazewave site is professional.
6. No automatic branch promotion, production deployment, site redesign, stock Colibri restart, or REA/BR-no-GTA modification.

## MCP boundary

The upstream `iris mcp` stdio service supports a `capture` tool. **Do not register it into every coding agent or global configuration automatically.** The naked upstream tool accepts arbitrary URLs; the current Harness policy does not yet enforce URL scope and redirects *inside that MCP server*. A direct registration would let subordinate agents access resources beyond a signed research grant.

Before enabling MCP for WAVE, implement and independently review a real URL/redirect/local-data enforcement layer, bind it to a specific project/task authorization, and test both `tools/list` and one controlled `tools/call` against the reviewed fixture. Merely installing the executable or running `iris mcp --help` does not prove agent connectivity.

Never report `IRIS_MCP_CONNECTED=PASS`, `IRIS_CODESPACE_READY=PASS` or `HAZEWAVE_SITE_QUALITY_APPROVED=PASS` from GitHub CI alone.

## Evidence and limitations

Receipt: `HazewaveIrisVisualEvidence/v1`, with image digest, dimensions, size, pinned version, owner-source fixture status, and explicit unproven MCP/production flags. First-party screenshots are only one measurement in the WAVE system. Audio expertise remains HAZE; REA remains software investigation. For a private screenshot the Harness must issue an exact scoped signed grant; do not copy pixels into public Git or third-party plugins.
