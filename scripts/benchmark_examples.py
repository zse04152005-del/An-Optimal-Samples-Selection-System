#!/usr/bin/env python3
"""Run benchmark checks against assignment and La Jolla examples."""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.solver import OptimalSamplesSolver
from database.db_manager import DatabaseManager


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    n: int
    k: int
    j: int
    s: int
    expected_groups: int
    time_limit_seconds: float = 60.0


QUICK_CASES = [
    BenchmarkCase("PDF example C(7,6,5)", 7, 6, 5, 5, 6),
    BenchmarkCase("PDF example C(8,6,5)", 8, 6, 5, 5, 12),
    BenchmarkCase("PDF example C(9,6,4)", 9, 6, 4, 4, 12),
    BenchmarkCase("PDF example overlap n=8", 8, 6, 6, 5, 4),
    BenchmarkCase("PDF example overlap n=9", 9, 6, 5, 4, 3),
    BenchmarkCase("PDF example overlap n=10", 10, 6, 6, 4, 3),
]

SLOW_CASES = [
    BenchmarkCase("PDF example overlap n=12", 12, 6, 6, 4, 6, 120.0),
]


def canonical_samples(n: int) -> List[int]:
    return list(range(1, n + 1))


def standard_cover_hint(db: DatabaseManager, case: BenchmarkCase) -> Tuple[List[Tuple], str]:
    standard_t = case.j if case.s == case.j else case.s
    cover = db.get_standard_cover(case.n, case.k, standard_t)
    if not cover:
        return [], "none"
    if case.s == case.j and cover["is_proven_optimal"]:
        return cover["blocks"], "exact-cache"
    return cover["blocks"], "upper-bound-cache"


def run_case(db: DatabaseManager, case: BenchmarkCase, force_solve: bool) -> dict:
    samples = canonical_samples(case.n)
    hint, hint_type = standard_cover_hint(db, case)

    if hint_type == "exact-cache" and not force_solve:
        solver = OptimalSamplesSolver(case.n, case.k, case.j, case.s, samples)
        elapsed = 0.0
        groups = hint
        method = "La Jolla exact cover cache"
        status = "OPTIMAL"
        valid = solver.verify_solution(groups)
    else:
        solver = OptimalSamplesSolver(case.n, case.k, case.j, case.s, samples)
        start = time.time()
        groups, solve_time, method = solver.solve_ilp(
            time_limit_seconds=case.time_limit_seconds,
            initial_solution=hint or None,
            initial_solution_status="FEASIBLE_CACHED" if hint else "FEASIBLE",
        )
        elapsed = time.time() - start
        elapsed = max(elapsed, solve_time)
        status = solver.last_status
        valid = solver.verify_solution(groups)

    return {
        "name": case.name,
        "params": f"n={case.n},k={case.k},j={case.j},s={case.s}",
        "expected": case.expected_groups,
        "actual": len(groups),
        "valid": valid,
        "status": status,
        "method": method,
        "hint": hint_type,
        "time": elapsed,
        "ok": valid and len(groups) == case.expected_groups and status == "OPTIMAL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark assignment examples.")
    parser.add_argument("--include-slow", action="store_true", help="Include slower n=12 example.")
    parser.add_argument("--force-solve", action="store_true", help="Solve even when exact cache exists.")
    args = parser.parse_args()

    db = DatabaseManager()
    db.seed_builtin_known_covers()

    cases = list(QUICK_CASES)
    if args.include_slow:
        cases.extend(SLOW_CASES)

    failures = 0
    print("name | params | expected | actual | status | valid | hint | time_s | method")
    print("-" * 110)
    for case in cases:
        row = run_case(db, case, args.force_solve)
        failures += 0 if row["ok"] else 1
        print(
            f"{row['name']} | {row['params']} | {row['expected']} | {row['actual']} | "
            f"{row['status']} | {row['valid']} | {row['hint']} | {row['time']:.3f} | {row['method']}"
        )

    if failures:
        print(f"FAILED: {failures} benchmark case(s) did not match expected optimal results.")
        return 1

    print("PASSED: all benchmark cases matched expected optimal results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
