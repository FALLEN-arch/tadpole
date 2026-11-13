# Tadpole - Meson build definition
project('tadpole', 'python',
  version: '1.0.0',
  license: 'MIT',
  default_options: ['warning_level=2', 'werror=false'])

# Python dependency
py = import('python').find_installation('python3')
py_dep = py.dependency()

# Check for GTK4 and libadwaita via pkg-config
gnome = import('gnome')
gtk4_dep = dependency('gtk4', version: '>=4.10')
adw_dep = dependency('libadwaita-1', version: '>=1.5')
gio_dep = dependency('gio-2.0', version: '>=2.76')
glib_dep = dependency('glib-2.0', version: '>=2.76')

# Install data files
install_data(
  'data/icons/hicolor/scalable/apps/com.fallen-arch.Tadpole.svg',
  install_dir: join_paths(get_option('datadir'), 'icons/hicolor/scalable/apps'),
  rename: 'com.fallen-arch.Tadpole.svg'
)

install_data(
  'data/applications/com.fallen-arch.Tadpole.desktop',
  install_dir: join_paths(get_option('datadir'), 'applications'),
  rename: 'com.fallen-arch.Tadpole.desktop'
)

install_data(
  'data/metainfo/com.fallen-arch.Tadpole.metainfo.xml',
  install_dir: join_paths(get_option('datadir'), 'metainfo'),
  rename: 'com.fallen-arch.Tadpole.metainfo.xml'
)

install_data(
  'man/tadpole.1',
  install_dir: join_paths(get_option('mandir'), 'man1'),
  rename: 'tadpole.1'
)

# Install UI files (if any)
ui_files = files('src/tadpole/ui/*.ui')
foreach ui_file : ui_files
  install_data(ui_file, install_dir: join_paths(get_option('datadir'), 'tadpole', 'ui'))
endforeach

# Python package installation
python = import('python')
python.install_sources(
  'src/tadpole',
  install_dir: python.get_install_dir(),
  pure: false
)

# Create executable wrapper
tadpole_script = configure_file(
  input: 'scripts/tadpole.in',
  output: 'tadpole',
  configuration: configuration_data()
)
install_script(tadpole_script, install_dir: get_option('bindir'), rename: 'tadpole')

# Test
test('import_test', py, args: ['-c', 'import tadpole; import tadpole.application; print("OK")'])

# Summary
summary = {
  'Project': 'Tadpole',
  'Version': meson.project_version(),
  'Python': py.version(),
  'GTK4': gtk4_dep.version(),
  'libadwaita': adw_dep.version(),
}
foreach key, val : summary
  message(key + ': ' + val)
endforeach
