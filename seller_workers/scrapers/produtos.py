"""Scraper de produtos listados em uma vitrine da Amazon."""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Callable

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from seller_workers.scrapers.vitrines import continuar_comprando_se_aparecer

StopFn = Callable[[], bool]


def capturar_produtos_vitrine(
    driver: WebDriver,
    vitrine: str,
    timeout: int = 8,
    max_paginas: int = 0,
    on_produto_encontrado: Callable[[dict[str, str]], None] | None = None,
    should_stop: StopFn = lambda: False,
) -> dict[str, object]:
    interromper_se_solicitado(should_stop)
    wait = WebDriverWait(driver, timeout)
    driver.get(vitrine)
    interromper_se_solicitado(should_stop)
    continuar_comprando_se_aparecer(driver)
    validar_pagina_amazon(driver)

    try:
        aguardar_resultados(driver)
    except TimeoutException:
        print("Produtos nao apareceram de imediato. Vou tentar detectar a paginacao mesmo assim.")

    rolar_ate_paginacao(driver)

    total_paginas = obter_total_paginas(driver, wait)
    if max_paginas > 0:
        total_paginas = min(total_paginas, max_paginas)

    print(f"Total de paginas da vitrine: {total_paginas}")
    produtos, paginas_processadas, paginas_com_erro = capturar_asins_itens(
        driver,
        driver.current_url,
        total_paginas,
        on_produto_encontrado=on_produto_encontrado,
        should_stop=should_stop,
    )

    return {
        "produtos": produtos,
        "total_paginas": total_paginas,
        "paginas_processadas": paginas_processadas,
        "paginas_com_erro": paginas_com_erro,
        "varredura_completa": len(paginas_com_erro) == 0
        and len(paginas_processadas) == total_paginas,
    }


def obter_total_paginas(driver: WebDriver, wait: WebDriverWait) -> int:
    total_por_texto = extrair_total_paginas_por_texto(driver)
    if total_por_texto > 1:
        return total_por_texto

    try:
        wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//*[contains(@class,'s-pagination-container') or @aria-label='pagination' or @role='navigation']",
                )
            )
        )
    except TimeoutException:
        return 1

    itens = driver.find_elements(
        By.XPATH,
        "//*[contains(@class,'s-pagination-container') or @aria-label='pagination' or @role='navigation']//a | "
        "//*[contains(@class,'s-pagination-container') or @aria-label='pagination' or @role='navigation']//span",
    )

    paginas = []
    for item in itens:
        texto = item.text.strip()
        if texto.isdigit():
            paginas.append(int(texto))

    return max(paginas) if paginas else 1


def extrair_total_paginas_por_texto(driver: WebDriver) -> int:
    texto_pagina = driver.find_element(By.TAG_NAME, "body").text
    match = re.search(r"Pagina\s+\d+\s+de\s+(\d+)", remover_acentos(texto_pagina), re.I)

    if not match:
        return 1

    return int(match.group(1))


def trocar_pagina_url(url: str, pagina: int) -> str:
    if "page=" not in url:
        separador = "&" if "?" in url else "?"
        return f"{url}{separador}page={pagina}"

    prefixo, sufixo = url.split("page=", 1)

    if "&" in sufixo:
        _, resto = sufixo.split("&", 1)
        return f"{prefixo}page={pagina}&{resto}"

    return f"{prefixo}page={pagina}"


def capturar_asins_itens(
    driver: WebDriver,
    url_base: str,
    qtd_paginas: int,
    on_produto_encontrado: Callable[[dict[str, str]], None] | None = None,
    should_stop: StopFn = lambda: False,
) -> tuple[list[dict[str, str]], list[int], list[int]]:
    lista: list[dict[str, str]] = []
    vistos: set[str] = set()
    paginas_processadas: list[int] = []
    paginas_com_erro: list[int] = []
    wait = WebDriverWait(driver, 20)

    for pagina in range(1, qtd_paginas + 1):
        interromper_se_solicitado(should_stop)
        total_antes_pagina = len(lista)
        url_pagina = url_base if pagina == 1 else trocar_pagina_url(url_base, pagina)
        print(f"Acessando pagina {pagina}: {url_pagina}")
        driver.get(url_pagina)
        interromper_se_solicitado(should_stop)
        continuar_comprando_se_aparecer(driver)
        validar_pagina_amazon(driver)

        try:
            wait.until(
                EC.presence_of_all_elements_located(
                    (
                        By.XPATH,
                        "//div[@data-component-type='s-search-result' and @data-asin!='']",
                    )
                )
            )
        except TimeoutException:
            print(f"Nao encontrei produtos na pagina {pagina}. Seguindo para a proxima.")
            paginas_com_erro.append(pagina)
            continue

        time.sleep(2)

        produtos = driver.find_elements(
            By.XPATH,
            "//div[@data-component-type='s-search-result' and @data-asin!='']",
        )

        print(f"Produtos encontrados na pagina {pagina}: {len(produtos)}")
        paginas_processadas.append(pagina)

        for produto in produtos:
            interromper_se_solicitado(should_stop)
            try:
                asin = produto.get_attribute("data-asin").strip()

                if asin and asin not in vistos:
                    vistos.add(asin)
                    produto_capturado = {"asin": asin, "pagina": str(pagina)}
                    lista.append(produto_capturado)

                    if on_produto_encontrado:
                        on_produto_encontrado(produto_capturado)
            except Exception as exc:
                print(f"Erro ao capturar item: {exc}")

        novos_pagina = len(lista) - total_antes_pagina
        duplicados_pagina = len(produtos) - novos_pagina
        print(
            f"Pagina {pagina}: {novos_pagina} ASIN(s) novo(s), "
            f"{duplicados_pagina} duplicado(s) na varredura."
        )

    print(f"Total de ASINs unicos capturados na vitrine: {len(lista)}")
    return lista, paginas_processadas, paginas_com_erro


def interromper_se_solicitado(should_stop: StopFn) -> None:
    if should_stop():
        raise RuntimeError("Execucao interrompida pelo usuario.")


def aguardar_resultados(driver: WebDriver) -> None:
    wait = WebDriverWait(driver, 20)
    wait.until(
        EC.presence_of_all_elements_located(
            (By.XPATH, "//div[@data-component-type='s-search-result' and @data-asin!='']")
        )
    )


def validar_pagina_amazon(driver: WebDriver) -> None:
    for tentativa in range(1, 4):
        texto = remover_acentos(driver.find_element(By.TAG_NAME, "body").text).lower()
        titulo = remover_acentos(driver.title or "").lower()

        if not (("desculpe" in texto and "algo deu errado" in texto) or "desculpe" in titulo):
            break

        print(f"Amazon retornou pagina de erro. Recarregando {tentativa}/3.")
        driver.refresh()
        time.sleep(3)
    else:
        raise RuntimeError("Amazon retornou a pagina 'Desculpe, algo deu errado'.")

    texto = remover_acentos(driver.find_element(By.TAG_NAME, "body").text).lower()
    titulo = remover_acentos(driver.title or "").lower()

    if "desculpe" in texto and "algo deu errado" in texto:
        raise RuntimeError("Amazon retornou a pagina 'Desculpe, algo deu errado'.")

    if "captcha" in texto or "digite os caracteres" in texto:
        raise RuntimeError("Amazon solicitou captcha/verificacao.")

    if "desculpe" in titulo:
        raise RuntimeError("Amazon retornou uma pagina de erro.")


def rolar_ate_paginacao(driver: WebDriver) -> None:
    for _ in range(4):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)


def remover_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto)
    return "".join(char for char in normalizado if unicodedata.category(char) != "Mn")
