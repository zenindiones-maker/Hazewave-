# ADR-0004 — Hazewave Telegram Runtime Isolation

- Status: Accepted for development
- Date: 2026-10-04
- Owner: Hazewave

## Context

Hazewave requires a dedicated Telegram control surface without making a mutable development checkout part of runtime state and without sharing credentials, state, or process identity with any other project.

The Telegram bot identity is `@HazewaveAgentBot`.

## Decision

Hazewave Telegram is a project-local transport runtime with the following boundaries:

- bot identity: `@HazewaveAgentBot`;
- runtime code: current immutable Hazewave release under `~/.local/share/hazewave/deploy/current`;
- configuration: `~/.config/hazewave/telegram/`;
- mutable state: `~/.local/state/hazewave/telegram/`;
- token: local credential file `bot-token`, mode 0600, never committed;
- access: one explicitly paired Telegram user at a time;
- transport: private-chat long polling;
- project authority remains `HAZEWAVE_HARNESS`;
- portfolio authority remains `NONE`.

The Telegram gateway is transport, not a new authority. It may expose project status and later submit bounded goals to Hazewave Harness, but it may not bypass Harness authorization.

The supervisor uses the stable immutable-release pointer rather than a development checkout. A new release is adopted only through the existing Hazewave runtime installer.

## Security consequences

- A token for another project is rejected if Telegram `getMe` does not resolve to `HazewaveAgentBot`.
- Tokens and paired user identifiers live outside the Git repository.
- Until pairing completes, only possession of the locally generated one-time pairing code can establish the first authorized user.
- Group chats are ignored by the gateway.
- External AI/model integration is not implied by Telegram connectivity.

## Operational consequences

The Telegram supervisor can be persistent across Termux restarts while remaining independent from active development work. Runtime revision is recorded in the Hazewave Telegram state root and must match the active immutable release SHA.
