# Material GNOME Manager

Material GNOME Manager is a GTK4/Libadwaita app for installing and customizing the
[Material GNOME theme](https://github.com/SakibShahariar/material-gnome-theme).

It can fetch the theme from GitHub, install it locally, apply color presets, generate
Matugen palettes, link GTK4/Libadwaita apps, and manage a few GNOME Shell options.

## Install

### Arch Linux

Using `yay`:

```bash
yay -S material-gnome-manager-git
```

Using `paru`:

```bash
paru -S material-gnome-manager-git
```

### Manual Install

```bash
meson setup build --prefix=/usr
sudo meson install -C build
```

Launch it from your app grid or run:

```bash
material-gnome-manager
```

## What It Does

- Fetches or updates Material GNOME from GitHub.
- Installs the theme to `~/.themes/Material-Gnome`.
- Applies bundled color presets.
- Generates colors with Matugen from your wallpaper or a selected image.
- Links GTK4/Libadwaita config files in `~/.config/gtk-4.0`.
- Applies GNOME Shell top bar layouts.
- Can reduce GTK and GNOME Shell theme animations.
- Can reset the GTK4 links it created.

## Notes

GTK apps need to be restarted after changing GTK theme files.

GNOME Shell layout changes require logging out and back in.


## Uninstall

For the AUR package:

```bash
sudo pacman -Rns material-gnome-manager-git
```

For a manual Meson install:

```bash
sudo ./scripts/uninstall.sh /usr
```
