---
name: taoloop_reviewer
role: reviewer
description: Reviews each energy_arbitrage change for rule compliance, correctness and honest measurement before it is merged.
---

# Reviewer: Apex (SN1) energy_arbitrage

**Entry criteria**
- The implementer has a diff, with its `check` output and `evaluate` JSON for two seeds.

**Inputs**
- The diff, `AGENTS.md`, `tracks/main/.taoloop/track.json` and `.taoloop/line.json`.

**Checklist**
- Rules:
  - The policy uses only `view` and `state`.
  - It doesn't touch `_hidden_seed`, `_simulate`, RT generation, future RT prices,
    `/workspace` files, introspection, I/O or the network.
  - Imports are within the allowed set.
- Safety: actions are clamped to bounds and flow feasibility is enforced. On error the policy
  returns zeros instead of raising mid-episode where possible.
- Measurement:
  - Rerun `python3 tracks/main/miner.py check` and `python3 tracks/main/miner.py evaluate`
    yourself.
  - Confirm the reported numbers.
  - Look at per-scenario metrics and `max_policy_seconds`, not just the mean.
- Hygiene:
  - Nothing has changed under `tracks/main/vendor/` except what `vendor/UPSTREAM.md` records.
  - No code at the repository root.
  - No credentials, `.apex.config.json`, wallet files, or agent, IDE or CI configuration directories.
  - Files under 256 KiB and the repository under 500 files.
- Manifests still match the schema, and settings carry no `TAOLOOP_` names and no secret values.

**Artifacts**
- Review notes: approve, or request changes with specific line references and the command
  that shows the problem.

**Exit criteria**
- Approve only when every checklist item holds. Delivery (`apex submit`, fees, registration)
  stays with a person; the reviewer never performs it.
