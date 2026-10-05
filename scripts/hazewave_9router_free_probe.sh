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
  catalog|probe|optimize) ;;
  *)
    echo "usage: $0 {catalog|probe|optimize}" >&2
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

bash "$CONTROL" doctor >/dev/null

AUTH_STATE="$(bash "$CONTROL" ensure-auth)"
printf '%s\n' "$AUTH_STATE"
if printf '%s\n' "$AUTH_STATE" | grep -qx 'HAZEWAVE_9ROUTER_CLI_AUTH_CREATED=1'; then
  echo "HAZEWAVE_9ROUTER_CLI_AUTH_RESTART=REQUIRED"
  bash "$CONTROL" restart >/dev/null
  bash "$CONTROL" doctor >/dev/null
fi

RELEASE="$(readlink -f "$CURRENT")"
UPSTREAM_COMMIT="$(cat "$RELEASE/UPSTREAM_COMMIT")"
mkdir -p "$STATE_ROOT"
chmod 700 "$STATE_ROOT"

HOME="$RUNTIME_HOME" \
DATA_DIR="$RUNTIME_HOME/.9router" \
HAZEWAVE_9ROUTER_MODE="$MODE" \
HAZEWAVE_9ROUTER_RELEASE="$RELEASE" \
HAZEWAVE_9ROUTER_RECEIPT="$RECEIPT" \
HAZEWAVE_9ROUTER_UPSTREAM_COMMIT="$UPSTREAM_COMMIT" \
node <<'NODE'
const fs = require("fs");
const crypto = require("crypto");

const mode = process.env.HAZEWAVE_9ROUTER_MODE;
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
const OPTIMIZE_MAX_MODELS = 16;

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
  if (!response.ok) throw new Error(`catalog_http_${response.status}`);
  const body = await response.json();
  const rows = Array.isArray(body) ? body : (body.data || body.models || []);
  const models = [...new Set(
    rows.map((row) => String(row?.id || "")).filter(isFreeModel)
  )].sort();
  if (!models.length) throw new Error("catalog_has_no_free_models");
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
  const response = await fetch(LOCAL_BASE + "/api/settings", {
    method,
    headers: {
      "Content-Type": "application/json",
      "x-9r-cli-token": readCliToken(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  const text = await response.text();
  let payload = {};
  try { payload = text ? JSON.parse(text) : {}; } catch {}
  if (!response.ok) {
    throw new Error(
      `settings_${method.toLowerCase()}_http_${response.status}:${payload.error || text.slice(0, 160)}`
    );
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
  return crypto.createHash("sha256").update(JSON.stringify(models)).digest("hex");
}

function normalizeUsage(payload) {
  const usage = payload?.usage && typeof payload.usage === "object" ? payload.usage : {};
  return {
    prompt_tokens: Number.isInteger(usage.prompt_tokens) ? usage.prompt_tokens : null,
    completion_tokens: Number.isInteger(usage.completion_tokens) ? usage.completion_tokens : null,
    total_tokens: Number.isInteger(usage.total_tokens) ? usage.total_tokens : null,
  };
}

async function runSemanticProbe(qualifiedModel) {
  const started = Date.now();
  const body = {
    model: qualifiedModel,
    messages: [{ role: "user", content: "Reply with exactly HAZEWAVE_OK" }],
    max_tokens: mode === "optimize" ? 256 : 128,
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
        "User-Agent": "Hazewave/9router-free-optimizer",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(90000),
    });
    responseText = await response.text();
  } catch {
    return {
      status: "transport_error",
      latency_ms: Date.now() - started,
      usage: { prompt_tokens: null, completion_tokens: null, total_tokens: null },
    };
  }

  const latencyMs = Date.now() - started;
  if (!response.ok) {
    return {
      status: `http_${response.status}`,
      latency_ms: latencyMs,
      usage: { prompt_tokens: null, completion_tokens: null, total_tokens: null },
    };
  }

  let payload;
  try { payload = JSON.parse(responseText); }
  catch {
    return {
      status: "invalid_json",
      latency_ms: latencyMs,
      usage: { prompt_tokens: null, completion_tokens: null, total_tokens: null },
    };
  }

  const firstChoice = payload?.choices?.[0] || {};
  const message = firstChoice?.message || {};
  const content =
    message?.content ?? firstChoice?.text ?? payload?.output_text ?? "";
  const reasoning =
    message?.reasoning ??
    message?.reasoning_content ??
    message?.thinking ??
    message?.thinking_content ??
    "";
  const finishReason = firstChoice?.finish_reason ?? null;
  const usage = normalizeUsage(payload);

  if (
    finishReason === "length" &&
    !String(content || "").trim() &&
    String(reasoning || "").trim()
  ) {
    return {
      status: "reasoning_only_length",
      latency_ms: latencyMs,
      usage,
      reasoning_observed: true,
    };
  }
  if (!String(content || "").trim()) {
    return { status: "empty_content", latency_ms: latencyMs, usage };
  }
  if (!String(content).includes("HAZEWAVE_OK")) {
    return { status: "semantic_mismatch", latency_ms: latencyMs, usage };
  }

  return {
    status: "semantic_pass",
    latency_ms: latencyMs,
    usage,
    reasoning_observed: Boolean(String(reasoning || "").trim()),
    response_sha256: crypto
      .createHash("sha256")
      .update(String(content))
      .digest("hex"),
  };
}

function rankAdmitted(modelProofs) {
  return Object.entries(modelProofs)
    .filter(([, proof]) => proof?.status === "semantic_pass")
    .sort(([modelA, a], [modelB, b]) => {
      const ta = Number.isInteger(a?.usage?.total_tokens) ? a.usage.total_tokens : 1e12;
      const tb = Number.isInteger(b?.usage?.total_tokens) ? b.usage.total_tokens : 1e12;
      if (ta !== tb) return ta - tb;
      const la = Number.isFinite(a?.latency_ms) ? a.latency_ms : 1e12;
      const lb = Number.isFinite(b?.latency_ms) ? b.latency_ms : 1e12;
      if (la !== lb) return la - lb;
      return modelA.localeCompare(modelB);
    })
    .map(([model]) => model);
}

async function main() {
  const freeModels = await fetchFreeCatalog();
  const qualified = freeModels.map((id) => `oc/${id}`);

  console.log("OPENCODE_FREE_CATALOG=PASS");
  console.log(`OPENCODE_FREE_MODEL_COUNT=${qualified.length}`);
  for (const id of qualified) console.log(`MODEL=${id}`);
  if (mode === "catalog") return;

  const original = await settingsRequest("GET");
  if (
    original.cloudEnabled === true ||
    original.tunnelEnabled === true ||
    original.tailscaleEnabled === true
  ) {
    throw new Error("external_exposure_enabled");
  }

  const ordered = [
    ...PREFERRED_PROBE_MODELS.filter((id) => freeModels.includes(id)),
    ...freeModels.filter((id) => !PREFERRED_PROBE_MODELS.includes(id)),
  ].filter(isFreeModel);
  const candidates = mode === "optimize"
    ? ordered.slice(0, OPTIMIZE_MAX_MODELS)
    : ordered.slice(0, MAX_PROBE_ATTEMPTS);

  const originalSettings = {
    requireApiKey: original.requireApiKey,
    capacityAdapter: original.capacityAdapter,
    outboundProxyEnabled: original.outboundProxyEnabled,
    rtkEnabled: original.rtkEnabled,
    headroomEnabled: original.headroomEnabled,
  };

  let restoreError = null;
  const attempts = [];
  const modelProofs = {};
  let connectivityProved = false;

  try {
    await settingsRequest("PATCH", {
      requireApiKey: false,
      capacityAdapter: capacityAdaptersDisabled(original.capacityAdapter),
      outboundProxyEnabled: false,
      rtkEnabled: true,
      headroomEnabled: false,
    });

    for (let index = 0; index < candidates.length; index += 1) {
      const qualifiedModel = `oc/${candidates[index]}`;
      const proof = await runSemanticProbe(qualifiedModel);
      modelProofs[qualifiedModel] = proof;
      attempts.push({ model: qualifiedModel, status: proof.status });
      if (!proof.status.startsWith("http_") && proof.status !== "transport_error") {
        connectivityProved = true;
      }
      console.log(
        `HAZEWAVE_9ROUTER_FREE_ATTEMPT=${index + 1}/${candidates.length} MODEL=${qualifiedModel} RESULT=${proof.status}`
      );
      if (proof.status === "semantic_pass") {
        console.log("HAZEWAVE_9ROUTER_FREE_CONNECTIVITY=PASS");
        if (mode === "probe") break;
      }
    }
  } finally {
    try {
      await settingsRequest("PATCH", originalSettings);
    } catch (error) {
      restoreError = error?.message || String(error);
    }
  }

  if (restoreError) throw new Error(`settings_restore_failed:${restoreError}`);
  if (!connectivityProved) throw new Error("free_connectivity_not_proved");

  const admitted = rankAdmitted(modelProofs);
  if (!admitted.length) throw new Error("semantic_mismatch_all_free_candidates");
  const bestModel = admitted[0];
  const bestProof = modelProofs[bestModel];

  const receipt = {
    schema: mode === "optimize"
      ? "Hazewave9RouterFreeAdmissionReceipt/v2"
      : "Hazewave9RouterFreeAdmissionReceipt/v1",
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
    execution_admitted_models: mode === "optimize" ? admitted : [bestModel],
    ...(mode === "optimize" ? {
      model_proofs: modelProofs,
      optimization_policy: {
        stream: false,
        rtk_enabled: true,
        headroom_enabled: false,
        combos_allowed: false,
        selection: "LOWEST_TOTAL_TOKENS_THEN_LATENCY",
      },
    } : {}),
    probe: {
      model: bestModel,
      max_tokens: mode === "optimize" ? 256 : 128,
      max_attempts: candidates.length,
      attempts,
      semantic_expected: "HAZEWAVE_OK",
      response_sha256: bestProof.response_sha256,
      status: "PASS",
    },
    observed_at: new Date().toISOString(),
  };

  const tmp = receiptPath + ".tmp." + process.pid;
  fs.writeFileSync(tmp, JSON.stringify(receipt, null, 2) + "\n", { mode: 0o600 });
  fs.renameSync(tmp, receiptPath);
  fs.chmodSync(receiptPath, 0o600);

  if (mode === "optimize") {
    console.log(`HAZEWAVE_9ROUTER_OPTIMIZED_MODEL_COUNT=${admitted.length}`);
    admitted.forEach((model, index) => {
      const proof = modelProofs[model];
      console.log(
        `RANK=${index + 1} MODEL=${model} TOKENS=${proof?.usage?.total_tokens ?? "unknown"} LATENCY_MS=${proof?.latency_ms ?? "unknown"}`
      );
    });
    console.log("HAZEWAVE_9ROUTER_OPTIMIZE=PASS");
  } else {
    console.log(`HAZEWAVE_9ROUTER_FREE_MODEL=${bestModel}`);
    console.log("HAZEWAVE_9ROUTER_FREE_PROBE=PASS");
  }
  console.log(`HAZEWAVE_9ROUTER_FREE_ADMISSION_RECEIPT=${receiptPath}`);
  console.log("HAZEWAVE_9ROUTER_PAID_FALLBACK=FORBIDDEN");
  console.log("HAZEWAVE_9ROUTER_UNKNOWN_COST=DENY");
}

main().catch((error) => {
  console.error(
    `HAZEWAVE_9ROUTER_${mode === "optimize" ? "OPTIMIZE" : "FREE_PROBE"}=FAIL:${error?.message || String(error)}`
  );
  process.exit(1);
});
NODE
