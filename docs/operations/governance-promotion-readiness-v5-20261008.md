# Governance V5 — exact-source adoption audit (2026-10-08, São Paulo)

Status: **BLOCKED — NO CANONICAL PROMOTION AUTHORIZED**. This is a durable audit artifact, not a merge authorization or a replacement for AGENTS.md. Original PRs #49, #50, #51 remain independent draft development objects.

## Independently observed GitHub state

- Repository: `zenindiones-maker/Hazewave-`; default `main` at `b97e1b7fde42cb74abf6585e5be0796f820cc69a`.
- REST `GET /branches/main`: `protected=false`, `protection.enabled=false`, required contexts/checks empty.
- REST `GET /rulesets?includes_parents=true`: empty array.
- REST `GET /branches/main/protection`: HTTP 403 `Resource not accessible by integration`, so detailed administrative protection cannot be certified.
- Authenticated GitHub user `zenindiones-maker`, repo `permissions.admin=true` on repository metadata; this does NOT confer the integration's missing administration API capability.
- `main` lacks `AGENTS.md`, `config/project-profile-v2.json`, `src/hazewave/harness.py`, `docs/DOCUMENTATION_REGISTRY_V2.json` and the current source-truth guard. Do not fabricate those as historical main files.
- PR #49 head `20482f93299e398e08a38a0e215a613ff37c136e` is **754 commits ahead** of the verified main SHA. This comparison had merge base `b97e1b7...` and 0 behind.
- PR #50 is based exactly on PR #49: `a8479a6190db51b7abeca071ccead1e3ac6e2c85`, with eight changed files: `.github/workflows/ci.yml`, `AGENTS.md`, `config/source-of-truth-deletions-v1.json`, `docs/DOCUMENTATION_REGISTRY_V2.json`, `docs/governance/source-of-truth.md`, `scripts/validate_repository_contracts.py`, `src/hazewave/source_truth_guard.py`, `tests/test_source_truth_guard.py`.
- PR #51 is based exactly on PR #50: `4a1af276b8200a76338b5c309f458e167904f8d7`, changing only the HAZE diagnostic workflow and its experiment document.
- Source-truth PR #50 run `37864702424` had jobs `source_truth`, `test (3.12)`, `test (3.14)` all SUCCESS, with authenticated receipt `REMOTE_HEAD=a8479a6...`, `REVIEWED_TREE=dbe6d7306532a177a6f8625c134beb702c3852ee`, 41 active references checked, one verified tombstone and zero restorations.
- PR #51 run `37865366312` had `source_truth`, `test (3.12)`, `test (3.14)` SUCCESS. CI success does not attest a genuine model run.

## Isolation feasibility and hard blockers

A new candidate cut directly from `main` using only PR #50's eight files **cannot run or preserve the existing Harness contracts**: several imports, pre-existing AGENTS authority, registries, accepted ADRs and source-history proof have no counterpart in `main`. The tombstone validation also requires deletion commit `8624e219882f11d39cd2c8cb893e984c3fcc86f5` to be an actual ancestor; this commit lies in development history, not current main.

Thus, a naïve cherry-pick would either fail or silently create an alternative architecture. A merge of the full stack would import hundreds of unrelated commits. Both routes are explicitly rejected. An isolated, promotion-ready *code* candidate is **NOT YET FEASIBLE** without a separately reviewed baseline-adoption decision and dependency inventory. Keep the eight-file governance diff separate from the unapproved HAZE seven-file PR #49 and the PR #51 experiment.

## Promotion requirements (owner-admin boundary)

1. Establish a reviewed **baseline migration** for main: explicitly decide which currently developed Harness core and canonical records are approved. Build an exact-bound migration with no obsolete file restorations and full suite run. No bulk stack merge.
2. Install a main-targeted GitHub ruleset or branch protection with PR-only changes, required reviews by an independent eligible reviewer, no author self-approval, stale-review dismissal, no force pushes/deletion, minimal or zero bypass, and review/approval for workflow/guard/policy changes. An owner with admin capability can modify protections unless administrative governance restricts that; do not misrepresent the check as immutable against the administrator.
3. Require the uniquely identified GitHub Actions `source_truth` job from the expected Actions app plus repository tests, exact head SHA, and where applicable merge-group events. Ensure protected checks originate from a **trusted main-maintained workflow** or otherwise cannot be neutralized by editing PR-controlled workflow code. A skipped job may be treated as successful, so avoid job-level skip conditions for required checks.
4. Bootstrap `source_truth` on `main` through an **approved governance-only/reviewed baseline** before requiring it for arbitrary PRs, or the missing check may deadlock merges. Never disable a required check just to get a PASS.
5. Query effective enforcement using a token with branch-protection/rulesets read privileges. Verify actual required checks, bypass actors, branch patterns, review settings, and deletion rules. Read-only verification **before** any administrative mutation.
6. If an intentional deleted-file restoration is proposed, require an exact reviewed commit/tree, reasons, regression tests, verified GitHub independent review, and no self-signed receipt. Existing PR #50 has no restoration.
7. Recompare current main/tree with the final approved candidate immediately before any prospective promotion. **Human approval is mandatory.**

Final recommendation: `SOURCE_TRUTH=IMPLEMENTED_ON_DEVELOPMENT`; `SOURCE_TRUTH_REQUIRED_ON_MAIN=FALSE`; `CANONICAL_PROMOTION=NOT_ATTEMPTED`; `GOVERNANCE_PROMOTION_READY=FALSE`.

Reference: [GitHub branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches); [required check and skipped-job semantics](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
