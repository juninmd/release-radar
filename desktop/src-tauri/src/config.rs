use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

/// Ajustes do app. O token de acesso fica só no disco, fora deste struct público.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct AppConfig {
    pub api_base_url: String,
    pub poll_minutes: u32,
    pub notify: bool,
    pub always_on_top: bool,
    pub autostart: bool,
    pub skin: String,
    pub shortcut: String,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            api_base_url: String::new(),
            poll_minutes: 10,
            notify: true,
            always_on_top: true,
            autostart: false,
            skin: "dark".to_string(),
            shortcut: "ctrl+shift+r".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase", default)]
pub struct StoredConfig {
    #[serde(flatten)]
    pub config: AppConfig,
    pub api_token: String,
}

/// O que a interface recebe: nunca devolve o token, apenas se há um guardado.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicConfig {
    #[serde(flatten)]
    pub config: AppConfig,
    pub has_token: bool,
    /// Qual atalho global ficou registrado de fato (None se nenhum).
    pub active_shortcut: Option<String>,
}

pub struct ConfigStore {
    path: PathBuf,
    inner: Mutex<StoredConfig>,
}

impl ConfigStore {
    pub fn load(app: &AppHandle) -> Self {
        // Sem diretório de config, usa a pasta temporária — nunca o diretório atual,
        // onde o token poderia acabar dentro de um repositório.
        let dir = app
            .path()
            .app_config_dir()
            .unwrap_or_else(|_| std::env::temp_dir().join("release-radar"));
        let _ = fs::create_dir_all(&dir);
        let path = dir.join("config.json");
        let stored = fs::read_to_string(&path)
            .ok()
            .and_then(|raw| serde_json::from_str::<StoredConfig>(&raw).ok())
            .unwrap_or_default();
        Self {
            path,
            inner: Mutex::new(stored),
        }
    }

    pub fn snapshot(&self) -> StoredConfig {
        self.inner.lock().map(|guard| guard.clone()).unwrap_or_default()
    }

    pub fn public(&self) -> PublicConfig {
        let stored = self.snapshot();
        public_from(&stored)
    }

    /// `api_token` ausente mantém o token atual; uma string vazia o apaga.
    pub fn set(&self, config: AppConfig, api_token: Option<String>) -> Result<PublicConfig, String> {
        let mut guard = self
            .inner
            .lock()
            .map_err(|_| "Configuração indisponível.".to_string())?;
        guard.config = sanitize(config);
        if let Some(token) = api_token {
            guard.api_token = token.trim().to_string();
        }
        let stored = guard.clone();
        drop(guard);
        self.persist(&stored)?;
        Ok(public_from(&stored))
    }

    fn persist(&self, stored: &StoredConfig) -> Result<(), String> {
        let body = serde_json::to_string_pretty(stored)
            .map_err(|error| format!("Não foi possível serializar os ajustes: {error}"))?;
        write_private(&self.path, &body).map_err(|error| format!("Não foi possível gravar os ajustes: {error}"))
    }
}

/// O arquivo guarda o token: no Unix nasce 0600, longe de outros usuários.
fn write_private(path: &Path, body: &str) -> std::io::Result<()> {
    let mut options = fs::OpenOptions::new();
    options.write(true).create(true).truncate(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(path)?;
    file.write_all(body.as_bytes())
}

fn public_from(stored: &StoredConfig) -> PublicConfig {
    PublicConfig {
        config: stored.config.clone(),
        has_token: !stored.api_token.is_empty(),
        active_shortcut: None,
    }
}

fn sanitize(mut config: AppConfig) -> AppConfig {
    config.api_base_url = config.api_base_url.trim().trim_end_matches('/').to_string();
    config.poll_minutes = config.poll_minutes.min(24 * 60);
    if config.skin != "light" && config.skin != "system" {
        config.skin = "dark".to_string();
    }
    config.shortcut = crate::shortcut::normalize(&config.shortcut);
    if config.shortcut.is_empty() {
        config.shortcut = AppConfig::default().shortcut;
    }
    config
}

#[cfg(test)]
mod tests {
    use super::{sanitize, AppConfig, StoredConfig};

    #[test]
    fn sanitize_trims_base_url_and_caps_poll_minutes() {
        let config = sanitize(AppConfig {
            api_base_url: "  https://radar.test/  ".to_string(),
            poll_minutes: 99_999,
            skin: "glass".to_string(),
            ..AppConfig::default()
        });
        assert_eq!(config.api_base_url, "https://radar.test");
        assert_eq!(config.poll_minutes, 24 * 60);
        assert_eq!(config.skin, "dark");
    }

    #[test]
    fn sanitize_keeps_known_skins() {
        for skin in ["light", "system", "dark"] {
            let config = sanitize(AppConfig {
                skin: skin.to_string(),
                ..AppConfig::default()
            });
            assert_eq!(config.skin, skin);
        }
    }

    #[test]
    fn sanitize_normalizes_the_shortcut_and_restores_the_default() {
        let custom = sanitize(AppConfig {
            shortcut: " Ctrl + Shift + R ".to_string(),
            ..AppConfig::default()
        });
        assert_eq!(custom.shortcut, "ctrl+shift+r");

        let empty = sanitize(AppConfig {
            shortcut: "   ".to_string(),
            ..AppConfig::default()
        });
        assert_eq!(empty.shortcut, "ctrl+shift+r");
    }

    #[test]
    fn public_config_serializes_the_new_fields_in_camel_case() {
        let stored: StoredConfig = serde_json::from_str(r#"{"apiToken":"segredo"}"#).unwrap();
        let mut public = super::public_from(&stored);
        public.active_shortcut = Some("ctrl+shift+r".to_string());
        let json = serde_json::to_value(&public).unwrap();
        assert_eq!(json["hasToken"], true);
        assert_eq!(json["activeShortcut"], "ctrl+shift+r");
        assert_eq!(json["apiBaseUrl"], "");
        assert!(json.get("api_token").is_none());
    }

    #[test]
    fn stored_config_tolerates_partial_json() {
        let stored: StoredConfig =
            serde_json::from_str(r#"{"apiBaseUrl":"https://radar.test"}"#).expect("config antiga deve carregar");
        assert_eq!(stored.config.api_base_url, "https://radar.test");
        assert_eq!(stored.config.poll_minutes, 10);
        assert!(stored.api_token.is_empty());
    }

    #[test]
    fn stored_config_roundtrips_the_token() {
        let stored: StoredConfig =
            serde_json::from_str(r#"{"apiBaseUrl":"https://radar.test","apiToken":"segredo","notify":false}"#)
                .expect("config completa deve carregar");
        assert_eq!(stored.api_token, "segredo");
        assert!(!stored.config.notify);
    }
}
