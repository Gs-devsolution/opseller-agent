"""Scraper de vitrines relacionadas a uma pagina de produto da Amazon."""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def capturar_vitrines_do_produto(
    driver: WebDriver,
    produto_url: str,
    timeout: int = 8,
) -> list[str]:
    wait = WebDriverWait(driver, timeout)
    vitrines: list[str] = []
    vitrines_vistas: set[str] = set()

    driver.get(produto_url)
    continuar_comprando_se_aparecer(driver)
    validar_pagina_amazon(driver)
    time.sleep(2)

    links_vendedores_buybox = capturar_links_vendedores_buybox_pagina_produto(driver)
    print(f"Vendedores encontrados na buybox da pagina: {len(links_vendedores_buybox)}")

    link_ofertas = capturar_link_outras_ofertas(driver, wait)
    if not link_ofertas:
        print("Nao foi possivel localizar o link de outras ofertas.")
        links_vendedores = links_vendedores_buybox
    else:
        print(f"Link de ofertas: {link_ofertas}")
        driver.get(link_ofertas)
        continuar_comprando_se_aparecer(driver)
        validar_pagina_amazon(driver)
        time.sleep(3)

        expandir_detalhes_ofertas_pinadas(driver)

        try:
            carregar_todas_as_ofertas(driver, wait)
        except Exception as exc:
            if erro_driver_indisponivel(exc):
                raise RuntimeError("Selenium ficou indisponivel ao carregar ofertas.") from exc
            print(f"Nao foi possivel carregar todas as ofertas: {exc}")

        vitrines_diretas = capturar_vitrines_diretas_pagina_ofertas(driver)
        for link_vitrine in vitrines_diretas:
            if link_vitrine not in vitrines_vistas:
                vitrines_vistas.add(link_vitrine)
                vitrines.append(link_vitrine)
                print(f"Vitrine direta encontrada: {link_vitrine}")

        links_vendedores = juntar_links_vendedores(
            links_vendedores_buybox,
            capturar_links_paginas_vendedores(driver),
        )
    print(f"Paginas de vendedores encontradas: {len(links_vendedores)}")

    for link_vendedor in links_vendedores:
        try:
            driver.get(link_vendedor)
            continuar_comprando_se_aparecer(driver)
            validar_pagina_amazon(driver)
            time.sleep(2)

            link_vitrine = capturar_link_vitrine_na_pagina_vendedor(driver, wait)

            if link_vitrine and link_vitrine not in vitrines_vistas:
                vitrines_vistas.add(link_vitrine)
                vitrines.append(link_vitrine)
                print(f"Vitrine encontrada: {link_vitrine}")
        except Exception as exc:
            if erro_driver_indisponivel(exc):
                raise RuntimeError("Selenium ficou indisponivel ao processar vendedor.") from exc
            print(f"Erro ao processar vendedor {link_vendedor}: {exc}")

    return vitrines


def continuar_comprando_se_aparecer(driver: WebDriver) -> bool:
    wait_curto = WebDriverWait(driver, 2)
    xpaths = [
        "//button[contains(., 'Continuar comprando')]",
        "//button[@type='submit' and contains(., 'Continuar comprando')]",
        "//span[contains(@class,'a-button')]//button[contains(., 'Continuar comprando')]",
        "//input[@type='submit' and contains(@aria-labelledby, 'continuar')]",
    ]

    for xp in xpaths:
        try:
            botao = wait_curto.until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].click();", botao)
            time.sleep(2)
            print("Cliquei em Continuar comprando.")
            return True
        except Exception:
            continue

    return False


def validar_pagina_amazon(driver: WebDriver) -> None:
    for tentativa in range(1, 4):
        texto = _remover_acentos(driver.find_element(By.TAG_NAME, "body").text).lower()
        titulo = _remover_acentos(driver.title or "").lower()

        if not (("desculpe" in texto and "algo deu errado" in texto) or "desculpe" in titulo):
            break

        print(f"Amazon retornou pagina de erro. Recarregando {tentativa}/3.")
        driver.refresh()
        time.sleep(3)
    else:
        raise RuntimeError("Amazon retornou a pagina 'Desculpe, algo deu errado'.")

    texto = _remover_acentos(driver.find_element(By.TAG_NAME, "body").text).lower()
    titulo = _remover_acentos(driver.title or "").lower()

    if "desculpe" in texto and "algo deu errado" in texto:
        raise RuntimeError("Amazon retornou a pagina 'Desculpe, algo deu errado'.")

    if "captcha" in texto or "digite os caracteres" in texto:
        raise RuntimeError("Amazon solicitou captcha/verificacao.")

    if "desculpe" in titulo:
        raise RuntimeError("Amazon retornou uma pagina de erro.")


def _remover_acentos(texto: str) -> str:
    mapa = str.maketrans(
        "áàãâéêíóõôúçÁÀÃÂÉÊÍÓÕÔÚÇ",
        "aaaaeeioooucAAAAEEIOOOUC",
    )
    return texto.translate(mapa)


def expandir_detalhes_ofertas_pinadas(driver: WebDriver) -> None:
    for xp in [
        "//div[@id='aod-pinned-offer']//a[contains(., 'Ver mais')]",
        "//div[contains(@class,'aod-pinned-offer')]//a[contains(., 'Ver mais')]",
        "//div[@id='aod-pinned-offer']//span[contains(., 'Ver mais')]",
    ]:
        try:
            for botao in driver.find_elements(By.XPATH, xp):
                if not botao.is_displayed():
                    continue

                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});",
                    botao,
                )
                driver.execute_script("arguments[0].click();", botao)
                time.sleep(1)
        except Exception:
            continue


def capturar_links_vendedores_buybox_pagina_produto(driver: WebDriver) -> list[str]:
    links: list[str] = []

    xpaths = [
        "//a[@id='sellerProfileTriggerId' and @href]",
        "//div[@id='merchant-info']//a[@href]",
        "//div[@id='tabular-buybox']//a[contains(@href,'seller=') and @href]",
        "//a[contains(@href,'/gp/aag/main') and contains(@href,'seller=')]",
        "//a[contains(@href,'seller=') and contains(@href,'asin=')]",
    ]

    for xp in xpaths:
        try:
            for el in driver.find_elements(By.XPATH, xp):
                href = el.get_attribute("href")
                if href and extrair_seller_id(href):
                    links.append(href)
        except Exception:
            continue

    return juntar_links_vendedores(links)


def capturar_vitrines_diretas_pagina_ofertas(driver: WebDriver) -> list[str]:
    vitrines: list[str] = []
    vistas: set[str] = set()

    for bloco in capturar_blocos_de_ofertas(driver):
        for link_vitrine in capturar_links_vitrine_no_bloco(bloco):
            if link_vitrine in vistas:
                continue

            vistas.add(link_vitrine)
            vitrines.append(link_vitrine)

    print(f"Vitrines diretas encontradas nos blocos de oferta: {len(vitrines)}")
    return vitrines


def capturar_link_outras_ofertas(driver: WebDriver, wait: WebDriverWait) -> str | None:
    xpaths = [
        "//a[contains(@href,'/gp/offer-listing/')]",
        "//div[contains(., 'Outros vendedores na Amazon')]//a[@href]",
        "//a[contains(., 'outras ofertas')]",
        "//a[contains(., 'Outros vendedores')]",
    ]

    for xp in xpaths:
        try:
            el = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
            href = el.get_attribute("href")
            if href:
                return href
        except Exception:
            continue

    return None


def carregar_todas_as_ofertas(
    driver: WebDriver,
    wait: WebDriverWait,
    max_tentativas_sem_novidade: int = 5,
) -> None:
    container = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[@id='all-offers-display-scroller']")
        )
    )

    tentativas_sem_novidade = 0
    ultimo_total_ofertas = -1

    while True:
        total_antes = contar_ofertas(driver)
        client_height = driver.execute_script("return arguments[0].clientHeight;", container)

        for _ in range(3):
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight;",
                container,
            )
            time.sleep(1)

        altura_depois = driver.execute_script("return arguments[0].scrollTop;", container)
        altura_max_depois = driver.execute_script("return arguments[0].scrollHeight;", container)

        clicou_ver_mais = False
        chegou_no_fim = altura_depois + client_height >= altura_max_depois - 5

        if chegou_no_fim:
            clicou_ver_mais = tentar_clicar_ver_mais(driver)

        total_final = contar_ofertas(driver)
        print(
            f"Ofertas antes: {total_antes} | final: {total_final} | "
            f"clicou ver mais: {clicou_ver_mais}"
        )

        if total_final == ultimo_total_ofertas:
            tentativas_sem_novidade += 1
        else:
            tentativas_sem_novidade = 0

        ultimo_total_ofertas = total_final

        if tentativas_sem_novidade >= max_tentativas_sem_novidade:
            break


def tentar_clicar_ver_mais(driver: WebDriver) -> bool:
    xpaths = [
        "//a[@id='aod-show-more-offers']",
        "//a[contains(., 'Ver mais')]",
        "//a[@aria-label='Veja mais. Opcoes']",
    ]

    for xp in xpaths:
        try:
            for botao in driver.find_elements(By.XPATH, xp):
                if not botao.is_displayed():
                    continue

                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});",
                    botao,
                )
                driver.execute_script("arguments[0].click();", botao)
                time.sleep(2)
                return True
        except Exception:
            continue

    return False


def capturar_links_paginas_vendedores(driver: WebDriver) -> list[str]:
    links_vendedores: list[str] = []
    sellers_vistos: set[str] = set()

    blocos = capturar_blocos_de_ofertas(driver)

    for bloco in blocos:
        href = capturar_link_vendedor_no_bloco(bloco)
        seller_id = extrair_seller_id(href) if href else None

        if seller_id and seller_id not in sellers_vistos:
            sellers_vistos.add(seller_id)
            links_vendedores.append(href)

    return links_vendedores


def juntar_links_vendedores(*listas_links: list[str]) -> list[str]:
    links_unicos: list[str] = []
    sellers_vistos: set[str] = set()

    for links in listas_links:
        for link in links:
            seller_id = extrair_seller_id(link)
            if not seller_id or seller_id in sellers_vistos:
                continue

            sellers_vistos.add(seller_id)
            links_unicos.append(link)

    return links_unicos


def capturar_blocos_de_ofertas(driver: WebDriver) -> list:
    blocos = []
    ids_vistos: set[str] = set()
    total_pinned = 0
    total_lista = 0

    # A buybox/oferta principal aparece fora da lista comum, no bloco pinned.
    for xp in [
        "//div[@id='aod-pinned-offer']",
        "//div[contains(@class,'aod-pinned-offer')]",
    ]:
        try:
            blocos_pinned = driver.find_elements(By.XPATH, xp)
            total_pinned += adicionar_blocos_unicos(blocos, ids_vistos, blocos_pinned)
        except Exception:
            continue

    try:
        listas = driver.find_elements(By.XPATH, "//div[@role='list']")
        for lista in listas:
            blocos_lista = lista.find_elements(
                    By.XPATH,
                    ".//div[@id='aod-offer' or contains(@class,'aod-offer')]",
                )
            total_lista += adicionar_blocos_unicos(blocos, ids_vistos, blocos_lista)
    except Exception:
        pass

    print(f"Blocos de oferta: pinned={total_pinned} | lista={total_lista}")
    return blocos


def adicionar_blocos_unicos(blocos: list, ids_vistos: set[str], novos_blocos: list) -> int:
    total_adicionado = 0

    for bloco in novos_blocos:
        bloco_id = bloco.id
        if bloco_id in ids_vistos:
            continue

        ids_vistos.add(bloco_id)
        blocos.append(bloco)
        total_adicionado += 1

    return total_adicionado


def capturar_link_vendedor_no_bloco(bloco) -> str | None:
    xpaths_vendedor = [
        ".//div[@id='aod-offer-soldBy']//a[@href]",
        ".//div[contains(@id,'aod-offer-soldBy')]//a[@href]",
        ".//a[contains(@href,'/gp/aag/main') and contains(@href,'seller=')]",
        ".//a[contains(@href,'seller=') and contains(@href,'asin=')]",
        ".//a[contains(@href,'seller=')]",
    ]

    for xp in xpaths_vendedor:
        try:
            el = bloco.find_element(By.XPATH, xp)
            href = el.get_attribute("href")
            if href:
                return href
        except Exception:
            continue

    return None


def capturar_links_vitrine_no_bloco(bloco) -> list[str]:
    links: list[str] = []

    xpaths_vitrine = [
        ".//a[contains(@href,'/s?') and contains(@href,'me=')]",
        ".//a[contains(@href,'/sp?') and contains(@href,'me=')]",
        ".//a[contains(@href,'me=') and contains(., 'Vitrine')]",
    ]

    for xp in xpaths_vitrine:
        try:
            for el in bloco.find_elements(By.XPATH, xp):
                href = el.get_attribute("href")
                if href and href not in links:
                    links.append(href)
        except Exception:
            continue

    return links


def capturar_link_vitrine_na_pagina_vendedor(
    driver: WebDriver,
    wait: WebDriverWait,
) -> str | None:
    xpaths = [
        "//div[@id='seller-info-storefront-link']//a[contains(@class,'a-link-normal') and contains(@href,'me=')]",
        "//a[contains(@href,'/s?') and contains(@href,'me=') and contains(., 'Acesse Vitrine')]",
        "//a[contains(@href,'/s?') and contains(@href,'me=')]",
    ]

    for xp in xpaths:
        try:
            el = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
            href = el.get_attribute("href")
            if href:
                return href
        except Exception:
            continue

    return None


def contar_ofertas(driver: WebDriver) -> int:
    return len(
        driver.find_elements(
            By.XPATH,
            "//div[@role='list']//div[@id='aod-offer' or contains(@class,'aod-offer')]",
        )
    )


def extrair_seller_id(url: str) -> str | None:
    try:
        query = parse_qs(urlparse(url).query)
        return query.get("seller", [None])[0]
    except Exception:
        return None


def erro_driver_indisponivel(exc: Exception) -> bool:
    texto = str(exc).lower()
    sinais = [
        "max retries exceeded",
        "failed to establish a new connection",
        "connection refused",
        "winerror 10061",
        "invalid session id",
        "chrome not reachable",
        "disconnected",
        "no such window",
        "target window already closed",
    ]

    return any(sinal in texto for sinal in sinais)
