"""Sessao persistente do Seller Central."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import pyotp
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from seller_workers.config import Config
from seller_workers.scrapers.teste_seller import sessao_seller_autenticada
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


@dataclass
class TesteSellerSessao:
    nome: str
    driver: WebDriver | None = None
    status: str = "fechada"
    erro: str | None = None


class TesteSellerSessionManager:
    """Gerencia perfis dedicados ao Executor 3: teste_seller_1, teste_seller_2..."""

    def __init__(self, config: Config, log: LogFn = print) -> None:
        self.config = config
        self.log = log
        self.sessoes: list[TesteSellerSessao] = [
            TesteSellerSessao(nome=f"teste_seller_{indice}")
            for indice in range(1, self._quantidade_sessoes() + 1)
        ]

    def _quantidade_sessoes(self) -> int:
        maximo = max(1, self.config.teste_seller_session_max)
        solicitado = max(1, self.config.teste_seller_session_count)
        return min(solicitado, maximo)

    def sessoes_prontas(self, should_stop: Callable[[], bool] = lambda: False) -> list[TesteSellerSessao]:
        prontas: list[TesteSellerSessao] = []

        for sessao in self.sessoes:
            if should_stop():
                break

            try:
                driver = self._abrir_driver(sessao)
                if self._garantir_login(sessao, driver):
                    sessao.status = "autenticada"
                    sessao.erro = None
                    prontas.append(sessao)
                else:
                    sessao.status = "deslogada"
            except Exception as exc:
                sessao.status = "erro"
                sessao.erro = str(exc)
                self.log(f"{sessao.nome}: erro ao preparar sessao Seller: {exc}")

        return prontas

    def _abrir_driver(self, sessao: TesteSellerSessao) -> WebDriver:
        if sessao.driver:
            try:
                _ = sessao.driver.current_url
                return sessao.driver
            except Exception:
                sessao.driver = None

        sessao.status = "abrindo"
        self.log(f"{sessao.nome}: abrindo Chrome dedicado.")
        sessao.driver = criar_driver(profile_name=sessao.nome, preparar_amazon=False)
        return sessao.driver

    def _garantir_login(self, sessao: TesteSellerSessao, driver: WebDriver) -> bool:
        self._abrir_area_interna(driver)

        if sessao_seller_autenticada(driver):
            self.log(f"{sessao.nome}: Seller ja autenticado.")
            return True

        if not self.config.seller_auto_login_enabled:
            self.log(f"{sessao.nome}: auto-login desligado; faca login manual se quiser usar esta sessao.")
            return False

        self._validar_credenciais_auto_login()
        sessao.status = "autenticando"
        self.log(f"{sessao.nome}: fazendo auto-login no Seller Central.")

        for tentativa in range(1, 5):
            if sessao_seller_autenticada(driver):
                self.log(f"{sessao.nome}: auto-login concluido.")
                return True

            if self._desafio_nao_suportado(driver):
                raise RuntimeError("Amazon exibiu desafio/captcha nao suportado para auto-login.")

            fez_acao = (
                self._preencher_otp(driver)
                or self._preencher_senha(driver)
                or self._preencher_email(driver)
                or self._clicar_botao_login_generico(driver)
            )

            if not fez_acao:
                self._abrir_area_interna(driver)

            time.sleep(3)
            self.log(f"{sessao.nome}: verificando login ({tentativa}/4).")

        return sessao_seller_autenticada(driver)

    def _validar_credenciais_auto_login(self) -> None:
        if not self.config.seller_email:
            raise RuntimeError("Configure SELLER_EMAIL para auto-login.")
        if not self.config.seller_password:
            raise RuntimeError("Configure SELLER_PASSWORD para auto-login.")
        if not self.config.seller_totp_secret:
            raise RuntimeError("Configure SELLER_TOTP_SECRET para auto-login com OTP.")

    def _abrir_area_interna(self, driver: WebDriver) -> None:
        url = self.config.seller_central_url.rstrip("/")
        if "/product-search" not in url:
            url = f"{url}/product-search"

        driver.get(url)
        time.sleep(2)

        if self._parece_landing_publica(driver):
            self._clicar_iniciar_sessao(driver)

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

    def _preencher_email(self, driver: WebDriver) -> bool:
        campos = [
            (By.ID, "ap_email"),
            (By.NAME, "email"),
        ]
        campo = self._primeiro_elemento(driver, campos)
        if not campo:
            return False

        self._preencher_campo(driver, campo, self.config.seller_email)
        clicou = self._clicar_por_selectors(
            driver,
            [
                (By.ID, "continue"),
                (By.NAME, "continue"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
            ],
        )
        if not clicou:
            campo.send_keys(Keys.ENTER)
        return True

    def _preencher_senha(self, driver: WebDriver) -> bool:
        campo = self._primeiro_elemento(driver, [(By.ID, "ap_password"), (By.NAME, "password")])
        if not campo:
            return False

        self._preencher_campo(driver, campo, self.config.seller_password)
        self._marcar_manter_conectado(driver)
        clicou = self._clicar_por_selectors(
            driver,
            [
                (By.ID, "signInSubmit"),
                (By.NAME, "signIn"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
            ],
        )
        if not clicou:
            campo.send_keys(Keys.ENTER)
        return True

    def _preencher_otp(self, driver: WebDriver) -> bool:
        campo = self._primeiro_elemento(
            driver,
            [
                (By.ID, "auth-mfa-otpcode"),
                (By.NAME, "otpCode"),
                (By.NAME, "mfaCode"),
                (By.CSS_SELECTOR, "input[type='tel']"),
                (By.CSS_SELECTOR, "input[type='text']"),
            ],
        )
        if not campo or not self._pagina_pede_otp(driver):
            return False

        codigo = pyotp.TOTP(self.config.seller_totp_secret.replace(" ", "")).now()
        self._preencher_campo(driver, campo, codigo)
        clicou = self._clicar_por_selectors(
            driver,
            [
                (By.ID, "auth-signin-button"),
                (By.ID, "signInSubmit"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
            ],
        )
        if not clicou:
            campo.send_keys(Keys.ENTER)
        return True

    def _pagina_pede_otp(self, driver: WebDriver) -> bool:
        texto = self._texto_pagina(driver).lower()
        termos = ["otp", "codigo", "código", "autenticador", "duas etapas", "two-step", "verification"]
        return any(termo in texto for termo in termos)

    def _clicar_botao_login_generico(self, driver: WebDriver) -> bool:
        return self._clicar_por_selectors(
            driver,
            [
                (By.ID, "continue"),
                (By.ID, "signInSubmit"),
                (By.ID, "auth-signin-button"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
            ],
        )

    def _marcar_manter_conectado(self, driver: WebDriver) -> None:
        for by, selector in [(By.ID, "auth-remember-me"), (By.NAME, "rememberMe"), (By.ID, "rememberMe")]:
            try:
                checkbox = driver.find_element(by, selector)
                if checkbox.is_displayed() and not checkbox.is_selected():
                    driver.execute_script("arguments[0].click();", checkbox)
                return
            except Exception:
                continue

    def _desafio_nao_suportado(self, driver: WebDriver) -> bool:
        texto = self._texto_pagina(driver).lower()
        termos = [
            "captcha",
            "digite os caracteres",
            "insira os caracteres",
            "quebra-cabeca",
            "quebra-cabeça",
            "aprove a notificacao",
            "aprove a notificação",
        ]
        return any(termo in texto for termo in termos)

    def _primeiro_elemento(
        self,
        driver: WebDriver,
        selectors: list[tuple[str, str]],
        timeout: int = 2,
    ):
        for by, selector in selectors:
            try:
                return WebDriverWait(driver, timeout).until(
                    lambda d: self._primeiro_campo_interativo(d.find_elements(by, selector))
                )
            except Exception:
                continue
        return None

    def _primeiro_campo_interativo(self, elementos):
        for elemento in elementos:
            try:
                tipo = (elemento.get_attribute("type") or "").lower()
                disabled = elemento.get_attribute("disabled")
                readonly = elemento.get_attribute("readonly")
                if tipo == "hidden" or disabled or readonly:
                    continue
                if elemento.is_displayed() and elemento.is_enabled():
                    return elemento
            except Exception:
                continue
        return False

    def _preencher_campo(self, driver: WebDriver, campo, valor: str) -> None:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", campo)
        try:
            campo.click()
            campo.clear()
            campo.send_keys(valor)
        except Exception:
            driver.execute_script(
                """
                arguments[0].focus();
                arguments[0].value = '';
                arguments[0].value = arguments[1];
                """,
                campo,
                valor,
            )
        driver.execute_script(
            """
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """,
            campo,
        )

    def _clicar_por_selectors(
        self,
        driver: WebDriver,
        selectors: list[tuple[str, str]],
        timeout: int = 2,
    ) -> bool:
        for by, selector in selectors:
            try:
                elemento = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((by, selector))
                )
                driver.execute_script("arguments[0].click();", elemento)
                return True
            except Exception:
                continue
        return False

    def _texto_pagina(self, driver: WebDriver) -> str:
        try:
            return driver.execute_script(
                "return document.body ? (document.body.innerText || document.body.textContent || '') : '';"
            )
        except Exception:
            return ""

    def status_resumo(self) -> str:
        return " | ".join(
            f"{sessao.nome}: {sessao.status}" for sessao in self.sessoes
        )

    def fechar_todas(self) -> None:
        for sessao in self.sessoes:
            if not sessao.driver:
                sessao.status = "fechada"
                continue

            try:
                sessao.driver.quit()
                self.log(f"{sessao.nome}: sessao fechada.")
            except Exception as exc:
                self.log(f"{sessao.nome}: erro ao fechar sessao: {exc}")
            finally:
                sessao.driver = None
                sessao.status = "fechada"
