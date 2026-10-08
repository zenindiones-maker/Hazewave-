# Hazewave — LLaMA-Factory isolated learning candidate v1

**Authority:** HAZEWAVE_HARNESS. **Upstream:** [hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory), Apache-2.0, **v0.9.5** (tag SHA `7af909522a951e3ad9f022ea6f88b6755257eaa5`).

**Stage distinction:** exact upstream wheel acquired ≠ installed release bytes verified ≠ Python import working ≠ required dependency stack satisfied ≠ CLI runnable ≠ model downloaded ≠ authorized training ≠ approved HAZE/WAVE specialist. Only report stages backed by concrete host-specific evidence.

## What was installed and what is not

- Official [PyPI wheel](https://pypi.org/project/llamafactory/0.9.5/) `llamafactory-0.9.5-py3-none-any.whl`; SHA-256 `10776e9b259798bf65f6c5343f6298f0302e92e9cd47472abe29eef69e286c6a`.
- Disposable GitHub CI installs **only the distribution** with `--no-deps --no-index` into its own venv. This is a real installed Python package, but it does NOT establish that `llamafactory-cli` can run training or inference. The CI validates package metadata and declared console entry points, not a trained model.
- The host installer targets **only** existing `hazewave-zero-cost-4jxp45676rq6279xx`, pins worktree SHA, uses the existing Python 3.11–3.13 if present, and installs in `~/.local/share/hazewave/llamafactory/0.9.5/venv`. The official SHA-256-verified wheel is retained privately under `~/.local/share/hazewave/llamafactory/0.9.5/release/` for future integrity checks. No packages are installed into the Colibri stock Python or host-global site packages.
- Absolutely no Torch/Transformers extras, CUDA, model weights, dataset download, WebUI listening port, training process, extra Codespace, GPU upgrade or paid fallback without separately reviewed resource and data-rights admission.
- Initial policy is `config/llamafactory-training-policy-v1.json`; the Harness inventory shows `learning_candidates.llamafactory` with `NOT_VERIFIED_ON_CODESPACE` and `NOT_PROVEN`. It is not counted as an operational HAZE/WAVE inference or media-engineering provider.

Official LLaMA-Factory 0.9.5 requires a substantial PyTorch/Transformers/PEFT/TRL/datasets stack. Parameter-efficient fine-tuning still requires suitable compute, a model whose license permits the task, approved training data and evaluation with held-out tests. It is **not** a replacement for REAPER audio mixing, FFmpeg, frame-level video analysis, REA/Ghidra or Iris screenshots.

## Ordered installation in the ONLY existing Codespace

Access its real terminal through Work's authenticated browser or the user's already-approved workstation. The GitHub repository connector does **not** itself offer a Codespaces shell. The active user worktree and Colibri stock must remain untouched.

Inside the already-existing Hazewave clone, fetch the reviewed branch and create a **detached worktree** without switching the active checkout:

```bash
set -euo pipefail
cd /workspaces/Hazewave-
test "${CODESPACE_NAME:-}" = "hazewave-zero-cost-4jxp45676rq6279xx"
git fetch --no-tags origin refs/heads/work/llamafactory-isolated-harness-v1
SHA="$(git rev-parse FETCH_HEAD)"
REMOTE="$(git ls-remote origin refs/heads/work/llamafactory-isolated-harness-v1 | awk 'NR==1 {print $1}')"
test "$SHA" = "$REMOTE"
WT="$HOME/.local/share/hazewave/llamafactory-review-${SHA:0:12}"
test ! -e "$WT"
git worktree add --detach "$WT" "$SHA"
cd "$WT"
export HAZEWAVE_LLAMA_EXPECTED_SHA="$SHA"
bash scripts/codespaces/install-llamafactory-foss.sh --preflight
bash scripts/codespaces/install-llamafactory-foss.sh --install
bash scripts/codespaces/install-llamafactory-foss.sh --doctor
bash scripts/codespaces/install-llamafactory-foss.sh --runtime-doctor
```

**New runtime proof (PR #40):** `--runtime-doctor` verifies the isolated interpreter, PEP 376 installed-file hashes, SHA-256 of the **cached exact original wheel**, and every installed `llamafactory/` package payload against the release archive **before importing package code**. It then imports the actual installed `llamafactory` module with `python -I`, checks `pip check` for missing or conflicting dependencies, and invokes `llamafactory-cli version` only if dependencies are satisfied. A missing Torch stack is reported as `cli_runnable=false` (expected on this limited 2-vCPU station), not as an installation failure or a false runtime PASS.

The observed result is written as a mode-0600 local receipt under `~/.local/state/hazewave/llamafactory/runtime-receipts/`. The receipt explicitly sets `model_training_ready=false`, `harness_connected=false`, `codespace_identity_verified=false` (the subprocess cannot independently attest host ownership) and `production_approved=false`. The enclosing Codespace shell supplies independent `CODESPACE_NAME`, git SHA, resource and installation preflight checks.

An already installed wheel-only venv can acquire and verify the cached official wheel by rerunning `--install`. The installer **does not** add Torch, Transformers, weights, GUI services, daemon processes or automatic model routing. It refuses to overwrite an existing cached wheel whose SHA256 differs from the official release.

**Negative control:** GitHub CI intentionally changes `llamafactory/cli.py` inside a disposable venv and demands `RUNTIME_DIAGNOSTIC=BLOCKED`. The tool compares independently against pinned release bytes, so rewriting a mutable local RECORD cannot certify the altered module. These checks demonstrate package integrity on the measured host, not supply-chain guarantees against a compromised Python interpreter or ownership of the entire machine.

`--preflight` checks Codespace identity, owner-repo remote, clean reviewed checkout SHA, Python version, disk/RAM without changes. `--install` downloads only the exact pinned upstream wheel, verifies SHA-256 before installation and creates a private venv; `--doctor` checks actual package metadata. `--training-preflight` is a read-only, intentionally fail-closed admission check; it never starts training, installs Torch or downloads weights. A 2-vCPU Codespace without compatible GPU must remain TRAINING_BLOCKED.

**If installation cannot run physically in the Codespace, return `CODESPACE_INSTALL_NOT_PROVEN`.** GitHub CI receipts cannot be rebound to the owner's host. Keep private logs, host SHA, wheel SHA, available memory/disk and receipt paths.

## Harness evidence bridge (format only, no training)

The actual source-owned native reconstruction trial and synthetic FFmpeg HAZE/WAVE QC trials can produce private JSON receipts. The offline bridge
`python -m hazewave.learning_dataset_bridge` accepts **only**:
- `HazewaveOwnedAutomaticNativeSynthesis/v1` with successful *bounded* 2,001-input finite-domain comparison, no claim of universal equivalence;
- `HazewaveSyntheticAudioVideoFidelity/v1` with real FFmpeg volume/SSIM positive and negative controls and explicit `owner_media_analyzed=false`.

It emits a small **Alpaca-format preview** (`dataset_info.json`, `hazewave_synthetic_research_demo.json`, `preview-receipt.json`) under an owner-private directory (mode 0600 files). This is a schema fixture with three didactic examples, **not** a production SFT dataset: synthetic answers derived from own tests are not independently validated teaching data. Reusing them to train or evaluate the same model would create contamination and self-confirming results.

Run only on owned private receipts:

```bash
PYTHONPATH=src python3 -m hazewave.learning_dataset_bridge \
  --native-receipt "$HOME/.local/state/hazewave/native-owned/synthesis-receipt.json" \
  --av-receipt "$HOME/.local/state/hazewave/av-owned/av-receipt.json" \
  --output-root "$HOME/.local/state/hazewave/llamafactory-demo-$(date -u +%Y%m%dT%H%M%SZ)"
```

The example paths above must be replaced by the actual receipt names; no auto-discovery of user files. No owner voice samples, Telegram media, private artist works, unreleased assets or licensed model data may be ingested.

## Graduation into genuine HAZE/WAVE learning

1. Prove the pinned package is physically present in the existing Codespace, and separately prove compatible runtime dependencies; no global installs.
2. Identify a permitted model and task (e.g. small research-reasoning classifier of recorded evidence, **not** general music/video generation). Record source, model/license, dataset provenance and expected GPU/CPU/RAM/disk bounds.
3. Build an owner-approved, private, representative, non-leaking train/validation/test split with fixed oracle judgments, negative cases and untouched held-out material. Prevent prompts/tests used for evaluation from entering training.
4. Under resource admission and a separate owner-signed task grant, install the appropriate dependency stack and run a tiny smoke training step, **without a paid fallback**. Report actual peak RAM/VRAM, wall time, model hash and failures.
5. Compare the resulting adapter on an independent REA/HAZE/WAVE task set, test hallucinations, false PASS, license/data retention and cost. Preserve failure examples but do not self-certify quality.
6. Only then apply Harness capability-plane signed exact-host attestation and register a narrowly scoped agent route. Human approval, model use and production publishing remain separate.

## Real proof versus code readiness

The [LLaMA-Factory wheel CI](https://github.com/zenindiones-maker/Hazewave-/actions/workflows/llamafactory-harness-release.yml) proves archive SHA/installed Python distribution and (when green) synthetic data-schema conversion on an **ephemeral runner**. It is not on-host proof, model inference, audio/video expertise or agent integration.

No branch merge, BR-no-GTA changes, original Codespace replacement, stock restart, new GPU or paid services were authorized by this work.

### Proof ledger and remaining gate

- CI install/import/official-wheel-content verification: PASS on the disposable runner.
- CI tampering rejection: PASS on that same disposable runner.
- Existing Codespace `hazewave-zero-cost-4jxp45676rq6279xx`: **NOT VERIFIED** by repository API access. It requires the terminal to execute the commands above on a detached worktree at the reviewed SHA.
- CLI runtime with full PyTorch/Transformers/PEFT/TRL: **NOT READY** in this wheel-only proof.
- REA/Iris/HAZE/WAVE specialist fine-tuning: **NOT TRAINED**. The 3-row synthetic Alpaca preview is not a training set.
- Signed on-host Harness capability grant and actual agent connection: **PENDING**, without automatic promotion.

If the existing Codespace proves fewer than the required resource limits or no compatible Python interpreter, preserve the existing machine and report the precise blocker. Do **not** create another Codespace or move to a paid accelerator.

