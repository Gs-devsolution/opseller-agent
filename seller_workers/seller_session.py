"""Sessao persistente do Seller Central."""

from __future__ import annotations

import time
from typing import Callable

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from seller_workers.config import Config
from seller_workers.selenium_factory import criar_driver

LogFn = Callable[[str], None]


class SellerSession:
    def __init__(self, config: Config, log: LogFn = print) -> None:
        self.config = config
        self.log = log
        self.driver: WebDriver | None = None

    @property
    def aberta(self) -> bool:
        if not self.driver:
            return False

        try:
            _ = self.driver.current_url
            return True
        except Exception:
            self.driver = None
            return False

    def abrir(self) -> WebDriver:
        if self.aberta and self.driver:
            self._abrir_area_interna(self.driver)
            self.log("Sessao Seller ja estava aberta.")
            return self.driver

        self.log("Abrindo sessao Seller Central.")
        self.driver = criar_driver(
            profile_name="seller",
            preparar_amazon=False,
        )
        self._abrir_area_interna(self.driver)
        self.log("Seller Central aberto. Faca login manual se necessario.")
        return self.driver

    def _abrir_area_interna(self, driver: WebDriver) -> None:
        url_interna = self._montar_url_interna()
        driver.get(url_interna)
        time.sleep(2)

        if self._parece_landing_publica(driver):
            self.log("Seller Central abriu a pagina de apresentacao. Tentando clicar em Iniciar sessao.")
            self._clicar_iniciar_sessao(driver)

    def _montar_url_interna(self) -> str:
        base_url = self.config.seller_central_url.rstrip("/")

        if "/product-search" in base_url:
            return base_url

        return f"{base_url}/product-search"

    def _parece_landing_publica(self, driver: WebDriver) -> bool:
        url = (driver.current_url or "").lower()
        texto = self._texto_pagina(driver).lower()

        if "product-search" in url or "signin" in url or "ap/signin" in url:
            return False

        return "comece a vender" in texto or "iniciar sessao" in texto or "iniciar sessão" in texto

    def _clicar_iniciar_sessao(self, driver: WebDriver) -> None:
        try:
            link = WebDriverWait(driver, 10).until(
                lambda d: d.find_element(By.CSS_SELECTOR, "a[href*='signin'], a[href*='/signin']")
            )
            driver.execute_script("arguments[0].click();", link)
            time.sleep(2)
        except Exception:
            driver.get("https://sellercentral.amazon.com.br/signin")
            time.sleep(2)

    def _texto_pagina(self, driver: WebDriver) -> str:
        try:
            return driver.execute_script(
                "return document.body ? (document.body.innerText || document.body.textContent || '') : '';"
            )
        except Exception:
            return ""

    def fechar(self) -> None:
        if not self.driver:
            self.log("Sessao Seller ja esta fechada.")
            return

        try:
            self.driver.quit()
            self.log("Sessao Seller fechada.")
        except Exception as exc:
            self.log(f"Erro ao fechar sessao Seller: {exc}")
        finally:
            self.driver = None
