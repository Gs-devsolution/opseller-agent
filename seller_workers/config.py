"""Configuracoes do OpSeller Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


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


def carregar_config() -> Config:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Configure as variaveis SUPABASE_URL e SUPABASE_KEY no arquivo .env."
        )

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
    )


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
