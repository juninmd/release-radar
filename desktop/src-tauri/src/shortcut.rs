use std::str::FromStr;
use std::sync::Mutex;

use tauri::AppHandle;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

/// Alternativas testadas em ordem quando a tecla preferida já está ocupada.
/// `Ctrl+Shift+R` é o padrão por `Ctrl+Alt+R` ser muito disputado (Steam, overlays).
pub const FALLBACKS: [&str; 4] = ["ctrl+shift+r", "ctrl+alt+d", "ctrl+shift+space", "ctrl+alt+r"];

/// Guarda qual acelerador ficou de fato registrado (pode diferir do pedido).
#[derive(Default)]
pub struct ShortcutState {
    active: Mutex<Option<String>>,
}

impl ShortcutState {
    pub fn active(&self) -> Option<String> {
        self.active.lock().ok().and_then(|value| value.clone())
    }

    fn set(&self, value: Option<String>) {
        if let Ok(mut guard) = self.active.lock() {
            *guard = value;
        }
    }
}

/// "Ctrl + Alt + R" -> "ctrl+alt+r"
pub fn normalize(value: &str) -> String {
    value
        .to_lowercase()
        .split('+')
        .map(|part| part.trim().replace(' ', ""))
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>()
        .join("+")
}

/// "ctrl+alt+r" -> "Ctrl+Alt+R"
pub fn label(value: &str) -> String {
    const NAMES: [(&str, &str); 12] = [
        ("ctrl", "Ctrl"),
        ("control", "Ctrl"),
        ("alt", "Alt"),
        ("shift", "Shift"),
        ("super", "Super"),
        ("cmd", "Cmd"),
        ("space", "Space"),
        ("enter", "Enter"),
        ("tab", "Tab"),
        ("escape", "Esc"),
        ("backspace", "Backspace"),
        ("delete", "Delete"),
    ];
    normalize(value)
        .split('+')
        .map(|part| match NAMES.iter().find(|(key, _)| *key == part) {
            Some((_, name)) => (*name).to_string(),
            None => part.to_uppercase(),
        })
        .collect::<Vec<_>>()
        .join("+")
}

/// Registra a preferência ou a primeira alternativa livre. Devolve a ativa.
pub fn apply(app: &AppHandle, preferred: &str, state: &ShortcutState) -> Option<String> {
    let manager = app.global_shortcut();
    let _ = manager.unregister_all();
    let mut candidates = vec![normalize(preferred)];
    for fallback in FALLBACKS {
        let value = normalize(fallback);
        if !value.is_empty() && !candidates.contains(&value) {
            candidates.push(value);
        }
    }
    for candidate in candidates {
        if candidate.is_empty() {
            continue;
        }
        let Ok(shortcut) = Shortcut::from_str(&candidate) else {
            eprintln!("Release Radar: atalho inválido ignorado: {candidate}");
            continue;
        };
        match manager.register(shortcut) {
            Ok(()) => {
                eprintln!("Release Radar: atalho global ativo: {candidate}");
                state.set(Some(candidate.clone()));
                return Some(candidate);
            }
            Err(error) => eprintln!("Release Radar: atalho {candidate} indisponível: {error}"),
        }
    }
    state.set(None);
    None
}

#[cfg(test)]
mod tests {
    use super::{label, normalize};

    #[test]
    fn normalize_ignores_case_and_spaces() {
        assert_eq!(normalize("Ctrl + Alt + R"), "ctrl+alt+r");
        assert_eq!(normalize("  CTRL+SHIFT+SPACE "), "ctrl+shift+space");
        assert_eq!(normalize(""), "");
    }

    #[test]
    fn label_uses_readable_modifier_names() {
        assert_eq!(label("ctrl+alt+r"), "Ctrl+Alt+R");
        assert_eq!(label("control+shift+f5"), "Ctrl+Shift+F5");
        assert_eq!(label("ctrl+shift+space"), "Ctrl+Shift+Space");
    }
}
