project(
  'material-gnome-manager',
  version: '0.1.0',
  meson_version: '>=0.61.0',
  license: 'MIT',
)

python = import('python').find_installation('python3')

prefix = get_option('prefix')
bindir = join_paths(prefix, get_option('bindir'))
datadir = join_paths(prefix, get_option('datadir'))
libdir = join_paths(prefix, get_option('libdir'))
app_id = 'io.github.materialgnome.Manager'
app_libdir = join_paths(libdir, meson.project_name())

install_data('main.py', install_dir: app_libdir)
install_subdir(
  'material_gnome_manager',
  install_dir: app_libdir,
  exclude_directories: ['__pycache__'],
)

launcher_conf = configuration_data()
launcher_conf.set('PYTHON', python.full_path())
launcher_conf.set('APP_LIBDIR', app_libdir)

configure_file(
  input: 'scripts/material-gnome-manager.in',
  output: 'material-gnome-manager',
  configuration: launcher_conf,
  install: true,
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
)

install_data(
  'data/applications/io.github.materialgnome.Manager.desktop',
  install_dir: join_paths(datadir, 'applications'),
)

install_data(
  'data/icons/hicolor/scalable/apps/io.github.materialgnome.Manager.svg',
  install_dir: join_paths(datadir, 'icons', 'hicolor', 'scalable', 'apps'),
)

meson.add_install_script('scripts/post-install.sh')
