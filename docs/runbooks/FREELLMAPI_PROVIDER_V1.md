# FreeLLMAPI Provider Runtime v1

## Scope

This runbook installs and operates the Hazewave-scoped FreeLLMAPI provider gateway on Termux.

FreeLLMAPI is a subordinate inference gateway only. Hazewave Harness remains the sole project-local routing and authorization authority.

## Accepted upstream

- release: `v0.13.4`
- exact commit: `716948f20b12ec1c9b7c6fcebd22a3e7233cda1b`
- license: MIT
- upstream mode: personal experimentation / learning

Do not replace the exact commit with `main` or `latest`.

## Requirements

The upstream Termux path requires Android 7+ and Node.js 22.13 or newer. Node 24 LTS is preferred upstream.

Install prerequisites in Termux:

```bash
pkg update
pkg install -y nodejs-lts git
node --version
```

## Install the pinned provider runtime

From the active Hazewave immutable release:

```bash
bash scripts/install_hazewave_freellmapi_termux.sh
```

Expected:

```text
HAZEWAVE_FREELLMAPI_INSTALL=PASS
HAZEWAVE_FREELLMAPI_SHA=716948f20b12ec1c9b7c6fcebd22a3e7233cda1b
```

The installer creates only project-local provider namespaces:

```text
~/.local/share/hazewave/providers/freellmapi/
~/.local/state/hazewave/providers/freellmapi/
~/.config/hazewave/providers/freellmapi/
```

The encryption key is generated locally with owner-only permissions and is never committed.

## Start and inspect

```bash
bash scripts/hazewave_freellmapi_control.sh start
bash scripts/hazewave_freellmapi_control.sh status
bash scripts/hazewave_freellmapi_control.sh doctor
```

Expected security assertions include:

```text
HAZEWAVE_FREELLMAPI_LOOPBACK_ONLY=PASS
HAZEWAVE_FREELLMAPI_UPDATE_CHECK=OFF
HAZEWAVE_FREELLMAPI_AUTHORITY=NONE
HAZEWAVE_FREELLMAPI_PROJECT_AUTHORITY=HAZEWAVE_HARNESS
HAZEWAVE_FREELLMAPI_PRIVATE_MEDIA_EGRESS=FORBIDDEN
```

The API endpoint is:

`http://127.0.0.1:3001/v1`

Do not expose the gateway directly to the public internet.

## First-run provider configuration

Open the FreeLLMAPI dashboard locally and create/configure the local account and upstream provider keys there.

Provider keys belong to FreeLLMAPI's encrypted local store. Do not place raw provider keys in:

- the Hazewave repository;
- Telegram messages;
- Hazewave logs;
- shell history where avoidable.

After FreeLLMAPI generates its unified API key, store only that local router key in:

```text
~/.config/hazewave/providers/freellmapi/unified-api-key
```

Then:

```bash
chmod 600 ~/.config/hazewave/providers/freellmapi/unified-api-key
```

Do not paste that credential into chat.

## Hazewave client boundary

`hazewave.freellmapi.FreeLLMAPIClient` requires:

- a Hazewave Harness authorization bound to the same task;
- the exact Hazewave capability ID;
- an allowed data classification;
- a loopback endpoint by default.

Initial outbound data policy:

```text
PUBLIC              ALLOW
INTERNAL_NON_SECRET DENY
PRIVATE_MEDIA       DENY
CREDENTIAL          DENY
```

The gateway does not gain domain-routing, promotion, publication or canonical-write authority.

## Stop / restart / logs

```bash
bash scripts/hazewave_freellmapi_control.sh stop
bash scripts/hazewave_freellmapi_control.sh restart
bash scripts/hazewave_freellmapi_control.sh logs 100
```

## Upgrade policy

Do not run `git pull` inside the active provider release.

To upgrade:

1. review the upstream release and security notes;
2. update the exact commit pin in Hazewave code, installer, tests and this runbook;
3. run Hazewave repository validation;
4. install the new SHA as a new provider release;
5. verify `doctor`;
6. switch only after validation.

## Failure policy

If the gateway is unavailable, Hazewave must report provider unavailability. It must not bypass Harness authorization or silently send private data to another endpoint.

If FreeLLMAPI, an upstream model provider, or a free-tier route changes terms or reliability materially, stop treating that route as eligible until reviewed.


## Live Harness-to-provider proof

After the unified API key is stored at:

`~/.config/hazewave/providers/freellmapi/unified-api-key`

run one bounded real provider call through the Hazewave client:

```bash
PYTHONPATH="$HOME/.local/share/hazewave/deploy/current/src" \
python -m hazewave.cli freellmapi probe
```

Expected:

```text
HAZEWAVE_FREELLMAPI_LIVE_PROBE=PASS
```

The JSON receipt contains the Hazewave task and authorization binding, selected HAZE capability, data classification, FreeLLMAPI route/model evidence, response-content digest and token usage. It does not contain the unified API key or raw upstream provider keys.

The proof prompt is synthetic, non-user text and is classified `PUBLIC`; it does not upload internal project context, private audio/media, or credentials.

The first observed keyless route in the A15 proof was Kilo. FreeLLMAPI's upstream provider documentation states that Kilo's anonymous free route logs prompts/outputs for training. For that reason Hazewave keeps generic FreeLLMAPI routing public-only until a provider/model eligibility policy has been reviewed and enforced.

## Persistence

Install a project-local singleton supervisor and Termux:Boot entry:

```bash
bash scripts/install_hazewave_freellmapi_persistence.sh
```

The supervisor checks the exact FreeLLMAPI process every 30 seconds and restarts it through the Hazewave control boundary when unavailable. The process is launched directly as:

`node server/dist/index.js`

rather than through an npm wrapper, so the recorded PID can be bound to the actual provider server process.

Expected:

```text
HAZEWAVE_FREELLMAPI_PERSISTENCE=PASS
```

Runtime persistence after a real Android reboot remains a runtime-evidence requirement; installation of the boot entry alone is not proof that Android executed it.
