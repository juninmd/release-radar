// Na release o app não abre console no Windows.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    release_radar_desktop_lib::run();
}
