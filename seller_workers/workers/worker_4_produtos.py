"""Worker 4: enriquece produtos aprovados fora do Seller Central."""

from __future__ import annotations

from typing import Any, Callable

from selenium.webdriver.remote.webdriver import WebDriver
from supabase import Client

from seller_workers.database import salvar_produto_minerado
from seller_workers.scrapers.produto_detalhes import capturar_detalhes_produto

LogFn = Callable[[str], None]


def enriquecer_produto(
    asin_produto: str,
    driver: WebDriver,
    supabase: Client,
    amazon_base_url: str,
    log: LogFn = print,
) -> dict[str, Any]:
    resultado = {
        "finalizado": False,
        "asin": asin_produto,
        "produto": None,
        "erro": None,
    }

    try:
        produto = capturar_detalhes_produto(
            driver=driver,
            asin=asin_produto,
            amazon_base_url=amazon_base_url,
        )

        if not produto.get("nome_do_produto"):
            raise RuntimeError("Produto sem nome capturado; pagina considerada invalida.")

        salvar_produto_minerado(supabase, produto)
        resultado["produto"] = produto
        resultado["finalizado"] = True
        log(f"Produto enriquecido gravado: {asin_produto}")
        return resultado

    except Exception as exc:
        resultado["erro"] = str(exc)
        log(f"Erro ao enriquecer produto {asin_produto}: {exc}")
        return resultado
