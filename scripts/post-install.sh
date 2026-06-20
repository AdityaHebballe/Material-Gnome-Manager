#!/usr/bin/env sh
set -eu

if [ -n "${DESTDIR:-}" ]; then
  exit 0
fi

prefix="${MESON_INSTALL_PREFIX:-/usr/local}"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f "$prefix/share/icons/hicolor" || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q "$prefix/share/applications" || true
fi
