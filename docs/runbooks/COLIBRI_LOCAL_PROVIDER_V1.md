# Colibri Local Provider V1 Runbook

This runbook installs and proves the decision-only Colibri lane. It does not authorize chat models, giant MoE models, paid infrastructure, external binds or automatic model downloads.

## 1. Admission before download

Inspect the machine with the Hazewave adapter and compare it to config/colibri-local-provider-v1.json. The Laya plan must preserve the configured system RAM and disk reserves. If the plan does not fit, stop. Do not resize a GitHub Codespace merely to force a PASS.

## 2. Pin the Colibri source

Use a project-local provider directory outside the repository.

    export COLIBRI_ROOT="$HOME/.local/share/hazewave/providers/colibri"
    mkdir -p "$COLIBRI_ROOT"
    git clone https://github.com/JustVugg/colibri.git "$COLIBRI_ROOT/source"
    git -C "$COLIBRI_ROOT/source" checkout --detach bf2442915d6e3dd4cdfd2eb9c2a3d2aa44a25850
    test "$(git -C "$COLIBRI_ROOT/source" rev-parse HEAD)" = "bf2442915d6e3dd4cdfd2eb9c2a3d2aa44a25850"

Do not run the upstream one-step installer with --yes from an autonomous Hazewave process. V1 forbids autonomous model selection/download.

## 3. Build only the decision engine

    make -C "$COLIBRI_ROOT/source/c" laya

A compiler/build PASS is only compatibility evidence.

## 4. Download the pinned Laya checkpoint explicitly

The model cache must remain outside the Git checkout.

    export COLIBRI_MODEL="$HOME/.local/share/hazewave/models/colibri/laya"
    mkdir -p "$COLIBRI_MODEL"

    hf download convaiinnovations/laya       --revision 7b928d828b7b0e022f929d9bd2e44165aa270148       model.safetensors rl_agent_config.json       "encoder/*" "tokenizer/*"       --local-dir "$COLIBRI_MODEL"

    printf '%s  %s\n'       891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c       "$COLIBRI_MODEL/model.safetensors" | sha256sum -c -

Do not substitute main for the pinned revision.

## 5. Start loopback-only with authentication

Generate the secret locally and do not commit it.

    export COLI_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    cd "$COLIBRI_ROOT/source"
    COLI_MODEL="$COLIBRI_MODEL" COLI_API_KEY="$COLI_API_KEY"       ./c/coli serve --host 127.0.0.1 --port 28080 --model-id laya

Do not bind 0.0.0.0, a LAN address or a public interface.

## 6. Runtime proof

In another terminal:

    curl --fail --silent       -H "Authorization: Bearer $COLI_API_KEY"       http://127.0.0.1:28080/health

The response must include status=ok.

Then exercise a bounded English machine-state decision:

    curl --fail --silent http://127.0.0.1:28080/v1/systemone       -H "Authorization: Bearer $COLI_API_KEY"       -H 'Content-Type: application/json'       -d '{"model":"laya","state":{"asset_kind":"audio","operation":"mix"},"questions":{"route":{"type":"choice","instructions":"Which Hazewave domain owns this task?","criteria":{"HAZE":"audio work","WAVE":"visual work","BRIDGE":"typed translation between audio and visual domains"}}}}'

This is a provider proof, not permission to let Laya decide policy by itself.

## 7. Hazewave adapter contract

Production code calls execute_colibri_system_one only after a Harness authorization for decision.route, decision.gate or decision.score.

The adapter independently requires a pinned loopback URL, allowed data class, allowlisted model, supported state language, installed/verified model evidence, RAM and disk reserve, authenticated health, a Colibri System One response, and usage.cost=0.

require_confident_choice defaults to the policy threshold of 0.80. A low-confidence answer fails closed.

## 8. PT-BR boundary

Do not send raw PT-BR Telegram text to the current Laya engine and call the result qualified. Colibri v2.0.0's Laya engine supports the English root checkpoint; its multilingual Laya checkpoint is not supported yet.

Until a multilingual runtime is proven, use deterministic routing from media/type metadata or a separately authorized normalization step that produces bounded English machine state.

## 9. Stop conditions

Stop and report instead of bypassing when hardware cannot preserve Hazewave resource reserve, source/model hashes differ, the listener is not loopback-only, authentication is absent, a model is not allowlisted, a request contains credentials, a decision needs direct PT-BR understanding, confidence is below threshold, Colibri would become security/promotion/publication authority, or installation would consume paid Codespaces capacity outside the owner's zero-cost policy.

## 10. Promotion states

KNOWN -> COMPATIBLE -> RUNTIME_PROVEN -> PRODUCTION_APPROVED

CI can establish only repository compatibility. Real workstation evidence is required for RUNTIME_PROVEN.
