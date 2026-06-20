# Material GNOME Manager

A local GTK4/Libadwaita manager for the Material GNOME theme.

## Run

```bash
cd ~/Documents/Material-Gnome-Manager
python3 main.py
```

or:

```bash
bash ~/Documents/Material-Gnome-Manager/run.sh
```

## Install

Install system-wide with Meson:

```bash
meson setup build --prefix=/usr
sudo meson install -C build
```

Then launch it from your app grid or run:

```bash
material-gnome-manager
```

The install includes:

- `/usr/bin/material-gnome-manager`
- the desktop entry `io.github.materialgnome.Manager.desktop`
- the app icon `io.github.materialgnome.Manager`

## Arch / AUR

The AUR package files live in:

```bash
/home/aditya/Documents/Material-Gnome-Manager-aur
```

After pushing this repository to GitHub, build locally with:

```bash
cd ~/Documents/Material-Gnome-Manager-aur
makepkg -si
```

When publishing to AUR:

```bash
makepkg --printsrcinfo > .SRCINFO
git add PKGBUILD .SRCINFO README.md .gitignore
git commit -m "Initial import"
git push
```

## v1 Scope

- Fetch or update the Material GNOME source from GitHub:
  `https://github.com/SakibShahariar/material-gnome-theme.git`
- Select a Material GNOME source directory.
- Install or update `~/.themes/Material-Gnome` from that source.
- Apply bundled `themes/*.json` color presets to the installed copy.
- Generate and apply Matugen palettes from the current wallpaper or a chosen image.
- Apply included GNOME Shell top bar layouts.
- Enable or disable reduced GTK and GNOME Shell theme animations.
- Enable GTK4/Libadwaita symlinks in `~/.config/gtk-4.0`, including `colors.css`.
- Reset manager-created GTK4 links and restore the latest backup.

GNOME Shell layout changes require logging out and back in before they are visible.
GTK animation changes require restarting the affected apps.
GNOME Shell gsettings and Flatpak overrides are intentionally outside v1.

The GitHub source is the primary workflow. Local source selection is available for development or offline testing.
