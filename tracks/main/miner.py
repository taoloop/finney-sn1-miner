"""Apex (SN1) energy_arbitrage miner harness.

Usage (from the repository root):
    python3 tracks/main/miner.py check      # static rules + unit tests + one sandboxed smoke run
    python3 tracks/main/miner.py evaluate   # local score; last stdout line is {"score": ..., "metrics": {...}}
    python3 tracks/main/miner.py run        # package the candidate and print the person-only submit command

Nothing here signs, pays or uploads. Submission is a person's step (see AGENTS.md).
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import math
import os
import shutil
import sys
import time
import unittest

TRACK_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(TRACK_DIR, "vendor")
CANDIDATE = os.path.join(TRACK_DIR, "solution.py")
CANDIDATE_MODULE = "solution"
DIST_DIR = os.path.join(TRACK_DIR, "dist")

for _p in (TRACK_DIR, VENDOR_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

QUALITY_PRECISION = 1_000_000
SCENARIO_ORDER = ("BASELINE", "CONGESTED", "MULTIDAY", "DENSE", "CAPSTONE")
MAX_SUBMISSION_BYTES = 200_000

# Imports a submission may use: stdlib modules that cannot reach outside the
# process, plus the evaluator's own package and the image's numpy/scipy.
ALLOWED_IMPORTS = {
    "__future__", "math", "cmath", "typing", "dataclasses", "functools", "itertools",
    "collections", "heapq", "bisect", "statistics", "enum", "copy", "operator", "random",
    "numpy", "scipy", "competition",
}
# Identifiers that would reach for hidden state, the host or the evaluator.
FORBIDDEN_NAMES = {
    "hidden_seed", "_hidden_seed", "_simulate", "generate_rt_prices", "take_step",
    "open", "exec", "eval", "compile", "__import__", "globals", "getattr", "setattr",
    "_getframe", "f_back", "f_globals", "gc", "inspect", "ctypes", "subprocess", "os", "sys",
    "socket", "pathlib", "importlib",
}


def _env_int(name: str, default: int, lo: int | None = None, hi: int | None = None) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        sys.exit(f"{name} must be an integer, got {raw!r}")
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        sys.exit(f"{name}={value} out of range [{lo}, {hi}]")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Static rules
# ---------------------------------------------------------------------------


def static_problems(path: str = CANDIDATE) -> list[str]:
    """Return rule violations for a candidate file (empty list = OK)."""
    problems: list[str] = []
    size = os.path.getsize(path)
    if size > MAX_SUBMISSION_BYTES:
        problems.append(f"file is {size} bytes (> {MAX_SUBMISSION_BYTES})")
    with open(path, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [f"syntax error: {exc}"]
    has_policy = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "policy" and node in tree.body:
            has_policy = len(node.args.args) == 2
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""] if node.level == 0 else []
        else:
            mods = []
        for mod in mods:
            if mod.split(".")[0] not in ALLOWED_IMPORTS:
                problems.append(f"line {node.lineno}: import of {mod!r} is not allowed")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            problems.append(f"line {node.lineno}: use of {node.id!r} is not allowed")
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            problems.append(f"line {node.lineno}: attribute {node.attr!r} is not allowed")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "/workspace" in node.value:
            problems.append(f"line {node.lineno}: references the evaluator workspace")
    if not has_policy:
        problems.append("missing top-level `def policy(view, state)`")
    return problems


# ---------------------------------------------------------------------------
# Evaluation (mirrors upstream test_challenge.evaluate_sandboxed, without the
# /workspace seed/baseline files which only exist inside the evaluator image)
# ---------------------------------------------------------------------------


def run_instances(master_seed: int, num_instances: int, sandbox: bool, scenarios=None) -> list[dict]:
    from competition.energy_arbitrage.python.challenge import Challenge, Track
    from competition.energy_arbitrage.python.scenarios import Scenario
    from competition.energy_arbitrage.python.test_challenge import seed_from_master_nonce

    order = [Scenario[name] for name in (scenarios or SCENARIO_ORDER)]
    if not sandbox:
        import importlib

        policy = importlib.import_module(CANDIDATE_MODULE).policy
    results = []
    for nonce in range(num_instances):
        scenario = order[nonce % len(order)]
        challenge = Challenge.generate_instance(seed_from_master_nonce(master_seed, nonce), Track(s=scenario))
        started = time.monotonic()
        if sandbox:
            solution = challenge.grid_optimize_sandboxed(CANDIDATE_MODULE)
        else:
            solution = challenge.grid_optimize(policy)
        elapsed = time.monotonic() - started
        profit = challenge.evaluate_total_profit(solution)
        with contextlib.redirect_stdout(io.StringIO()):  # compute_baseline prints
            _, baseline = challenge.compute_baseline()
        quality_f = (profit - baseline) / (baseline + 1e-6)
        quality = round(max(-10.0, min(quality_f, 10.0)) * QUALITY_PRECISION)
        row = {
            "nonce": nonce,
            "scenario": scenario.name,
            "profit": profit,
            "baseline_profit": baseline,
            "quality": quality,
            "policy_seconds": round(elapsed, 2),
        }
        print(json.dumps(row), file=sys.stderr)
        results.append(row)
    return results


def summarise(results: list[dict]) -> dict:
    total = sum(r["quality"] for r in results)
    avg_quality = total // len(results) if results else 0  # upstream uses floor division
    metrics: dict = {
        "avg_quality": avg_quality,
        "instances": len(results),
        "capped_instances": sum(1 for r in results if abs(r["quality"]) >= 10 * QUALITY_PRECISION),
        "total_profit": round(sum(r["profit"] for r in results), 2),
        "total_baseline_profit": round(sum(r["baseline_profit"] for r in results), 2),
        "max_policy_seconds": max((r["policy_seconds"] for r in results), default=0.0),
    }
    for name in SCENARIO_ORDER:
        rows = [r for r in results if r["scenario"] == name]
        if rows:
            metrics[f"quality_{name.lower()}"] = sum(r["quality"] for r in rows) / len(rows) / QUALITY_PRECISION
    return {"score": avg_quality / QUALITY_PRECISION, "metrics": metrics}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_check(_args) -> int:
    print(f"[check] static rules on {os.path.relpath(CANDIDATE)}")
    problems = static_problems()
    for p in problems:
        print(f"  FAIL {p}")
    if problems:
        return 1
    print("  ok")

    print("[check] unit tests")
    suite = unittest.defaultTestLoader.discover(os.path.join(TRACK_DIR, "tests"), top_level_dir=TRACK_DIR)
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1

    print("[check] sandboxed smoke run (1 BASELINE instance, seed 7)")
    rows = run_instances(7, 1, sandbox=True, scenarios=["BASELINE"])
    row = rows[0]
    print(f"  profit={row['profit']:.2f} baseline={row['baseline_profit']:.2f} quality={row['quality']}")
    if not math.isfinite(row["profit"]):
        print("  FAIL profit is not finite")
        return 1
    print("check passed")
    return 0


def cmd_evaluate(_args) -> int:
    seed = _env_int("EA_SEED", 123)
    num = _env_int("EA_NUM_INSTANCES", 5, 1, 100)
    sandbox = _env_bool("EA_SANDBOX", True)
    problems = static_problems()
    if problems:
        print(json.dumps({"score": -10.0, "metrics": {"static_problems": len(problems)}}))
        return 1
    results = run_instances(seed, num, sandbox=sandbox)
    out = summarise(results)
    out["metrics"].update({"seed": seed, "sandbox": sandbox})
    print(json.dumps(out))
    return 0


def cmd_run(_args) -> int:
    problems = static_problems()
    if problems:
        for p in problems:
            print(f"FAIL {p}")
        return 1
    os.makedirs(DIST_DIR, exist_ok=True)
    target = os.path.join(DIST_DIR, "solution.py")
    shutil.copyfile(CANDIDATE, target)
    with open(target, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    competition = os.environ.get("APEX_COMPETITION_ID", "").strip() or "<APEX_COMPETITION_ID>"
    manifest = {"file": os.path.relpath(target), "sha256": digest, "competition_id": competition}
    with open(os.path.join(DIST_DIR, "submission.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Packaged {os.path.relpath(target)} (sha256 {digest})")
    print("A person submits it (signs with the hotkey and pays the on-chain fee):")
    print(f"  apex submit {os.path.relpath(target)} -c {competition}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("evaluate").set_defaults(fn=cmd_evaluate)
    sub.add_parser("run").set_defaults(fn=cmd_run)
    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
