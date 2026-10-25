from pathlib import Path

from release_radar.config import Settings

# Lista explicita de campos de Settings que estao dispensados de constar no .env.example,
# acompanhados do motivo da excecao.
EXCEPTIONS: dict[str, str] = {
    # Exemplo:
    # "campo_interno": "Campo de configuracao interna nao exposto como variavel de ambiente."
}


def test_env_example_keys_match_settings() -> None:
    """Garante sincronia entre .env.example e Settings para evitar drift de documentacao."""
    env_path = Path(__file__).parents[1] / ".env.example"
    assert env_path.exists(), ".env.example nao encontrado"

    env_keys: set[str] = set()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip().lower()
            env_keys.add(key)

    settings_fields = {k.lower(): k for k in Settings.model_fields}

    # (a) Toda chave em .env.example deve corresponder a um campo de Settings
    unknown_env_keys = env_keys - set(settings_fields)
    assert not unknown_env_keys, (
        f"Chaves em .env.example inexistentes em Settings: {sorted(unknown_env_keys)}"
    )

    # (b) Todo campo escalar de Settings deve constar no .env.example ou na lista de excecoes
    missing_fields = set(settings_fields.keys()) - env_keys - set(EXCEPTIONS.keys())
    assert not missing_fields, (
        f"Campos de Settings ausentes em .env.example e sem excecao: {sorted(missing_fields)}"
    )
