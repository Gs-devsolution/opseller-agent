"""Worker 3: testa ASIN no Seller Central autenticado."""

from __future__ import annotations

from typing import Any, Callable

from selenium.webdriver.remote.webdriver import WebDriver

from seller_workers.scrapers.teste_seller import testar_asin_no_seller

LogFn = Callable[[str], None]


def testar_produto_seller(
    asin_produto: str,
    driver: WebDriver,
    log: LogFn = print,
) -> dict[str, Any]:
    resultado = {
        "finalizado": False,
        "resultado": None,
        "motivo": None,
        "erro": None,
    }

    teste = testar_asin_no_seller(driver, asin_produto)
    resultado["finalizado"] = bool(teste.get("finalizado"))
    resultado["resultado"] = teste.get("resultado")
    resultado["motivo"] = teste.get("motivo")

    if not resultado["finalizado"]:
        resultado["erro"] = resultado["motivo"]
        log(f"Teste Seller incompleto para {asin_produto}: {resultado['motivo']}")
    else:
        log(
            f"Teste Seller finalizado para {asin_produto}: "
            f"{resultado['resultado']} | {resultado['motivo']}"
        )

    return resultado
