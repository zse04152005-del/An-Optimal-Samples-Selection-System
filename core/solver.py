"""core.solver

Optimal Samples Selection Solver.

Problem (informal):
Given a selected sample set S of size n, choose as few k-groups (size-k subsets of S)
as possible such that every j-subset T of S is "covered" by at least one chosen
k-group G with |T intersection G| >= s.

This can be formulated as a set cover ILP. The desktop flow first uses
simulated annealing to obtain a strong feasible upper bound, then refines or
proves optimality with OR-Tools (preferred) or PuLP. If those solvers are
unavailable, we fall back to an exact branch-and-bound search.

Note: The search space grows quickly with n; practical instances on mobile
should use small n.
"""

from __future__ import annotations

from itertools import combinations
from typing import List, Tuple, Set, Optional, Callable, Dict
from math import comb
import math
import os
import random
import time


MAX_DEFAULT_COVER_RELATION_CHECKS = 50_000_000
DEFAULT_CPU_WORKER_RATIO = 0.90


def safe_comb(n: int, r: int) -> int:
    if r < 0 or r > n:
        return 0
    return comb(n, r)


def estimate_coverage_generation(n: int, k: int, j: int, s: int) -> dict:
    """Estimate optimized coverage generation work for a parameter set."""
    num_j_subsets = safe_comb(n, j)
    num_k_groups = safe_comb(n, k)

    covered_subsets_per_group = 0
    for overlap_size in range(s, j + 1):
        covered_subsets_per_group += (
            safe_comb(k, overlap_size) *
            safe_comb(n - k, j - overlap_size)
        )

    optimized_coverage_entries = num_k_groups * covered_subsets_per_group
    naive_relation_checks = num_j_subsets * num_k_groups

    return {
        "num_j_subsets": num_j_subsets,
        "num_k_groups": num_k_groups,
        "covered_subsets_per_group": covered_subsets_per_group,
        "optimized_coverage_entries": optimized_coverage_entries,
        "naive_relation_checks": naive_relation_checks,
    }


def verify_solution_details(
    n: int,
    k: int,
    j: int,
    s: int,
    samples: List[int],
    selected_groups: List[Tuple],
    max_examples: int = 5,
) -> dict:
    """Validate a selected group list and return UI-friendly details."""

    sample_values = list(samples)
    sample_set = set(sample_values)
    expected_total = safe_comb(n, j)
    unique_sample_total = len(sample_set)

    parameter_errors = []
    if len(sample_values) != n:
        parameter_errors.append(f"expected {n} samples, got {len(sample_values)}")
    if unique_sample_total != len(sample_values):
        parameter_errors.append("sample list contains duplicates")
    if not (s <= j <= k):
        parameter_errors.append("expected s <= j <= k")
    if k > unique_sample_total:
        parameter_errors.append("k is larger than the selected sample count")
    if j > unique_sample_total:
        parameter_errors.append("j is larger than the selected sample count")

    valid_group_sets = []
    seen_groups = set()
    duplicate_groups = 0
    invalid_groups = 0
    invalid_examples = []

    for idx, group in enumerate(selected_groups, start=1):
        group_values = list(group)
        group_set = set(group_values)
        issues = []

        if len(group_values) != k:
            issues.append(f"size {len(group_values)} != k")
        if len(group_set) != len(group_values):
            issues.append("duplicate members")

        outside = sorted(group_set - sample_set)
        if outside:
            issues.append(f"outside samples {outside[:max_examples]}")

        if issues:
            invalid_groups += 1
            if len(invalid_examples) < max_examples:
                invalid_examples.append(f"#{idx}: {', '.join(issues)}")
            continue

        canonical = tuple(sorted(group_set))
        if canonical in seen_groups:
            duplicate_groups += 1
            continue

        seen_groups.add(canonical)
        valid_group_sets.append(group_set)

    covered_subsets = 0
    uncovered_examples = []
    can_check_coverage = not parameter_errors and bool(valid_group_sets)

    if can_check_coverage:
        for subset in combinations(sorted(sample_set), j):
            subset_set = set(subset)
            is_covered = any(
                len(subset_set.intersection(group_set)) >= s
                for group_set in valid_group_sets
            )
            if is_covered:
                covered_subsets += 1
            elif len(uncovered_examples) < max_examples:
                uncovered_examples.append(subset)

    total_subsets = expected_total if not parameter_errors else safe_comb(unique_sample_total, j)
    if not can_check_coverage and total_subsets == 0:
        coverage_percent = 0.0
    elif total_subsets:
        coverage_percent = covered_subsets / total_subsets * 100.0
    else:
        coverage_percent = 100.0

    uncovered_count = max(total_subsets - covered_subsets, 0)
    structure_valid = not parameter_errors and invalid_groups == 0 and duplicate_groups == 0
    covers_all = can_check_coverage and uncovered_count == 0
    is_valid = structure_valid and covers_all

    if is_valid:
        message = "All required j-subsets are covered."
    elif parameter_errors:
        message = "; ".join(parameter_errors)
    elif invalid_groups:
        message = "Some output groups are structurally invalid."
    elif duplicate_groups:
        message = "Duplicate groups found; remove duplicates before claiming a final result."
    else:
        message = "Some j-subsets are not covered by any selected k-group."

    return {
        "is_valid": is_valid,
        "structure_valid": structure_valid,
        "covers_all": covers_all,
        "message": message,
        "parameter_errors": parameter_errors,
        "group_count": len(selected_groups),
        "unique_group_count": len(valid_group_sets),
        "invalid_groups": invalid_groups,
        "invalid_examples": invalid_examples,
        "duplicate_groups": duplicate_groups,
        "covered_subsets": covered_subsets,
        "total_subsets": total_subsets,
        "uncovered_count": uncovered_count,
        "uncovered_examples": uncovered_examples,
        "coverage_percent": coverage_percent,
    }


def default_num_search_workers(cpu_count: Optional[int] = None) -> int:
    """Use about 90% of logical CPU cores for OR-Tools search by default."""
    if cpu_count is None:
        cpu_count = os.cpu_count() or 1
    return max(1, min(cpu_count, int(cpu_count * DEFAULT_CPU_WORKER_RATIO)))


class OptimalSamplesSolver:
    """Solver for the Optimal Samples Selection Problem."""

    def __init__(
        self,
        n: int,
        k: int,
        j: int,
        s: int,
        samples: List[int],
        max_cover_relation_checks: Optional[int] = MAX_DEFAULT_COVER_RELATION_CHECKS,
    ):
        self.n = n
        self.k = k
        self.j = j
        self.s = s
        self.samples = sorted(samples)

        self._validate_parameters()
        self._validate_problem_size(max_cover_relation_checks)

        # All j-subsets must be covered; all k-groups are candidate sets.
        self.j_subsets = list(combinations(self.samples, j))
        self.k_groups = list(combinations(self.samples, k))
        self._k_group_index: Dict[Tuple[int, ...], int] = {
            group: idx for idx, group in enumerate(self.k_groups)
        }

        self.last_status = "NOT_SOLVED"
        self.last_objective = None
        self.last_best_bound = None

        # Coverage relations.
        # subset_to_groups[i] = list of group indices that cover j-subset i
        # group_to_subsets[g] = set of j-subset indices covered by group g
        self.subset_to_groups, self.group_to_subsets = self._build_cover_relations()

    def _validate_parameters(self) -> None:
        if not (4 <= self.k <= 7):
            raise ValueError(f"k must be between 4 and 7, got {self.k}")
        if not (3 <= self.s <= 7):
            raise ValueError(f"s must be between 3 and 7, got {self.s}")
        if not (self.s <= self.j <= self.k):
            raise ValueError(f"Must have s <= j <= k, got s={self.s}, j={self.j}, k={self.k}")
        if len(self.samples) != self.n:
            raise ValueError(f"Expected {self.n} samples, got {len(self.samples)}")

    def _validate_problem_size(self, max_cover_relation_checks: Optional[int]) -> None:
        if max_cover_relation_checks is None:
            return

        estimate = estimate_coverage_generation(self.n, self.k, self.j, self.s)
        coverage_entries = estimate["optimized_coverage_entries"]

        if coverage_entries > max_cover_relation_checks:
            raise ValueError(
                "Problem is too large for exact local solving with the current implementation. "
                f"It would generate about {coverage_entries:,} coverage entries "
                f"({estimate['num_k_groups']:,} k-groups x "
                f"{estimate['covered_subsets_per_group']:,} covered j-subsets per group). "
                "Use a cached cover, reduce n/k/j, or import more known covers."
            )

    def _build_cover_relations(self) -> Tuple[List[List[int]], List[Set[int]]]:
        subset_to_groups: List[List[int]] = [[] for _ in range(len(self.j_subsets))]
        group_to_subsets: List[Set[int]] = [set() for _ in range(len(self.k_groups))]
        j_subset_index = {subset: idx for idx, subset in enumerate(self.j_subsets)}

        for g, k_group in enumerate(self.k_groups):
            group_set = set(k_group)
            outside_group = tuple(sample for sample in self.samples if sample not in group_set)

            for overlap_size in range(self.s, self.j + 1):
                outside_size = self.j - overlap_size
                if overlap_size > len(k_group) or outside_size > len(outside_group):
                    continue

                for inside_part in combinations(k_group, overlap_size):
                    for outside_part in combinations(outside_group, outside_size):
                        j_subset = tuple(sorted(inside_part + outside_part))
                        subset_idx = j_subset_index[j_subset]
                        subset_to_groups[subset_idx].append(g)
                        group_to_subsets[g].add(subset_idx)

        # Early infeasibility check.
        for i, groups in enumerate(subset_to_groups):
            if not groups:
                raise ValueError(f"j-subset {i} cannot be covered by any k-group")

        return subset_to_groups, group_to_subsets

    def solve_ilp(
        self,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
        time_limit_seconds: float = 70.0,
        prefer_ortools: bool = True,
        allow_pulp: bool = True,
        initial_solution: Optional[List[Tuple]] = None,
        initial_solution_status: str = "FEASIBLE",
        initial_solution_method: str = "Initial feasible upper bound",
        num_search_workers: Optional[int] = None,
        relative_gap_limit: float = 0.05,
        extension_seconds: float = 5.0,
        early_stop_gap: float = 0.02,
    ) -> Tuple[List[Tuple], float, str]:
        """Solve the instance.

        Returns:
            (selected_groups, solve_time, method_used)

        Method selection:
        - If prefer_ortools is True, try OR-Tools CP-SAT.
        - Otherwise, or if OR-Tools is unavailable, try PuLP.
        - Otherwise fall back to an exact Branch and Bound search.

        Time behaviour:
        - Stops early if the gap is already <= early_stop_gap (default 2%).
        - Extends by extension_seconds (default 5s) when the gap is between
          early_stop_gap and relative_gap_limit (2%–5%), trying to close it.
        - Hard upper bound per call: time_limit_seconds + extension_seconds.

        If time_limit_seconds is exceeded in the fallback search, a TimeoutError
        is raised.
        """

        start_time = time.time()

        if prefer_ortools:
            try:
                result = self._solve_with_ortools(
                    time_limit_seconds=time_limit_seconds,
                    initial_solution=initial_solution,
                    num_search_workers=num_search_workers,
                    relative_gap_limit=relative_gap_limit,
                    extension_seconds=extension_seconds,
                    early_stop_gap=early_stop_gap,
                )
                method = "OR-Tools CP-SAT"
                return result, time.time() - start_time, method
            except RuntimeError:
                if initial_solution and self.verify_solution(initial_solution):
                    self.last_status = initial_solution_status
                    self.last_objective = len(initial_solution)
                    self.last_best_bound = None
                    return initial_solution, time.time() - start_time, initial_solution_method
                raise
            except ImportError:
                pass

        if allow_pulp:
            try:
                result = self._solve_with_pulp(
                    time_limit_seconds=time_limit_seconds,
                    relative_gap_limit=relative_gap_limit,
                )
                method = "PuLP CBC"
                return result, time.time() - start_time, method
            except ImportError:
                pass

        # Exact fallback.
        result = self._solve_branch_and_bound(
            progress_callback=progress_callback,
            time_limit_seconds=time_limit_seconds,
            initial_solution=initial_solution,
        )
        self.last_status = "OPTIMAL"
        self.last_objective = len(result)
        self.last_best_bound = len(result)
        method = "Branch and Bound (Exact)"
        return result, time.time() - start_time, method

    def _solve_with_ortools(
        self,
        time_limit_seconds: float = 70.0,
        initial_solution: Optional[List[Tuple]] = None,
        num_search_workers: Optional[int] = None,
        relative_gap_limit: float = 0.05,
        extension_seconds: float = 5.0,
        early_stop_gap: float = 0.02,
    ) -> List[Tuple]:
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        num_groups = len(self.k_groups)

        x = [model.NewBoolVar(f"x_{g}") for g in range(num_groups)]

        for i, covering_group_ids in enumerate(self.subset_to_groups):
            model.Add(sum(x[g] for g in covering_group_ids) >= 1)

        model.Minimize(sum(x))

        initial_group_ids = self._initial_group_indices(initial_solution)
        if initial_group_ids:
            model.Add(sum(x) <= len(initial_group_ids))
            for g in initial_group_ids:
                model.AddHint(x[g], 1)

        if num_search_workers is None:
            num_search_workers = default_num_search_workers()

        def _make_solver(time_limit: float, gap: float) -> cp_model.CpSolver:
            s = cp_model.CpSolver()
            s.parameters.max_time_in_seconds = float(time_limit)
            s.parameters.relative_gap_limit = float(gap)
            s.parameters.num_search_workers = int(num_search_workers)
            # Stronger LP relaxation for tighter bounds
            s.parameters.linearization_level = 2
            return s

        # ── Phase 1: run up to time_limit_seconds, stop early if gap ≤ early_stop_gap ──
        solver = _make_solver(time_limit_seconds, early_stop_gap)
        status = solver.Solve(model)
        self.last_status = solver.StatusName(status)
        self.last_best_bound = solver.BestObjectiveBound()

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            result = [self.k_groups[g] for g in range(num_groups) if solver.Value(x[g]) == 1]
            self.last_objective = len(result)

            # Compute actual gap
            obj = float(len(result))
            bound = float(self.last_best_bound) if self.last_best_bound else obj
            gap = (obj - bound) / obj if obj > 0 else 0.0

            # ── Early exit: gap already within target ──
            if gap <= early_stop_gap or status == cp_model.OPTIMAL:
                return result

            # ── Phase 2: gap is between early_stop_gap and relative_gap_limit ──
            # Run an additional extension_seconds to try to close it further.
            if gap <= relative_gap_limit:
                solver2 = _make_solver(extension_seconds, 0.0)
                # Provide current best as a warm hint
                for g in range(num_groups):
                    solver2.parameters  # no-op; hints live on the model
                for g_idx in [i for i in range(num_groups) if solver.Value(x[i]) == 1]:
                    model.AddHint(x[g_idx], 1)
                status2 = solver2.Solve(model)
                self.last_status = solver2.StatusName(status2)
                self.last_best_bound = solver2.BestObjectiveBound()
                if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    result2 = [self.k_groups[g] for g in range(num_groups) if solver2.Value(x[g]) == 1]
                    if len(result2) <= len(result):
                        self.last_objective = len(result2)
                        return result2

            return result

        raise RuntimeError("No solution found")

    def _initial_group_indices(self, initial_solution: Optional[List[Tuple]]) -> List[int]:
        if not initial_solution:
            return []

        group_ids = []
        for group in initial_solution:
            normalized = tuple(sorted(group))
            idx = self._k_group_index.get(normalized)
            if idx is None:
                return []
            group_ids.append(idx)

        return group_ids if self.verify_solution(initial_solution) else []

    def solve_simulated_annealing(
        self,
        time_limit_seconds: float = 8.0,
        max_iterations: int = 4000,
        initial_solution: Optional[List[Tuple]] = None,
        random_seed: Optional[int] = None,
        initial_temperature: Optional[float] = None,
        cooling_rate: float = 0.995,
        min_temperature: float = 0.01,
    ) -> List[Tuple]:
        """Find a feasible upper bound with simulated annealing.

        The state is a selected subset of candidate k-groups. A perturbation
        removes, swaps, or adds groups; uncovered constraints are repaired with
        randomized coverage choices. Worse states may be accepted according to
        the current temperature, which helps escape local minima.
        """
        group_ids = self._solve_simulated_annealing_indices(
            time_limit_seconds=time_limit_seconds,
            max_iterations=max_iterations,
            initial_solution=initial_solution,
            random_seed=random_seed,
            initial_temperature=initial_temperature,
            cooling_rate=cooling_rate,
            min_temperature=min_temperature,
        )
        result = [self.k_groups[g] for g in sorted(group_ids)]
        self.last_status = "FEASIBLE_SA"
        self.last_objective = len(result)
        self.last_best_bound = None
        return result

    def _solve_simulated_annealing_indices(
        self,
        time_limit_seconds: float = 8.0,
        max_iterations: int = 4000,
        initial_solution: Optional[List[Tuple]] = None,
        random_seed: Optional[int] = None,
        initial_temperature: Optional[float] = None,
        cooling_rate: float = 0.995,
        min_temperature: float = 0.01,
    ) -> List[int]:
        rng = random.Random(random_seed)
        start = time.time()
        num_groups = len(self.k_groups)
        num_subsets = len(self.j_subsets)

        if num_groups == 0 or num_subsets == 0:
            return []

        selected: Set[int] = set()
        coverage_counts = [0] * num_subsets
        uncovered: Set[int] = set(range(num_subsets))

        def add_group(group_id: int, ops: Optional[List[Tuple[str, int]]] = None) -> bool:
            if group_id in selected:
                return False
            selected.add(group_id)
            for subset_id in self.group_to_subsets[group_id]:
                if coverage_counts[subset_id] == 0:
                    uncovered.discard(subset_id)
                coverage_counts[subset_id] += 1
            if ops is not None:
                ops.append(("remove", group_id))
            return True

        def remove_group(group_id: int, ops: Optional[List[Tuple[str, int]]] = None) -> bool:
            if group_id not in selected:
                return False
            selected.remove(group_id)
            for subset_id in self.group_to_subsets[group_id]:
                coverage_counts[subset_id] -= 1
                if coverage_counts[subset_id] == 0:
                    uncovered.add(subset_id)
            if ops is not None:
                ops.append(("add", group_id))
            return True

        def undo(ops: List[Tuple[str, int]]) -> None:
            for action, group_id in reversed(ops):
                if action == "add":
                    add_group(group_id)
                else:
                    remove_group(group_id)

        def random_unselected_group() -> Optional[int]:
            if len(selected) >= num_groups:
                return None
            for _ in range(24):
                group_id = rng.randrange(num_groups)
                if group_id not in selected:
                    return group_id
            for group_id in range(num_groups):
                if group_id not in selected:
                    return group_id
            return None

        def random_selected_groups(count: int) -> List[int]:
            if not selected:
                return []
            pool = tuple(selected)
            count = min(count, len(pool))
            return rng.sample(pool, count)

        def pick_uncovered_subset() -> Optional[int]:
            if not uncovered:
                return None
            target_offset = rng.randrange(len(uncovered))
            for i, subset_id in enumerate(uncovered):
                if i == target_offset:
                    return subset_id
            return next(iter(uncovered))

        def uncovered_gain(group_id: int) -> int:
            return sum(
                1
                for subset_id in self.group_to_subsets[group_id]
                if coverage_counts[subset_id] == 0
            )

        def pick_repair_group(target_subset: int, temperature_ratio: float) -> Optional[int]:
            candidates = self.subset_to_groups[target_subset]
            sample_limit = 96

            if len(candidates) <= sample_limit:
                pool = candidates
            else:
                pool = [candidates[rng.randrange(len(candidates))] for _ in range(sample_limit)]

            scored = []
            for group_id in pool:
                if group_id in selected:
                    continue
                gain = uncovered_gain(group_id)
                if gain > 0:
                    scored.append((gain, group_id))

            if not scored and len(candidates) > len(pool):
                for group_id in candidates:
                    if group_id in selected:
                        continue
                    gain = uncovered_gain(group_id)
                    if gain > 0:
                        scored.append((gain, group_id))
                    if len(scored) >= sample_limit:
                        break

            if not scored:
                for group_id in candidates:
                    if group_id not in selected:
                        return group_id
                return None

            scored.sort(reverse=True)
            choice_width = min(len(scored), max(1, 2 + int(temperature_ratio * 10)))
            return rng.choice(scored[:choice_width])[1]

        def repair(
            ops: Optional[List[Tuple[str, int]]] = None,
            max_added: Optional[int] = None,
            temperature_ratio: float = 1.0,
        ) -> bool:
            added = 0
            while uncovered and (max_added is None or added < max_added):
                target_subset = pick_uncovered_subset()
                if target_subset is None:
                    return True
                group_id = pick_repair_group(target_subset, temperature_ratio)
                if group_id is None:
                    return False
                if add_group(group_id, ops):
                    added += 1
            return not uncovered

        def prune(
            ops: Optional[List[Tuple[str, int]]] = None,
            max_checks: Optional[int] = None,
        ) -> None:
            candidates = list(selected)
            rng.shuffle(candidates)
            if max_checks is not None:
                candidates = candidates[:max_checks]

            for group_id in candidates:
                if group_id not in selected:
                    continue
                if all(coverage_counts[subset_id] > 1 for subset_id in self.group_to_subsets[group_id]):
                    remove_group(group_id, ops)

        max_cover = max((len(subsets) for subsets in self.group_to_subsets), default=1)
        lower_bound = max(1, (num_subsets + max_cover - 1) // max_cover)
        initial_ids = self._initial_group_indices(initial_solution)

        if initial_ids:
            for group_id in initial_ids:
                add_group(group_id)
        else:
            start_size = min(num_groups, max(lower_bound, int(lower_bound * 1.2)))
            for group_id in rng.sample(range(num_groups), start_size):
                add_group(group_id)

        repair()
        prune()

        if uncovered:
            raise RuntimeError("Simulated annealing could not construct a feasible starting solution")

        best_selected = set(selected)
        temperature = initial_temperature or max(1.0, len(selected) * 0.5)
        start_temperature = max(temperature, min_temperature)
        uncovered_penalty = max(10, lower_bound + 1)

        def energy() -> float:
            return len(selected) + len(uncovered) * uncovered_penalty

        for iteration in range(max_iterations):
            if time.time() - start >= time_limit_seconds:
                break

            old_energy = energy()
            ops: List[Tuple[str, int]] = []
            temperature_ratio = max(min_temperature, temperature) / start_temperature
            move = rng.random()

            if selected and move < 0.65:
                remove_count = 2 if len(selected) > 1 and rng.random() < 0.25 else 1
                for group_id in random_selected_groups(remove_count):
                    remove_group(group_id, ops)
                if rng.random() < 0.85:
                    repair(
                        ops,
                        max_added=remove_count + 3,
                        temperature_ratio=temperature_ratio,
                    )
            elif selected and move < 0.90:
                for group_id in random_selected_groups(1):
                    remove_group(group_id, ops)
                group_id = random_unselected_group()
                if group_id is not None:
                    add_group(group_id, ops)
                if rng.random() < 0.70:
                    repair(ops, max_added=4, temperature_ratio=temperature_ratio)
            else:
                group_id = random_unselected_group()
                if group_id is not None:
                    add_group(group_id, ops)

            if not uncovered and rng.random() < 0.55:
                prune(ops, max_checks=max(8, len(selected) // 2))

            new_energy = energy()
            delta = new_energy - old_energy
            accept = delta <= 0
            if not accept:
                accept_probability = math.exp(-delta / max(temperature, min_temperature))
                accept = rng.random() < accept_probability

            if not accept:
                undo(ops)

            if not uncovered:
                if iteration % 50 == 0:
                    prune()
                if len(selected) < len(best_selected):
                    best_selected = set(selected)

            temperature = max(min_temperature, temperature * cooling_rate)

        if not best_selected:
            repair()
            prune()
            if uncovered:
                raise RuntimeError("Simulated annealing did not find a feasible solution")
            best_selected = set(selected)

        return sorted(best_selected)

    def _solve_with_pulp(self, time_limit_seconds: float = 65.0, relative_gap_limit: float = 0.10) -> List[Tuple]:
        import pulp

        num_groups = len(self.k_groups)

        prob = pulp.LpProblem("OptimalSamplesSelection", pulp.LpMinimize)
        x = [pulp.LpVariable(f"x_{g}", cat="Binary") for g in range(num_groups)]

        prob += pulp.lpSum(x)

        for i, covering_group_ids in enumerate(self.subset_to_groups):
            prob += pulp.lpSum(x[g] for g in covering_group_ids) >= 1

        prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=float(time_limit_seconds), fracGap=float(relative_gap_limit)))

        if prob.status in (pulp.LpStatusOptimal, pulp.LpStatus.get(0, None)) or pulp.value(pulp.lpSum(x)) is not None:
            try:
                result = [self.k_groups[g] for g in range(num_groups) if (pulp.value(x[g]) or 0) >= 0.5]
                if result:
                    is_optimal = prob.status == pulp.LpStatusOptimal
                    self.last_status = "OPTIMAL" if is_optimal else "FEASIBLE"
                    self.last_objective = len(result)
                    self.last_best_bound = len(result) if is_optimal else None
                    return result
            except Exception:
                pass
        raise RuntimeError("No solution found")

    def _greedy_feasible_solution(self) -> List[int]:
        """Return a feasible solution (list of group indices) using a greedy heuristic."""
        uncovered: Set[int] = set(range(len(self.j_subsets)))
        selected: List[int] = []

        while uncovered:
            # Pick a most constrained subset, then choose a group that covers the most uncovered.
            target = min(uncovered, key=lambda i: len(self.subset_to_groups[i]))
            best_g = None
            best_gain = -1
            for g in self.subset_to_groups[target]:
                gain = len(self.group_to_subsets[g].intersection(uncovered))
                if gain > best_gain:
                    best_gain = gain
                    best_g = g

            if best_g is None or best_gain <= 0:
                # Should not happen due to infeasibility check in _build_cover_relations.
                raise RuntimeError("Failed to construct a feasible solution")

            selected.append(best_g)
            uncovered.difference_update(self.group_to_subsets[best_g])

        return selected

    def _solve_branch_and_bound(
        self,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
        time_limit_seconds: float = 300.0,
        initial_solution: Optional[List[Tuple]] = None,
    ) -> List[Tuple]:
        """Exact Branch and Bound fallback.

        This method is used when ILP solvers are unavailable (e.g., mobile builds).
        It is guaranteed optimal if it finishes before time_limit_seconds.
        """

        start = time.time()
        num_subsets = len(self.j_subsets)

        # Initial upper bound from a cached or simulated annealing feasible solution.
        initial_group_ids = self._initial_group_indices(initial_solution)
        if initial_group_ids:
            best_solution = initial_group_ids
        else:
            annealing_budget = min(5.0, max(1.0, time_limit_seconds * 0.10))
            best_solution = self._solve_simulated_annealing_indices(
                time_limit_seconds=annealing_budget,
                max_iterations=2500,
            )
        best_size = len(best_solution)

        global_max_cover = max((len(s) for s in self.group_to_subsets), default=0)
        if global_max_cover <= 0:
            raise RuntimeError("No solution found")

        def lower_bound(uncovered: Set[int]) -> int:
            # Safe (possibly loose) bound: each group can cover at most global_max_cover subsets.
            # Using a larger denominator makes the bound smaller => never overestimates.
            return (len(uncovered) + global_max_cover - 1) // global_max_cover

        def branch(selected: List[int], uncovered: Set[int], depth: int) -> None:
            nonlocal best_solution, best_size

            if time.time() - start > time_limit_seconds:
                raise TimeoutError(f"Branch and bound exceeded time limit ({time_limit_seconds}s)")

            if not uncovered:
                if len(selected) < best_size:
                    best_solution = selected.copy()
                    best_size = len(selected)
                return

            # Basic pruning.
            if len(selected) >= best_size:
                return

            if len(selected) + lower_bound(uncovered) >= best_size:
                return

            # Choose a most constrained uncovered subset.
            target = min(uncovered, key=lambda i: len(self.subset_to_groups[i]))

            # Try groups that cover target, best-first by gain.
            candidates = list(self.subset_to_groups[target])
            candidates.sort(key=lambda g: len(self.group_to_subsets[g].intersection(uncovered)), reverse=True)

            for g in candidates:
                gain = self.group_to_subsets[g].intersection(uncovered)
                if not gain:
                    continue

                new_uncovered = uncovered.difference(gain)
                branch(selected + [g], new_uncovered, depth + 1)

                if progress_callback and depth == 0:
                    progress_callback(depth, len(selected) + 1, best_size)

        uncovered0: Set[int] = set(range(num_subsets))
        branch([], uncovered0, 0)

        return [self.k_groups[g] for g in best_solution]

    def verify_solution(self, selected_groups: List[Tuple]) -> bool:
        for j_subset in self.j_subsets:
            j_set = set(j_subset)
            if not any(len(j_set.intersection(k_group)) >= self.s for k_group in selected_groups):
                return False
        return True

    def get_statistics(self) -> dict:
        return {
            "n": self.n,
            "k": self.k,
            "j": self.j,
            "s": self.s,
            "num_j_subsets": len(self.j_subsets),
            "num_k_groups": len(self.k_groups),
            "optimized_coverage_entries": estimate_coverage_generation(
                self.n, self.k, self.j, self.s
            )["optimized_coverage_entries"],
            "samples": self.samples,
        }
