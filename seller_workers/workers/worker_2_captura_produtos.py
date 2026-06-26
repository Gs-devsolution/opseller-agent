"""Worker 2: captura produtos de uma vitrine."""

from __future__ import annotations

from typing import Any, Callable

from selenium.webdriver.remote.webdriver import WebDriver
from supabase import Client

from seller_workers.database import inserir_produto_capturado_se_nao_existir
from seller_workers.scrapers.produtos import capturar_produtos_vitrine

LogFn = Callable[[str], None]
StopFn = Callable[[], bool]


def capturar_produtos(
    vitrine: str,
    driver: WebDriver,
    supabase: Client,
    max_paginas: int = 0,
    log: LogFn = print,
    should_stop: StopFn = lambda: False,
) -> dict[str, Any]:
    resultado = {
        "finalizado": False,
        "total_produtos": 0,
        "novos_produtos": 0,
        "produtos_duplicados": 0,
        "total_paginas": 0,
        "paginas_processadas": [],
        "paginas_com_erro": [],
        "total_produtos_unicos": 0,
        "erro": None,
    }

    try:
        def gravar_produto_na_hora(produto: dict[str, Any]) -> None:
            if should_stop():
                raise RuntimeError("Execucao interrompida pelo usuario.")

            asin_produto = str(produto.get("asin", "")).strip()
            if not asin_produto:
                return

            resultado["total_produtos"] += 1
            resultado["total_produtos_unicos"] += 1
            pagina = produto.get("pagina", "?")

            inseriu = inserir_produto_capturado_se_nao_existir(
                supabase=supabase,
                vitrine=vitrine,
                asin_produto=asin_produto,
            )

            if inseriu:
                resultado["novos_produtos"] += 1
                log(f"Produto inserido: {asin_produto} | pagina {pagina}")
            else:
                resultado["produtos_duplicados"] += 1
                log(f"Produto duplicado ignorado: {asin_produto} | pagina {pagina}")

        mineracao = capturar_produtos_vitrine(
            driver=driver,
            vitrine=vitrine,
            max_paginas=max_paginas,
            on_produto_encontrado=gravar_produto_na_hora,
            should_stop=should_stop,
        )
        produtos_capturados = mineracao["produtos"]
        asins_capturados = _extrair_asins_unicos(produtos_capturados)
        resultado["total_produtos_unicos"] = len(asins_capturados)
        resultado["total_paginas"] = mineracao["total_paginas"]
        resultado["paginas_processadas"] = mineracao["paginas_processadas"]
        resultado["paginas_com_erro"] = mineracao["paginas_com_erro"]

        if not mineracao["varredura_completa"]:
            resultado["erro"] = "Varredura incompleta; vitrine permanecera pendente."
            return resultado

        resultado["finalizado"] = True
        return resultado

    except Exception as exc:
        resultado["erro"] = str(exc)
        return resultado


def _extrair_asins_unicos(produtos: list[dict[str, Any]]) -> list[str]:
    asins: list[str] = []
    vistos: set[str] = set()

    for produto in produtos:
        asin_produto = str(produto.get("asin", "")).strip()
        if not asin_produto or asin_produto in vistos:
            continue

        vistos.add(asin_produto)
        asins.append(asin_produto)

    return asins
