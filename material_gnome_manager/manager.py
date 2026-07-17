from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


APP_NAME = "material-gnome-manager"
THEME_NAME = "Material-Gnome"
DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
STATE_FILE = DATA_DIR / "state.json"
BACKUP_DIR = DATA_DIR / "backup"
GITHUB_REPO_URL = "https://github.com/SakibShahariar/material-gnome-theme.git"
GITHUB_SOURCE_DIR = DATA_DIR / "material-gnome-theme"
INSTALL_DIR = Path.home() / ".themes" / THEME_NAME
GTK4_CONFIG_DIR = Path.home() / ".config" / "gtk-4.0"

REQUIRED_SOURCE_PATHS = (
    "index.theme",
    "gtk-3.0/colors.css",
    "gtk-4.0/colors.css",
    "gnome-shell/gnome-shell-template.css",
    "themes",
)

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
SHELL_TOKEN_RE = re.compile(r"\{\{colors\.([a-z0-9_]+)\.default\.(hex|red|green|blue)\}\}")
MANAGER_LAYOUT_START = "/* Material GNOME Manager: Top Bar Layout Start */"
MANAGER_LAYOUT_END = "/* Material GNOME Manager: Top Bar Layout End */"
MANAGER_ANIMATIONS_START = "/* Material GNOME Manager: Reduced Animations Start */"
MANAGER_ANIMATIONS_END = "/* Material GNOME Manager: Reduced Animations End */"
ANIMATION_DECL_RE = re.compile(
    r"(?m)(^|[{\s;])([ \t]*)(animation(?:-[a-zA-Z-]+)?|transition(?:-[a-zA-Z-]+)?)\s*:[^;]*;"
)
GTK_ANIMATION_FILES = (
    "gtk-3.0/gtk.css",
    "gtk-3.0/gtk-dark.css",
    "gtk-4.0/gtk.css",
    "gtk-4.0/gtk-dark.css",
)
LAYOUT_COLOR_MAP = {
    # Current upstream layouts use this palette (as of July 2026).
    "#dfc2a3": "primary",
    "#3f2d17": "on_primary",
    "#151311": "surface",
    "#221f1d": "surface_container",
    "#e8e1dd": "on_surface",
    # Retain the original palette so locally checked-out older sources work too.
    "#b1c5ff": "primary",
    "#002c71": "on_primary",
    "#11131a": "surface",
    "#1d1f27": "surface_container",
    "#e1e2ec": "on_surface",
    "#ffb4ab": "error",
    "#ffb695": "error",
    "#571e00": "on_error",
    "#f3ded7": "on_error_container",
}
GTK_NAMED_COLOR_TOKEN_MAP = {
    "theme_fg_color": "on_surface",
    "theme_text_color": "on_surface",
    "theme_bg_color": "surface",
    "theme_base_color": "surface_container",
    "theme_selected_bg_color": "primary",
    "theme_selected_fg_color": "on_primary",
    "insensitive_bg_color": "surface_container_low",
    "insensitive_fg_color": "on_surface_variant",
    "insensitive_base_color": "surface",
    "theme_unfocused_fg_color": "on_surface_variant",
    "theme_unfocused_text_color": "on_surface_variant",
    "theme_unfocused_bg_color": "surface",
    "theme_unfocused_base_color": "surface_container_low",
    "theme_unfocused_selected_bg_color": "secondary_container",
    "theme_unfocused_selected_fg_color": "on_secondary_container",
    "unfocused_insensitive_color": "on_surface_variant",
    "borders": "outline_variant",
    "unfocused_borders": "outline_variant",
    "warning_color": "tertiary",
    "error_color": "error",
    "success_color": "primary",
    "wm_focused_title": "primary",
    "wm_unfocused_title": "on_surface_variant",
    "wm_highlight": "primary",
    "wm_border": "shadow",
    "wm_focused_bg": "surface",
    "wm_unfocused_bg": "surface",
    "wm_button_icon": "on_surface",
    "wm_button_focused_bg": "surface_container",
    "wm_button_unfocused_bg": "surface_container_low",
    "wm_button_hover_fg": "on_primary_container",
    "wm_button_active_fg": "on_primary_container",
    "wm_button_hover_bg": "primary_container",
    "wm_button_active_bg": "primary_container",
    "content_view_bg": "surface_container",
    "placeholder_text_color": "primary",
    "text_view_bg": "surface_container",
    "accent_bg_color": "primary_container",
    "accent_fg_color": "on_primary_container",
    "accent_color": "primary",
    "destructive_bg_color": "error_container",
    "destructive_fg_color": "on_error_container",
    "destructive_color": "error",
    "success_bg_color": "secondary_container",
    "success_fg_color": "on_secondary_container",
    "warning_bg_color": "tertiary_container",
    "warning_fg_color": "on_tertiary_container",
    "error_bg_color": "error_container",
    "error_fg_color": "on_error_container",
    "window_bg_color": "surface",
    "window_fg_color": "on_surface",
    "view_bg_color": "surface_container",
    "view_fg_color": "on_surface",
    "headerbar_bg_color": "surface",
    "headerbar_fg_color": "primary",
    "headerbar_border_color": "outline_variant",
    "headerbar_backdrop_color": "surface",
    "headerbar_shade_color": "shadow",
    "card_bg_color": "surface_container",
    "card_fg_color": "on_surface",
    "card_shade_color": "shadow",
    "dialog_bg_color": "surface_container_high",
    "dialog_fg_color": "on_surface",
    "popover_bg_color": "surface_container_high",
    "popover_fg_color": "on_surface",
    "shade_color": "shadow",
    "scrollbar_outline_color": "outline_variant",
}


class ManagerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PresetPreview:
    name: str
    colors: dict[str, str]


@dataclass(frozen=True)
class ThemeStatus:
    source_dir: Path | None
    source_valid: bool
    source_message: str
    github_source_dir: Path
    github_state: str
    installed: bool
    gtk_css_state: str
    gtk_dark_css_state: str
    gtk_colors_state: str
    matugen_state: str
    current_wallpaper: Path | None
    presets: list[str]
    layouts: list[str]
    last_preset: str | None
    current_preset: str | None
    active_layout: str | None
    reduced_animations: bool


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"created_files": []}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"created_files": []}
    if not isinstance(data, dict):
        return {"created_files": []}
    data.setdefault("created_files", [])
    return data


def save_state(state: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def set_source_dir(path: Path) -> None:
    source = path.expanduser().resolve()
    valid, message = validate_source(source)
    if not valid:
        raise ManagerError(message)
    state = load_state()
    state["source_dir"] = str(source)
    state["source_kind"] = "local"
    save_state(state)


def use_github_source() -> None:
    valid, message = validate_source(GITHUB_SOURCE_DIR)
    if not valid:
        raise ManagerError(message)
    state = load_state()
    state["source_dir"] = str(GITHUB_SOURCE_DIR)
    state["source_kind"] = "github"
    save_state(state)


def get_source_dir() -> Path | None:
    value = load_state().get("source_dir")
    if not value:
        return None
    return Path(value).expanduser()


def validate_source(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"Source does not exist: {path}"
    if not path.is_dir():
        return False, f"Source is not a directory: {path}"
    missing = [item for item in REQUIRED_SOURCE_PATHS if not (path / item).exists()]
    if missing:
        return False, "Missing required theme files: " + ", ".join(missing)
    return True, "Valid Material GNOME source"


def list_presets(source: Path | None = None) -> list[str]:
    source = source or get_source_dir()
    if source is None:
        return []
    themes_dir = source / "themes"
    if not themes_dir.is_dir():
        return []
    return sorted(path.stem for path in themes_dir.glob("*.json"))


def get_preset_previews(source: Path | None = None) -> list[PresetPreview]:
    source = source or get_source_dir()
    if source is None:
        return []
    previews: list[PresetPreview] = []
    for name in list_presets(source):
        path = source / "themes" / f"{name}.json"
        try:
            colors = _load_colors(path)
        except ManagerError:
            continue
        previews.append(PresetPreview(name=name, colors=colors))
    return previews


def get_preview_colors(source: Path | None = None) -> dict[str, str]:
    """Return the installed palette when available, otherwise the source default."""
    source = source or get_source_dir()
    if source is None:
        return {}
    if INSTALL_DIR.is_dir():
        try:
            return _load_installed_colors()
        except ManagerError:
            pass
    return _load_source_default_colors(source)


def get_current_preset_name(source: Path | None = None) -> str | None:
    source = source or get_source_dir()
    if source is None:
        return None
    state = load_state()
    last_preset = state.get("last_preset")
    presets = set(list_presets(source))
    if isinstance(last_preset, str) and last_preset in presets:
        return last_preset
    return infer_installed_preset(source)


def infer_installed_preset(source: Path | None = None) -> str | None:
    source = source or get_source_dir()
    if source is None or not INSTALL_DIR.is_dir():
        return None
    try:
        installed = _load_installed_colors()
    except ManagerError:
        return None
    required = _tokens_from_gtk4(source / "gtk-4.0" / "colors.css")
    for preview in get_preset_previews(source):
        if all(installed.get(token) == preview.colors.get(token) for token in required):
            return preview.name
    return None


def list_layouts(source: Path | None = None) -> list[str]:
    source = source or get_source_dir()
    if source is None:
        return []
    layouts_dir = source / "gnome-shell" / "layouts"
    if not layouts_dir.is_dir():
        return []
    return sorted(
        path.stem
        for path in layouts_dir.glob("*.css")
        if path.name != "active-layout.css"
    )


def get_status() -> ThemeStatus:
    state = load_state()
    source = get_source_dir()
    if source is None:
        valid = False
        message = "No source directory selected"
    else:
        valid, message = validate_source(source)
    return ThemeStatus(
        source_dir=source,
        source_valid=valid,
        source_message=message,
        github_source_dir=GITHUB_SOURCE_DIR,
        github_state=get_github_source_state(),
        installed=INSTALL_DIR.is_dir(),
        gtk_css_state=_gtk_link_state("gtk.css"),
        gtk_dark_css_state=_gtk_link_state("gtk-dark.css"),
        gtk_colors_state=_gtk_link_state("colors.css"),
        matugen_state=get_matugen_state(),
        current_wallpaper=get_current_wallpaper_path(),
        presets=list_presets(source if valid else None),
        layouts=list_layouts(source if valid else None),
        last_preset=state.get("last_preset"),
        current_preset=get_current_preset_name(source if valid else None),
        active_layout=state.get("active_layout"),
        reduced_animations=bool(state.get("reduced_animations")),
    )


def fetch_or_update_github_source() -> str:
    if shutil.which("git") is None:
        raise ManagerError("git is not installed")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not GITHUB_SOURCE_DIR.exists():
        _run_git(["clone", GITHUB_REPO_URL, str(GITHUB_SOURCE_DIR)])
        use_github_source()
        return f"Fetched Material GNOME from GitHub into {GITHUB_SOURCE_DIR}"

    if not (GITHUB_SOURCE_DIR / ".git").is_dir():
        raise ManagerError(f"GitHub source path exists but is not a git repository: {GITHUB_SOURCE_DIR}")

    remote_url = _run_git(["-C", str(GITHUB_SOURCE_DIR), "remote", "get-url", "origin"]).strip()
    if remote_url != GITHUB_REPO_URL:
        raise ManagerError(f"GitHub source has unexpected origin: {remote_url}")

    _run_git(["-C", str(GITHUB_SOURCE_DIR), "fetch", "--prune", "origin"])
    remote_ref = _remote_head_ref()
    if not remote_ref:
        raise ManagerError("Could not determine origin default branch")

    ahead, behind = _ahead_behind(remote_ref)
    if behind:
        _run_git(["-C", str(GITHUB_SOURCE_DIR), "merge", "--ff-only", remote_ref])
    use_github_source()

    if behind:
        return f"Updated GitHub source by {behind} commit(s)"
    if ahead:
        return f"GitHub source selected, but local clone is {ahead} commit(s) ahead of origin"
    return "GitHub source is already up to date"


def update_github_source_and_installed_theme() -> str:
    installed = INSTALL_DIR.is_dir()
    installed_colors: dict[str, str] | None = None
    if installed:
        try:
            installed_colors = _load_installed_colors()
        except ManagerError:
            installed_colors = None

    message = fetch_or_update_github_source()
    if not installed:
        return message

    source = _require_source()
    colors = _merge_with_source_default_colors(source, installed_colors)
    _install_theme_from_source(source, colors=colors)
    return f"{message}. Refreshed installed theme files."


def check_github_updates() -> str:
    if shutil.which("git") is None:
        raise ManagerError("git is not installed")
    if not GITHUB_SOURCE_DIR.exists():
        return "GitHub source has not been fetched"
    if not (GITHUB_SOURCE_DIR / ".git").is_dir():
        raise ManagerError(f"GitHub source path exists but is not a git repository: {GITHUB_SOURCE_DIR}")

    _run_git(["-C", str(GITHUB_SOURCE_DIR), "fetch", "--prune", "origin"])
    use_github_source()
    return get_github_source_state()


def get_github_source_state() -> str:
    if not GITHUB_SOURCE_DIR.exists():
        return "not fetched"
    if not (GITHUB_SOURCE_DIR / ".git").is_dir():
        return "path exists but is not a git repository"
    valid, message = validate_source(GITHUB_SOURCE_DIR)
    if not valid:
        return message
    remote_ref = _remote_head_ref()
    if not remote_ref:
        return "fetched; update to check remote branch"
    try:
        ahead, behind = _ahead_behind(remote_ref)
    except ManagerError as exc:
        return str(exc)
    if ahead and behind:
        return f"diverged from origin ({ahead} ahead, {behind} behind)"
    if behind:
        return f"update available ({behind} commit(s) behind)"
    if ahead:
        return f"local clone ahead of origin ({ahead} commit(s))"
    return "up to date"


def install_theme() -> str:
    source = _require_source()
    _install_theme_from_source(source)
    return f"Installed {THEME_NAME} to {INSTALL_DIR}"


def _install_theme_from_source(source: Path, colors: dict[str, str] | None = None) -> None:
    _reset_backup("install")
    if INSTALL_DIR.exists() or INSTALL_DIR.is_symlink():
        _backup_path(INSTALL_DIR)
        if INSTALL_DIR.is_dir() and not INSTALL_DIR.is_symlink():
            shutil.rmtree(INSTALL_DIR)
        else:
            INSTALL_DIR.unlink()
    INSTALL_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, INSTALL_DIR, ignore=_copy_ignore)
    if colors is not None:
        _write_installed_colors(source, colors)
    if load_state().get("reduced_animations"):
        installed_colors = _load_installed_colors()
        _write_shell_css(source, installed_colors)
        _write_gtk_animation_overrides(source, True)


def apply_preset(preset_name: str) -> str:
    source = _require_source()
    if not INSTALL_DIR.is_dir():
        install_theme()

    preset_path = source / "themes" / f"{preset_name}.json"
    colors = _load_colors(preset_path)
    _apply_colors(colors)

    state = load_state()
    state["last_preset"] = preset_name
    save_state(state)
    return f"Applied preset {preset_name} to installed theme"


def apply_matugen_from_current_wallpaper() -> str:
    wallpaper = get_current_wallpaper_path()
    if wallpaper is None:
        raise ManagerError("No current wallpaper image was detected")
    return apply_matugen_from_image(wallpaper, label="Current Wallpaper")


def apply_matugen_from_image(path: Path, label: str | None = None) -> str:
    _require_source()
    if not INSTALL_DIR.is_dir():
        install_theme()

    image = path.expanduser().resolve()
    colors = _matugen_colors_from_image(image)
    _apply_colors(colors)

    name = label or image.name
    state = load_state()
    state["last_preset"] = f"Matugen: {name}"
    state["last_matugen_image"] = str(image)
    save_state(state)
    return f"Generated and applied Matugen colors from {name}"


def apply_top_bar_layout(layout_name: str) -> str:
    source = _require_source()
    if not INSTALL_DIR.is_dir():
        install_theme()
    layout_path = source / "gnome-shell" / "layouts" / f"{layout_name}.css"
    if not layout_path.is_file() or layout_name not in list_layouts(source):
        raise ManagerError(f"Unknown top bar layout: {layout_name}")

    _reset_backup("shell-options")
    _backup_shell_option_targets()

    state = load_state()
    state["active_layout"] = layout_name
    save_state(state)
    colors = _load_installed_colors()
    _write_shell_css(source, colors)
    _write_active_layout(source, colors, layout_name)
    return "Applied top bar layout. Log out and back in to see the change."


def set_reduced_animations(enabled: bool) -> str:
    source = _require_source()
    if not INSTALL_DIR.is_dir():
        install_theme()

    _reset_backup("animations")
    _backup_animation_targets()

    state = load_state()
    state["reduced_animations"] = enabled
    save_state(state)
    colors = _load_installed_colors()
    _write_shell_css(source, colors)
    _write_gtk_animation_overrides(source, enabled)
    return (
        "Reduced GTK animations enabled"
        if enabled
        else "Reduced GTK animations disabled"
    )


def get_matugen_state() -> str:
    executable = shutil.which("matugen")
    if executable is None:
        return "not installed"
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "installed"
    return (result.stdout or result.stderr or "installed").strip()


def get_current_wallpaper_path() -> Path | None:
    for key in ("picture-uri-dark", "picture-uri"):
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.background", key],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
        value = result.stdout.strip().strip("'")
        path = _path_from_uri(value)
        if path and path.is_file():
            return path
    return None


def _apply_colors(colors: dict[str, str]) -> None:
    source = _require_source()
    _reset_backup("preset")
    gtk3_target = INSTALL_DIR / "gtk-3.0" / "colors.css"
    gtk4_target = INSTALL_DIR / "gtk-4.0" / "colors.css"
    shell_target = INSTALL_DIR / "gnome-shell" / "gnome-shell.css"
    active_layout_target = INSTALL_DIR / "gnome-shell" / "layouts" / "active-layout.css"
    for target in (gtk3_target, gtk4_target, shell_target, active_layout_target):
        _backup_path(target)

    _write_installed_colors(source, colors)


def _write_installed_colors(source: Path, colors: dict[str, str]) -> None:
    colors = _merge_with_source_default_colors(source, colors)
    gtk3_target = INSTALL_DIR / "gtk-3.0" / "colors.css"
    gtk4_target = INSTALL_DIR / "gtk-4.0" / "colors.css"
    gtk3_target.write_text(_render_gtk3(source / "gtk-3.0" / "colors.css", colors), encoding="utf-8")
    gtk4_target.write_text(_render_gtk4(source / "gtk-4.0" / "colors.css", colors), encoding="utf-8")
    _write_shell_css(source, colors)
    active_layout = load_state().get("active_layout")
    if isinstance(active_layout, str) and active_layout in list_layouts(source):
        _write_active_layout(source, colors, active_layout)


def enable_gtk4_links() -> str:
    if not (INSTALL_DIR / "gtk-4.0" / "gtk.css").exists():
        raise ManagerError("Install the theme before enabling GTK4 links")

    _reset_backup("gtk4-links")
    GTK4_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for name in ("gtk.css", "gtk-dark.css", "colors.css"):
        target = GTK4_CONFIG_DIR / name
        source = INSTALL_DIR / "gtk-4.0" / name
        _replace_with_symlink(target, source)
        created.append(str(target))

    state = load_state()
    existing = set(state.get("created_files", []))
    existing.update(created)
    state["created_files"] = sorted(existing)
    save_state(state)
    return "GTK4 links enabled"


def reset_gtk4_links() -> str:
    state = load_state()
    created = {Path(value) for value in state.get("created_files", [])}
    for target in (
        GTK4_CONFIG_DIR / "gtk.css",
        GTK4_CONFIG_DIR / "gtk-dark.css",
        GTK4_CONFIG_DIR / "colors.css",
    ):
        if target in created and target.is_symlink():
            target.unlink()
    _restore_backup("gtk4-links")
    state["created_files"] = [
        value for value in state.get("created_files", []) if Path(value).exists()
    ]
    save_state(state)
    return "GTK4 links reset"


def safe_reset() -> str:
    reset_gtk4_links()
    return "Safe reset complete"


def _require_source() -> Path:
    source = get_source_dir()
    if source is None:
        raise ManagerError("Select a Material GNOME source directory first")
    valid, message = validate_source(source)
    if not valid:
        raise ManagerError(message)
    return source


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {".git", "__pycache__", ".pytest_cache"}
    if Path(directory).name == THEME_NAME:
        ignored.add("backups")
    return ignored.intersection(names)


def _load_colors(path: Path) -> dict[str, str]:
    if not path.exists():
        raise ManagerError(f"Preset does not exist: {path.name}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManagerError(f"Invalid JSON preset: {path.name}") from exc
    return _extract_colors(raw, path.name)


def _load_installed_colors() -> dict[str, str]:
    path = INSTALL_DIR / "gtk-4.0" / "colors.css"
    if not path.is_file():
        source = _require_source()
        path = source / "gtk-4.0" / "colors.css"
    colors: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*--([a-z0-9_]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", line)
        if match:
            colors[match.group(1)] = match.group(2).upper()
    _validate_required_tokens(colors)
    return colors


def _merge_with_source_default_colors(
    source: Path,
    colors: dict[str, str] | None,
) -> dict[str, str]:
    merged = _load_source_default_colors(source)
    if colors:
        merged.update(colors)
    return merged


def _load_source_default_colors(source: Path) -> dict[str, str]:
    colors: dict[str, str] = {}
    gtk3_path = source / "gtk-3.0" / "colors.css"
    gtk4_path = source / "gtk-4.0" / "colors.css"

    if gtk3_path.is_file():
        for line in gtk3_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"@define-color\s+([a-z0-9_]+)\s+(#[0-9a-fA-F]{6})\s*;", line)
            if match:
                colors[match.group(1)] = match.group(2).upper()

    if gtk4_path.is_file():
        for line in gtk4_path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*--([a-z0-9_]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", line)
            if match:
                colors[match.group(1)] = match.group(2).upper()

    return colors


def _backup_shell_option_targets() -> None:
    for target in (
        INSTALL_DIR / "gnome-shell" / "gnome-shell.css",
        INSTALL_DIR / "gnome-shell" / "layouts" / "active-layout.css",
    ):
        _backup_path(target)


def _backup_animation_targets() -> None:
    _backup_shell_option_targets()
    for relative in GTK_ANIMATION_FILES:
        _backup_path(INSTALL_DIR / relative)


def _write_gtk_animation_overrides(source: Path, enabled: bool) -> None:
    for relative in GTK_ANIMATION_FILES:
        target = INSTALL_DIR / relative
        source_file = source / relative
        if not source_file.is_file():
            continue
        text = source_file.read_text(encoding="utf-8")
        if enabled:
            text = _reduce_gtk_animations(text)
        target.write_text(text, encoding="utf-8")


def _remove_manager_block(text: str) -> str:
    pattern = re.compile(
        rf"\n?{re.escape(MANAGER_ANIMATIONS_START)}.*?{re.escape(MANAGER_ANIMATIONS_END)}\n?",
        re.DOTALL,
    )
    return pattern.sub("\n", text).rstrip() + "\n"


def _gtk_reduced_animations_block() -> str:
    return (
        f"{MANAGER_ANIMATIONS_START}\n"
        "/* GTK keyframes and transition declarations were disabled from this file. */\n"
        f"{MANAGER_ANIMATIONS_END}\n"
    )


def _reduce_gtk_animations(text: str) -> str:
    text = _reduce_css_motion(text)
    return text.rstrip() + "\n\n" + _gtk_reduced_animations_block()


def _reduce_css_motion(text: str) -> str:
    text = ANIMATION_DECL_RE.sub(_replace_animation_declaration, text)
    return _remove_keyframes(text)


def _replace_animation_declaration(match: re.Match[str]) -> str:
    prefix, indent, property_name = match.group(1), match.group(2), match.group(3)
    if property_name.startswith("animation"):
        return f"{prefix}{indent}animation: none;"
    return f"{prefix}{indent}transition: none;"


def _remove_keyframes(text: str) -> str:
    output: list[str] = []
    index = 0
    while True:
        start = text.find("@keyframes", index)
        if start == -1:
            output.append(text[index:])
            break
        opening_brace = text.find("{", start)
        if opening_brace == -1:
            output.append(text[index:])
            break
        depth = 0
        end = opening_brace
        while end < len(text):
            char = text[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end += 1
                    break
            end += 1
        if depth != 0:
            output.append(text[index:])
            break
        output.append(text[index:start])
        name = text[start + len("@keyframes") : opening_brace].strip() or "unnamed"
        output.append(f"/* Material GNOME Manager disabled @keyframes {name}. */")
        index = end
    return "".join(output)


def _write_shell_css(source: Path, colors: dict[str, str]) -> None:
    shell_target = INSTALL_DIR / "gnome-shell" / "gnome-shell.css"
    text = _render_shell(source / "gnome-shell" / "gnome-shell-template.css", colors)
    state = load_state()
    active_layout = state.get("active_layout")
    if isinstance(active_layout, str) and active_layout in list_layouts(source):
        text += "\n" + _render_layout_block(source, colors, active_layout)
    if state.get("reduced_animations"):
        text = _reduce_css_motion(text)
        text += "\n" + _reduced_animations_block()
    shell_target.write_text(text, encoding="utf-8")


def _write_active_layout(source: Path, colors: dict[str, str], layout_name: str) -> None:
    target = INSTALL_DIR / "gnome-shell" / "layouts" / "active-layout.css"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render_layout(source, colors, layout_name), encoding="utf-8")


def _render_layout_block(source: Path, colors: dict[str, str], layout_name: str) -> str:
    return (
        f"{MANAGER_LAYOUT_START}\n"
        f"/* Active layout: {layout_name}. Log out and back in to see changes. */\n"
        f"{_render_layout(source, colors, layout_name).rstrip()}\n"
        f"{MANAGER_LAYOUT_END}\n"
    )


def _render_layout(source: Path, colors: dict[str, str], layout_name: str) -> str:
    path = source / "gnome-shell" / "layouts" / f"{layout_name}.css"
    text = path.read_text(encoding="utf-8")
    for original, token in LAYOUT_COLOR_MAP.items():
        if token in colors:
            text = re.sub(re.escape(original), colors[token], text, flags=re.IGNORECASE)
    return text.rstrip() + "\n"


def _reduced_animations_block() -> str:
    return (
        f"{MANAGER_ANIMATIONS_START}\n"
        "/* GNOME Shell animation and transition declarations were disabled. */\n"
        "/* Log out and back in to see changes. */\n"
        f"{MANAGER_ANIMATIONS_END}\n"
    )


def _matugen_colors_from_image(path: Path) -> dict[str, str]:
    executable = shutil.which("matugen")
    if executable is None:
        raise ManagerError("matugen is not installed")
    if not path.is_file():
        raise ManagerError(f"Image does not exist: {path}")
    try:
        result = subprocess.run(
            [
                executable,
                "image",
                "--dry-run",
                "--json",
                "hex",
                "--source-color-index",
                "0",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if detail:
            raise ManagerError(detail) from exc
        raise ManagerError("matugen failed to generate colors") from exc
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManagerError("matugen returned invalid JSON") from exc
    return _extract_colors(raw, path.name)


def _extract_colors(raw: Any, label: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ManagerError(f"Color data is not a JSON object: {label}")
    colors_obj = raw.get("colors")
    if not isinstance(colors_obj, dict):
        raise ManagerError(f"Color data has no colors object: {label}")

    colors: dict[str, str] = {}
    for token, token_obj in colors_obj.items():
        try:
            color = token_obj["default"]["color"]
        except (KeyError, TypeError) as exc:
            raise ManagerError(f"Color token is missing default.color: {token}") from exc
        if not isinstance(color, str) or not HEX_RE.match(color):
            raise ManagerError(f"Color token has invalid hex color: {token}")
        colors[token] = color.upper()
    _validate_required_tokens(colors)
    return colors


def _path_from_uri(value: str) -> Path | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme:
        return None
    return Path(value).expanduser()


def _validate_required_tokens(colors: dict[str, str]) -> None:
    required = set(_tokens_from_gtk3(get_source_dir() / "gtk-3.0" / "colors.css"))
    required.update(_tokens_from_gtk4(get_source_dir() / "gtk-4.0" / "colors.css"))
    missing = sorted(required.difference(colors))
    if missing:
        raise ManagerError("Preset is missing required color tokens: " + ", ".join(missing))


def _tokens_from_gtk3(path: Path) -> list[str]:
    tokens: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"@define-color\s+([a-z0-9_]+)\s+", line)
        if match:
            tokens.append(match.group(1))
    return tokens


def _tokens_from_gtk4(path: Path) -> list[str]:
    tokens: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*--([a-z0-9_]+)\s*:", line)
        if match:
            tokens.append(match.group(1))
    return tokens


def _render_gtk3(template: Path, colors: dict[str, str]) -> str:
    lines: list[str] = []
    for line in template.read_text(encoding="utf-8").splitlines():
        match = re.match(r"(@define-color\s+)([a-z0-9_]+)(\s+)(#[0-9a-fA-F]{6})(;.*)", line)
        if match and match.group(2) in colors:
            lines.append(f"{match.group(1)}{match.group(2)}{match.group(3)}{colors[match.group(2)]}{match.group(5)}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def _render_gtk4(template: Path, colors: dict[str, str]) -> str:
    lines: list[str] = []
    for line in template.read_text(encoding="utf-8").splitlines():
        match = re.match(r"(\s*--)([a-z0-9_]+)(\s*:\s*)(#[0-9a-fA-F]{6})(;.*)", line)
        if match and match.group(2) in colors:
            lines.append(f"{match.group(1)}{match.group(2)}{match.group(3)}{colors[match.group(2)]}{match.group(5)}")
            continue
        named_match = re.match(
            r"(@define-color\s+)([a-z0-9_-]+)(\s+)(#[0-9a-fA-F]{6})(;.*)",
            line,
        )
        if named_match:
            token = GTK_NAMED_COLOR_TOKEN_MAP.get(named_match.group(2))
            if token in colors:
                lines.append(
                    f"{named_match.group(1)}{named_match.group(2)}{named_match.group(3)}"
                    f"{colors[token]}{named_match.group(5)}"
                )
                continue
        lines.append(line)
    return "\n".join(lines) + "\n"


def _render_shell(template: Path, colors: dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        token, attr = match.groups()
        if token not in colors:
            raise ManagerError(f"Shell template needs missing color token: {token}")
        if attr == "hex":
            return colors[token]
        red, green, blue = _hex_to_rgb(colors[token])
        return {"red": red, "green": green, "blue": blue}[attr]

    return SHELL_TOKEN_RE.sub(replace, text)


def _hex_to_rgb(value: str) -> tuple[str, str, str]:
    return (
        str(int(value[1:3], 16)),
        str(int(value[3:5], 16)),
        str(int(value[5:7], 16)),
    )


def _gtk_link_state(name: str) -> str:
    target = GTK4_CONFIG_DIR / name
    expected = INSTALL_DIR / "gtk-4.0" / name
    if not target.exists() and not target.is_symlink():
        return "missing"
    if target.is_symlink():
        try:
            resolved = target.resolve(strict=False)
        except OSError:
            return "broken symlink"
        if resolved == expected:
            return "linked"
        return f"linked elsewhere: {resolved}"
    return "custom file"


def _run_git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ManagerError("git is not installed") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if detail:
            raise ManagerError(detail) from exc
        raise ManagerError("git command failed") from exc
    return result.stdout


def _remote_head_ref() -> str | None:
    if not (GITHUB_SOURCE_DIR / ".git").is_dir():
        return None
    try:
        ref = _run_git(
            ["-C", str(GITHUB_SOURCE_DIR), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"]
        ).strip()
    except ManagerError:
        ref = ""
    if ref:
        return ref
    for candidate in ("origin/main", "origin/master"):
        try:
            _run_git(["-C", str(GITHUB_SOURCE_DIR), "rev-parse", "--verify", candidate])
        except ManagerError:
            continue
        return candidate
    return None


def _ahead_behind(remote_ref: str) -> tuple[int, int]:
    output = _run_git(
        [
            "-C",
            str(GITHUB_SOURCE_DIR),
            "rev-list",
            "--left-right",
            "--count",
            f"HEAD...{remote_ref}",
        ]
    ).strip()
    try:
        ahead_text, behind_text = output.split()
        return int(ahead_text), int(behind_text)
    except ValueError as exc:
        raise ManagerError(f"Could not parse git status: {output}") from exc


def _replace_with_symlink(target: Path, source: Path) -> None:
    if not source.exists():
        raise ManagerError(f"Missing installed GTK4 file: {source.name}")
    if target.exists() or target.is_symlink():
        if target.is_symlink() and target.resolve(strict=False) == source:
            return
        _backup_path(target)
        if target.is_dir() and not target.is_symlink():
            raise ManagerError(f"Refusing to replace directory: {target}")
        target.unlink()
    os.symlink(source, target)


def _reset_backup(scope: str) -> None:
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "manifest.json").write_text(
        json.dumps({"scope": scope, "paths": []}, indent=2),
        encoding="utf-8",
    )


def _read_backup_manifest() -> dict[str, Any]:
    manifest_path = BACKUP_DIR / "manifest.json"
    if not manifest_path.exists():
        return {"scope": None, "paths": []}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"scope": None, "paths": []}
    data.setdefault("paths", [])
    return data


def _write_backup_manifest(data: dict[str, Any]) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "manifest.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _backup_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _read_backup_manifest()
    backup_name = f"item-{len(manifest['paths'])}"
    backup_path = BACKUP_DIR / backup_name
    if path.is_symlink():
        manifest["paths"].append(
            {"path": str(path), "type": "symlink", "target": os.readlink(path)}
        )
    elif path.is_dir():
        shutil.copytree(path, backup_path)
        manifest["paths"].append({"path": str(path), "type": "dir", "backup": backup_name})
    else:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        manifest["paths"].append({"path": str(path), "type": "file", "backup": backup_name})
    _write_backup_manifest(manifest)


def _restore_backup(scope: str) -> None:
    manifest = _read_backup_manifest()
    if manifest.get("scope") != scope:
        return
    for entry in reversed(manifest.get("paths", [])):
        path = Path(entry["path"])
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        if entry["type"] == "symlink":
            os.symlink(entry["target"], path)
        elif entry["type"] == "dir":
            shutil.copytree(BACKUP_DIR / entry["backup"], path)
        elif entry["type"] == "file":
            shutil.copy2(BACKUP_DIR / entry["backup"], path)
