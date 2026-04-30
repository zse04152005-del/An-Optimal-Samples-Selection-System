import sys
import os

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QPushButton, QStatusBar, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.styles import (
    APP_STYLE, C_CARD, C_BORDER, C_TEXT, C_ACCENT, C_ACCENT_LIGHT,
    C_LABEL, FONT_SANS, MAX_DISPLAYED_GROUPS,
)
from gui.solver_thread import SolverThread
from gui.tabs.computation_tab import ComputationTab
from gui.tabs.database_tab import DatabaseTab
from core.solver import verify_solution_details
from core.solution_service import SolutionService, MAX_COVER_RELATION_CHECKS
from database.db_manager import DatabaseManager


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.db_manager.seed_builtin_known_covers()
        self.svc = SolutionService(self.db_manager)

        self.solver_thread = None
        self.last_solve_time = 0.0
        self.last_method = ""
        self.last_status = "NOT_SOLVED"
        self.last_best_bound = None

        self.setStyleSheet(APP_STYLE)
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("An Optimal Samples Selection System")
        self.setMinimumSize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        topbar = QWidget()
        topbar.setFixedHeight(48)
        topbar.setStyleSheet(f"background:{C_CARD}; border-bottom:1px solid {C_BORDER};")
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(10)

        # Logo
        logo = QLabel("O")
        logo.setFixedSize(28, 28)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            f"background:{C_ACCENT}; color:white; border-radius:7px;"
            f"font-family:{FONT_SANS}; font-size:15px; font-weight:800;")
        tl.addWidget(logo)

        title = QLabel("Optimal Samples Selection")
        title.setStyleSheet(
            f"color:{C_TEXT}; font-family:{FONT_SANS}; font-size:15px; font-weight:600;")
        tl.addWidget(title)
        tl.addStretch()

        # Pill tabs
        self._tab_btns = []
        for i, name in enumerate(("Computation", "Database")):
            btn = QPushButton(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            self._tab_btns.append(btn)
            tl.addWidget(btn)
        root.addWidget(topbar)

        # Stacked pages
        self._stack = QStackedWidget()
        self.comp_tab = ComputationTab()
        self.db_tab = DatabaseTab(self.db_manager)
        self._stack.addWidget(self.comp_tab)
        self._stack.addWidget(self.db_tab)
        root.addWidget(self._stack, stretch=1)

        self._switch_tab(0)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Wire signals
        self.comp_tab.solve_requested.connect(self._solve)
        self.comp_tab.verify_requested.connect(self._verify_results)
        self.comp_tab.save_requested.connect(self._save_results)
        self.comp_tab.export_requested.connect(self._export_results)
        self.comp_tab.clear_requested.connect(self._clear_all)
        self.db_tab.load_requested.connect(self._load_from_db)
        self.db_tab.export_requested.connect(self._export_db_result)

    def _switch_tab(self, idx):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_btns):
            if i == idx:
                btn.setStyleSheet(
                    f"QPushButton{{background:{C_ACCENT_LIGHT};color:{C_ACCENT};"
                    f"border:none;border-radius:8px;font-family:{FONT_SANS};"
                    f"font-size:13px;font-weight:600;padding:4px 16px;}}")
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{C_LABEL};"
                    f"border:none;border-radius:8px;font-family:{FONT_SANS};"
                    f"font-size:13px;font-weight:500;padding:4px 16px;}}"
                    f"QPushButton:hover{{color:{C_TEXT};}}")

    # ── Solve ────────────────────────────────────────────────────────────────

    def _solve(self):
        if self.solver_thread and self.solver_thread.isRunning():
            self.status_bar.showMessage("Solver is already running")
            return

        samples = self.comp_tab.get_samples()
        if not samples:
            QMessageBox.warning(self, "Error",
                                "Please generate or select samples first.")
            return

        p = self.comp_tab.get_params()
        n, k, j, s, r = p['n'], p['k'], p['j'], p['s'], p['r']
        time_limit = p['time_limit']

        if len(samples) != n:
            QMessageBox.warning(
                self, "Error",
                "Sample count doesn't match n. Please regenerate samples.")
            return

        self.solver_thread = None
        self.last_best_bound = None

        try:
            cached, cached_status, cached_msg = \
                self.svc.get_precomputed_solution(n, k, j, s, samples)
            if cached and cached_status == "OPTIMAL":
                self._on_solve_finished(cached, 0.0, cached_msg, cached_status)
                self.status_bar.showMessage(
                    f"Loaded {len(cached)} proven optimal groups from cache")
                return

            estimate = self.svc.estimate_problem_size(n, k, j, s)
            if estimate['relation_checks'] > MAX_COVER_RELATION_CHECKS:
                if cached:
                    self._on_solve_finished(cached, 0.0, cached_msg, cached_status)
                    self.status_bar.showMessage(
                        f"Problem too large; loaded {len(cached)} cached groups")
                    return
                QMessageBox.warning(
                    self, "Problem Too Large",
                    "This parameter set is too large for the current solver.\n\n"
                    f"j-subsets: {estimate['num_j_subsets']:,}\n"
                    f"k-groups: {estimate['num_k_groups']:,}\n"
                    f"Coverage entries: {estimate['optimized_coverage_entries']:,}\n\n"
                    "Reduce n/k/j or import a known cover.")
                self.status_bar.showMessage("Problem too large")
                return

            # Start progress bar BEFORE heavy work begins
            budget_ms = int(
                (time_limit + SolverThread.ANNEALING_TIME_LIMIT + 10.0) * r * 1000)
            self.comp_tab.start_progress(budget_ms)
            self.status_bar.showMessage(
                f"Building model (n={n}, k={k}, j={j}, s={s}, limit={time_limit}s)...")

            # All heavy work (solver construction + ILP solve) runs in the thread
            worker = SolverThread(
                self.svc, n, k, j, s, samples,
                precomputed_hint=cached,
                precomputed_hint_status=cached_status or "FEASIBLE",
                num_rounds=r,
                time_limit_per_round=time_limit)
            self.solver_thread = worker
            worker.solve_finished.connect(
                lambda result, solve_time, method, status, w=worker:
                self._on_solve_finished(result, solve_time, method, status, w))
            worker.error.connect(
                lambda error_msg, w=worker: self._on_solve_error(error_msg, w))
            worker.round_progress.connect(self._on_round_progress)
            worker.building_model.connect(
                lambda: self.status_bar.showMessage("Building coverage model..."))
            worker.annealing.connect(
                lambda: self.status_bar.showMessage("Running simulated annealing heuristic..."))
            worker.finished.connect(worker.deleteLater)
            worker.start()

        except Exception as e:
            self.comp_tab.stop_progress()
            QMessageBox.critical(self, "Error", str(e))

    def _on_solve_finished(self, result, solve_time, method, status, worker=None):
        self.comp_tab.stop_progress()
        self.last_solve_time = solve_time
        self.last_method = method
        self.last_status = status

        p = self.comp_tab.get_params()
        samples = self.comp_tab.get_samples()
        self.svc.save_project_result_if_valid(
            p['n'], p['k'], p['j'], p['s'], samples, result, status, method)

        solver_owner = worker or self.solver_thread
        solver = getattr(solver_owner, 'solver', None) if solver_owner else None
        best_bound = getattr(solver, 'last_best_bound', None) if solver else None
        self.last_best_bound = best_bound
        gap_str = ""
        if best_bound and best_bound > 0 and len(result) > 0:
            gap = (len(result) - best_bound) / len(result) * 100
            gap_str = f" ({gap:.1f}% gap)"

        self.comp_tab.show_results(
            result, solve_time, method, status,
            stats={'best_bound': best_bound})

        msg = (f"Found {len(result)} groups in {solve_time:.3f}s  |  "
               f"Method: {method}  |  Status: {status}{gap_str}")
        if len(result) > MAX_DISPLAYED_GROUPS:
            msg += f"  |  Showing first {MAX_DISPLAYED_GROUPS}"
        self.status_bar.showMessage(msg)
        self._release_solver_thread(worker)

    def _on_solve_error(self, error_msg, worker=None):
        self.comp_tab.stop_progress()
        QMessageBox.critical(self, "Solver Error", error_msg)
        self.status_bar.showMessage("Solver failed")
        self._release_solver_thread(worker)

    def _release_solver_thread(self, worker=None):
        worker = worker or self.solver_thread
        if worker is None:
            return
        try:
            worker.solver = None
        except RuntimeError:
            pass
        if self.solver_thread is worker:
            self.solver_thread = None

    def _on_round_progress(self, current, total, best_size):
        self.comp_tab.set_round_info(current, total, best_size)
        self.status_bar.showMessage(
            f"Completed round {current} / {total}...")

    # ── Save / Export / Clear ────────────────────────────────────────────────

    def _verify_results(self):
        results = self.comp_tab.current_results
        if not results:
            QMessageBox.warning(self, "Error", "No results to verify.")
            return

        p = self.comp_tab.get_params()
        samples = self.comp_tab.get_samples()
        report = verify_solution_details(
            p['n'], p['k'], p['j'], p['s'], samples, results)
        self.comp_tab.show_verification(
            report, self.last_status, self.last_best_bound)

        if report['is_valid']:
            msg = (f"Verification passed: {report['covered_subsets']:,} / "
                   f"{report['total_subsets']:,} constraints covered")
        else:
            msg = f"Verification failed: {report['message']}"
        self.status_bar.showMessage(msg)

    def _save_results(self):
        results = self.comp_tab.current_results
        if not results:
            QMessageBox.warning(self, "Error", "No results to save.")
            return
        p = self.comp_tab.get_params()
        samples = self.comp_tab.get_samples()
        try:
            filename = self.db_manager.save_result(
                p['m'], p['n'], p['k'], p['j'], p['s'],
                samples, results,
                self.last_solve_time, self.last_method or "ILP",
                self.last_status or "UNKNOWN")
            QMessageBox.information(self, "Success", f"Saved to: {filename}")
            self.db_tab.refresh_list()
            self.status_bar.showMessage(f"Saved to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _export_results(self):
        results = self.comp_tab.current_results
        if not results:
            QMessageBox.warning(self, "Error", "No results to export.")
            return
        p = self.comp_tab.get_params()
        samples = self.comp_tab.get_samples()
        default_name = f"{p['m']}-{p['n']}-{p['k']}-{p['j']}-{p['s']}-results.txt"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Results", default_name,
            "Text Files (*.txt);;All Files (*)")
        if not filepath:
            return
        self._write_export(filepath, p, samples, results, self.last_method, self.last_status)

    def _export_db_result(self, filename):
        result = self.db_manager.load_result(filename)
        if not result:
            QMessageBox.critical(self, "Error", "Failed to load the selected record.")
            return
        default_name = filename.replace('.db', '.txt')
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export DB Record", default_name,
            "Text Files (*.txt);;All Files (*)")
        if not filepath:
            return
        p = {k: result[k] for k in ('m', 'n', 'k', 'j', 's')}
        self._write_export(
            filepath, p, result['samples'], result['groups'],
            result['method'], result.get('status', 'UNKNOWN'),
            extra_header=f"File       : {filename}\nCreated    : {result['created_at']}\n")
        self.status_bar.showMessage(f"Exported to {filepath}")

    def _write_export(self, filepath, p, samples, groups, method, status, extra_header=""):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("An Optimal Samples Selection System\n")
                f.write("=" * 44 + "\n")
                if extra_header:
                    f.write(extra_header)
                f.write(f"Parameters : m={p['m']}, n={p['n']}, "
                        f"k={p['k']}, j={p['j']}, s={p['s']}\n")
                f.write(f"Samples ({p['n']}): {', '.join(map(str, samples))}\n")
                f.write(f"Method     : {method}\n")
                f.write(f"Status     : {status}\n")
                f.write(f"Total Groups: {len(groups)}\n")
                f.write("=" * 44 + "\n\n")
                for i, group in enumerate(groups):
                    f.write(f"Group {i + 1:>4d}: {', '.join(map(str, group))}\n")
            QMessageBox.information(
                self, "Export Successful", f"Saved to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed:\n{e}")

    def _clear_all(self):
        self.comp_tab.clear_results()
        self.last_best_bound = None
        self.status_bar.showMessage("Cleared")

    # ── Load from DB ─────────────────────────────────────────────────────────

    def _load_from_db(self, result):
        self.comp_tab.m_combo.setCurrentText(str(result['m']))
        self.comp_tab.n_combo.setCurrentText(str(result['n']))
        self.comp_tab.k_combo.setCurrentText(str(result['k']))
        self.comp_tab.j_combo.setCurrentText(str(result['j']))
        self.comp_tab.s_combo.setCurrentText(str(result['s']))
        self.comp_tab.set_samples(result['samples'])

        self.last_solve_time = result['solve_time']
        self.last_method = result['method']
        self.last_status = result.get('status', 'UNKNOWN')
        self.last_best_bound = None

        self.comp_tab.show_results(
            result['groups'], result['solve_time'],
            result['method'], self.last_status)

        self._switch_tab(0)
        self.status_bar.showMessage(f"Loaded result into Computation tab")
