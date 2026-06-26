"""Factory do Selenium usado pelos workers."""

from __future__ import annotations

from pathlib import Path
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from seller_workers.config import carregar_config

AMAZON_HOME = "https://www.amazon.com.br"


def criar_driver(
    profile_name: str = "default",
    preparar_amazon: bool = True,
) -> webdriver.Chrome:
    config = carregar_config()
    base_profile_dir = Path(config.selenium_profile_dir)
    if not base_profile_dir.is_absolute():
        base_profile_dir = Path.cwd() / base_profile_dir

    profile_dir = base_profile_dir / profile_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=pt-BR")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    if preparar_amazon:
        preparar_sessao_amazon(driver)

    return driver


def preparar_sessao_amazon(driver: webdriver.Chrome) -> None:
    driver.get(AMAZON_HOME)
    time.sleep(2)

    for tentativa in range(1, 4):
        continuar_comprando_se_aparecer(driver)

        if not pagina_desculpe(driver):
            return

        print(f"Amazon retornou pagina de erro na preparacao. Reload {tentativa}/3.")
        driver.refresh()
        time.sleep(3)


def continuar_comprando_se_aparecer(driver: webdriver.Chrome) -> bool:
    wait = WebDriverWait(driver, 2)
    xpaths = [
        "//button[contains(., 'Continuar comprando')]",
        "//button[@type='submit' and contains(., 'Continuar comprando')]",
        "//span[contains(@class,'a-button')]//button[contains(., 'Continuar comprando')]",
        "//input[@type='submit' and contains(@aria-labelledby, 'continuar')]",
    ]

    for xp in xpaths:
        try:
            botao = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].click();", botao)
            time.sleep(2)
            print("Cliquei em Continuar comprando na preparacao do driver.")
            return True
        except Exception:
            continue

    return False


def pagina_desculpe(driver: webdriver.Chrome) -> bool:
    try:
        texto = driver.find_element(By.TAG_NAME, "body").text.lower()
        titulo = (driver.title or "").lower()
    except Exception:
        return False

    return (
        ("desculpe" in texto and "algo deu errado" in texto)
        or "desculpe" in titulo
    )
