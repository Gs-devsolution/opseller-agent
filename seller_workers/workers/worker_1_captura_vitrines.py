"""Worker 1: captura vitrines relacionadas a um ASIN inicial."""

from __future__ import annotations

from typing import Any

from selenium.webdriver.remote.webdriver import WebDriver
from supabase import Client

from seller_workers.database import inserir_vitrine_se_nao_existir
from seller_workers.scrapers.vitrines import capturar_vitrines_do_produto


def capturar_vitrines(
    asin_inicial: str,
    driver: WebDriver,
    supabase: Client,
    amazon_base_url: str,
) -> dict[str, Any]:
    resultado = {
        "finalizado": False,
        "total_vitrines": 0,
        "novas_vitrines": 0,
        "vitrines_duplicadas": 0,
        "erro": None,
    }

    try:
        url_produto = f"{amazon_base_url}/{asin_inicial}"
        vitrines_capturadas = capturar_vitrines_do_produto(driver, url_produto)
        resultado["total_vitrines"] = len(vitrines_capturadas)

        for vitrine in vitrines_capturadas:
            inseriu = inserir_vitrine_se_nao_existir(
                supabase=supabase,
                asin_inicial=asin_inicial,
                vitrine=vitrine,
            )

            if inseriu:
                resultado["novas_vitrines"] += 1
            else:
                resultado["vitrines_duplicadas"] += 1

        resultado["finalizado"] = True
        return resultado

    except Exception as exc:
        resultado["erro"] = str(exc)
        return resultado
