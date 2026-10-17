mod api;
mod commands;
mod config;
mod shortcut;
mod tray;
mod window;

use std::sync::atomic::{AtomicBool, Ordering};

use tauri::Manager;
use tauri_plugin_global_shortcut::ShortcutState as GlobalShortcutState;

/// No Windows o `show()` no setup se perde antes de o webview existir; ancoramos
/// e mostramos no primeiro carregamento de página, uma única vez.
static FIRST_SHOW: AtomicBool = AtomicBool::new(false);

pub fn run() {
    // O provider do rustls precisa existir antes de qualquer conexão TLS.
    let _ = rustls::crypto::ring::default_provider().install_default();

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            window::show(app);
        }))
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == GlobalShortcutState::Pressed {
                        window::toggle(app);
                    }
                })
                .build(),
        )
        .plugin(tauri_plugin_updater::Builder::new().build())
        .on_page_load(|webview, _payload| {
            if webview.label() != "main" || FIRST_SHOW.swap(true, Ordering::SeqCst) {
                return;
            }
            if let Some(window) = webview.app_handle().get_webview_window("main") {
                let always_on_top = webview.state::<config::ConfigStore>().snapshot().config.always_on_top;
                let _ = window.set_always_on_top(always_on_top);
                window::position_corner(&window);
                let _ = window.show();
                let _ = window.set_focus();
            }
        })
        .setup(|app| {
            let handle = app.handle().clone();
            let store = config::ConfigStore::load(&handle);
            let config = store.snapshot().config;
            app.manage(store);
            app.manage(api::ApiClient::new());
            app.manage(shortcut::ShortcutState::default());

            // Ancorar antes do primeiro quadro; o on_page_load confirma depois.
            if let Some(window) = app.get_webview_window("main") {
                window::position_corner(&window);
            }

            tray::build(&handle)?;

            let shortcuts = app.state::<shortcut::ShortcutState>();
            let active = shortcut::apply(&handle, &config.shortcut, &shortcuts);
            tray::set_shortcut_hint(&handle, active.as_deref());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::read_config,
            commands::save_config,
            commands::set_always_on_top,
            commands::notify,
            commands::open_link,
            commands::toggle_window,
            commands::show_window,
            commands::hide_window,
            api::health,
            api::list_releases,
            api::read_settings,
            api::write_settings,
            api::start_run,
            api::run_status,
        ])
        .run(tauri::generate_context!())
        .expect("erro ao executar o Release Radar");
}
