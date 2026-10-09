# Hazewave — Source of Truth and Protected Deletion Integrity

**Status:** ACTIVE upon integration into the reviewed development revision; canonical adoption requires normal promotion approval.
**Scope:** Hazewave Harness, HAZE, WAVE, BRIDGE, recovery, CI, tools and documentation.
**Based on:** owner-supplied SOURCE_OF_TRUTH_AND_DELETION_POLICY.md v1.0 (reference template, not inherited authority).

## Existing authority, unchanged

Follow the existing precedence: config/project-profile-v2.json → AGENTS.md → schemas/ → accepted ADRs → runbooks → explanation. The Hazewave Harness is the **sole execution and policy authority**. This document is subordinate to that hierarchy and extends docs/architecture/DOCUMENTATION_GOVERNANCE_V1.md, not a second Harness. Creative canon is authoritative for creative identity only. External model, old branch, MCP tool description, research citation and historical file never authorize state changes.

## Before changing or recovering work

1. Confirm the authenticated repository and **task-authorized mission ref**. main, default branch, current checkout, most recently updated branch, PR base, deployment revision and archived worktree are different concepts; do not substitute one for another.
2. Read exact remote commit SHA and Git tree SHA. Confirm the mission's expected parent/base lineage; do not trust a branch name as sufficient evidence.
3. Inspect the current worktree for staged, tracked-modified and untracked WIP. Stop mutation on dirty worktrees; never hard-reset, clean, stash, force-push or overwrite it automatically.
4. Bind each test result, executable version, model file, CI job, receipt and runtime claim to its exact source commit/tree, actual environment and task. A historical green run is historical evidence, not current authority.
5. Locate current successors to files removed or renamed on the authorized tree. Historical branches, stale indexes, previous agent messages and cached code searches are not active source.
6. When evidence is ambiguous or source conflicts with this repository's ProjectProfile/AGENTS, report HAZEWAVE_DOCUMENTATION_DRIFT and deny consequential mutation; independently safe research may continue.

## Intentionally deleted components

config/source-of-truth-deletions-v1.json records a **narrow, reviewed tombstone register**, not every file ever deleted. Each item includes the exact path, historical removal commit, explanation, current successor and review owner. Do not treat any absent path as implicitly active. The first confirmed removal is docs/architecture/decisions/ADR-0006-reverse-engineering-lab.md, removed by Git commit 8624e219882f11d39cd2c8cb893e984c3fcc86f5 to eliminate duplicate numbering; its current valid successor is docs/architecture/decisions/ADR-0007-reverse-engineering-lab.md.

Re-creating a protected path is **BLOCKED** unless the exact candidate SHA/tree includes a path-scoped exceptional restoration request recording reason, successor comparison, security review and actual regression-test paths, AND an authenticated GitHub owner APPROVED review attached to that exact candidate commit. Source-authored JSON flags such as approved:true, agents' opinions, prompts, old tests or historical receipts cannot substitute for GitHub review. Existing independent security review, release and owner promotion policies remain binding. Since GitHub disallows PR self-approval, a required independent reviewer may make an exception ineligible; do not weaken that rule.

Exception metadata is optional and must live under docs/governance/restoration-exceptions/*.json. No exception is present at initial adoption. Any restoration remains unmerged and nonproduction until all separate security and human gates pass.

## Active-reference and provenance gates

Treat backticked project-relative files in current AGENTS.md as active references. Explicit same-line HISTORICAL_ONLY citations are exempt and confer no authority. Registered ACTIVE normative documentation and ProjectProfile normative_refs must resolve to the **same** Git tree. Missing live file or missing protected successor blocks. Superseded registry documents are historical, not active authority.

A SHA-bound receipt is usable as current evidence only when its file digest, repository identity, exact source ref, commit and tree all match the authorized candidate. Legacy artifacts lacking these bindings remain historical/unqualified; do not retroactively stamp them PASS. Real CI passes do not equal host execution, model competence, approved voice, REAPER engineering, publication or production approval.

## Enforced workflow (not a manual slogan)

- The existing repository-contract validator calls hazewave.source_truth_guard static checks on each normal CI run.
- The CI pull-request source_truth job checks out the exact PR head SHA, reads the Git tree, checks cleanliness, verifies current remote branch and Git commit object from the authenticated GitHub API, verifies historical deletion commits and active references, and denies unapproved reintroductions.
- The source_truth job uses read-only GitHub token permissions (contents and pull requests), no secrets in logs, no persistent service, no code write, no restore and no production deployment.
- Python negative tests verify stale head/tree, dirty WIP, missing live reference, resurrection of retired ADR, mismatched digest/ref/SHA/tree, and forged or stale restoration approval. A synthetic reviewed exception test demonstrates contract behavior, not a real owner approval.
- New externally supplied receipts are not automatically trusted. Pass the exact candidate ref/SHA/tree and separately obtained digest to verify_bound_receipt; do not classify historic receipts as current without full provenance.

CI code living only on an unmerged candidate cannot enforce branch protection globally: repository administrators must require this check on protected refs as part of separately approved canonical adoption. A PR that removes the guard or bypasses its job must not be considered promotable. Do not silently infer branch protection from green candidate tests.

## Mandatory handoff / incident fields

SOURCE_OF_TRUTH = VERIFIED | BLOCKED | LOCAL_CONTRACTS_ONLY
AUTHORIZED_REF = current verified mission ref or BLOCKED
REMOTE_HEAD = exact 40-byte Git commit ID or UNKNOWN
REVIEWED_TREE = exact Git tree ID or UNKNOWN
RUNTIME_REVISION = exact separate runtime ID or NOT_APPLICABLE/UNKNOWN
WIP_PRESERVED = PASS_CLEAN_NO_MUTATION | BLOCKED
PROTECTED_DELETION_CHECK = PASS | FAIL | NOT_RUN
STALE_ACTIVE_REFERENCE_CHECK = PASS | FAIL | NOT_RUN
CI_PROVENANCE = PASS | FAIL | NOT_RUN
REVIEW_OR_APPROVAL = verified external review or PENDING / NOT_REQUIRED
DURABLE_CHECKPOINT = immutable commit and reviewed branch or NOT_CREATED

### Concrete invocation

Static contracts: python scripts/validate_repository_contracts.py
Read-only checkout preflight on a GitHub PR: PYTHONPATH=src python -m hazewave.source_truth_guard --github-pr
Offline static check without remote assurance: PYTHONPATH=src python -m hazewave.source_truth_guard --local

These checks do not execute HAZE/WAVE models, change Termux, restart Colibri/Reflex, access owner media or authorize publication.
