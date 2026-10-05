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

AUTH_STATE="$(bash "$CONTROL" ensure-auth)"
printf '%s\n' "$AUTH_STATE"

if printf '%s\n' "$AUTH_STATE" | grep -qx 'HAZEWAVE_9ROUTER_CLI_AUTH_CREATED=1'; then
  echo "HAZEWAVE_9ROUTER_CLI_AUTH_RESTART=REQUIRED"
  bash "$CONTROL" restart >/dev/null
  bash "$CONTROL" doctor >/dev/null
fi

RELEASE="$(readlink -f "$CURRENT")"
test -f "$RELEASE/UPSTREAM_COMMIT"
UPSTREAM_COMMIT="$(cat "$RELEASE/UPSTREAM_COMMIT")"

mkdir -p "$STATE_ROOT"
chmod 700 "$STATE_ROOT"

HOME="$RUNTIME_HOME" \
DATA_DIR="$RUNTIME_HOME/.9router" \
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

const DATA_DIR = process.env.DATA_DIR || (process.env.HOME + "/.9router");
const MACHINE_ID_FILE = DATA_DIR + "/machine-id";
const CLI_SECRET_FILE = DATA_DIR + "/auth/cli-secret";
const CLI_TOKEN_SALT = "9r-cli-auth";

const CATALOG_URL = "https://opencode.ai/zen/v1/models";
const LOCAL_BASE = "http://127.0.0.1:20128";
const DEAD_FREE = new Set(["deepseek-v4-flash-free"]);
const KNOWN_FREE = new Set(["big-pickle"]);
const PREFERRED_PROBE_MODELS = [
  "mimo-v2.6-flash-free",
  "nemotron-3.5-lightning-free",
  "space-bunny-free",
  "muse-spark-1.3-contributor-free",
  "mimo-v2.5-free",
  "big-pickle",
];
const MAX_PROBE_ATTEMPTS = 3;

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

function readCliToken() {
  const raw = fs.readFileSync(MACHINE_ID_FILE, "utf8").trim();
  const secret = fs.readFileSync(CLI_SECRET_FILE, "utf8").trim();
  if (!raw || !secret) throw new Error("cli_token_material_missing");
  return crypto
    .createHash("sha256")
    .update(raw + CLI_TOKEN_SALT + secret)
    .digest("hex")
    .substring(0, 16);
}

async function settingsRequest(method, body = undefined) {
  const token = readCliToken();
  const response = await fetch(LOCAL_BASE + "/api/settings", {
    method,
    headers: {
      "Content-Type": "application/json",
      "x-9r-cli-token": token,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(`settings_${method.toLowerCase()}_http_${response.status}:${payload.error || text.slice(0, 160)}`);
  }
  return payload;
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

  const original = await settingsRequest("GET");

  // API-key bypass is allowed only for a non-exposed local sidecar.
  if (
    original.cloudEnabled === true ||
    original.tunnelEnabled === true ||
    original.tailscaleEnabled === true
  ) {
    throw new Error("external_exposure_enabled");
  }

  const candidates = [
    ...PREFERRED_PROBE_MODELS.filter((id) => freeModels.includes(id)),
    ...freeModels.filter((id) => !PREFERRED_PROBE_MODELS.includes(id)),
  ].filter(isFreeModel).slice(0, MAX_PROBE_ATTEMPTS);

  if (!candidates.length) {
    throw new Error("no_free_probe_candidates");
  }

  const originalRequireApiKey = original.requireApiKey;
  const originalCapacityAdapter = original.capacityAdapter;
  const originalOutboundProxyEnabled = original.outboundProxyEnabled;

  const safeCapacityAdapter = capacityAdaptersDisabled(originalCapacityAdapter);

  let restoreError = null;
  let admittedModel = null;
  let responseFingerprint = null;
  let connectivityProved = false;
  const attempts = [];

  try {
    await settingsRequest("PATCH", {
      requireApiKey: false,
      capacityAdapter: safeCapacityAdapter,
      outboundProxyEnabled: false,
    });

    for (let index = 0; index < candidates.length; index += 1) {
      const selected = candidates[index];
      const qualifiedModel = `oc/${selected}`;
      const body = {
        model: qualifiedModel,
        messages: [
          {
            role: "user",
            content: "Reply with exactly HAZEWAVE_OK",
          },
        ],
        max_tokens: 128,
        temperature: 0,
        stream: false,
      };

      let response;
      let responseText = "";
      try {
        response = await fetch(`${LOCAL_BASE}/v1/chat/completions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Hazewave/9router-free-probe",
          },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(60000),
        });
        responseText = await response.text();
      } catch (error) {
        attempts.push({ model: qualifiedModel, status: "transport_error" });
        console.log(
          `HAZEWAVE_9ROUTER_FREE_ATTEMPT=${index + 1}/${candidates.length} MODEL=${qualifiedModel} RESULT=transport_error`
        );
        continue;
      }

      if (!response.ok) {
        attempts.push({
          model: qualifiedModel,
          status: `http_${response.status}`,
        });
        console.log(
          `HAZEWAVE_9ROUTER_FREE_ATTEMPT=${index + 1}/${candidates.length} MODEL=${qualifiedModel} RESULT=HTTP_${response.status}`
        );
        continue;
      }

      connectivityProved = true;

      let payload;
      try {
        payload = JSON.parse(responseText);
      } catch {
        attempts.push({ model: qualifiedModel, status: "invalid_json" });
        console.log(
          `HAZEWAVE_9ROUTER_FREE_ATTEMPT=${index + 1}/${candidates.length} MODEL=${qualifiedModel} RESULT=invalid_json`
        );
        continue;
      }

      const firstChoice = payload?.choices?.[0] || {};
      const message = firstChoice?.message || {};
      const content =
        message?.content ??
        firstChoice?.text ??
        payload?.output_text ??
        "";
      const reasoning =
        message?.reasoning ??
        message?.reasoning_content ??
        message?.thinking ??
        message?.thinking_content ??
        "";
      const finishReason = firstChoice?.finish_reason ?? null;

      if (
        finishReason === "length" &&
        !String(content || "").trim() &&
        String(reasoning || "").trim()
      ) {
        attempts.push({
          model: qualifiedModel,
          status: "reasoning_only_length",
        });
        console.log("HAZEWAVE_9ROUTER_FREE_CONNECTIVITY=PASS");
        console.log(
          `HAZEWAVE_9ROUTER_FREE_ATTEMPT=${index + 1}/${candidates.length} MODEL=${qualifiedModel} RESULT=reasoning_only_length`
        );
        continue;
      }

      if (!String(content || "").trim()) {
        attempts.push({ model: qualifiedModel, status: "empty_content" });
        console.log(
          `HAZEWAVE_9ROUTER_FREE_ATTEMPT=${index + 1}/${candidates.length} MODEL=${qualifiedModel} RESULT=empty_content`
        );
        continue;
      }

      if (!String(content).includes("HAZEWAVE_OK")) {
        attempts.push({ model: qualifiedModel, status: "semantic_mismatch" });
        console.log(
          `HAZEWAVE_9ROUTER_FREE_ATTEMPT=${index + 1}/${candidates.length} MODEL=${qualifiedModel} RESULT=semantic_mismatch`
        );
        continue;
      }

      responseFingerprint = crypto
        .createHash("sha256")
        .update(String(content))
        .digest("hex");
      admittedModel = qualifiedModel;
      attempts.push({ model: qualifiedModel, status: "semantic_pass" });
      console.log("HAZEWAVE_9ROUTER_FREE_CONNECTIVITY=PASS");
      console.log(
        `HAZEWAVE_9ROUTER_FREE_ATTEMPT=${index + 1}/${candidates.length} MODEL=${qualifiedModel} RESULT=semantic_pass`
      );
      break;
    }
  } finally {
    try {
      await settingsRequest("PATCH", {
        requireApiKey: originalRequireApiKey,
        capacityAdapter: originalCapacityAdapter,
        outboundProxyEnabled: originalOutboundProxyEnabled,
      });
    } catch (error) {
      restoreError = error?.message || String(error);
    }
  }

  if (restoreError) {
    throw new Error(`settings_restore_failed:${restoreError}`);
  }
  if (!connectivityProved) {
    throw new Error("free_connectivity_not_proved");
  }
  if (!admittedModel) {
    throw new Error("semantic_mismatch_all_free_candidates");
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
    execution_admitted_models: [admittedModel],
    probe: {
      model: admittedModel,
      max_tokens: 128,
      max_attempts: MAX_PROBE_ATTEMPTS,
      attempts,
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
