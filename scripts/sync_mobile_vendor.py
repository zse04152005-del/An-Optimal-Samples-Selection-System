"""Sync vendored code for the mobile build.

The Android/iOS build (mobile/) uses a self-contained source tree.
To avoid buildozer configuration complexity, we vendor copies of:

- core/ -> mobile/core/
- database/ -> mobile/database/

Run this script after changing core/database.
"""

from __future__ import annotations

from pathlib import Path
import shutil

REPO_ROOT = Path(__file__).resolve().parents[1]

PAIRS = [
    (REPO_ROOT / "core" / "__init__.py", REPO_ROOT / "mobile" / "core" / "__init__.py"),
    (REPO_ROOT / "core" / "solver.py", REPO_ROOT / "mobile" / "core" / "solver.py"),
    (REPO_ROOT / "database" / "__init__.py", REPO_ROOT / "mobile" / "database" / "__init__.py"),
    (REPO_ROOT / "database" / "db_manager.py", REPO_ROOT / "mobile" / "database" / "db_manager.py"),
]


def main() -> None:
    for src, dst in PAIRS:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"Synced {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
