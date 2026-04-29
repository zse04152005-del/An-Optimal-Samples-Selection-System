#!/usr/bin/env python3
"""Compare optimized coverage generation with the naive pairwise method."""

from __future__ import annotations

import argparse
import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.solver import OptimalSamplesSolver, estimate_coverage_generation


def naive_relations(solver: OptimalSamplesSolver):
    subset_to_groups = [[] for _ in range(len(solver.j_subsets))]
    group_to_subsets = [set() for _ in range(len(solver.k_groups))]

    for subset_idx, j_subset in enumerate(solver.j_subsets):
        j_set = set(j_subset)
        for group_idx, k_group in enumerate(solver.k_groups):
            if len(j_set.intersection(k_group)) >= solver.s:
                subset_to_groups[subset_idx].append(group_idx)
                group_to_subsets[group_idx].add(subset_idx)

    return subset_to_groups, group_to_subsets


def check_case(n: int, k: int, j: int, s: int) -> bool:
    solver = OptimalSamplesSolver(n, k, j, s, list(range(1, n + 1)))
    naive_subset_to_groups, naive_group_to_subsets = naive_relations(solver)

    optimized_subset_to_groups = [sorted(groups) for groups in solver.subset_to_groups]
    optimized_group_to_subsets = [set(groups) for groups in solver.group_to_subsets]

    ok = (
        optimized_subset_to_groups == naive_subset_to_groups and
        optimized_group_to_subsets == naive_group_to_subsets
    )

    estimate = estimate_coverage_generation(n, k, j, s)
    generated_entries = sum(len(groups) for groups in solver.group_to_subsets)
    ok = ok and generated_entries == estimate["optimized_coverage_entries"]

    ratio = (
        estimate["naive_relation_checks"] / estimate["optimized_coverage_entries"]
        if estimate["optimized_coverage_entries"] else 0
    )
    print(
        f"n={n},k={k},j={j},s={s}: ok={ok}, "
        f"entries={generated_entries:,}, naive={estimate['naive_relation_checks']:,}, "
        f"reduction={ratio:.2f}x"
    )
    return ok


def iter_cases(max_n: int):
    for n in range(7, max_n + 1):
        for k in range(4, min(7, n) + 1):
            for j in range(3, k + 1):
                for s in range(3, j + 1):
                    yield n, k, j, s


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate optimized coverage generation.")
    parser.add_argument("--max-n", type=int, default=11)
    args = parser.parse_args()

    failures = 0
    for n, k, j, s in iter_cases(args.max_n):
        if not check_case(n, k, j, s):
            failures += 1

    if failures:
        print(f"FAILED: {failures} coverage-generation case(s) mismatched naive relations.")
        return 1

    print("PASSED: optimized coverage generation matches naive relations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
