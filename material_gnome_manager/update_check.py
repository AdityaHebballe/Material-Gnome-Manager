from __future__ import annotations

import shutil
import subprocess
import sys

from . import manager


def _show_notification(commits: int) -> None:
    if shutil.which("notify-send") is None:
        return
    commit_text = "commit" if commits == 1 else "commits"
    try:
        result = subprocess.run(
            [
                "notify-send",
                "--app-name=Material GNOME Manager",
                "--icon=io.github.materialgnome.Manager",
                "--urgency=normal",
                "--expire-time=30000",
                "--action=update=Run Update",
                "Theme update available",
                f"Material GNOME has {commits} new {commit_text}.",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    if result.stdout.strip() == "update" and shutil.which("material-gnome-manager"):
        subprocess.Popen(
            ["material-gnome-manager", "--update"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main() -> int:
    try:
        commits = manager.check_scheduled_theme_update()
    except manager.ManagerError as exc:
        print(f"Material GNOME update check failed: {exc}", file=sys.stderr)
        return 1
    if commits:
        _show_notification(commits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
