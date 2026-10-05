# Hazewave Termux Runtime Runbook v1

## Scope

This runbook operates only the Hazewave Termux runtime. It does not define creative policy or broaden project authority.

## Layout

```text
~/.local/share/hazewave/deploy/
├── repo.git
├── releases/<exact-sha>/
└── current -> releases/<exact-sha>/

~/.local/state/hazewave/
~/.config/hazewave/
```

The development checkout is separate from the active runtime.

## Bootstrap

From an authorized Hazewave checkout:

```bash
bash scripts/install_hazewave_termux_runtime.sh
```

The installer fetches the configured ref into a machine-managed bare repository, materializes the exact SHA as an immutable release, validates required runtime contracts and switches `current`.

## Doctor

```bash
bash scripts/hazewave_termux_control.sh doctor
```

Expected invariants:
- active release exists;
- active release SHA matches the recorded SHA;
- ProjectProfile v2 exists;
- documentation registry exists;
- Hazewave Harness is importable;
- runtime reports `HAZEWAVE_RUNTIME_IMMUTABLE_RELEASE=PASS`.

## Locate runtime

```bash
bash scripts/hazewave_termux_control.sh where
```

## Synchronize

```bash
bash scripts/hazewave_termux_control.sh sync
```

The sync operation uses the installer contained in the active release and does not make the mutable development checkout the runtime source.

## Harness status

```bash
bash scripts/hazewave_termux_control.sh harness
```

## Failure handling

If doctor fails:
1. preserve runtime state and private media;
2. record the active SHA and failing invariant;
3. verify the configured remote/ref;
4. rerun the installer from an authorized Hazewave source;
5. rerun doctor;
6. treat unresolved profile/harness mismatch as a blocker.

Do not repair runtime drift by turning the development checkout into the production/runtime source.
