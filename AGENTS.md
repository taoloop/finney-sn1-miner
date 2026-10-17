# Apex (Bittensor subnet 1, finney): shared miner line

This file is for any coding agent or IDE working in this repository. Read it whole before
changing anything.

## What a miner is here

Apex (netuid 1, built by Macrocosmos) runs **coding competitions**. A miner does not serve
traffic. It writes a solution file, and the person approves its submission with the Apex CLI
(`apex submit <file> -c <competition_id>`). The upload is signed with the miner hotkey
(Epistula) and needs an on-chain fee. The Macrocosmos orchestrator
(`apex.api.macrocosmos.ai`) scores each submission in an isolated sandbox. Validators fetch
per-uid scores from it and call `set_weights` every 1260 s. Rewards are **winner-takes-all per
competition**: only the top submission earns, and scores under 0.01 get no weight.

This line has one track:

| track | competition | candidate | what is scored |
|---|---|---|---|
| `main` | `energy_arbitrage` (Python) | `tracks/main/solution.py` | battery-arbitrage profit vs the upstream baseline |

There is no `shared/` folder, because only one track exists.

## How `main` is scored

The candidate is one self-contained Python module that exposes `policy(view, state) -> list[float]`.
The evaluator (vendored unchanged in `tracks/main/vendor/competition/energy_arbitrage/python/`)
runs the following steps:

1. It generates instances from a hidden master seed. Scenarios cycle through BASELINE (20 nodes,
   96 steps), CONGESTED, MULTIDAY, DENSE and CAPSTONE (150 nodes, 100 batteries, 192 steps).
2. It runs the policy in a **subprocess sandbox** (`sandbox.py` / `sandbox_worker.py`). Each step
   the policy receives only a `PolicyView` and the current `State`, and has 30 s per step.
3. It rejects an action outside `state.action_bounds`, and any action that breaks a line-flow
   limit, by raising an error, so the submission fails.
4. It scores each instance as `quality = clip((profit - baseline) / baseline, -10, 10)`. The
   baseline is the better of upstream `greedy` and `conservative`. The score is the floor
   average of `quality * 1e6`.

The profile's "total profit" is the raw quantity; the code ranks on the baseline-relative quality
above. Local `evaluate` reports `score = avg_quality / 1e6`, **higher is better**, with a
maximum of 10.

Facts the candidate relies on, all public: the step-t profit is settled at
`state.rt_prices`, which the policy already sees. RT prices are the day-ahead price × (1 + σ·shock),
plus a congestion premium and Pareto jumps (`market.py`). Congestion probability follows from the
PTDF and the exogenous injections (`network.py`). The per-scenario σ, jump rate and tail index
come from `scenarios.py`.

## Build, check, run, evaluate (always from the repository root)

```bash
python3 -m pip install -r tracks/main/requirements.txt   # build: numpy/scipy pinned to the evaluator image
python3 tracks/main/miner.py check      # static rules + unit tests + 1 sandboxed instance (~5 s)
python3 tracks/main/miner.py evaluate   # last stdout line: {"score": <float>, "metrics": {...}}
python3 tracks/main/miner.py run        # packages tracks/main/dist/solution.py, prints the submit command
```

- `evaluate` settings: `EA_SEED` (default 123), `EA_NUM_INSTANCES` (default 5, one per
  scenario, about 45 s) and `EA_SANDBOX` (default true). Use at least 10 instances and two
  seeds before claiming an improvement, and report per-scenario metrics, not just the mean.
- `check` must pass before any commit. Per-instance rows go to stderr; the JSON summary goes to stdout.
- Without numpy the vendored `utils.py` falls back to pure Python. Scores then differ from the
  image only by float rounding.

## Rules for the candidate (`check` enforces most of them)

- Keep `solution.py` a single file. Imports are limited to math/stdlib helpers, `numpy`,
  `scipy` and `competition.energy_arbitrage.python.*`, which is what the evaluator image has.
- Never touch hidden state. That rules out `_hidden_seed`, `_simulate`, RT-price generation,
  future RT prices, `/workspace/.seed` and `.baselines`, introspection (`gc`, `inspect`,
  frames), the filesystem, processes and the network. That is cheating and the evaluator is
  designed to block it.
- Every action must stay inside `state.action_bounds` and keep line flows within limits. Keep
  the flow-feasibility pass at the end of `policy`.
- Keep the first-step planning well under the 30 s per-step limit on CAPSTONE. `max_policy_seconds`
  in `evaluate` is the whole-episode time.

## Where to improve

The tunables are at the top of `solution.py`: the SOC grid, the DP action fractions, the
decision action count and the shock quadrature. Ideas worth trying:

- Estimate σ online from observed RT/DA ratios.
- Account for coupling between batteries through line limits instead of only softening after the fact.
- Replan periodically.
- Price the option value of jumps more accurately.

Two instance types already hit the +10 cap, so gains now come from BASELINE and CONGESTED.

## Delivery

The steps are listed in `tracks/main/.taoloop/track.json`. TaoLoop runs them, not an
improvement round. Hotkey registration on netuid 1 is TaoLoop's job and not a step.

1. *agent*: install the Apex CLI at upstream commit `da4a308` (`./install_cli.sh`).
2. *agent*: `python3 -m pip install -r tracks/main/requirements.txt`.
3. *agent*: `apex link -l <wallets dir> -w <wallet> -k <hotkey>`. This writes
   `.apex.config.json`, which is never committed.
4. *agent*: `apex competitions`. Take the energy_arbitrage id and fee, confirm it still takes a
   Python `policy(view, state)` file, and set `APEX_COMPETITION_ID`.
5. *agent*: `check`, `evaluate`, then `run`, which packages `tracks/main/dist/solution.py`.
6. **person** (needs payment): `apex submit tracks/main/dist/solution.py -c $APEX_COMPETITION_ID`.
   The CLI pays the per-competition TAO fee from the coldkey, which asks for the coldkey
   password, and uploads the file signed with the hotkey.
7. *agent*: read-only tracking with `apex list -c <id> -m`, `apex list -c <id> -t` and
   `apex result <id>`.

A coding agent working on the candidate never runs `apex submit` or any payment. Each submission
costs a fee and rewards are winner-takes-all, so propose a submission only for a candidate that
clearly beats the current leader (`apex list -c <id> -t`).

## Off limits

- Wallets, mnemonics, hotkey files, `.apex.config.json`, payment receipts and any credential
  must never be committed.
- Do not edit `tracks/main/vendor/` beyond what `vendor/UPSTREAM.md` records. It is the scorer;
  re-sync it from upstream instead.
- Code goes under `tracks/` only. The root holds docs, licences and `.taoloop/`.
- Do not add `.claude/`, `.codex/` or `.github/` files, hooks or tool configuration.
- Keep the repository under 500 files and 20 MiB, with each file under 256 KiB. Generate large
  fixtures; never commit them.
