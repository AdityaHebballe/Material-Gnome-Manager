#!/usr/bin/env sh
set -eu

prefix="${1:-/usr}"

rm -f "$prefix/bin/material-gnome-manager"
rm -f "$prefix/share/applications/io.github.materialgnome.Manager.desktop"
rm -f "$prefix/share/icons/hicolor/scalable/apps/io.github.materialgnome.Manager.svg"
rm -rf "$prefix/lib/material-gnome-manager"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f "$prefix/share/icons/hicolor" || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q "$prefix/share/applications" || true
fi
