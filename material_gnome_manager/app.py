from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import manager


APP_ID = "io.github.materialgnome.Manager"
PREVIEW_TOKENS = ("primary", "secondary", "tertiary", "error")


PICKER_CSS = b"""
.palette-card.selected {
  border: 2px solid @accent_bg_color;
  border-radius: 12px;
  background-color: alpha(@accent_bg_color, 0.14);
}
"""


@dataclass
class ActionControl:
    button: Gtk.Button
    spinner: Gtk.Spinner
    check_icon: Gtk.Image


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return (
        int(value[0:2], 16) / 255,
        int(value[2:4], 16) / 255,
        int(value[4:6], 16) / 255,
    )


def _swatch(color: str, width: int = 28, height: int = 18) -> Gtk.DrawingArea:
    area = Gtk.DrawingArea()
    area.set_content_width(width)
    area.set_content_height(height)

    def draw(_area, ctx, draw_width: int, draw_height: int) -> None:
        red, green, blue = _hex_to_rgb(color)
        ctx.set_source_rgb(red, green, blue)
        ctx.rectangle(0, 0, draw_width, draw_height)
        ctx.fill()

    area.set_draw_func(draw)
    return area


def _swatch_strip(colors: dict[str, str], large: bool = False) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
    box.set_valign(Gtk.Align.CENTER)
    width = 34 if large else 24
    height = 22 if large else 16
    for token in PREVIEW_TOKENS:
        color = colors.get(token)
        if color:
            box.append(_swatch(color, width, height))
    return box


def _set_card_selected(card: Gtk.Widget, selected: bool) -> None:
    if selected:
        card.add_css_class("selected")
    else:
        card.remove_css_class("selected")


def _install_picker_css() -> None:
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(PICKER_CSS)
    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def _layout_preview(layout_name: str, colors: dict[str, str]) -> Gtk.DrawingArea:
    """Draw a small, palette-aware representation of a GNOME Shell panel layout."""
    area = Gtk.DrawingArea()
    area.set_content_width(230)
    area.set_content_height(58)
    area.set_hexpand(True)

    primary = colors.get("primary", "#b1c5ff")
    surface = colors.get("surface", "#11131a")
    container = colors.get("surface_container", surface)
    on_surface = colors.get("on_surface", "#e1e2ec")
    outline = colors.get("outline_variant", primary)

    def rounded_rect(ctx, x: float, y: float, width: float, height: float, radius: float) -> None:
        ctx.new_sub_path()
        ctx.arc(x + width - radius, y + radius, radius, -1.5708, 0)
        ctx.arc(x + width - radius, y + height - radius, radius, 0, 1.5708)
        ctx.arc(x + radius, y + height - radius, radius, 1.5708, 3.1416)
        ctx.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
        ctx.close_path()

    def paint(ctx, color: str, alpha: float = 1.0) -> None:
        ctx.set_source_rgba(*_hex_to_rgb(color), alpha)
        ctx.fill()

    def draw(_area, ctx, width: int, height: int) -> None:
        def panel(
            x: float,
            y: float,
            panel_width: float,
            panel_height: float,
            radius: float,
            *,
            alpha: float = 0.96,
            border: bool = False,
        ) -> None:
            rounded_rect(ctx, x, y, panel_width, panel_height, radius)
            paint(ctx, container, alpha)
            if border:
                ctx.set_source_rgba(*_hex_to_rgb(outline), 0.72)
                ctx.set_line_width(1)
                rounded_rect(ctx, x + 0.5, y + 0.5, panel_width - 1, panel_height - 1, radius)
                ctx.stroke()

        def items(x: float, y: float, count: int = 3, spacing: float = 9) -> None:
            ctx.set_source_rgba(*_hex_to_rgb(on_surface), 0.82)
            for index in range(count):
                ctx.arc(x + index * spacing, y, 1.8, 0, 6.2832)
                ctx.fill()

        bottom = "bottom" in layout_name
        y = height - 26 if bottom else 8
        if layout_name in {"default", "default-transparecy", "unified-border"}:
            panel(4, y, width - 8, 20, 0, alpha=0.74 if layout_name == "default-transparecy" else 1)
            if layout_name == "unified-border":
                ctx.set_source_rgb(*_hex_to_rgb(primary))
                ctx.set_line_width(2)
                ctx.move_to(4, y + 19)
                ctx.line_to(width - 4, y + 19)
                ctx.stroke()
            items(22, y + 10)
            items(width - 50, y + 10)
        elif layout_name == "unified-bar":
            panel(8, y, width - 16, 22, 9, alpha=0.9)
            ctx.set_source_rgba(*_hex_to_rgb(outline), 0.5)
            ctx.set_line_width(1)
            for divider in (width * 0.32, width * 0.68):
                ctx.move_to(divider, y + 5)
                ctx.line_to(divider, y + 17)
            ctx.stroke()
            items(24, y + 11)
            items(width - 52, y + 11)
        elif layout_name == "structured-box":
            panel(12, y, width - 24, 22, 6, alpha=0.94, border=True)
            items(28, y + 11)
            items(width - 56, y + 11)
        elif layout_name == "pill-duo":
            panel(14, y, 82, 22, 11, alpha=0.72)
            panel(width - 96, y, 82, 22, 11, alpha=0.72)
            items(30, y + 11, 3)
            items(width - 78, y + 11, 3)
        elif layout_name in {"segmented-dock", "segmented-pill", "unified-pill"}:
            radius = 11 if layout_name == "segmented-dock" else 16
            panel(12, y, 64, 22, radius, alpha=0.88, border=True)
            panel(width / 2 - 34, y, 68, 22, radius, alpha=0.88, border=True)
            panel(width - 76, y, 64, 22, radius, alpha=0.88, border=True)
            items(26, y + 11, 2)
            items(width / 2 - 18, y + 11, 3)
            items(width - 61, y + 11, 2)
        elif layout_name in {"floating-capsule", "floating-capsule-glass"}:
            glass = layout_name == "floating-capsule-glass"
            panel(12, y, 58, 22, 7 if glass else 10, alpha=0.58 if glass else 0.9, border=True)
            panel(width / 2 - 30, y, 60, 22, 7 if glass else 10, alpha=0.58 if glass else 0.9, border=True)
            panel(width - 70, y, 58, 22, 7 if glass else 10, alpha=0.58 if glass else 0.9, border=True)
            items(25, y + 11, 2)
            items(width / 2 - 12, y + 11, 2)
            items(width - 56, y + 11, 2)
        else:  # Unified capsule variants.
            panel(12, y, width - 24, 22, 11, alpha=0.9, border=True)
            items(29, y + 11)
            items(width / 2 - 8, y + 11, 2)
            items(width - 56, y + 11)

    area.set_draw_func(draw)
    return area


def _layout_title(layout_name: str) -> str:
    return layout_name.replace("-", " ").title()


def _palette_sample(colors: dict[str, str]) -> Gtk.DrawingArea:
    area = Gtk.DrawingArea()
    area.set_content_width(330)
    area.set_content_height(118)
    area.set_hexpand(True)

    def draw(_area, ctx, width: int, height: int) -> None:
        surface = colors.get("surface", "#111111")
        container = colors.get("surface_container", surface)
        primary = colors.get("primary", "#888888")
        secondary = colors.get("secondary", primary)
        on_surface = colors.get("on_surface", "#ffffff")
        error = colors.get("error", "#ff0000")
        ctx.set_source_rgb(*_hex_to_rgb(surface))
        ctx.rectangle(0, 0, width, height)
        ctx.fill()
        ctx.set_source_rgb(*_hex_to_rgb(container))
        ctx.rectangle(14, 16, width - 28, 86)
        ctx.fill()
        ctx.set_source_rgb(*_hex_to_rgb(on_surface))
        ctx.rectangle(30, 32, width * 0.38, 6)
        ctx.fill()
        ctx.set_source_rgba(*_hex_to_rgb(on_surface), 0.55)
        ctx.rectangle(30, 48, width * 0.54, 4)
        ctx.fill()
        ctx.set_source_rgb(*_hex_to_rgb(primary))
        ctx.rectangle(30, 68, 84, 20)
        ctx.fill()
        ctx.set_source_rgb(*_hex_to_rgb(secondary))
        ctx.arc(width - 58, 43, 12, 0, 6.2832)
        ctx.fill()
        ctx.set_source_rgb(*_hex_to_rgb(error))
        ctx.arc(width - 28, 43, 6, 0, 6.2832)
        ctx.fill()

    area.set_draw_func(draw)
    return area


GUIDED_COLOR_TOKENS = (
    ("Primary", "primary"),
    ("Secondary", "secondary"),
    ("Tertiary", "tertiary"),
    ("Error", "error"),
    ("Surface", "surface"),
)


def _token_title(token: str) -> str:
    return token.replace("_", " ").title()


class CustomPaletteEditorWindow(Gtk.Window):
    def __init__(
        self,
        parent: "ManagerWindow",
        previews: list[manager.PresetPreview],
        *,
        palette: manager.CustomPalette | None = None,
        initial_name: str | None = None,
    ):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("Design Custom Palette")
        self.set_default_size(680, 720)
        self.parent_window = parent
        self.previews = previews
        self.palette = palette
        self._previews_by_name = {preview.name: preview for preview in previews}
        default_name = palette.base_preset if palette else parent._current_preset_name
        self.base_name = default_name if default_name in self._previews_by_name else previews[0].name
        self.colors = dict(
            palette.colors if palette else self._previews_by_name[self.base_name].colors
        )
        self._color_rows: dict[str, list[tuple[Gtk.Button, Gtk.Label]]] = {}
        self._advanced_rows: dict[str, Gtk.Widget] = {}

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Design Custom Palette"))
        self.set_titlebar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        self.set_child(scrolled)
        clamp = Adw.Clamp()
        clamp.set_maximum_size(640)
        clamp.set_tightening_threshold(480)
        scrolled.set_child(clamp)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_hexpand(True)
        content.set_vexpand(False)
        content.set_valign(Gtk.Align.START)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(18)
        content.set_margin_end(18)
        clamp.set_child(content)

        name_group = Adw.PreferencesGroup(title="Palette")
        content.append(name_group)
        self.name_entry = Adw.EntryRow(title="Name")
        self.name_entry.set_text(palette.name if palette else initial_name or "")
        name_group.add(self.name_entry)
        self.base_dropdown = Adw.ComboRow(
            title="Start from",
            subtitle="Changing this resets the draft to that preset",
        )
        self.base_dropdown.set_model(Gtk.StringList.new([preview.name for preview in previews]))
        self.base_dropdown.set_selected([preview.name for preview in previews].index(self.base_name))
        self.base_dropdown.connect("notify::selected", self._base_changed)
        name_group.add(self.base_dropdown)

        preview_group = Adw.PreferencesGroup(title="Live Preview")
        content.append(preview_group)
        self.sample_box = Gtk.Box()
        self.sample_box.append(_palette_sample(self.colors))
        preview_group.add(self.sample_box)

        guided_group = Adw.PreferencesGroup(
            title="Core Colors",
            description="Adjust the main palette colors. Fine-tune all dependent roles below when needed.",
        )
        content.append(guided_group)
        for title, token in GUIDED_COLOR_TOKENS:
            guided_group.add(self._color_row(title, token))

        advanced_group = Adw.PreferencesGroup(title="Fine-tuning")
        content.append(advanced_group)
        advanced = Adw.ExpanderRow(
            title="Advanced colors",
            subtitle="Edit every Material color role",
        )
        advanced_group.add(advanced)
        search_row = Adw.ActionRow(title="Find a color role")
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Role or hex value")
        self.search_entry.connect("search-changed", self._filter_advanced)
        search_row.add_suffix(self.search_entry)
        advanced.add_row(search_row)
        for token in sorted(self.colors):
            row = self._color_row(_token_title(token), token)
            advanced.add_row(row)
            self._advanced_rows[token] = row

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_halign(Gtk.Align.END)
        content.append(footer)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _button: self.close())
        import_button = Gtk.Button(label="Import")
        import_button.connect("clicked", self._import_palette)
        export_button = Gtk.Button(label="Export")
        export_button.connect("clicked", self._export_palette)
        save = Gtk.Button(label="Save")
        save.connect("clicked", self._save)
        apply = Gtk.Button(label="Apply")
        apply.add_css_class("suggested-action")
        apply.connect("clicked", self._apply)
        footer.append(cancel)
        footer.append(import_button)
        footer.append(export_button)
        footer.append(save)
        footer.append(apply)

    def _color_row(self, title: str, token: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title)
        button = Gtk.Button()
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda _button: self._choose_color(token))
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        swatch = _swatch(self.colors.get(token, "#000000"), 28, 20)
        label = Gtk.Label(label=self.colors.get(token, "#000000"))
        label.add_css_class("monospace")
        content.append(swatch)
        content.append(label)
        button.set_child(content)
        row.add_suffix(button)
        self._color_rows.setdefault(token, []).append((button, label))
        return row

    def _base_changed(self, _dropdown: Gtk.DropDown, _param) -> None:
        selected = self.base_dropdown.get_selected()
        if selected < 0 or selected >= len(self.previews):
            return
        self.base_name = self.previews[selected].name
        self.colors = dict(self._previews_by_name[self.base_name].colors)
        self._refresh_colors()

    def _choose_color(self, token: str) -> None:
        initial = Gdk.RGBA()
        initial.parse(self.colors[token])
        dialog = Gtk.ColorDialog()
        dialog.set_title(f"Choose {_token_title(token)}")
        dialog.choose_rgba(self, initial, None, lambda dialog, result: self._color_chosen(dialog, result, token))

    def _color_chosen(self, dialog: Gtk.ColorDialog, result, token: str) -> None:
        try:
            color = dialog.choose_rgba_finish(result)
        except GLib.Error:
            return
        self.colors[token] = "#{:02X}{:02X}{:02X}".format(
            round(color.red * 255), round(color.green * 255), round(color.blue * 255)
        )
        self._refresh_colors()

    def _refresh_colors(self) -> None:
        for token, rows in self._color_rows.items():
            for button, label in rows:
                label.set_text(self.colors.get(token, "#000000"))
                child = button.get_child()
                if isinstance(child, Gtk.Box):
                    old_swatch = child.get_first_child()
                    if old_swatch:
                        child.remove(old_swatch)
                    child.prepend(_swatch(self.colors.get(token, "#000000"), 28, 20))
        while child := self.sample_box.get_first_child():
            self.sample_box.remove(child)
        self.sample_box.append(_palette_sample(self.colors))

    def _filter_advanced(self, _entry: Gtk.SearchEntry) -> None:
        query = self.search_entry.get_text().strip().lower()
        for token, row in self._advanced_rows.items():
            role = token.replace("_", " ")
            value = self.colors.get(token, "").lower()
            row.set_visible(not query or query in role or query in value)

    def _save(self, _button: Gtk.Button) -> None:
        try:
            saved = manager.save_custom_palette(self.name_entry.get_text(), self.base_name, self.colors)
        except manager.ManagerError as exc:
            self.parent_window._set_log(str(exc))
            return
        self.palette = saved
        self.name_entry.set_text(saved.name)
        self.parent_window._set_log(f"Saved custom palette {saved.name}")

    def _import_palette(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative(
            title="Import Palette",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="Import",
            cancel_label="Cancel",
        )
        palette_filter = Gtk.FileFilter()
        palette_filter.set_name("Palette JSON or GTK CSS")
        palette_filter.add_pattern("*.json")
        palette_filter.add_pattern("*.css")
        dialog.add_filter(palette_filter)
        dialog.connect("response", self._import_palette_response)
        dialog.show()

    def _import_palette_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            path = file.get_path() if file else None
            if path:
                try:
                    palette = manager.load_custom_palette_file(Path(path))
                except manager.ManagerError as exc:
                    self.parent_window._set_log(str(exc))
                else:
                    self.name_entry.set_text(palette.name)
                    self.colors = dict(palette.colors)
                    if palette.base_preset in self._previews_by_name:
                        self.base_name = palette.base_preset
                        self.base_dropdown.set_selected(
                            [preview.name for preview in self.previews].index(self.base_name)
                        )
                    self._refresh_colors()
                    self.parent_window._set_log(f"Imported palette {palette.name}")
        dialog.destroy()

    def _export_palette(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative(
            title="Export Palette",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="Export",
            cancel_label="Cancel",
        )
        name = self.name_entry.get_text().strip() or "custom-palette"
        dialog.set_current_name(f"{name}.json")
        dialog.connect("response", self._export_palette_response)
        dialog.show()

    def _export_palette_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            path = file.get_path() if file else None
            if path:
                try:
                    manager.export_custom_palette_file(
                        Path(path),
                        self.name_entry.get_text(),
                        self.base_name,
                        self.colors,
                    )
                except manager.ManagerError as exc:
                    self.parent_window._set_log(str(exc))
                else:
                    self.parent_window._set_log("Palette exported")
        dialog.destroy()

    def _apply(self, _button: Gtk.Button) -> None:
        label = self.name_entry.get_text().strip() or "Unsaved palette"
        self.parent_window.apply_custom_colors_from_editor(self.colors, label)
        self.close()


class LayoutPickerWindow(Gtk.Window):
    def __init__(
        self,
        parent: "ManagerWindow",
        layouts: list[str],
        current: str | None,
        colors: dict[str, str],
    ):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("Choose Top Bar Layout")
        self.set_default_size(700, 540)
        self.parent_window = parent
        self.layouts = layouts
        self.current = current
        self.colors = colors
        self.cards: dict[str, Gtk.Image] = {}
        self.card_widgets: dict[str, Gtk.Widget] = {}

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_child(scrolled)

        self.flow = Gtk.FlowBox()
        self.flow.set_hexpand(True)
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_margin_top(12)
        self.flow.set_margin_bottom(12)
        self.flow.set_margin_start(12)
        self.flow.set_margin_end(12)
        self.flow.set_column_spacing(12)
        self.flow.set_row_spacing(12)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_min_children_per_line(2)
        self.flow.set_max_children_per_line(3)
        scrolled.set_child(self.flow)
        for layout_name in layouts:
            self.flow.append(self._card(layout_name))

    def _card(self, layout_name: str) -> Gtk.Widget:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.add_css_class("card")
        content.add_css_class("palette-card")
        _set_card_selected(content, layout_name == self.current)
        content.set_size_request(210, -1)
        content.set_margin_top(6)
        content.set_margin_bottom(6)
        content.set_margin_start(6)
        content.set_margin_end(6)
        gesture = Gtk.GestureClick()
        gesture.connect("released", lambda _gesture, _n_press, _x, _y: self._select(layout_name))
        content.add_controller(gesture)
        content.append(_layout_preview(layout_name, self.colors))

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(label=_layout_title(layout_name))
        title.set_xalign(0)
        title.set_hexpand(True)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        check = Gtk.Image.new_from_icon_name("object-select-symbolic")
        check.add_css_class("success")
        check.set_visible(layout_name == self.current)
        title_row.append(check)
        title_row.append(title)
        self.cards[layout_name] = check
        self.card_widgets[layout_name] = content
        content.append(title_row)
        return content

    def _select(self, layout_name: str) -> None:
        if self.parent_window.is_busy():
            return
        for name, check in self.cards.items():
            check.set_visible(name == layout_name)
            _set_card_selected(self.card_widgets[name], name == layout_name)
        self.parent_window.select_layout_from_picker(layout_name)
        self.close()


class PresetPickerWindow(Gtk.Window):
    def __init__(
        self,
        parent: "ManagerWindow",
        previews: list[manager.PresetPreview],
        current: str | None,
    ):
        super().__init__(transient_for=parent, modal=True)
        self.set_title("Choose Color Preset")
        self.set_default_size(700, 560)
        self.parent_window = parent
        self.previews = previews
        self.current = current
        self.cards: dict[str, Gtk.Image] = {}
        self.card_widgets: dict[str, Gtk.Widget] = {}

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.set_vexpand(True)
        self.set_child(root)

        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="Choose Color Preset"))
        self.set_titlebar(header)

        create_group = Adw.PreferencesGroup()
        create_group.set_margin_top(12)
        create_group.set_margin_start(12)
        create_group.set_margin_end(12)
        create_row = Adw.ActionRow(
            title="Create custom palette",
            subtitle="Start from a preset, tune the colors, and save it for later",
        )
        create_button = Gtk.Button(label="Design")
        create_button.add_css_class("suggested-action")
        create_button.set_valign(Gtk.Align.CENTER)
        create_button.connect("clicked", self._create_custom)
        create_row.add_suffix(create_button)
        create_group.add(create_row)
        root.append(create_group)

        search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        search_box.set_margin_top(12)
        search_box.set_margin_bottom(12)
        search_box.set_margin_start(12)
        search_box.set_margin_end(12)
        root.append(search_box)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search presets")
        self.search_entry.connect("search-changed", lambda _entry: self._populate())
        search_box.append(self.search_entry)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        root.append(scrolled)

        self.flow = Gtk.FlowBox()
        self.flow.set_hexpand(True)
        self.flow.set_vexpand(True)
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_margin_start(12)
        self.flow.set_margin_end(12)
        self.flow.set_margin_bottom(12)
        self.flow.set_column_spacing(12)
        self.flow.set_row_spacing(12)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_min_children_per_line(2)
        self.flow.set_max_children_per_line(3)
        scrolled.set_child(self.flow)
        self._populate()

    def _populate(self) -> None:
        while child := self.flow.get_first_child():
            self.flow.remove(child)
        self.cards.clear()
        self.card_widgets.clear()
        query = self.search_entry.get_text().strip().lower()
        custom_palettes = manager.list_custom_palettes()
        for palette in custom_palettes:
            if query and query not in palette.name.lower():
                continue
            self.flow.append(self._custom_card(palette))
        for preview in self.previews:
            if query and query not in preview.name.lower():
                continue
            self.flow.append(self._card(preview))

    def _card(self, preview: manager.PresetPreview) -> Gtk.Widget:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.add_css_class("card")
        content.add_css_class("palette-card")
        _set_card_selected(content, preview.name == self.current)
        content.set_size_request(190, -1)
        content.set_margin_top(6)
        content.set_margin_bottom(6)
        content.set_margin_start(6)
        content.set_margin_end(6)
        gesture = Gtk.GestureClick()
        gesture.connect("released", lambda _gesture, _n_press, _x, _y: self._apply(preview.name))
        content.add_controller(gesture)

        surface = preview.colors.get("surface", "#000000")
        surface_area = _swatch(surface, 160, 64)
        surface_area.set_hexpand(True)
        content.append(surface_area)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_row.set_valign(Gtk.Align.CENTER)
        content.append(title_row)

        title = Gtk.Label(label=preview.name)
        title.set_xalign(0)
        title.set_hexpand(True)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title_row.append(title)

        check = Gtk.Image.new_from_icon_name("object-select-symbolic")
        check.add_css_class("success")
        check.set_visible(preview.name == self.current)
        title_row.append(check)
        self.cards[preview.name] = check
        self.card_widgets[preview.name] = content

        content.append(_swatch_strip(preview.colors, large=True))

        chip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chip_row.set_valign(Gtk.Align.CENTER)
        on_primary = preview.colors.get("on_primary")
        on_surface = preview.colors.get("on_surface")
        if on_primary:
            chip_row.append(_swatch(on_primary, 18, 14))
            primary_chip = Gtk.Label(label="on primary")
            primary_chip.add_css_class("caption")
            chip_row.append(primary_chip)
        if on_surface:
            chip_row.append(_swatch(on_surface, 18, 14))
            surface_chip = Gtk.Label(label="on surface")
            surface_chip.add_css_class("caption")
            chip_row.append(surface_chip)
        content.append(chip_row)

        return content

    def _custom_card(self, palette: manager.CustomPalette) -> Gtk.Widget:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.add_css_class("card")
        content.set_size_request(190, -1)
        content.set_margin_top(6)
        content.set_margin_bottom(6)
        content.set_margin_start(6)
        content.set_margin_end(6)
        surface = palette.colors.get("surface", "#000000")
        area = _swatch(surface, 160, 64)
        area.set_hexpand(True)
        content.append(area)
        title = Gtk.Label(label=palette.name)
        title.set_xalign(0)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        content.append(title)
        caption = Gtk.Label(label=f"Custom · {palette.base_preset or 'Source default'}")
        caption.set_xalign(0)
        caption.add_css_class("caption")
        content.append(caption)
        content.append(_swatch_strip(palette.colors, large=True))
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        apply = Gtk.Button(label="Apply")
        apply.add_css_class("suggested-action")
        apply.connect("clicked", lambda _button: self._apply_custom(palette.name))
        edit = Gtk.Button(label="Edit")
        edit.connect("clicked", lambda _button: self._edit_custom(palette))
        duplicate = Gtk.Button(icon_name="edit-copy-symbolic")
        duplicate.set_tooltip_text("Duplicate palette")
        duplicate.connect("clicked", lambda _button: self._edit_custom(palette, duplicate=True))
        delete = Gtk.Button(icon_name="user-trash-symbolic")
        delete.set_tooltip_text("Delete palette")
        delete.connect("clicked", lambda _button: self._delete_custom(palette.name))
        actions.append(apply)
        actions.append(edit)
        actions.append(duplicate)
        actions.append(delete)
        content.append(actions)
        return content

    def _apply(self, preset_name: str) -> None:
        if self.parent_window.is_busy():
            return
        self.current = preset_name
        for name, check in self.cards.items():
            check.set_visible(name == preset_name)
            _set_card_selected(self.card_widgets[name], name == preset_name)
        self.parent_window.apply_preset_from_picker(preset_name)

    def _apply_custom(self, name: str) -> None:
        if self.parent_window.is_busy():
            return
        self.parent_window.apply_saved_custom_palette(name)

    def _create_custom(self, _button: Gtk.Button) -> None:
        self.close()
        self.parent_window.open_custom_palette_editor()

    def _edit_custom(self, palette: manager.CustomPalette, duplicate: bool = False) -> None:
        self.close()
        self.parent_window.open_custom_palette_editor(palette, duplicate=duplicate)

    def _delete_custom(self, name: str) -> None:
        try:
            manager.delete_custom_palette(name)
        except manager.ManagerError as exc:
            self.parent_window._set_log(str(exc))
            return
        self.parent_window._set_log(f"Deleted custom palette {name}")
        self._populate()


class ManagerWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Material GNOME Manager")
        self.set_default_size(1120, 860)
        _install_picker_css()

        self._preset_names: list[str] = []
        self._preset_previews: list[manager.PresetPreview] = []
        self._preset_preview_by_name: dict[str, manager.PresetPreview] = {}
        self._current_preset_name: str | None = None
        self._last_preset_label: str | None = None
        self._theme_installed = False
        self._layout_names: list[str] = []
        self._selected_layout_name: str | None = None
        self._layout_preview_colors: dict[str, str] = {}
        self._github_busy = False
        self._busy_action: str | None = None
        self._actions: dict[str, ActionControl] = {}
        self._update_checks_busy = False
        self._refreshing_update_checks = False
        self._github_source_selected = False
        self._notify_after_requested_update = False

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_button.set_tooltip_text("Refresh Status")
        refresh_button.connect("clicked", lambda _button: self.refresh())
        header.pack_end(refresh_button)
        toolbar.add_top_bar(header)

        self.toast_overlay = Adw.ToastOverlay()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.toast_overlay.set_child(scrolled)
        toolbar.set_content(self.toast_overlay)
        self.set_content(toolbar)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(860)
        clamp.set_tightening_threshold(480)
        scrolled.set_child(clamp)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(18)
        content.set_margin_end(18)
        clamp.set_child(content)

        source_group = Adw.PreferencesGroup(title="Source")
        content.append(source_group)
        self.github_row = Adw.ActionRow(title="GitHub Source")
        self.github_row.set_subtitle("Not checked")
        github_suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        github_suffix.set_valign(Gtk.Align.CENTER)
        self.github_spinner = Gtk.Spinner()
        self.github_status_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
        self.github_status_icon.add_css_class("success")
        self.fetch_button = Gtk.Button(label="Fetch")
        self.fetch_button.add_css_class("suggested-action")
        self.fetch_button.connect("clicked", self._fetch_github)
        self.check_button = Gtk.Button(label="Check")
        self.check_button.connect("clicked", self._check_github)
        self.update_button = Gtk.Button(label="Update")
        self.update_button.add_css_class("suggested-action")
        self.update_button.connect("clicked", self._update_github)
        github_suffix.append(self.github_spinner)
        github_suffix.append(self.github_status_icon)
        github_suffix.append(self.fetch_button)
        github_suffix.append(self.check_button)
        github_suffix.append(self.update_button)
        self.github_row.add_suffix(github_suffix)
        source_group.add(self.github_row)

        self.source_row = Adw.ActionRow(title="Material GNOME Source")
        self.source_row.set_subtitle("No source selected")
        choose_button = Gtk.Button(label="Choose Local")
        choose_button.set_valign(Gtk.Align.CENTER)
        choose_button.connect("clicked", self._choose_source)
        self.source_row.add_suffix(choose_button)
        source_group.add(self.source_row)

        updates_group = Adw.PreferencesGroup(
            title="Automatic Updates",
            description="Check the GitHub theme source in the background. No tray icon is used.",
        )
        content.append(updates_group)
        self.update_checks_row = Adw.SwitchRow(
            title="Check for theme updates",
            subtitle="Off",
        )
        self.update_checks_row.connect("notify::active", self._update_checks_toggled)
        updates_group.add(self.update_checks_row)
        self.update_interval_row = Adw.ComboRow(
            title="Check interval",
            subtitle="Choose how often to look for new commits",
        )
        self._update_interval_keys = list(manager.UPDATE_CHECK_INTERVALS)
        self.update_interval_row.set_model(
            Gtk.StringList.new(
                [manager.UPDATE_CHECK_INTERVALS[key][0] for key in self._update_interval_keys]
            )
        )
        self.update_interval_row.connect("notify::selected", self._update_interval_changed)
        updates_group.add(self.update_interval_row)

        self.status_group = Adw.PreferencesGroup(title="Status")
        content.append(self.status_group)
        self.install_row = Adw.ActionRow(title="Installed Theme")
        self.gtk_css_row = Adw.ActionRow(title="GTK4 gtk.css")
        self.gtk_dark_row = Adw.ActionRow(title="GTK4 gtk-dark.css")
        self.gtk_colors_row = Adw.ActionRow(title="GTK4 colors.css")
        self.status_group.add(self.install_row)
        self.status_group.add(self.gtk_css_row)
        self.status_group.add(self.gtk_dark_row)
        self.status_group.add(self.gtk_colors_row)

        preset_group = Adw.PreferencesGroup(title="Color Preset")
        content.append(preset_group)
        self.preset_row = Adw.ActionRow(title="Preset")
        preset_suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        preset_suffix.set_valign(Gtk.Align.CENTER)
        self.preset_preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        self.preset_preview_box.set_valign(Gtk.Align.CENTER)
        self.preset_spinner = Gtk.Spinner()
        self.preset_spinner.set_valign(Gtk.Align.CENTER)
        self.preset_check_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
        self.preset_check_icon.add_css_class("success")
        self.choose_preset_button = Gtk.Button(label="Choose")
        self.choose_preset_button.set_valign(Gtk.Align.CENTER)
        self.choose_preset_button.connect("clicked", self._open_preset_picker)
        preset_suffix.append(self.preset_preview_box)
        preset_suffix.append(self.preset_spinner)
        preset_suffix.append(self.preset_check_icon)
        preset_suffix.append(self.choose_preset_button)
        self.preset_row.add_suffix(preset_suffix)
        preset_group.add(self.preset_row)

        matugen_group = Adw.PreferencesGroup(title="Matugen")
        content.append(matugen_group)
        self.matugen_row = Adw.ActionRow(title="Generator")
        matugen_group.add(self.matugen_row)
        self.wallpaper_row = Adw.ActionRow(title="Current Wallpaper")
        self._add_action_row_suffix(
            self.wallpaper_row,
            "matugen_wallpaper",
            "Generate",
            self._apply_matugen_wallpaper,
        )
        matugen_group.add(self.wallpaper_row)
        self.image_row = Adw.ActionRow(title="Image")
        self._add_action_row_suffix(
            self.image_row,
            "matugen_image",
            "Choose Image",
            self._choose_matugen_image,
        )
        matugen_group.add(self.image_row)

        shell_group = Adw.PreferencesGroup(title="GNOME Shell")
        content.append(shell_group)
        self.layout_row = Adw.ActionRow(title="Top Bar Layout")
        layout_suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        layout_suffix.set_valign(Gtk.Align.CENTER)
        self.layout_preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        self.layout_preview_box.set_valign(Gtk.Align.CENTER)
        self.layout_choose_button = Gtk.Button(label="Choose")
        self.layout_choose_button.set_valign(Gtk.Align.CENTER)
        self.layout_choose_button.connect("clicked", self._open_layout_picker)
        layout_suffix.append(self.layout_preview_box)
        layout_suffix.append(self.layout_choose_button)
        self._add_inline_action(
            layout_suffix,
            "shell_layout",
            "Apply",
            self._apply_shell_layout,
        )
        self.layout_row.add_suffix(layout_suffix)
        shell_group.add(self.layout_row)
        self._add_action(
            shell_group,
            "reduce_animations",
            "Reduced GTK Animations",
            "Disables GTK3, GTK4, and shell CSS motion",
            "Enable",
            self._toggle_reduced_animations,
        )

        actions_group = Adw.PreferencesGroup(title="Actions")
        content.append(actions_group)
        self._add_action(
            actions_group,
            "install",
            "Install / Update Theme",
            "Copy the selected source into ~/.themes/Material-Gnome",
            "Install",
            self._install_theme,
            suggested=True,
        )
        self._add_action(
            actions_group,
            "gtk4",
            "GTK4 / Libadwaita Links",
            "Point ~/.config/gtk-4.0 at the installed theme",
            "Enable",
            self._enable_gtk4,
        )
        self._add_action(
            actions_group,
            "reset_gtk4",
            "Reset GTK4 Links",
            "Remove manager-created GTK4 links and restore backup files",
            "Reset",
            self._reset_gtk4,
        )
        self._add_action(
            actions_group,
            "safe_reset",
            "Safe Reset",
            "Restore only files managed by this app",
            "Reset",
            self._safe_reset,
        )
        self.refresh()
        if manager.GITHUB_SOURCE_DIR.exists():
            self._check_github(None, quiet=True)

    def _add_action(
        self,
        group: Adw.PreferencesGroup,
        action_id: str,
        title: str,
        subtitle: str,
        label: str,
        callback,
        suggested: bool = False,
    ) -> None:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        button = Gtk.Button(label=label)
        button.set_valign(Gtk.Align.CENTER)
        if suggested:
            button.add_css_class("suggested-action")
        button.connect("clicked", callback)
        spinner = Gtk.Spinner()
        spinner.set_valign(Gtk.Align.CENTER)
        check_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
        check_icon.add_css_class("success")
        suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        suffix.set_valign(Gtk.Align.CENTER)
        suffix.append(spinner)
        suffix.append(check_icon)
        suffix.append(button)
        row.add_suffix(suffix)
        group.add(row)
        self._actions[action_id] = ActionControl(button=button, spinner=spinner, check_icon=check_icon)

    def _add_action_row_suffix(
        self,
        row: Adw.ActionRow,
        action_id: str,
        label: str,
        callback,
        suggested: bool = False,
    ) -> None:
        button = Gtk.Button(label=label)
        button.set_valign(Gtk.Align.CENTER)
        if suggested:
            button.add_css_class("suggested-action")
        button.connect("clicked", callback)
        spinner = Gtk.Spinner()
        spinner.set_valign(Gtk.Align.CENTER)
        check_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
        check_icon.add_css_class("success")
        suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        suffix.set_valign(Gtk.Align.CENTER)
        suffix.append(spinner)
        suffix.append(check_icon)
        suffix.append(button)
        row.add_suffix(suffix)
        self._actions[action_id] = ActionControl(button=button, spinner=spinner, check_icon=check_icon)

    def _add_inline_action(
        self,
        box: Gtk.Box,
        action_id: str,
        label: str,
        callback,
        suggested: bool = False,
    ) -> None:
        spinner = Gtk.Spinner()
        spinner.set_valign(Gtk.Align.CENTER)
        check_icon = Gtk.Image.new_from_icon_name("object-select-symbolic")
        check_icon.add_css_class("success")
        button = Gtk.Button(label=label)
        button.set_valign(Gtk.Align.CENTER)
        if suggested:
            button.add_css_class("suggested-action")
        button.connect("clicked", callback)
        box.append(spinner)
        box.append(check_icon)
        box.append(button)
        self._actions[action_id] = ActionControl(button=button, spinner=spinner, check_icon=check_icon)

    def _choose_source(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative(
            title="Choose Material GNOME Source",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="Choose",
            cancel_label="Cancel",
        )
        dialog.connect("response", self._source_response)
        dialog.show()

    def _source_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            path = file.get_path() if file else None
            if path:
                try:
                    manager.set_source_dir(Path(path))
                except manager.ManagerError as exc:
                    self._set_log(str(exc))
                else:
                    self._set_log("Source selected")
                self.refresh(keep_log=True)
        dialog.destroy()

    def _update_checks_toggled(self, _row: Adw.SwitchRow, _param) -> None:
        if self._refreshing_update_checks:
            return
        interval = self._selected_update_interval() if self.update_checks_row.get_active() else None
        self._configure_update_checks(interval)

    def _update_interval_changed(self, _row: Adw.ComboRow, _param) -> None:
        if self._refreshing_update_checks or not self.update_checks_row.get_active():
            return
        self._configure_update_checks(self._selected_update_interval())

    def _selected_update_interval(self) -> str:
        selected = self.update_interval_row.get_selected()
        if selected >= len(self._update_interval_keys):
            return self._update_interval_keys[0]
        return self._update_interval_keys[selected]

    def _configure_update_checks(self, interval: str | None) -> None:
        if self._update_checks_busy:
            return
        if interval is not None and not self._github_source_selected:
            self._set_log("Fetch and select the GitHub source before enabling update checks")
            self.refresh(keep_log=True)
            return
        self._update_checks_busy = True
        self._refresh_update_check_controls()

        def worker() -> None:
            try:
                message = manager.configure_update_checks(interval)
            except manager.ManagerError as exc:
                GLib.idle_add(self._finish_update_check_configuration, str(exc))
            except OSError as exc:
                GLib.idle_add(self._finish_update_check_configuration, f"Filesystem error: {exc}")
            else:
                GLib.idle_add(self._finish_update_check_configuration, message)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_update_check_configuration(self, message: str) -> bool:
        self._update_checks_busy = False
        self._set_log(message)
        self.refresh(keep_log=True)
        return GLib.SOURCE_REMOVE

    def _fetch_github(self, _button: Gtk.Button | None) -> None:
        self._run_github_action(manager.fetch_or_update_github_source, "Fetching GitHub source...")

    def _check_github(self, _button: Gtk.Button | None, quiet: bool = False) -> None:
        self._run_github_action(manager.check_github_updates, "Checking for updates...", quiet=quiet)

    def _update_github(self, _button: Gtk.Button | None) -> None:
        self._run_github_action(
            manager.update_github_source_and_installed_theme,
            "Updating source and installed theme...",
        )

    def run_requested_update(self) -> bool:
        if not self._github_busy:
            self._notify_after_requested_update = True
            self._update_github(None)
        return GLib.SOURCE_REMOVE

    def _install_theme(self, _button: Gtk.Button) -> None:
        self._run_action("install", manager.install_theme, "Installing theme...")

    def _open_preset_picker(self, _button: Gtk.Button) -> None:
        if not self._preset_previews:
            self._set_log("No presets available")
            return
        picker = PresetPickerWindow(self, self._preset_previews, self._current_preset_name)
        picker.present()

    def open_custom_palette_editor(
        self,
        palette: manager.CustomPalette | None = None,
        duplicate: bool = False,
    ) -> None:
        if not self._preset_previews:
            self._set_log("Fetch or choose a theme source before creating a palette")
            return
        if duplicate and palette:
            palette = manager.CustomPalette(
                name=f"{palette.name} copy",
                base_preset=palette.base_preset,
                colors=dict(palette.colors),
            )
        editor = CustomPaletteEditorWindow(self, self._preset_previews, palette=palette)
        editor.present()

    def _open_layout_picker(self, _button: Gtk.Button) -> None:
        if not self._layout_names:
            self._set_log("No top bar layouts available")
            return
        picker = LayoutPickerWindow(
            self,
            self._layout_names,
            self._selected_layout_name,
            self._layout_preview_colors,
        )
        picker.present()

    def select_layout_from_picker(self, layout_name: str) -> None:
        self._selected_layout_name = layout_name
        self._refresh_layout_row(manager.get_status())
        self._refresh_action_controls(manager.get_status())

    def apply_preset_from_picker(self, preset_name: str) -> None:
        self._current_preset_name = preset_name
        self._refresh_preset_row()
        self._run_action("preset", lambda: manager.apply_preset(preset_name), "Applying color preset...")

    def apply_saved_custom_palette(self, name: str) -> None:
        self._current_preset_name = None
        self._last_preset_label = f"Custom: {name}"
        self._refresh_preset_row()
        self._run_action("preset", lambda: manager.apply_custom_palette(name), "Applying custom palette...")

    def apply_custom_colors_from_editor(self, colors: dict[str, str], label: str) -> None:
        self._current_preset_name = None
        self._last_preset_label = f"Custom: {label}"
        self._refresh_preset_row()
        self._run_action(
            "preset",
            lambda: manager.apply_custom_colors(colors, label),
            "Applying custom palette...",
        )

    def _apply_matugen_wallpaper(self, _button: Gtk.Button) -> None:
        self._run_action(
            "matugen_wallpaper",
            manager.apply_matugen_from_current_wallpaper,
            "Generating colors from current wallpaper...",
        )

    def _choose_matugen_image(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileChooserNative(
            title="Choose Image",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="Generate",
            cancel_label="Cancel",
        )
        image_filter = Gtk.FileFilter()
        image_filter.set_name("Images")
        image_filter.add_pixbuf_formats()
        dialog.add_filter(image_filter)
        dialog.connect("response", self._matugen_image_response)
        dialog.show()

    def _matugen_image_response(self, dialog: Gtk.FileChooserNative, response: int) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            path = file.get_path() if file else None
            if path:
                image = Path(path)
                self._run_action(
                    "matugen_image",
                    lambda: manager.apply_matugen_from_image(image),
                    "Generating colors from image...",
                )
        dialog.destroy()

    def _apply_shell_layout(self, _button: Gtk.Button) -> None:
        layout = self._selected_layout()
        if layout is None:
            self._set_log("Select a top bar layout first")
            return
        self._run_action(
            "shell_layout",
            lambda: manager.apply_top_bar_layout(layout),
            "Applying top bar layout...",
        )

    def _toggle_reduced_animations(self, _button: Gtk.Button) -> None:
        status = manager.get_status()
        enabled = not status.reduced_animations
        self._run_action(
            "reduce_animations",
            lambda: manager.set_reduced_animations(enabled),
            "Updating animation setting...",
        )

    def _enable_gtk4(self, _button: Gtk.Button) -> None:
        self._run_action("gtk4", manager.enable_gtk4_links, "Enabling GTK4 links...")

    def _reset_gtk4(self, _button: Gtk.Button) -> None:
        self._run_action("reset_gtk4", manager.reset_gtk4_links, "Resetting GTK4 links...")

    def _safe_reset(self, _button: Gtk.Button) -> None:
        self._run_action("safe_reset", manager.safe_reset, "Running safe reset...")

    def is_busy(self) -> bool:
        return self._busy_action is not None or self._github_busy

    def _run_action(self, action_id: str, callback, loading_message: str) -> None:
        if self._busy_action is not None:
            return
        self._busy_action = action_id
        self._set_log(loading_message)
        self.refresh(keep_log=True)

        def worker() -> None:
            try:
                result = callback()
            except manager.ManagerError as exc:
                GLib.idle_add(self._finish_action, str(exc))
            except OSError as exc:
                GLib.idle_add(self._finish_action, f"Filesystem error: {exc}")
            else:
                GLib.idle_add(self._finish_action, str(result or "Done"))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_action(self, message: str) -> bool:
        self._busy_action = None
        self._set_log(message)
        self.refresh(keep_log=True)
        return GLib.SOURCE_REMOVE

    def _run_github_action(self, callback, loading_message: str, quiet: bool = False) -> None:
        if self._github_busy:
            return
        self._github_busy = True
        if not quiet:
            self._set_log(loading_message)
        self.refresh(keep_log=True)

        def worker() -> None:
            try:
                result = callback()
            except manager.ManagerError as exc:
                GLib.idle_add(self._finish_github_action, str(exc))
            except OSError as exc:
                GLib.idle_add(self._finish_github_action, f"Filesystem error: {exc}")
            else:
                GLib.idle_add(self._finish_github_action, str(result or "Done"))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_github_action(self, message: str) -> bool:
        self._github_busy = False
        self._set_log(message)
        if self._notify_after_requested_update:
            self._notify_after_requested_update = False
            if message.startswith("Updated GitHub source"):
                notification = Gio.Notification.new("Theme updated")
                notification.set_body("Material GNOME was updated and reinstalled.")
                app = self.get_application()
                if isinstance(app, Gio.Application):
                    app.send_notification("theme-update-complete", notification)
        self.refresh(keep_log=True)
        return GLib.SOURCE_REMOVE

    def refresh(self, keep_log: bool = False) -> None:
        status = manager.get_status()
        self.github_row.set_subtitle(f"{manager.GITHUB_REPO_URL}\n{status.github_source_dir}\n{status.github_state}")
        self._refresh_github_controls(status.github_state)
        self._github_source_selected = status.source_dir == manager.GITHUB_SOURCE_DIR
        self._refresh_update_checks(status)
        if status.source_dir:
            self.source_row.set_subtitle(f"{status.source_dir}\n{status.source_message}")
        else:
            self.source_row.set_subtitle(status.source_message)

        self.install_row.set_subtitle("Installed" if status.installed else "Not installed")
        self._theme_installed = status.installed
        self.gtk_css_row.set_subtitle(status.gtk_css_state)
        self.gtk_dark_row.set_subtitle(status.gtk_dark_css_state)
        self.gtk_colors_row.set_subtitle(status.gtk_colors_state)
        self._refresh_status_rows(status)
        self.matugen_row.set_subtitle(status.matugen_state)
        if status.current_wallpaper:
            self.wallpaper_row.set_subtitle(str(status.current_wallpaper))
        else:
            self.wallpaper_row.set_subtitle("No local wallpaper image detected")
        self.image_row.set_subtitle("Generate a palette from a selected image")

        self._preset_names = status.presets
        self._preset_previews = manager.get_preset_previews(status.source_dir if status.source_valid else None)
        self._preset_preview_by_name = {preview.name: preview for preview in self._preset_previews}
        self._current_preset_name = status.current_preset
        self._last_preset_label = status.last_preset
        self._refresh_preset_row()
        self._layout_names = status.layouts
        if self._selected_layout_name not in self._layout_names:
            self._selected_layout_name = status.active_layout if status.active_layout in self._layout_names else None
        self._layout_preview_colors = manager.get_preview_colors(
            status.source_dir if status.source_valid else None
        )
        self._refresh_layout_row(status)
        self._refresh_action_controls(status)

        if not keep_log:
            self._set_log("Ready")

    def _refresh_preset_row(self) -> None:
        while child := self.preset_preview_box.get_first_child():
            self.preset_preview_box.remove(child)

        preview = (
            self._preset_preview_by_name.get(self._current_preset_name)
            if self._current_preset_name
            else None
        )
        if preview:
            self.preset_row.set_subtitle(f"{preview.name} selected")
            self.preset_preview_box.append(_swatch_strip(preview.colors))
            self.preset_check_icon.set_visible(self._busy_action != "preset")
        elif self._preset_previews:
            if self._last_preset_label and self._last_preset_label.startswith("Custom: "):
                label = self._last_preset_label
            else:
                label = "Custom / Matugen" if self._theme_installed else "No preset applied"
            self.preset_row.set_subtitle(f"{label}. {len(self._preset_previews)} presets available.")
            self.preset_check_icon.set_visible(False)
        else:
            self.preset_row.set_subtitle("No presets available")
            self.preset_check_icon.set_visible(False)

        busy = self._busy_action == "preset"
        self.preset_spinner.set_visible(busy)
        if busy:
            self.preset_spinner.start()
        else:
            self.preset_spinner.stop()
        self.choose_preset_button.set_visible(not busy)
        self.choose_preset_button.set_sensitive(self._busy_action is None and not self._github_busy)

    def _refresh_layout_row(self, status: manager.ThemeStatus) -> None:
        while child := self.layout_preview_box.get_first_child():
            self.layout_preview_box.remove(child)
        if self._selected_layout_name:
            self.layout_preview_box.append(
                _layout_preview(self._selected_layout_name, self._layout_preview_colors)
            )
        active_layout = status.active_layout or "None"
        selected = self._selected_layout_name or "None"
        if selected == status.active_layout:
            self.layout_row.set_subtitle(
                f"Active: {_layout_title(active_layout)}. Log out and back in to see changes."
            )
        else:
            self.layout_row.set_subtitle(
                f"Selected: {_layout_title(selected)}. Active: {_layout_title(active_layout)}."
            )
        self.layout_choose_button.set_sensitive(self._busy_action is None and not self._github_busy)

    def _set_log(self, message: str) -> None:
        if message and message != "Ready":
            self.toast_overlay.add_toast(Adw.Toast(title=message))

    def _refresh_github_controls(self, github_state: str) -> None:
        self.github_spinner.set_visible(self._github_busy)
        if self._github_busy:
            self.github_spinner.start()
        else:
            self.github_spinner.stop()

        not_fetched = github_state == "not fetched"
        update_available = "update available" in github_state or "behind" in github_state
        up_to_date = github_state == "up to date"

        self.fetch_button.set_visible(not_fetched and not self._github_busy)
        self.check_button.set_visible(
            not not_fetched and not update_available and not self._github_busy
        )
        self.update_button.set_visible(update_available and not self._github_busy)
        self.github_status_icon.set_visible(up_to_date and not self._github_busy)

    def _refresh_update_checks(self, status: manager.ThemeStatus) -> None:
        self._refreshing_update_checks = True
        interval = status.update_check_interval or self._update_interval_keys[0]
        self.update_checks_row.set_active(status.update_check_interval is not None)
        self.update_interval_row.set_selected(self._update_interval_keys.index(interval))
        self._refreshing_update_checks = False
        self.update_checks_row.set_subtitle(status.update_check_state)
        self._refresh_update_check_controls()

    def _refresh_update_check_controls(self) -> None:
        enabled = self.update_checks_row.get_active()
        can_enable = self._github_source_selected or enabled
        self.update_checks_row.set_sensitive(not self._update_checks_busy and can_enable)
        self.update_interval_row.set_sensitive(
            not self._update_checks_busy and enabled and self._github_source_selected
        )

    def _refresh_status_rows(self, status: manager.ThemeStatus) -> None:
        self.install_row.set_visible(not status.installed)
        self.gtk_css_row.set_visible(status.gtk_css_state != "linked")
        self.gtk_dark_row.set_visible(status.gtk_dark_css_state != "linked")
        self.gtk_colors_row.set_visible(status.gtk_colors_state != "linked")
        self.status_group.set_visible(
            not status.installed
            or status.gtk_css_state != "linked"
            or status.gtk_dark_css_state != "linked"
            or status.gtk_colors_state != "linked"
        )

    def _refresh_action_controls(self, status: manager.ThemeStatus) -> None:
        gtk4_linked = (
            status.gtk_css_state == "linked"
            and status.gtk_dark_css_state == "linked"
            and status.gtk_colors_state == "linked"
        )
        matugen_available = status.matugen_state != "not installed"
        matugen_wallpaper_applied = status.last_preset == "Matugen: Current Wallpaper"
        matugen_image_applied = bool(
            status.last_preset
            and status.last_preset.startswith("Matugen: ")
            and not matugen_wallpaper_applied
        )
        selected_layout = self._selected_layout()
        done = {
            "install": status.installed,
            "matugen_wallpaper": matugen_wallpaper_applied,
            "matugen_image": matugen_image_applied,
            "shell_layout": bool(
                status.installed and selected_layout and status.active_layout == selected_layout
            ),
            "reduce_animations": status.reduced_animations,
            "gtk4": gtk4_linked,
            "reset_gtk4": not self._has_manager_created_targets(),
            "safe_reset": not self._has_manager_created_targets(),
        }
        runnable = {
            "install": status.source_valid,
            "matugen_wallpaper": bool(
                status.source_valid and matugen_available and status.current_wallpaper
            ),
            "matugen_image": bool(status.source_valid and matugen_available),
            "shell_layout": bool(status.source_valid and status.layouts and selected_layout),
            "reduce_animations": status.source_valid,
            "gtk4": status.installed,
            "reset_gtk4": self._has_manager_created_targets(),
            "safe_reset": self._has_manager_created_targets(),
        }
        if "reduce_animations" in self._actions:
            self._actions["reduce_animations"].button.set_label(
                "Disable" if status.reduced_animations else "Enable"
            )

        for action_id, control in self._actions.items():
            busy = self._busy_action == action_id
            repeatable = action_id in {"matugen_wallpaper", "matugen_image", "reduce_animations"}
            control.spinner.set_visible(busy)
            if busy:
                control.spinner.start()
            else:
                control.spinner.stop()
            control.check_icon.set_visible(
                action_id != "shell_layout" and done[action_id] and not busy
            )
            control.button.set_visible(
                runnable[action_id] and (repeatable or not done[action_id]) and not busy
            )
            control.button.set_sensitive(self._busy_action is None and not self._github_busy)

    def _selected_layout(self) -> str | None:
        return self._selected_layout_name if self._selected_layout_name in self._layout_names else None

    def _has_manager_created_targets(self) -> bool:
        state = manager.load_state()
        return any(Path(value).exists() or Path(value).is_symlink() for value in state.get("created_files", []))


class ManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._run_update_on_activate = False

    def do_startup(self):
        Adw.Application.do_startup(self)
        GLib.set_application_name("Material GNOME Manager")
        Gtk.Window.set_default_icon_name(APP_ID)

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = ManagerWindow(self)
        window.present()
        if self._run_update_on_activate:
            self._run_update_on_activate = False
            GLib.idle_add(window.run_requested_update)

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        arguments = command_line.get_arguments()[1:]
        if "--update" in arguments:
            self._run_update_on_activate = True
        self.activate()
        return 0


def main(argv: list[str] | None = None) -> int:
    app = ManagerApp()
    return app.run(argv or sys.argv)
