from core.solver import OptimalSamplesSolver, estimate_coverage_generation
from database.db_manager import DatabaseManager

MAX_COVER_RELATION_CHECKS = 20_000_000


class SolutionService:

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    @staticmethod
    def estimate_problem_size(n, k, j, s):
        est = estimate_coverage_generation(n, k, j, s)
        est['relation_checks'] = est['optimized_coverage_entries']
        return est

    @staticmethod
    def map_canonical_groups_to_samples(groups, samples):
        ordered = sorted(samples)
        return [tuple(ordered[i - 1] for i in group) for group in groups]

    @staticmethod
    def map_sample_groups_to_canonical(groups, samples):
        idx = {s: i + 1 for i, s in enumerate(sorted(samples))}
        return [tuple(sorted(idx[v] for v in group)) for group in groups]

    def get_precomputed_solution(self, n, k, j, s, samples):
        cached = self.db.get_project_result(n, k, j, s)
        if cached:
            groups = self.map_canonical_groups_to_samples(cached['groups'], samples)
            if cached['status'] == "OPTIMAL":
                return groups, "OPTIMAL", "Project result cache"
            best_groups = groups
            best_status = cached['status']
            best_message = "Project result cache"
        else:
            best_groups = None
            best_status = "FEASIBLE"
            best_message = "Cached upper bound"

        standard_t = j if s == j else s
        standard = self.db.get_standard_cover(n, k, standard_t)
        if standard:
            groups = self.map_canonical_groups_to_samples(standard['blocks'], samples)
            if s == j and standard['is_proven_optimal']:
                self.db.save_project_result(
                    n, k, j, s, standard['blocks'], "OPTIMAL",
                    method="La Jolla Covering Repository",
                    source=standard['source_url'])
                return groups, "OPTIMAL", "La Jolla exact cover cache"
            if best_groups is None or len(groups) < len(best_groups):
                best_groups = groups
                best_status = "FEASIBLE_CACHED"
                best_message = "La Jolla upper-bound cache"

        return best_groups, best_status, best_message

    def get_cached_solution_hint(self, solver, n, k, j, s, samples):
        cached = self.db.get_project_result(n, k, j, s)
        if cached:
            groups = self.map_canonical_groups_to_samples(cached['groups'], samples)
            if solver.verify_solution(groups):
                if cached['status'] == "OPTIMAL":
                    return groups, "OPTIMAL", "Project result cache"
                best_groups = groups
                best_status = cached['status']
            else:
                best_groups = None
                best_status = "FEASIBLE"
        else:
            best_groups = None
            best_status = "FEASIBLE"

        standard_t = j if s == j else s
        standard = self.db.get_standard_cover(n, k, standard_t)
        if standard:
            groups = self.map_canonical_groups_to_samples(standard['blocks'], samples)
            if solver.verify_solution(groups):
                if s == j and standard['is_proven_optimal']:
                    self.db.save_project_result(
                        n, k, j, s, standard['blocks'], "OPTIMAL",
                        method="La Jolla Covering Repository",
                        source=standard['source_url'])
                    return groups, "OPTIMAL", "La Jolla exact cover cache"
                if best_groups is None or len(groups) < len(best_groups):
                    best_groups = groups
                    best_status = "FEASIBLE_CACHED"

        return best_groups, best_status, "Cached upper bound"

    def save_project_result_if_valid(self, n, k, j, s, samples, result, status, method):
        sample_set = set(samples)
        if all(v in sample_set for group in result for v in group):
            canonical = self.map_sample_groups_to_canonical(result, samples)
            self.db.save_project_result(
                n, k, j, s, canonical, status,
                method=method, source="local solve/cache")
