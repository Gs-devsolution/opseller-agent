"""Scraper de detalhes de produto Amazon para o Worker 4."""

from __future__ import annotations

import re
import time
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from seller_workers.selenium_factory import continuar_comprando_se_aparecer, pagina_desculpe


def capturar_detalhes_produto(
    driver: WebDriver,
    asin: str,
    amazon_base_url: str,
    timeout: int = 10,
) -> dict[str, Any]:
    link = f"{amazon_base_url.rstrip('/')}/{asin}"
    wait = WebDriverWait(driver, timeout)
    driver.get(link)
    time.sleep(1)

    continuar_comprando_se_aparecer(driver)
    if pagina_desculpe(driver):
        driver.refresh()
        time.sleep(2)
        continuar_comprando_se_aparecer(driver)

    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    _validar_pagina_produto(driver, asin, wait)

    nome = _capturar_nome(driver)
    preco = _capturar_preco(driver)
    texto_pagina = _texto_pagina(driver)
    dados_oferta = _capturar_dados_oferta(driver)
    rankings = _capturar_rankings(driver)
    qtd_concorrentes = _capturar_qtd_concorrentes(driver, texto_pagina)

    enviado_por = dados_oferta.get("enviado_por")
    vendido_por = dados_oferta.get("vendido_por")
    enviado_por_amazon = _valor_eh_amazon(enviado_por)
    vendido_por_amazon = _valor_eh_amazon(vendido_por)
    alerta = _definir_alerta(enviado_por_amazon, vendido_por_amazon)

    return {
        "asin": asin,
        "nome_do_produto": nome,
        "preco": preco,
        "enviado_por_amazon": enviado_por_amazon,
        "vendido_por_amazon": vendido_por_amazon,
        "qtd_concorrentes": qtd_concorrentes,
        "ranking_1": rankings[0] if len(rankings) > 0 else None,
        "ranking_2": rankings[1] if len(rankings) > 1 else None,
        "ranking_3": rankings[2] if len(rankings) > 2 else None,
        "fornecedor": None,
        "link": None,
        "custo": None,
        "preco_minimo_lucrativo": None,
        "alerta": alerta,
        "status": "pendente",
    }


def _capturar_nome(driver: WebDriver) -> str | None:
    try:
        texto = driver.find_element(By.ID, "productTitle").text.strip()
        return texto or None
    except Exception:
        return None


def _validar_pagina_produto(driver: WebDriver, asin: str, wait: WebDriverWait) -> None:
    titulo = (driver.title or "").strip().lower()
    url = (driver.current_url or "").strip().lower()
    texto = _texto_pagina(driver).lower()

    sinais_erro = [
        "não é possível acessar esse site",
        "nao e possivel acessar esse site",
        "this site can't be reached",
        "err_name_not_resolved",
        "dns_probe",
        "getaddrinfo",
    ]

    if any(sinal in titulo or sinal in texto for sinal in sinais_erro):
        raise RuntimeError("Pagina do produto nao carregou; navegador exibiu erro de acesso.")

    if pagina_desculpe(driver):
        raise RuntimeError("Pagina do produto nao carregou; Amazon exibiu pagina de erro.")

    if asin.lower() not in url and asin.lower() not in texto:
        raise RuntimeError("Pagina carregada nao corresponde ao ASIN esperado.")

    try:
        wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
    except Exception:
        raise RuntimeError("Pagina do produto nao carregou o titulo do produto.")


def _capturar_preco(driver: WebDriver) -> str | None:
    try:
        inteiro = driver.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
        fracao = driver.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text.strip()
        inteiro = inteiro.replace(".", "").replace("\n", "").strip()
        fracao = fracao.replace("\n", "").strip()
        if inteiro and fracao:
            return f"{inteiro},{fracao}"
    except Exception:
        pass

    return None


def _capturar_dados_oferta(driver: WebDriver) -> dict[str, str | None]:
    dados = {"enviado_por": None, "vendido_por": None}

    try:
        dados_js = driver.execute_script(
            """
            const normalizar = (texto) => (texto || "").replace(/\\s+/g, " ").trim();
            const dados = {};
            const containers = [
                document.querySelector("#tabular-buybox"),
                document.querySelector("#desktop_qualifiedBuyBox"),
                document.querySelector("#offerDisplayFeatures"),
                document.querySelector("#buybox"),
                document.querySelector("#corePrice_feature_div")?.closest("[cel_widget_id]")
            ].filter(Boolean);

            const registrar = (label, valor) => {
                label = normalizar(label).toLowerCase();
                valor = normalizar(valor);
                if (!label || !valor) return;
                if (label.includes("enviado")) dados.enviado_por = dados.enviado_por || valor;
                if (label.includes("vendido")) dados.vendido_por = dados.vendido_por || valor;
            };

            for (const container of containers) {
                for (const feature of container.querySelectorAll("[data-feature-name], .celwidget")) {
                    const labelEl = feature.querySelector(".offer-display-feature-label, [id*='label']");
                    const valueEl = feature.querySelector(".offer-display-feature-text, [id*='text']");
                    if (!labelEl || !valueEl) continue;

                    const label = normalizar(labelEl.innerText || labelEl.textContent || "");
                    const valor = normalizar(valueEl.innerText || valueEl.textContent || "");
                    registrar(label, valor);
                }

                for (const row of container.querySelectorAll(".tabular-buybox-container, .tabular-buybox-text, .a-row, tr")) {
                    const texto = normalizar(row.innerText || row.textContent || "");
                    if (!texto) continue;

                    let label = "";
                    let valor = "";

                    const labelEl = row.querySelector(".tabular-buybox-label, .a-color-secondary, th");
                    const valueEl = row.querySelector(".tabular-buybox-text, .a-size-small:not(.a-color-secondary), td");

                    if (labelEl && valueEl && labelEl !== valueEl) {
                        label = normalizar(labelEl.innerText || labelEl.textContent || "");
                        valor = normalizar(valueEl.innerText || valueEl.textContent || "");
                    } else if (/Enviado por|Enviado pela/i.test(texto)) {
                        label = "Enviado por";
                        valor = texto.replace(/.*(?:Enviado por|Enviado pela)\\s*/i, "");
                    } else if (/Vendido por/i.test(texto)) {
                        label = "Vendido por";
                        valor = texto.replace(/.*Vendido por\\s*/i, "");
                    }

                    registrar(label, valor);
                }
            }

            return dados;
            """
        )
    except Exception:
        dados_js = {}

    for chave in dados:
        valor = dados_js.get(chave) if isinstance(dados_js, dict) else None
        if valor:
            dados[chave] = _limpar_valor_oferta(str(valor))

    if not dados["enviado_por"]:
        dados["enviado_por"] = _capturar_valor_por_label(driver, "Enviado por")
    if not dados["enviado_por"]:
        dados["enviado_por"] = _capturar_valor_por_label(driver, "Enviado pela")
    if not dados["vendido_por"]:
        dados["vendido_por"] = _capturar_valor_por_label(driver, "Vendido por")

    return dados


def _capturar_valor_por_label(driver: WebDriver, label: str) -> str | None:
    xpaths = [
        f"//*[normalize-space()='{label}']/following::*[normalize-space()][1]",
        f"//*[contains(normalize-space(),'{label}')]/following::*[normalize-space()][1]",
    ]

    for xp in xpaths:
        try:
            valor = driver.find_element(By.XPATH, xp).text.strip()
            valor = _limpar_valor_oferta(valor)
            if valor:
                return valor
        except Exception:
            continue

    return None


def _limpar_valor_oferta(valor: str) -> str | None:
    valor = " ".join(valor.split())
    valor = re.sub(r"^(Enviado por|Enviado pela|Vendido por)\s*", "", valor, flags=re.IGNORECASE).strip()
    valor = re.split(r"\s+(Política de devolução|Detalhes|Atualizar local|Saiba mais)", valor, maxsplit=1)[0].strip()
    return valor or None


def _capturar_rankings(driver: WebDriver) -> list[str]:
    rankings: list[str] = []

    xpaths = [
        "//tr[.//th[contains(., 'Ranking dos mais vendidos')]]//td//li",
        "//tr[.//span[contains(normalize-space(.), 'Ranking dos mais vendidos')]]//li",
    ]

    for xp in xpaths:
        try:
            itens = driver.find_elements(By.XPATH, xp)
            for item in itens:
                textos = _extrair_rankings_de_texto(item.get_attribute("textContent") or "")
                for texto in textos:
                    if texto not in rankings:
                        rankings.append(texto)
                    if len(rankings) >= 3:
                        return rankings
        except Exception:
            continue

    return rankings


def _extrair_rankings_de_texto(texto: str) -> list[str]:
    texto_limpo = _limpar_texto_ranking(texto)
    partes = re.findall(
        r"N\s*[ºo°?]?\s*[\d\.\,]+\s+em\s+.*?(?=\s+N\s*[ºo°?]?\s*[\d\.\,]+\s+em\s+|$)",
        texto_limpo,
        flags=re.IGNORECASE,
    )

    return [parte.strip() for parte in partes if _ranking_valido(parte)]


def _limpar_texto_ranking(texto: str) -> str:
    texto_limpo = " ".join(texto.split())
    texto_limpo = re.sub(r"\([^)]*Top 100[^)]*\)", "", texto_limpo, flags=re.IGNORECASE)
    return " ".join(texto_limpo.split())


def _ranking_valido(texto: str) -> bool:
    if not texto:
        return False

    texto_normalizado = texto.lower()
    if any(termo in texto_normalizado for termo in ["asin", "dimens", "sp_ppu_string", "avalia"]):
        return False

    return bool(re.search(r"n\s*[ºo°]?\s*[\d\.\,]+\s+em\s+", texto, re.IGNORECASE))


def _capturar_qtd_concorrentes(driver: WebDriver, texto_pagina: str) -> int:
    candidatos: list[str] = []

    seletores = [
        "#aod-ingress-link",
        "#aod-ingress-box",
        "#all-offers-display",
        "[id*='aod-ingress']",
        ".aod-ingress-link",
    ]

    for seletor in seletores:
        try:
            for elemento in driver.find_elements(By.CSS_SELECTOR, seletor):
                texto = elemento.text.strip()
                if texto:
                    candidatos.append(texto)
        except Exception:
            continue

    xpaths = [
        "//*[contains(normalize-space(.), 'Comparar outras') and contains(normalize-space(.), 'ofertas')]",
        "//a[contains(@href,'/gp/offer-listing/') and contains(normalize-space(.), 'ofertas')]",
        "//a[contains(normalize-space(.), 'ofertas de produtos usados e novos')]",
    ]

    for xp in xpaths:
        try:
            for elemento in driver.find_elements(By.XPATH, xp):
                texto = elemento.text.strip()
                if texto:
                    candidatos.append(texto)
        except Exception:
            continue

    padroes_prioritarios = [
        r"comparar\s+outras?\s+(\d+)\s+ofertas?",
        r"outras?\s+(\d+)\s+ofertas?",
        r"(\d+)\s+outras?\s+ofertas?",
    ]

    for candidato in candidatos:
        resultado = _extrair_qtd_concorrentes(candidato, padroes_prioritarios)
        if resultado is not None:
            return resultado

    # Fallback restrito: algumas paginas mostram o texto fora do bloco de ofertas.
    padroes_fallback = [
        r"comparar\s+outras?\s+(\d+)\s+ofertas?",
        r"(\d+)\s+ofertas?\s+de\s+produtos\s+usados\s+e\s+novos",
    ]
    resultado = _extrair_qtd_concorrentes(texto_pagina, padroes_fallback)
    if resultado is not None:
        return resultado

    return 1


def _extrair_qtd_concorrentes(texto: str, padroes: list[str]) -> int | None:
    texto = " ".join(texto.split())

    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def _texto_pagina(driver: WebDriver) -> str:
    try:
        return driver.execute_script(
            "return document.body ? (document.body.innerText || document.body.textContent || '') : '';"
        )
    except Exception:
        return ""


def _valor_eh_amazon(valor: str | None) -> bool:
    if not valor:
        return False

    normalizado = valor.lower()
    return normalizado in {"amazon", "amazon.com.br"} or normalizado.startswith("amazon.com")


def _definir_alerta(enviado_por_amazon: bool, vendido_por_amazon: bool) -> str | None:
    if vendido_por_amazon:
        return "VENDIDO POR AMAZON"
    if enviado_por_amazon:
        return "ENVIADO POR AMAZON"
    return None
