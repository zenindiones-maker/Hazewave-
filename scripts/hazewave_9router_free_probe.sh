#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

MODE="${1:-catalog}"
ROOT="${HAZEWAVE_9ROUTER_ROOT:-$HOME/.local/share/hazewave/providers/9router}"
CURRENT="$ROOT/current"
STATE_ROOT="${HAZEWAVE_9ROUTER_STATE_ROOT:-$HOME/.local/state/hazewave/providers/9router}"
RUNTIME_HOME="$STATE_ROOT/home"
RECEIPT="$STATE_ROOT/free-admission.json"
CONTROL="${HAZEWAVE_RUNTIME_CURRENT:-$HOME/.local/share/hazewave/deploy/current}/scripts/hazewave_9router_control.sh"

case "$MODE" in
  catalog|probe) ;;
  *)
    echo "usage: $0 {catalog|probe}" >&2
    exit 2
    ;;
esac

test -L "$CURRENT" || {
  echo "HAZEWAVE_9ROUTER_FREE_PROBE=FAIL:not_installed" >&2
  exit 2
}

test -f "$CONTROL" || {
  echo "HAZEWAVE_9ROUTER_FREE_PROBE=FAIL:control_not_found" >&2
  exit 2
}

# Fail closed unless the exact managed loopback sidecar is healthy.
bash "$CONTROL" doctor >/dev/null

RELEASE="$(readlink -f "$CURRENT")"
test -f "$RELEASE/UPSTREAM_COMMIT"
UPSTREAM_COMMIT="$(cat "$RELEASE/UPSTREAM_COMMIT")"

mkdir -p "$STATE_ROOT"
chmod 700 "$STATE_ROOT"

HOME="$RUNTIME_HOME" \
HAZEWAVE_9ROUTER_MODE="$MODE" \
HAZEWAVE_9ROUTER_RELEASE="$RELEASE" \
HAZEWAVE_9ROUTER_STATE_ROOT="$STATE_ROOT" \
HAZEWAVE_9ROUTER_RECEIPT="$RECEIPT" \
HAZEWAVE_9ROUTER_UPSTREAM_COMMIT="$UPSTREAM_COMMIT" \
node <<'NODE'
const fs = require("fs");
const crypto = require("crypto");

const mode = process.env.HAZEWAVE_9ROUTER_MODE;
const release = process.env.HAZEWAVE_9ROUTER_RELEASE;
const stateRoot = process.env.HAZEWAVE_9ROUTER_STATE_ROOT;
const receiptPath = process.env.HAZEWAVE_9ROUTER_RECEIPT;
const upstreamCommit = process.env.HAZEWAVE_9ROUTER_UPSTREAM_COMMIT;

const cliClientPath = release + "/node_modules/9router/src/cli/api/client.js";
const api = require(cliClientPath);

const CATALOG_URL = "https://opencode.ai/zen/v1/models";
const LOCAL_BASE = "http://127.0.0.1:20128";
const DEAD_FREE = new Set(["deepseek-v4-flash-free"]);
const KNOWN_FREE = new Set(["big-pickle"]);
const PREFERRED_PROBE_MODELS = [
  "mimo-v2.6-flash-free",
  "nemotron-3.5-lightning-free",
  "muse-spark-1.3-contributor-free",
  "mimo-v2.5-free",
  "big-pickle",
];

function isFreeModel(id) {
  return (
    typeof id === "string" &&
    !DEAD_FREE.has(id) &&
    (id.endsWith("-free") || KNOWN_FREE.has(id))
  );
}

async function fetchFreeCatalog() {
  const response = await fetch(CATALOG_URL, {
    headers: {
      "x-opencode-client": "desktop",
      "User-Agent": "opencode/1.18.31",
    },
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) {
    throw new Error(`catalog_http_${response.status}`);
  }
  const body = await response.json();
  const rows = Array.isArray(body) ? body : (body.data || body.models || []);
  const models = [...new Set(
    rows
      .map((row) => String(row?.id || ""))
      .filter(isFreeModel)
  )].sort();
  if (!models.length) {
    throw new Error("catalog_has_no_free_models");
  }
  return models;
}

function capacityAdaptersDisabled(original) {
  const source = original && typeof original === "object" ? original : {};
  const out = {};
  for (const [key, value] of Object.entries(source)) {
    out[key] = {
      ...(value && typeof value === "object" ? value : {}),
      enabled: false,
      models: [],
    };
  }
  return out;
}

function catalogHash(models) {
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(models))
    .digest("hex");
}

async function main() {
  const freeModels = await fetchFreeCatalog();
  const qualified = freeModels.map((id) => `oc/${id}`);

  console.log("OPENCODE_FREE_CATALOG=PASS");
  console.log(`OPENCODE_FREE_MODEL_COUNT=${qualified.length}`);
  for (const id of qualified) console.log(`MODEL=${id}`);

  if (mode === "catalog") return;

  const settingsResult = await api.getSettings();
  if (!settingsResult.success) {
    throw new Error(`settings_read_failed:${settingsResult.error || "unknown"}`);
  }
  const original = settingsResult.data || {};

  // API-key bypass is allowed only for a non-exposed local sidecar.
  if (
    original.cloudEnabled === true ||
    original.tunnelEnabled === true ||
    original.tailscaleEnabled === true
  ) {
    throw new Error("external_exposure_enabled");
  }

  const selected =
    PREFERRED_PROBE_MODELS.find((id) => freeModels.includes(id)) ||
    freeModels[0];

  if (!isFreeModel(selected)) {
    throw new Error("selected_model_not_free");
  }

  const originalRequireApiKey = original.requireApiKey;
  const originalCapacityAdapter = original.capacityAdapter;
  const originalOutboundProxyEnabled = original.outboundProxyEnabled;

  const safeCapacityAdapter = capacityAdaptersDisabled(originalCapacityAdapter);

  let restoreError = null;
  let probeSucceeded = false;
  let responseFingerprint = null;

  try {
    const patched = await api.updateSettings({
      requireApiKey: false,
      capacityAdapter: safeCapacityAdapter,
      outboundProxyEnabled: false,
    });
    if (!patched.success) {
      throw new Error(`settings_patch_failed:${patched.error || "unknown"}`);
    }

    const body = {
      model: `oc/${selected}`,
      messages: [
        {
          role: "user",
          content: "Reply with exactly HAZEWAVE_OK",
        },
      ],
      max_tokens: 12,
      temperature: 0,
      stream: false,
    };

    const response = await fetch(`${LOCAL_BASE}/v1/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Hazewave/9router-free-probe",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60000),
    });

    const responseText = await response.text();
    if (!response.ok) {
      throw new Error(
        `probe_http_${response.status}:${responseText.slice(0, 240)}`
      );
    }

    let payload;
    try {
      payload = JSON.parse(responseText);
    } catch {
      throw new Error("probe_response_not_json");
    }

    const content =
      payload?.choices?.[0]?.message?.content ??
      payload?.choices?.[0]?.text ??
      payload?.output_text ??
      "";

    if (typeof content !== "string" || !content.trim()) {
      throw new Error("probe_empty_response");
    }
    if (!content.includes("HAZEWAVE_OK")) {
      throw new Error("probe_semantic_mismatch");
    }

    responseFingerprint = crypto
      .createHash("sha256")
      .update(content)
      .digest("hex");

    probeSucceeded = true;
  } finally {
    const restored = await api.updateSettings({
      requireApiKey: originalRequireApiKey,
      capacityAdapter: originalCapacityAdapter,
      outboundProxyEnabled: originalOutboundProxyEnabled,
    }).catch((error) => ({
      success: false,
      error: error?.message || String(error),
    }));

    if (!restored?.success) {
      restoreError = restored?.error || "unknown";
    }
  }

  if (restoreError) {
    throw new Error(`settings_restore_failed:${restoreError}`);
  }
  if (!probeSucceeded) {
    throw new Error("probe_did_not_complete");
  }

  const receipt = {
    schema: "Hazewave9RouterFreeAdmissionReceipt/v1",
    project_id: "HAZEWAVE",
    authority: "HAZEWAVE_HARNESS",
    gateway: "9router",
    gateway_authority: "NONE",
    upstream_repository: "decolua/9router",
    upstream_commit: upstreamCommit,
    endpoint: LOCAL_BASE,
    provider: "opencode",
    provider_alias: "oc",
    provider_policy: {
      has_free: true,
      no_auth: true,
      paid_fallback: "FORBIDDEN",
      unknown_cost: "DENY",
      catalog_rule: "id.endswith(-free) OR id==big-pickle",
      denylist: [...DEAD_FREE].sort(),
    },
    catalog_source: CATALOG_URL,
    catalog_sha256: catalogHash(qualified),
    catalog_discovered_models: qualified,
    execution_admitted_models: [`oc/${selected}`],
    probe: {
      model: `oc/${selected}`,
      max_tokens: 12,
      semantic_expected: "HAZEWAVE_OK",
      response_sha256: responseFingerprint,
      status: "PASS",
    },
    observed_at: new Date().toISOString(),
  };

  const tmp = receiptPath + ".tmp." + process.pid;
  fs.writeFileSync(tmp, JSON.stringify(receipt, null, 2) + "\n", {
    mode: 0o600,
  });
  fs.renameSync(tmp, receiptPath);
  fs.chmodSync(receiptPath, 0o600);

  console.log(`HAZEWAVE_9ROUTER_FREE_MODEL=${receipt.probe.model}`);
  console.log(`HAZEWAVE_9ROUTER_FREE_ADMISSION_RECEIPT=${receiptPath}`);
  console.log("HAZEWAVE_9ROUTER_PAID_FALLBACK=FORBIDDEN");
  console.log("HAZEWAVE_9ROUTER_UNKNOWN_COST=DENY");
  console.log("HAZEWAVE_9ROUTER_FREE_PROBE=PASS");
}

main().catch((error) => {
  console.error(
    "HAZEWAVE_9ROUTER_FREE_PROBE=FAIL:" +
      (error?.message || String(error))
  );
  process.exit(1);
});
NODE
