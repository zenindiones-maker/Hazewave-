# Reverse Engineering Lab Runbook V1

## Purpose

Install and verify the zero-cost Hazewave reverse-engineering core in an isolated worktree on the existing Hazewave Codespace.

Do not create another Codespace. Do not switch or reset another active Hazewave worktree.

## Core installation

Run the pinned repository installer:

```bash
bash scripts/codespaces/install-reverse-engineering-foundation.sh
```

The installer manages REA, Ghidra, Rizin and an isolated Frida virtual environment. It reuses the existing qualified FFmpeg runtime and records an owner-only install receipt.

## Verification

Read-only provider verification:

```bash
bash scripts/codespaces/reverse-engineering-doctor.sh
```

Real core proof against the harmless system binary `/bin/true`:

```bash
bash scripts/codespaces/reverse-engineering-doctor.sh --deep
```

The deep proof uses the Ghidra provider and stores the REA JSON result locally as evidence. It does not establish production approval for arbitrary targets.

## Planning an investigation

Example HAZE plug-in study:

```bash
PYTHONPATH=src python -m hazewave.cli reverse-engineering plan \
  --domain HAZE \
  --target-kind audio_plugin \
  --purpose AUTHORIZED_FEATURE_STUDY \
  --authorized
```

Example WAVE shader study:

```bash
PYTHONPATH=src python -m hazewave.cli reverse-engineering plan \
  --domain WAVE \
  --target-kind visual_shader \
  --purpose AUTHORIZED_FEATURE_STUDY \
  --authorized
```

Omitting `--authorized` must fail closed.

## Evidence handling

Keep proprietary or sensitive snapshots local and owner-readable. Do not commit target binaries, decompiler output, runtime dumps or proprietary snapshots to the Hazewave repository.

Commit only Hazewave-owned implementation, fixtures that are legally redistributable, policy, tests and non-sensitive receipts/metadata appropriate for source control.
