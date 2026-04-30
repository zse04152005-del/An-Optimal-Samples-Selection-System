import time

from PyQt5.QtCore import QThread, pyqtSignal

from core.solver import OptimalSamplesSolver
from core.solution_service import SolutionService


class SolverThread(QThread):
    solve_finished = pyqtSignal(list, float, str, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int, int)
    round_progress = pyqtSignal(int, int, int)
    building_model = pyqtSignal()
    annealing = pyqtSignal()

    TIME_LIMIT_PER_ROUND = 70.0
    ANNEALING_TIME_LIMIT = 8.0

    def __init__(self, svc: SolutionService, n, k, j, s, samples,
                 precomputed_hint=None, precomputed_hint_status="FEASIBLE",
                 num_rounds=1, time_limit_per_round=None):
        super().__init__()
        self.svc = svc
        self.n = n
        self.k = k
        self.j = j
        self.s = s
        self.samples = samples
        self.precomputed_hint = precomputed_hint
        self.precomputed_hint_status = precomputed_hint_status
        self.num_rounds = max(1, num_rounds)
        if time_limit_per_round is None:
            time_limit_per_round = self.TIME_LIMIT_PER_ROUND
        self.time_limit_per_round = max(5.0, float(time_limit_per_round))
        self.solver = None

    def run(self):
        try:
            self.building_model.emit()

            self.solver = OptimalSamplesSolver(
                self.n, self.k, self.j, self.s, self.samples)

            hint = self.precomputed_hint
            hint_status = self.precomputed_hint_status

            cache_hint, cache_status, cache_msg = \
                self.svc.get_cached_solution_hint(
                    self.solver, self.n, self.k, self.j, self.s, self.samples)

            if cache_hint and cache_status == "OPTIMAL":
                self.solve_finished.emit(cache_hint, 0.0, cache_msg, "OPTIMAL")
                return

            if cache_hint:
                if hint is None or len(cache_hint) < len(hint):
                    hint = cache_hint
                    hint_status = cache_status

            best_result = hint
            best_status = hint_status
            best_method = "Cached upper bound"
            total_time = 0.0

            seed = (
                self.n * 1_000_003
                + self.k * 10_007
                + self.j * 503
                + self.s * 31
                + sum((idx + 1) * value for idx, value in enumerate(self.samples))
            )
            annealing_time = time.time()
            self.annealing.emit()
            annealing_start = self.solver.solve_simulated_annealing(
                time_limit_seconds=self.ANNEALING_TIME_LIMIT,
                max_iterations=4000,
                initial_solution=best_result,
                random_seed=seed,
            )
            total_time += time.time() - annealing_time
            if annealing_start and (best_result is None or len(annealing_start) <= len(best_result)):
                best_result = annealing_start
                best_status = self.solver.last_status
                best_method = "Simulated Annealing"

            for rnd in range(1, self.num_rounds + 1):
                result, solve_time, method = self.solver.solve_ilp(
                    progress_callback=lambda d, c, b: self.progress.emit(d, c, b),
                    initial_solution=best_result,
                    initial_solution_status=best_status,
                    initial_solution_method=best_method,
                    time_limit_seconds=self.time_limit_per_round,
                    relative_gap_limit=0.05,
                    extension_seconds=5.0,
                    early_stop_gap=0.02,
                )
                total_time += solve_time
                current_status = self.solver.last_status

                if (
                    best_result is None
                    or len(result) < len(best_result)
                    or (current_status == "OPTIMAL" and len(result) <= len(best_result))
                ):
                    best_result = result
                    best_status = current_status
                    best_method = f"{method} (round {rnd}/{self.num_rounds})"

                self.round_progress.emit(rnd, self.num_rounds,
                                         len(best_result) if best_result else -1)
                if current_status == "OPTIMAL":
                    break

            self.solve_finished.emit(best_result, total_time, best_method, best_status)
        except Exception as e:
            self.error.emit(str(e))
