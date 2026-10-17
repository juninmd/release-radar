use std::time::Duration;

use reqwest::Method;
use serde_json::{json, Value};
use tauri::State;

use crate::config::ConfigStore;

/// Só o processo Rust fala com a rede; o token nunca chega ao webview.
pub struct ApiClient {
    client: reqwest::Client,
}

impl ApiClient {
    pub fn new() -> Self {
        // Sem timeout, uma API travada deixaria a UI em "carregando" para sempre.
        let client = reqwest::Client::builder()
            .connect_timeout(Duration::from_secs(10))
            .timeout(Duration::from_secs(30))
            .build()
            .unwrap_or_else(|_| reqwest::Client::new());
        Self { client }
    }
}

fn endpoint(base: &str, path: &str) -> Result<String, String> {
    let base = base.trim().trim_end_matches('/');
    if base.is_empty() {
        return Err("Defina o endereço da API do radar nos ajustes.".to_string());
    }
    if !base.starts_with("http://") && !base.starts_with("https://") {
        return Err("O endereço da API deve começar com http:// ou https://.".to_string());
    }
    Ok(format!("{base}{path}"))
}

async fn send(
    client: &reqwest::Client,
    base: &str,
    token: &str,
    method: Method,
    path: &str,
    body: Option<Value>,
) -> Result<Value, String> {
    let url = endpoint(base, path)?;
    let mut request = client.request(method, url);
    if !token.is_empty() {
        request = request.bearer_auth(token);
    }
    if let Some(payload) = body {
        request = request.json(&payload);
    }
    let response = request.send().await.map_err(network_error)?;
    let status = response.status();
    let value = response.json::<Value>().await.unwrap_or(Value::Null);
    if !status.is_success() {
        let message = value
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("A API do radar recusou o pedido.");
        return Err(message.to_string());
    }
    Ok(value)
}

fn network_error(error: reqwest::Error) -> String {
    if error.is_timeout() {
        "A API do radar demorou demais para responder.".to_string()
    } else if error.is_connect() {
        "Não foi possível conectar à API do radar. Confira o endereço e a rede.".to_string()
    } else {
        format!("Falha de rede ao falar com o radar: {error}")
    }
}

#[cfg(test)]
mod tests {
    use super::endpoint;

    #[test]
    fn endpoint_normalizes_slashes() {
        assert_eq!(
            endpoint("https://radar.test/", "/api/health"),
            Ok("https://radar.test/api/health".into())
        );
        assert_eq!(
            endpoint("  https://radar.test  ", "/api/run"),
            Ok("https://radar.test/api/run".into())
        );
    }

    #[test]
    fn endpoint_rejects_empty_and_non_http_bases() {
        assert!(endpoint("", "/api/releases").is_err());
        assert!(endpoint("   ", "/api/releases").is_err());
        assert!(endpoint("ftp://radar.test", "/api/releases").is_err());
        assert!(endpoint("radar.test", "/api/releases").is_err());
    }
}

#[tauri::command]
pub async fn health(store: State<'_, ConfigStore>, api: State<'_, ApiClient>) -> Result<Value, String> {
    let cfg = store.snapshot();
    send(
        &api.client,
        &cfg.config.api_base_url,
        &cfg.api_token,
        Method::GET,
        "/api/health",
        None,
    )
    .await
}

#[tauri::command]
pub async fn list_releases(store: State<'_, ConfigStore>, api: State<'_, ApiClient>) -> Result<Value, String> {
    let cfg = store.snapshot();
    let value = send(
        &api.client,
        &cfg.config.api_base_url,
        &cfg.api_token,
        Method::GET,
        "/api/releases",
        None,
    )
    .await?;
    Ok(value.get("items").cloned().unwrap_or_else(|| Value::Array(Vec::new())))
}

#[tauri::command]
pub async fn read_settings(store: State<'_, ConfigStore>, api: State<'_, ApiClient>) -> Result<Value, String> {
    let cfg = store.snapshot();
    send(
        &api.client,
        &cfg.config.api_base_url,
        &cfg.api_token,
        Method::GET,
        "/api/settings",
        None,
    )
    .await
}

#[tauri::command]
pub async fn write_settings(
    values: Value,
    store: State<'_, ConfigStore>,
    api: State<'_, ApiClient>,
) -> Result<Value, String> {
    let cfg = store.snapshot();
    send(
        &api.client,
        &cfg.config.api_base_url,
        &cfg.api_token,
        Method::PUT,
        "/api/settings",
        Some(values),
    )
    .await
}

#[tauri::command]
pub async fn start_run(
    dry_run: bool,
    store: State<'_, ConfigStore>,
    api: State<'_, ApiClient>,
) -> Result<Value, String> {
    let cfg = store.snapshot();
    send(
        &api.client,
        &cfg.config.api_base_url,
        &cfg.api_token,
        Method::POST,
        "/api/run",
        Some(json!({ "dry_run": dry_run })),
    )
    .await
}

#[tauri::command]
pub async fn run_status(store: State<'_, ConfigStore>, api: State<'_, ApiClient>) -> Result<Value, String> {
    let cfg = store.snapshot();
    send(
        &api.client,
        &cfg.config.api_base_url,
        &cfg.api_token,
        Method::GET,
        "/api/run",
        None,
    )
    .await
}
