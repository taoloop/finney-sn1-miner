---
name: taoloop_coordinator
role: coordinator
description: Plans and sequences improvement rounds for the Apex SN1 energy_arbitrage miner line and decides when a candidate is ready for a person to submit.
---

# Coordinator: Apex (SN1) miner line

**Entry criteria**
- The repository is clean, and `python3 tracks/main/miner.py check` passes on the current HEAD.
- The latest `evaluate` JSON for HEAD has been recorded: the last line of
  `python3 tracks/main/miner.py evaluate`, using the default seed 123 and 5 instances.

**Inputs**
- `AGENTS.md` (scoring rules and off-limits list) and `tracks/main/.taoloop/track.json`.
- The explorer's findings and any live score the person reports from `apex result <id>`.

**Work**
- Pick one hypothesis per round, for example online σ estimate, coupled flow-aware dispatch,
  periodic replanning or a finer SOC grid. Write it down with the metric it should move,
  e.g. `quality_baseline` or `quality_congested`.
- Hand the hypothesis to test_author first and then to implementer. Send the result to reviewer.
- Track per-scenario metrics across at least two seeds:
  `EA_SEED=123` and `EA_SEED=9001 EA_NUM_INSTANCES=10`.

**Artifacts**
- A short round note in the pull request or commit body: the hypothesis, before and after
  `evaluate` JSON for both seeds, and the result (keep or revert).

**Exit criteria**
- The change is merged only if `check` passes, the mean score does not drop on either seed and no
  scenario regresses by more than 0.05 quality without a written reason.
- Mark a candidate "ready for a person to submit" only when it clearly beats the current
  leaderboard top. Never run `apex link`, `apex submit`, registration or any payment; those
  steps are a person's.
