use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter};

use crate::window;

pub fn build(app: &AppHandle) -> tauri::Result<()> {
    let toggle = MenuItem::with_id(app, "toggle", "Mostrar / ocultar", true, None::<&str>)?;
    let refresh = MenuItem::with_id(app, "refresh", "Atualizar lista", true, None::<&str>)?;
    let run = MenuItem::with_id(app, "run", "Buscar novidades agora", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "Ajustes", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let quit = MenuItem::with_id(app, "quit", "Sair", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&toggle, &refresh, &run, &separator, &settings, &quit])?;

    let mut builder = TrayIconBuilder::with_id("radar")
        .tooltip("Release Radar")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "toggle" => window::toggle(app),
            "refresh" => {
                let _ = app.emit("radar://refresh", ());
            }
            "run" => {
                window::show(app);
                let _ = app.emit("radar://run", ());
            }
            "settings" => {
                window::show(app);
                let _ = app.emit("radar://settings", ());
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                window::toggle(tray.app_handle());
            }
        });

    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

/// Reflete o atalho ativo na dica da bandeja (pode ser uma alternativa).
pub fn set_shortcut_hint(app: &AppHandle, active: Option<&str>) {
    let Some(tray) = app.tray_by_id("radar") else {
        return;
    };
    let text = match active {
        Some(accelerator) => format!("Release Radar · {} mostra/oculta", crate::shortcut::label(accelerator)),
        None => "Release Radar · atalho global indisponível".to_string(),
    };
    let _ = tray.set_tooltip(Some(text));
}
