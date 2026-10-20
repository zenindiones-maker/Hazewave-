# Reverse Engineering Lab V1 — owner-controlled operations

This runbook is subordinate to `AGENTS.md`, the project profile and the HAZE/WAVE research policy. **Development candidate only; NOT production ready** until physical Codespace evidence exists.

## Operating boundary

- Use the **existing** Hazewave Codespace. Do not create another, resize, add paid services or overwrite the active Reflex/HAZE/WAVE branches.
- REA 6.0.0 is a **side-by-side candidate**: its environment is `~/.config/hazewave/reverse-engineering-rea6.env`; launch it through `hazewave-rea6` and `hazewave-re6-cli`. The legacy global `rea` command, `reverse-engineering.env` and older wrappers must remain untouched.
- GitHub Actions proving published npm 6.0.0 is distinct from a real Codespace installation and an actual connected MCP client.
- Do not run analysis of a target without a specific authorization and actual target digest.
- Tool authority = NONE; HAZEWAVE_HARNESS alone approves scope. REA/Ghidra/Rizin/Frida are analyzers, never control-plane authorities.
- Never confuse a CI pass, an installed command, `rea doctor` success and a successful real target analysis.
- For source-available Colibri, prefer direct source profiling and `hazewave-reflex engine-re-doctor` over heavy decompilation.

## Safe installation

Perform in a dedicated isolated `git worktree` tied to the exact reviewed candidate SHA, not by switching the current Codespace checkout. Before installation, check the exact worktree HEAD and approved runner resource budget. No automatic fresh Codespaces or paid route.

```bash
bash scripts/codespaces/install-reverse-engineering-foundation.sh --preflight
```

The read-only preflight checks Linux x86_64 and at least 8 GiB disk headroom and returns `HAZEWAVE_RE_INSTALL=NOT_ATTEMPTED`.

Only after that and reviewed upstream pins:

```bash
bash scripts/codespaces/install-reverse-engineering-foundation.sh
bash scripts/codespaces/reverse-engineering-doctor.sh
bash scripts/codespaces/reverse-engineering-doctor.sh --deep
```

The installer records a local installation receipt with `runtime_ready=false`; its own PASS means **installation only**. The standard doctor must exit zero. The REA 6.0.0 `--deep` check now compiles a small **Hazewave-owned ELF fixture**, asks the explicitly selected Ghidra provider to inspect `main`, and validates the returned direct Evidence envelope against the target SHA-256 and known upstream schema. Any missing evidence, wrong provider, wrong digest, absent memory headroom or tool failure is fail-closed; retain output for inspection. A passing deep doctor establishes a bounded on-host Ghidra fixture proof, **not** agent MCP connectivity, arbitrary target authorization or production approval. No forced retry loop, no stock changes.

Install receipt and provider diagnostics remain local to `~/.local/share/hazewave/reverse-engineering`. Never copy secrets, target binaries, decompiled output or private media into Git.

## Owner/Harness authorization of each target

The old `--authorized` flag is intentionally not admitted. The caller could assert it without external verification. The plan now requires a **signed owner grant**, bound to one immutable binary hash, purpose, domain, target kind and expiry (24h maximum); it verifies the signature with OpenSSH Ed25519 signature support and a local trusted public-key allowlist.

The owner controls a private signing key outside the workstation running the analysis. The trust file is local to the analyzer at:

`~/.config/hazewave/reverse-engineering/allowed_signers`

Use owner-controlled provisioning to place **only the approved public key** as a single allowed-signers entry:

```text
hazewave-owner ssh-ed25519 AAAA... owner-key-comment
```

File mode 0600; do not include the signing private key in the Codespace, any plugin, Git, environment files, prompts, or receipts. A privileged actor who can change the trusted signers file could substitute trust; the gate protects against ordinary untrusted task inputs, not a compromised owner account. For stronger adversarial isolation, provision/pin the signer through a separate trusted control plane.

Example payload (filled and signed by owner/Harness; never auto-generated as a fake approval):

```json
{
  "schema": "HazewaveReverseEngineeringTargetGrant/v1",
  "authority": "HAZEWAVE_HARNESS",
  "issuer": "hazewave-owner",
  "grant_id": "authorized-research-20261008-001",
  "domain": "HAZE",
  "target_kind": "audio_plugin",
  "purpose": "AUTHORIZED_FEATURE_STUDY",
  "target_sha256": "64_lowercase_hex_digest_of_exact_authorized_target_file",
  "issued_at": "2026-10-08T12:00:00+00:00",
  "expires_at": "2026-10-08T12:30:00+00:00"
}
```

The target digest above is a placeholder, not a valid grant. Compute the digest over the actual target file and sign the **unchanged JSON bytes** on the owner-controlled machine:

```bash
ssh-keygen -Y sign -f /path/to/owner-private-ed25519 -n hazewave-research-grant /path/to/approved-grant.json
```

Move only `approved-grant.json`, `approved-grant.json.sig` and the explicitly authorized target to the work environment. They must be regular files, owner-owned, mode 0600 for both grant and signature. Do not symlink the target or trust files.

```bash
hazewave-re6-cli plan \
  --domain HAZE \
  --target-kind audio_plugin \
  --purpose AUTHORIZED_FEATURE_STUDY \
  --target-file /absolute/path/to/authorized-target \
  --grant-file /absolute/path/to/approved-grant.json \
  --signature-file /absolute/path/to/approved-grant.json.sig
```

A resulting `authorized_target=true` means the signature, target hash, scope and validity window were checked. It does **not** grant reverse-engineering tool execution, API credentials, installation rights, model promotion, production approval or permission to redistribute the original artifact.

## Operational research practice

1. Log target identity, license, provenance, intended observation and consent basis.
2. Inspect source and format metadata before choosing static or dynamic tooling.
3. Use REA with **explicit Ghidra provider**; no Hopper fallback. Verify actual provider health and preserve limitations, not just tool presence.
4. Work with isolated resource budgets and owner-controlled datasets. Never attach arbitrary processes or ingest secrets.
5. Record reproducible findings, confidence level, source evidence, limitations and target digest. Never call pseudocode the original source.
6. Recreate behavior independently in Hazewave-owned code and test correctness before benchmarking speed. Avoid DRM bypass or unauthorized access.
7. Preserve all failed runs and no-op results as evidence; no automatic merge/promotion.

## Runtime proof gate

Until the doctor and deep analysis complete **in the existing Codespace**, report `RE_RUNTIME_PROVEN=false`. Do not represent successful GitHub Actions or an installer receipt as proof of workstation readiness.

The independent [Reflex Binary Research runbook](REFLEX_BINARY_RESEARCH_V1.md) is in another candidate branch and must not be assumed to be checked out by this worktree.
