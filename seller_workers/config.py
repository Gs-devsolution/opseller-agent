"""Configuracoes do OpSeller Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
ENV_EXAMPLE_PATH = Path(__file__).resolve().parent.parent / ".env.example"

load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class Config:
    supabase_url: str
    supabase_key: str
    executor_1_vitrines_enabled: bool = False
    executor_2_produtos_enabled: bool = False
    executor_3_teste_seller_enabled: bool = False
    executor_4_produtos_enabled: bool = False
    intervalo_orquestrador_segundos: int = 5
    intervalo_sem_pendentes_segundos: int = 60 * 60
    intervalo_apos_lote_segundos: int = 20 * 60
    max_paginas_por_vitrine: int = 0
    selenium_profile_dir: str = "chrome_profile"
    amazon_base_url: str = "https://www.amazon.com.br/dp"
    seller_central_url: str = "https://sellercentral.amazon.com.br/product-search"
    seller_auto_login_enabled: bool = True
    seller_email: str = ""
    seller_password: str = ""
    seller_totp_secret: str = ""
    teste_seller_session_count: int = 2
    teste_seller_session_max: int = 4
    executor_3_batch_size: int = 100


def carregar_config() -> Config:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Configure as variaveis SUPABASE_URL e SUPABASE_KEY no arquivo .env."
        )

    return carregar_config_permissiva()


def carregar_config_permissiva() -> Config:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()

    return Config(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        executor_1_vitrines_enabled=_env_bool("EXECUTOR_1_VITRINES_ENABLED", False),
        executor_2_produtos_enabled=_env_bool("EXECUTOR_2_PRODUTOS_ENABLED", False),
        executor_3_teste_seller_enabled=_env_bool(
            "EXECUTOR_3_TESTE_SELLER_ENABLED",
            False,
        ),
        executor_4_produtos_enabled=_env_bool("EXECUTOR_4_PRODUTOS_ENABLED", False),
        intervalo_orquestrador_segundos=_env_int("INTERVALO_ORQUESTRADOR_SEGUNDOS", 5),
        intervalo_sem_pendentes_segundos=_env_int(
            "INTERVALO_SEM_PENDENTES_SEGUNDOS",
            60 * 60,
        ),
        intervalo_apos_lote_segundos=_env_int(
            "INTERVALO_APOS_LOTE_SEGUNDOS",
            20 * 60,
        ),
        max_paginas_por_vitrine=_env_int("MAX_PAGINAS_POR_VITRINE", 0),
        selenium_profile_dir=os.getenv("SELENIUM_PROFILE_DIR", "chrome_profile").strip()
        or "chrome_profile",
        seller_central_url=os.getenv(
            "SELLER_CENTRAL_URL",
            "https://sellercentral.amazon.com.br/product-search",
        ).strip()
        or "https://sellercentral.amazon.com.br/product-search",
        seller_auto_login_enabled=_env_bool("SELLER_AUTO_LOGIN_ENABLED", True),
        seller_email=os.getenv("SELLER_EMAIL", "").strip(),
        seller_password=os.getenv("SELLER_PASSWORD", "").strip(),
        seller_totp_secret=os.getenv("SELLER_TOTP_SECRET", "").strip(),
        teste_seller_session_count=_env_int("TESTE_SELLER_SESSION_COUNT", 2),
        teste_seller_session_max=_env_int("TESTE_SELLER_SESSION_MAX", 4),
        executor_3_batch_size=_env_int("EXECUTOR_3_BATCH_SIZE", 100),
    )


def config_supabase_completa(config: Config) -> bool:
    return bool(config.supabase_url and config.supabase_key)


def salvar_config_supabase(supabase_url: str, supabase_key: str) -> Config:
    supabase_url = supabase_url.strip()
    supabase_key = supabase_key.strip()

    if not supabase_url or not supabase_key:
        raise RuntimeError("Informe SUPABASE_URL e SUPABASE_KEY.")

    valores = _ler_env()
    valores["SUPABASE_URL"] = supabase_url
    valores["SUPABASE_KEY"] = supabase_key
    _aplicar_defaults_env(valores)
    _salvar_env(valores)

    os.environ["SUPABASE_URL"] = supabase_url
    os.environ["SUPABASE_KEY"] = supabase_key
    load_dotenv(ENV_PATH, override=True)

    return carregar_config()


def _ler_env() -> dict[str, str]:
    origem = ENV_PATH if ENV_PATH.exists() else ENV_EXAMPLE_PATH
    valores: dict[str, str] = {}

    if not origem.exists():
        return _defaults_env()

    for linha in origem.read_text(encoding="utf-8").splitlines():
        texto = linha.strip()
        if not texto or texto.startswith("#") or "=" not in texto:
            continue

        chave, valor = texto.split("=", 1)
        valores[chave.strip()] = valor.strip()

    _aplicar_defaults_env(valores)
    return valores


def _defaults_env() -> dict[str, str]:
    return {
        "SUPABASE_URL": "",
        "SUPABASE_KEY": "",
        "EXECUTOR_1_VITRINES_ENABLED": "false",
        "EXECUTOR_2_PRODUTOS_ENABLED": "false",
        "EXECUTOR_3_TESTE_SELLER_ENABLED": "false",
        "EXECUTOR_4_PRODUTOS_ENABLED": "false",
        "INTERVALO_ORQUESTRADOR_SEGUNDOS": "5",
        "INTERVALO_SEM_PENDENTES_SEGUNDOS": "3600",
        "INTERVALO_APOS_LOTE_SEGUNDOS": "1200",
        "MAX_PAGINAS_POR_VITRINE": "0",
        "SELENIUM_PROFILE_DIR": "chrome_profile",
        "SELLER_CENTRAL_URL": "https://sellercentral.amazon.com.br/product-search",
        "SELLER_AUTO_LOGIN_ENABLED": "true",
        "SELLER_EMAIL": "",
        "SELLER_PASSWORD": "",
        "SELLER_TOTP_SECRET": "",
        "TESTE_SELLER_SESSION_COUNT": "2",
        "TESTE_SELLER_SESSION_MAX": "4",
        "EXECUTOR_3_BATCH_SIZE": "100",
    }


def _aplicar_defaults_env(valores: dict[str, str]) -> None:
    for chave, valor in _defaults_env().items():
        valores.setdefault(chave, valor)


def _salvar_env(valores: dict[str, str]) -> None:
    ordem = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "EXECUTOR_1_VITRINES_ENABLED",
        "EXECUTOR_2_PRODUTOS_ENABLED",
        "EXECUTOR_3_TESTE_SELLER_ENABLED",
        "EXECUTOR_4_PRODUTOS_ENABLED",
        "INTERVALO_ORQUESTRADOR_SEGUNDOS",
        "INTERVALO_SEM_PENDENTES_SEGUNDOS",
        "INTERVALO_APOS_LOTE_SEGUNDOS",
        "MAX_PAGINAS_POR_VITRINE",
        "SELENIUM_PROFILE_DIR",
        "SELLER_CENTRAL_URL",
        "SELLER_AUTO_LOGIN_ENABLED",
        "SELLER_EMAIL",
        "SELLER_PASSWORD",
        "SELLER_TOTP_SECRET",
        "TESTE_SELLER_SESSION_COUNT",
        "TESTE_SELLER_SESSION_MAX",
        "EXECUTOR_3_BATCH_SIZE",
    ]

    linhas: list[str] = []
    for chave in ordem:
        if chave in valores:
            linhas.append(f"{chave}={valores[chave]}")
            if chave == "SUPABASE_KEY":
                linhas.append("")

    ENV_PATH.write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8")


def _env_bool(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao

    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _env_int(nome: str, padrao: int) -> int:
    valor = os.getenv(nome)
    if valor is None or not valor.strip():
        return padrao

    try:
        return int(valor)
    except ValueError:
        raise RuntimeError(f"A variavel {nome} precisa ser um numero inteiro.")
