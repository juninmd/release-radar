use tauri::{AppHandle, Manager, PhysicalPosition, WebviewWindow};

pub fn toggle(app: &AppHandle) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };
    if window.is_visible().unwrap_or(false) {
        let _ = window.hide();
    } else {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

pub fn show(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

pub fn hide(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

/// Ancora o widget no canto inferior direito do monitor principal, como no Canto.
pub fn position_corner(window: &WebviewWindow) {
    const MARGIN: i32 = 24;
    let Ok(Some(monitor)) = window.primary_monitor() else {
        return;
    };
    let Ok(size) = window.outer_size() else {
        return;
    };
    let origin = monitor.position();
    let screen = monitor.size();
    let x = origin.x + screen.width as i32 - size.width as i32 - MARGIN;
    let y = origin.y + screen.height as i32 - size.height as i32 - MARGIN;
    let _ = window.set_position(PhysicalPosition::new(x, y));
}
