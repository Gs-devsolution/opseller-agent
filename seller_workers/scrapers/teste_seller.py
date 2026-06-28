"""Automacao de teste de ASIN no Seller Central."""

from __future__ import annotations

import re
import time
import unicodedata

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SELLER_PRODUCT_SEARCH_URL = "https://sellercentral.amazon.com.br/product-search"


def testar_asin_no_seller(driver: WebDriver, asin: str) -> dict[str, str | bool]:
    try:
        driver.get(SELLER_PRODUCT_SEARCH_URL)
        time.sleep(2)

        if not sessao_seller_autenticada(driver):
            return {
                "finalizado": False,
                "resultado": "",
                "motivo": "Sessao Seller nao autenticada",
            }

        inserir_asin(driver, asin)
        clicar_pesquisar(driver)

        if asin_exige_aprovacao(driver):
            return {
                "finalizado": True,
                "resultado": "Desqualificado",
                "motivo": "Requer Aprovacao",
            }

        if asin_nao_aceita_solicitacoes(driver):
            return {
                "finalizado": True,
                "resultado": "Desqualificado",
                "motivo": "Nao aceita solicitacoes",
            }

        if not selecionar_condicao_novo(driver, timeout=30):
            if asin_nao_aceita_solicitacoes(driver):
                return {
                    "finalizado": True,
                    "resultado": "Desqualificado",
                    "motivo": "Nao aceita solicitacoes",
                }

            return {
                "finalizado": False,
                "resultado": "Erro",
                "motivo": "Nao carregou condicao Novo",
            }

        if asin_exige_aprovacao(driver):
            return {
                "finalizado": True,
                "resultado": "Desqualificado",
                "motivo": "Requer Aprovacao",
            }

        if asin_nao_aceita_solicitacoes(driver):
            return {
                "finalizado": True,
                "resultado": "Desqualificado",
                "motivo": "Nao aceita solicitacoes",
            }

        aba_base = driver.current_window_handle

        try:
            abrir_aba_oferta(driver, aba_base, timeout=30)
        except Exception:
            try:
                driver.switch_to.window(aba_base)
            except Exception:
                pass

            return {
                "finalizado": False,
                "resultado": "Erro",
                "motivo": "Falha ao abrir aba de oferta",
            }

        try:
            if asin_erro_5886(driver, timeout=30):
                return {
                    "finalizado": True,
                    "resultado": "Desqualificado",
                    "motivo": "Erro 5886",
                }

            return {
                "finalizado": True,
                "resultado": "Aprovado",
                "motivo": "Sem restricoes",
            }
        finally:
            fechar_aba_oferta_e_voltar(driver, aba_base)

    except Exception as exc:
        return {
            "finalizado": False,
            "resultado": "",
            "motivo": str(exc),
        }


def sessao_seller_autenticada(driver: WebDriver) -> bool:
    url = (driver.current_url or "").lower()
    texto = obter_texto_pagina(driver).lower()

    if (
        "signin" in url
        or "ap/signin" in url
        or "/ap/mfa" in url
        or "account-switcher" in url
    ):
        return False

    sinais_login = [
        "fazer login",
        "selecione uma conta",
        "selecionar conta",
        "senha",
        "verificacao em duas etapas",
        "verificaÃ§Ã£o em duas etapas",
        "insira o codigo",
        "insira o cÃ³digo",
        "codigo de uso unico",
        "cÃ³digo de uso Ãºnico",
        "otp",
        "mantenha-me conectado",
        "trocar contas",
        "esqueci a senha",
        "ap_email",
        "ap_password",
        "auth-mfa-otpcode",
    ]

    if "amazon" in texto and any(sinal in texto for sinal in sinais_login):
        return False

    try:
        if driver.find_elements(By.ID, "ap_password"):
            return False
        if driver.find_elements(By.ID, "auth-mfa-otpcode"):
            return False
        if driver.find_elements(By.NAME, "otpCode"):
            return False
        if driver.find_elements(By.NAME, "mfaSubmit"):
            return False
        if driver.find_elements(By.ID, "signInSubmit"):
            return False
        if driver.find_elements(By.NAME, "signIn"):
            return False
    except Exception:
        pass

    return True


def inserir_asin(driver: WebDriver, asin: str, timeout: int = 30) -> None:
    wait = WebDriverWait(driver, timeout)

    host = wait.until(
        lambda d: d.find_element(
            By.CSS_SELECTOR,
            "kat-predictive-input[data-testid='keywords-input']",
        )
    )

    campo_asin = wait.until(
        lambda d: d.execute_script(
            """
            const host = arguments[0];
            if (!host || !host.shadowRoot) return null;
            return host.shadowRoot.querySelector("input[part='predictive-input-input']");
            """,
            host,
        )
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", campo_asin)
    driver.execute_script("arguments[0].focus();", campo_asin)

    try:
        campo_asin.clear()
    except Exception:
        pass

    campo_asin.send_keys(asin)


def clicar_pesquisar(driver: WebDriver, timeout: int = 30) -> None:
    wait = WebDriverWait(driver, timeout)

    host = wait.until(
        lambda d: d.find_element(
            By.CSS_SELECTOR,
            "kat-button[data-testid='omnibox-submit-button']",
        )
    )

    botao = wait.until(
        lambda d: d.execute_script(
            """
            const host = arguments[0];
            if (!host || !host.shadowRoot) return null;
            return host.shadowRoot.querySelector("button");
            """,
            host,
        )
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", botao)
    driver.execute_script("arguments[0].click();", botao)


def asin_exige_aprovacao(driver: WebDriver, timeout: int = 8) -> bool:
    fim = time.time() + timeout

    while time.time() < fim:
        try:
            botao_host = driver.find_elements(
                By.CSS_SELECTOR,
                "kat-button[data-testid='sell-this-product']",
            )

            if botao_host:
                texto_botao = driver.execute_script(
                    """
                    const host = arguments[0];
                    if (!host || !host.shadowRoot) return "";
                    const btn = host.shadowRoot.querySelector("button");
                    return btn ? (btn.innerText || btn.textContent || "").trim() : "";
                    """,
                    botao_host[0],
                )

                if "Solicitar aprovacao" in remover_acentos(texto_botao):
                    return True

            texto_tela = remover_acentos(obter_texto_pagina(driver))
            texto_shadow = remover_acentos(obter_texto_com_shadow_dom(driver))
            texto_completo = f"{texto_tela} {texto_shadow}".lower()

            termos_aprovacao = [
                "solicitar aprovacao",
                "voce precisa de aprovacao",
                "precisa de aprovacao para publicar ofertas",
                "requer aprovacao",
            ]

            if any(termo in texto_completo for termo in termos_aprovacao):
                return True

        except Exception:
            pass

        time.sleep(0.5)

    return False


def asin_nao_aceita_solicitacoes(driver: WebDriver, timeout: int = 8) -> bool:
    termos = [
        "nao estamos aceitando solicitacoes",
        "nao estamos aceitando solicitacao",
        "nao estamos aceitando solicitacoes para este produto",
        "restringimos a publicacao ou venda",
        "restringimos a publicacao",
        "restringimos a venda",
    ]

    fim = time.time() + timeout

    while time.time() < fim:
        texto_tela = remover_acentos(obter_texto_pagina(driver))
        texto_shadow = remover_acentos(obter_texto_com_shadow_dom(driver))
        texto_completo = re.sub(r"\s+", " ", f"{texto_tela} {texto_shadow}").strip().lower()

        if any(termo in texto_completo for termo in termos):
            return True

        time.sleep(0.5)

    return False


def selecionar_condicao_novo(driver: WebDriver, timeout: int = 30) -> bool:
    fim = time.time() + timeout

    while time.time() < fim:
        try:
            host_dropdown = driver.find_element(
                By.CSS_SELECTOR,
                "kat-dropdown[data-testid='conditions-dropdown']",
            )

            header = driver.execute_script(
                """
                const host = arguments[0];
                if (!host || !host.shadowRoot) return null;
                return host.shadowRoot.querySelector("[part='dropdown-header']");
                """,
                host_dropdown,
            )

            if not header:
                time.sleep(0.5)
                continue

            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", header)
            driver.execute_script("arguments[0].click();", header)
            time.sleep(1)

            opcao_host = driver.execute_script(
                """
                const host = arguments[0];
                if (!host || !host.shadowRoot) return null;
                return host.shadowRoot.querySelector("kat-option[value='new']");
                """,
                host_dropdown,
            )

            if not opcao_host:
                time.sleep(0.5)
                continue

            opcao_click = driver.execute_script(
                """
                const opt = arguments[0];
                if (!opt || !opt.shadowRoot) return null;
                return opt.shadowRoot.querySelector(".standard-option-content")
                    || opt.shadowRoot.querySelector(".option-inner-container")
                    || opt.shadowRoot.querySelector("div");
                """,
                opcao_host,
            )

            if not opcao_click:
                time.sleep(0.5)
                continue

            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", opcao_click)
            driver.execute_script("arguments[0].click();", opcao_click)
            return True

        except Exception:
            pass

        time.sleep(0.5)

    return False


def clicar_vender_produto(driver: WebDriver, timeout: int = 30) -> None:
    wait = WebDriverWait(driver, timeout)

    host = wait.until(
        lambda d: d.find_element(
            By.CSS_SELECTOR,
            "kat-button[data-testid='sell-this-product']",
        )
    )

    botao = wait.until(
        lambda d: d.execute_script(
            """
            const host = arguments[0];
            if (!host || !host.shadowRoot) return null;
            return host.shadowRoot.querySelector("button");
            """,
            host,
        )
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", botao)
    driver.execute_script("arguments[0].click();", botao)


def asin_erro_5886(driver: WebDriver, timeout: int = 10) -> bool:
    termos = [
        "5886",
        "asin generico restrito",
        "e necessario criar um novo codigo asin",
        "criar novo produto",
    ]

    fim = time.time() + timeout

    while time.time() < fim:
        texto_norm = re.sub(r"\s+", " ", remover_acentos(obter_texto_pagina(driver))).strip().lower()

        if any(termo in texto_norm for termo in termos):
            return True

        time.sleep(0.5)

    return False


def abrir_aba_oferta(driver: WebDriver, aba_base: str, timeout: int = 30) -> str:
    handles_antes = set(driver.window_handles)
    fim = time.time() + timeout
    clicou = False

    while time.time() < fim:
        novas_abas = list(set(driver.window_handles) - handles_antes)

        if novas_abas:
            nova_aba = novas_abas[0]
            driver.switch_to.window(nova_aba)
            return nova_aba

        if not clicou:
            clicar_vender_produto(driver, timeout=30)
            clicou = True
        else:
            try:
                clicar_vender_produto(driver, timeout=30)
            except Exception:
                pass

        time.sleep(1)

    raise RuntimeError("Nenhuma nova aba foi aberta.")


def fechar_aba_oferta_e_voltar(driver: WebDriver, aba_base: str) -> None:
    if driver.current_window_handle != aba_base:
        driver.close()
    driver.switch_to.window(aba_base)


def obter_texto_pagina(driver: WebDriver) -> str:
    try:
        return driver.execute_script(
            "return document.body ? (document.body.innerText || document.body.textContent || '') : '';"
        )
    except Exception:
        return ""


def obter_texto_com_shadow_dom(driver: WebDriver) -> str:
    try:
        return driver.execute_script(
            """
            const textos = [];
            const visitar = (node) => {
                if (!node) return;
                if (node.nodeType === Node.TEXT_NODE) {
                    const texto = (node.textContent || "").trim();
                    if (texto) textos.push(texto);
                    return;
                }
                if (node.shadowRoot) visitar(node.shadowRoot);
                for (const child of node.childNodes || []) visitar(child);
            };
            visitar(document.body);
            return textos.join(" ");
            """
        )
    except Exception:
        return ""


def remover_acentos(texto: str) -> str:
    mapa = str.maketrans(
        "áàãâéêíóõôúçÁÀÃÂÉÊÍÓÕÔÚÇ",
        "aaaaeeioooucAAAAEEIOOOUC",
    )
    return texto.translate(mapa)


def remover_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(char for char in normalizado if not unicodedata.combining(char))
