"""Mobile UI entry point (Kivy).

Targets Android/iOS builds.

This mobile app runs offline and uses the solver fallback (exact Branch-and-Bound)
by calling:

    solve_ilp(prefer_ortools=False, allow_pulp=False)

Exact solving can be slow; keep n small on mobile.
"""

from __future__ import annotations

import os
import sys
import random
import shutil
import threading
from typing import List

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty
from kivy.uix.screenmanager import Screen
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock

from core.solver import OptimalSamplesSolver
from core.solver import estimate_coverage_generation
from database.db_manager import DatabaseManager


MOBILE_WARNING_COVER_RELATION_CHECKS = 1_000_000
MOBILE_HARD_COVER_RELATION_CHECKS = 20_000_000
MAX_MOBILE_DISPLAYED_GROUPS = 1000
MOBILE_SOLVE_TIME_LIMIT_SECONDS = 180.0


def _parse_int(text: str, name: str) -> int:
    try:
        return int(str(text).strip())
    except Exception:
        raise ValueError(f"Invalid integer for {name}: {text!r}")


def _parse_samples(text: str) -> List[int]:
    text = str(text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return [int(p) for p in parts]


class ComputeScreen(Screen):
    m_text = StringProperty("45")
    n_text = StringProperty("9")
    k_text = StringProperty("6")
    j_text = StringProperty("4")
    s_text = StringProperty("4")

    mode = StringProperty("Random")
    samples_text = StringProperty("")
    status_text = StringProperty("Ready")
    results_text = StringProperty("")

    _samples: List[int] = []
    _last_groups = None
    _last_solve_time = 0.0
    _last_method = ""
    _last_status = "NOT_SOLVED"

    def generate_samples(self) -> None:
        try:
            m = _parse_int(self.ids.m_in.text, "m")
            n = _parse_int(self.ids.n_in.text, "n")

            if n <= 0:
                raise ValueError("n must be positive")
            if m <= 0:
                raise ValueError("m must be positive")

            if self.mode == "Random":
                if n > m:
                    raise ValueError("n must be <= m")
                self._samples = sorted(random.sample(range(1, m + 1), n))
            else:
                raw = self.ids.manual_samples.text
                samples = _parse_samples(raw)
                if len(samples) != n:
                    raise ValueError(f"Please enter exactly {n} samples")
                if len(set(samples)) != len(samples):
                    raise ValueError("Duplicate samples are not allowed")
                if any(x < 1 or x > m for x in samples):
                    raise ValueError(f"All samples must be between 1 and {m}")
                self._samples = sorted(samples)

            self.samples_text = ", ".join(map(str, self._samples))
            self.status_text = f"Selected {len(self._samples)} samples"
            self.results_text = ""
            self._last_groups = None
        except Exception as e:
            self.status_text = f"Error: {e}"

    def solve(self, force: bool = False) -> None:
        if not self._samples:
            self.status_text = "Please generate/select samples first"
            return

        try:
            n = _parse_int(self.ids.n_in.text, "n")
            k = _parse_int(self.ids.k_in.text, "k")
            j = _parse_int(self.ids.j_in.text, "j")
            s = _parse_int(self.ids.s_in.text, "s")
            if len(self._samples) != n:
                raise ValueError("Sample count does not match n")

            cached_groups, cached_status, cached_method = self.get_precomputed_solution(n, k, j, s)
            if cached_groups and cached_status == "OPTIMAL":
                self.apply_result(cached_groups, 0.0, cached_method, cached_status)
                self.status_text = f"Loaded proven optimal cache: {len(cached_groups)} groups"
                return

            estimate = self.estimate_problem_size(n, k, j, s)
            if estimate["relation_checks"] > MOBILE_HARD_COVER_RELATION_CHECKS:
                if cached_groups:
                    self.apply_result(cached_groups, 0.0, cached_method, cached_status)
                    self.status_text = (
                        "Too large for phone exact solving; loaded cached feasible result"
                    )
                    return
                self.status_text = (
                    "Too large for mobile memory. Please run this parameter set on desktop."
                )
                return

            if (
                estimate["relation_checks"] > MOBILE_WARNING_COVER_RELATION_CHECKS
                and not force
            ):
                self.show_large_problem_popup(estimate)
                return

        except Exception as e:
            self.status_text = f"Error: {e}"
            return

        self.status_text = "Solving on phone (CPU, exact fallback)..."
        self.results_text = ""

        def _run() -> None:
            try:
                solver = OptimalSamplesSolver(
                    n=n,
                    k=k,
                    j=j,
                    s=s,
                    samples=self._samples,
                    max_cover_relation_checks=MOBILE_HARD_COVER_RELATION_CHECKS,
                )
                groups, solve_time, method = solver.solve_ilp(
                    time_limit_seconds=MOBILE_SOLVE_TIME_LIMIT_SECONDS,
                    prefer_ortools=False,
                    allow_pulp=False,
                    initial_solution=cached_groups,
                    initial_solution_status=cached_status,
                )
                status = solver.last_status

                def _update(_dt):
                    self.apply_result(groups, solve_time, method, status)
                    if status == "OPTIMAL":
                        self.status_text = f"Done: {len(groups)} proven optimal groups"
                    else:
                        self.status_text = f"Done: {len(groups)} feasible groups; optimality not proven"

                Clock.schedule_once(_update, 0)
            except TimeoutError as e:
                if cached_groups:
                    def _use_cache(_dt):
                        self.apply_result(cached_groups, 0.0, cached_method, cached_status)
                        self.status_text = (
                            f"Exact solve timed out; loaded cached {cached_status} result"
                        )

                    Clock.schedule_once(_use_cache, 0)
                else:
                    Clock.schedule_once(lambda _dt: setattr(self, "status_text", f"Solver timeout: {e}"), 0)
            except Exception as e:
                Clock.schedule_once(lambda _dt: setattr(self, "status_text", f"Solver error: {e}"), 0)

        threading.Thread(target=_run, daemon=True).start()

    def estimate_problem_size(self, n: int, k: int, j: int, s: int) -> dict:
        estimate = estimate_coverage_generation(n, k, j, s)
        estimate["relation_checks"] = estimate["optimized_coverage_entries"]
        return estimate

    def show_large_problem_popup(self, estimate: dict) -> None:
        layout = BoxLayout(orientation="vertical", padding="12dp", spacing="10dp")
        message = (
            "This input is large for a phone.\n\n"
            f"j-subsets: {estimate['num_j_subsets']:,}\n"
            f"k-groups: {estimate['num_k_groups']:,}\n"
            f"Coverage entries: {estimate['optimized_coverage_entries']:,}\n"
            f"Naive pair checks avoided: {estimate['naive_relation_checks']:,}\n\n"
            "Desktop OR-Tools is recommended. Continue on phone?"
        )
        layout.add_widget(Label(text=message))

        buttons = BoxLayout(size_hint_y=None, height="44dp", spacing="8dp")
        cancel_btn = Button(text="Cancel")
        continue_btn = Button(text="Continue")
        buttons.add_widget(cancel_btn)
        buttons.add_widget(continue_btn)
        layout.add_widget(buttons)

        popup = Popup(title="Large Mobile Solve", content=layout, size_hint=(0.9, 0.65))
        cancel_btn.bind(on_release=popup.dismiss)
        continue_btn.bind(on_release=lambda *_: (popup.dismiss(), self.solve(force=True)))
        popup.open()

    def get_db(self) -> DatabaseManager:
        app = App.get_running_app()
        db_folder = os.path.join(app.user_data_dir, "results")
        return DatabaseManager(db_folder=db_folder)

    def get_precomputed_solution(self, n: int, k: int, j: int, s: int):
        db = self.get_db()
        cached = db.get_project_result(n, k, j, s)
        if cached:
            groups = self.map_canonical_groups_to_samples(cached["groups"])
            if cached["status"] == "OPTIMAL":
                return groups, "OPTIMAL", "Project result cache"
            best_groups = groups
            best_status = cached["status"]
            best_method = "Project result cache"
        else:
            best_groups = None
            best_status = "FEASIBLE"
            best_method = "Cached upper bound"

        standard_t = j if s == j else s
        standard = db.get_standard_cover(n, k, standard_t)
        if standard:
            groups = self.map_canonical_groups_to_samples(standard["blocks"])
            if s == j and standard["is_proven_optimal"]:
                db.save_project_result(
                    n, k, j, s, standard["blocks"], "OPTIMAL",
                    method="La Jolla Covering Repository",
                    source=standard["source_url"],
                )
                return groups, "OPTIMAL", "La Jolla exact cover cache"

            if best_groups is None or len(groups) < len(best_groups):
                best_groups = groups
                best_status = "FEASIBLE_CACHED"
                best_method = "La Jolla upper-bound cache"

        return best_groups, best_status, best_method

    def map_canonical_groups_to_samples(self, groups):
        samples = sorted(self._samples)
        return [tuple(samples[index - 1] for index in group) for group in groups]

    def map_sample_groups_to_canonical(self, groups):
        index_by_sample = {sample: i + 1 for i, sample in enumerate(sorted(self._samples))}
        return [tuple(sorted(index_by_sample[value] for value in group)) for group in groups]

    def apply_result(self, groups, solve_time: float, method: str, status: str) -> None:
        self._last_groups = groups
        self._last_solve_time = solve_time
        self._last_method = method
        self._last_status = status

        try:
            n = _parse_int(self.ids.n_in.text, "n")
            k = _parse_int(self.ids.k_in.text, "k")
            j = _parse_int(self.ids.j_in.text, "j")
            s = _parse_int(self.ids.s_in.text, "s")
            canonical_groups = self.map_sample_groups_to_canonical(groups)
            self.get_db().save_project_result(
                n, k, j, s, canonical_groups, status,
                method=method, source="mobile solve/cache",
            )
        except Exception:
            pass

        self.results_text = "\n".join(self.format_result_lines(groups, solve_time, method, status))

    def format_result_lines(self, groups, solve_time: float, method: str, status: str):
        lines = [
            f"Method: {method}",
            f"Status: {status}",
            f"Time: {solve_time:.3f}s",
            f"Groups: {len(groups)}",
            "",
        ]
        shown_groups = groups[:MAX_MOBILE_DISPLAYED_GROUPS]
        for idx, group in enumerate(shown_groups, 1):
            members = ", ".join(map(str, group))
            lines.append(f"{idx}. {members}")
        if len(groups) > MAX_MOBILE_DISPLAYED_GROUPS:
            lines.append("")
            lines.append(f"Showing first {MAX_MOBILE_DISPLAYED_GROUPS} groups only.")
        return lines

    def save_to_db(self) -> None:
        try:
            if not self._samples:
                self.status_text = "No samples selected"
                return
            if not self._last_groups:
                self.status_text = "No results to save"
                return

            m = _parse_int(self.ids.m_in.text, "m")
            n = _parse_int(self.ids.n_in.text, "n")
            k = _parse_int(self.ids.k_in.text, "k")
            j = _parse_int(self.ids.j_in.text, "j")
            s = _parse_int(self.ids.s_in.text, "s")

            app = App.get_running_app()
            db_folder = os.path.join(app.user_data_dir, "results")
            db = DatabaseManager(db_folder=db_folder)

            filename = db.save_result(
                m=m,
                n=n,
                k=k,
                j=j,
                s=s,
                samples=self._samples,
                groups=self._last_groups,
                solve_time=float(self._last_solve_time),
                method=str(self._last_method or "B&B"),
                status=str(self._last_status or "UNKNOWN"),
            )
            self.status_text = f"Saved: {filename}"
        except Exception as e:
            self.status_text = f"Save error: {e}"


class DatabaseScreen(Screen):
    filenames = ListProperty([])
    selected_filename = StringProperty("")
    preview_text = StringProperty("")

    def _get_db(self) -> DatabaseManager:
        app = App.get_running_app()
        db_folder = os.path.join(app.user_data_dir, "results")
        return DatabaseManager(db_folder=db_folder)

    def refresh(self) -> None:
        try:
            db = self._get_db()
            rows = db.list_results()
            self.filenames = [r["filename"] for r in rows]
            if self.filenames and (self.selected_filename not in self.filenames):
                self.selected_filename = self.filenames[0]
            self.preview_text = f"DB folder: {db.get_db_folder()}\nFiles: {len(self.filenames)}"
        except Exception as e:
            self.preview_text = f"Error: {e}"

    def preview(self) -> None:
        try:
            if not self.selected_filename:
                self.preview_text = "No file selected"
                return
            db = self._get_db()
            r = db.load_result(self.selected_filename)
            if not r:
                self.preview_text = "Failed to load"
                return

            lines = [
                f"File: {self.selected_filename}",
                f"Parameters: m={r['m']} n={r['n']} k={r['k']} j={r['j']} s={r['s']}",
                f"Samples: {r['samples']}",
                f"Method: {r['method']}",
                f"Status: {r.get('status', 'UNKNOWN')}",
                f"Time: {r['solve_time']:.3f}s",
                f"Created: {r['created_at']}",
                f"Groups: {r['num_groups']}",
                "",
            ]
            for i, g in enumerate(r["groups"][:MAX_MOBILE_DISPLAYED_GROUPS], 1):
                members = ", ".join(map(str, g))
                lines.append(f"{i}. {members}")
            if len(r["groups"]) > MAX_MOBILE_DISPLAYED_GROUPS:
                lines.append("")
                lines.append(f"Showing first {MAX_MOBILE_DISPLAYED_GROUPS} groups only.")

            self.preview_text = "\n".join(lines)
        except Exception as e:
            self.preview_text = f"Error: {e}"

    def load_into_compute(self) -> None:
        try:
            if not self.selected_filename:
                self.preview_text = "No file selected"
                return
            db = self._get_db()
            r = db.load_result(self.selected_filename)
            if not r:
                self.preview_text = "Failed to load"
                return

            compute = self.manager.get_screen("compute")

            compute.ids.m_in.text = str(r["m"])
            compute.ids.n_in.text = str(r["n"])
            compute.ids.k_in.text = str(r["k"])
            compute.ids.j_in.text = str(r["j"])
            compute.ids.s_in.text = str(r["s"])

            compute._samples = list(r["samples"])
            compute.samples_text = ", ".join(map(str, r["samples"]))

            lines = [
                f"Loaded: {self.selected_filename}",
                f"Method: {r['method']}",
                f"Status: {r.get('status', 'UNKNOWN')}",
                f"Time: {r['solve_time']:.3f}s",
                f"Groups: {r['num_groups']}",
                "",
            ]
            for idx, g in enumerate(r["groups"][:MAX_MOBILE_DISPLAYED_GROUPS], 1):
                members = ", ".join(map(str, g))
                lines.append(f"{idx}. {members}")
            if len(r["groups"]) > MAX_MOBILE_DISPLAYED_GROUPS:
                lines.append("")
                lines.append(f"Showing first {MAX_MOBILE_DISPLAYED_GROUPS} groups only.")

            compute._last_groups = r["groups"]
            compute._last_solve_time = r["solve_time"]
            compute._last_method = r["method"]
            compute._last_status = r.get("status", "UNKNOWN")
            compute.results_text = "\n".join(lines)
            compute.status_text = "Loaded from DB"

            self.manager.current = "compute"
        except Exception as e:
            self.preview_text = f"Error: {e}"

    def delete_selected(self) -> None:
        try:
            if not self.selected_filename:
                self.preview_text = "No file selected"
                return
            db = self._get_db()
            ok = db.delete_result(self.selected_filename)
            if ok:
                deleted = self.selected_filename
                self.selected_filename = ""
                self.refresh()
                self.preview_text = f"Deleted: {deleted}"
            else:
                self.preview_text = "Delete failed"
        except Exception as e:
            self.preview_text = f"Error: {e}"


class MobileApp(App):
    def build(self):
        self.ensure_known_covers_cache()
        return Builder.load_file(os.path.join(os.path.dirname(__file__), "app.kv"))

    def ensure_known_covers_cache(self) -> None:
        db_folder = os.path.join(self.user_data_dir, "results")
        os.makedirs(db_folder, exist_ok=True)

        bundled = os.path.join(os.path.dirname(__file__), "results", "known_covers.sqlite")
        target = os.path.join(db_folder, "known_covers.sqlite")
        if os.path.exists(bundled) and not os.path.exists(target):
            shutil.copyfile(bundled, target)

        DatabaseManager(db_folder=db_folder).seed_builtin_known_covers()


if __name__ == "__main__":
    MobileApp().run()
