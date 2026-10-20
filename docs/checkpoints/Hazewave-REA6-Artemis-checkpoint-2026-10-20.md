# Hazewave progress checkpoint — 2026-10-20

## Purpose

Preserve the current Hazewave recovery and integration state, plus the intended architecture boundary with Artemis. This document is a progress checkpoint, not a claim that the end-to-end system is fully validated.

## Architecture agreed with the project owner

- **HAZE** owns audio, sound, music, and audio-production capabilities.
- **WAVE** owns video, images, and visual-media capabilities.
- **BRIDGE** translates structured state between the HAZE and WAVE domains.
- **REA** is already integrated into Hazewave; recovered REA6 work must be reconciled with that existing integration rather than duplicated.
- **Artemis** is the agent/executor that may consume Hazewave capabilities through explicit interfaces. Artemis, IA Memory, the LLM/provider layer, and Hazewave have different responsibilities. The exact integration point must be confirmed from the repositories before implementation.
- IA Memory must not be replaced by an LLM; provider routing must not be confused with persistent memory.
- Do not modify BR-no-GTA as part of Hazewave tasks.

## Local Termux repository state (reported in working session)

Original repository:
- Path: `$HOME/Hazewave-dev`
- Branch: `work/wave-living-resonance-v1`
- HEAD at checkpoint: `d27f68d7310922cbcfb04bf85d3803040511ae9d`
- 21 staged paths were present. They are user work and must remain untouched until explicitly authorized. Do not reset, clean, checkout over, commit, or merge this original worktree as part of recovery.

Isolated recovery worktree:
- Path: `$HOME/Hazewave-REA6-recovery`
- Detached HEAD: `ad66ab81f53bcc9798ac611c1ad5513586590605`

Isolated integration worktree:
- Path: `$HOME/Hazewave-REA6-integration`
- Branch: `work/rea6-integration-recovery`
- Local merge commit: `081cd5f61e2975ee25c2d5e582c3558fb7157095`
- Subject: `feat(hazewave): integrate recovered REA6 research capabilities`
- The merge includes a broad recovery from PR #38 (189 files); it is not a narrowly scoped REA-only patch.
- The commit was local only at checkpoint; it had not been pushed.
- A stray untracked path named `-` was reported in the integration worktree. Inspect and preserve it until its contents and origin are understood.

## Verification status

- The selected REA6, research harness, MCP, native behavior, and proof tests passed with exit code 0.
- The full pytest suite did not pass: 9 failures, with 2 skipped.
- Reported failure groups: 9Router ranking/fallback/admission tests; runtime receipt and reaper tests due to `os.link` being unavailable in the Termux Python 3.14.6 build.
- Do not weaken atomic create-only receipt semantics to work around the missing `os.link`. Any compatibility fix must preserve non-overwrite behavior and include regression tests.
- The existing NVIDIA/provider and 9Router files indicate implementation work, but the full live LLM request path has not yet been proven end-to-end.

## Safe next steps

1. In Termux, create a timestamped archive of both Hazewave worktrees and a separate patch/status record, without changing either worktree.
2. Verify archive contents and checksums.
3. Push the existing local integration branch as a new remote branch only after confirming its current HEAD and status. Do not push the original staged worktree by accident.
4. Keep the original `work/wave-living-resonance-v1` staged changes untouched.
5. Investigate the 9Router failures and Termux receipt compatibility separately, with regression tests.
6. Inventory the real Artemis and IA Memory interfaces before deciding where the Hazewave LLM/provider router should connect.
7. Do not claim Artemis is already integrated with this recovered branch until that connection is implemented and tested.

## Important safety boundary

This checkpoint documents the current known state. It does not contain secrets, API keys, private voice references, or credentials. Never print provider tokens while diagnosing configuration.
