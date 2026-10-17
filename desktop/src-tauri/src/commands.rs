use tauri::{AppHandle, Manager, State};

use crate::config::{AppConfig, ConfigStore, PublicConfig};
use crate::shortcut::{self, ShortcutState};
use crate::tray;
use crate::window;

#[tauri::command]
pub fn read_config(store: State<'_, ConfigStore>, shortcuts: State<'_, ShortcutState>) -> PublicConfig {
    let mut public = store.public();
    public.active_shortcut = shortcuts.active();
    public
}

#[tauri::command]
pub fn save_config(
    config: AppConfig,
    api_token: Option<String>,
    app: AppHandle,
    store: State<'_, ConfigStore>,
    shortcuts: State<'_, ShortcutState>,
) -> Result<PublicConfig, String> {
    let saved = store.set(config, api_token)?;
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_always_on_top(saved.config.always_on_top);
    }
    apply_autostart(&app, saved.config.autostart);

    let active = shortcut::apply(&app, &saved.config.shortcut, &shortcuts);
    tray::set_shortcut_hint(&app, active.as_deref());

    let mut public = store.public();
    public.active_shortcut = active;
    Ok(public)
}

#[tauri::command]
pub fn set_always_on_top(app: AppHandle, value: bool) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.set_always_on_top(value).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn notify(app: AppHandle, store: State<'_, ConfigStore>, title: String, body: String) -> Result<(), String> {
    if !store.snapshot().config.notify {
        return Ok(());
    }
    use tauri_plugin_notification::NotificationExt;
    app.notification()
        .builder()
        .title(title)
        .body(body)
        .show()
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub fn open_link(app: AppHandle, url: String) -> Result<(), String> {
    let parsed = url::Url::parse(&url).map_err(|_| "Endereço inválido.".to_string())?;
    if parsed.scheme() != "http" && parsed.scheme() != "https" {
        return Err("Só links http(s) podem ser abertos.".to_string());
    }
    use tauri_plugin_opener::OpenerExt;
    app.opener()
        .open_url(url, None::<&str>)
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub fn toggle_window(app: AppHandle) {
    window::toggle(&app);
}

#[tauri::command]
pub fn show_window(app: AppHandle) {
    window::show(&app);
}

#[tauri::command]
pub fn hide_window(app: AppHandle) {
    window::hide(&app);
}

fn apply_autostart(app: &AppHandle, enabled: bool) {
    use tauri_plugin_autostart::ManagerExt;
    let manager = app.autolaunch();
    let _ = if enabled { manager.enable() } else { manager.disable() };
}
