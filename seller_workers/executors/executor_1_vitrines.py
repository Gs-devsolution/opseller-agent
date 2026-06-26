"""Executor 1: consulta ASINs pendentes e aciona o Worker 1."""

from __future__ import annotations

from typing import Any, Callable

from supabase import Client

from seller_workers.config import Config
from seller_workers.database import (
    buscar_produtos_iniciais_pendentes,
    marcar_produto_inicial_como_finalizado,
)
from seller_workers.selenium_factory import criar_driver
from seller_workers.workers.worker_1_captura_vitrines import capturar_vitrines

LogFn = Callable[[str], None]
StopFn = Callable[[], bool]
DriverFn = Callable[[Any | None], None]
SellerDriverFn = Callable[[], Any | None]


def executar_executor_1() -> None:
    raise RuntimeError(
        "Use a GUI do OpSeller Agent. "
        "Os executores precisam de uma sessao Supabase autenticada."
    )


def rodar_ciclo_executor_1(
    config: Config,
    supabase: Client,
    log: LogFn = print,
    should_stop: StopFn = lambda: False,
    on_driver: DriverFn = lambda driver: None,
    get_seller_driver: SellerDriverFn = lambda: None,
) -> int:
    if should_stop():
        log("Executor 1: desligamento solicitado antes do ciclo.")
        return config.intervalo_orquestrador_segundos

    pendentes = buscar_produtos_iniciais_pendentes(supabase)

    if not pendentes:
        log("Executor 1: nenhum ASIN pendente encontrado.")
        return config.intervalo_sem_pendentes_segundos

    asins = _extrair_asins(pendentes)
    log(f"Executor 1: {len(asins)} ASIN(s) pendente(s): {', '.join(asins)}")

    driver = None
    try:
        driver = criar_driver(profile_name="executor_1")
        on_driver(driver)

        for asin in asins:
            if should_stop():
                log("Executor 1: ciclo interrompido antes do proximo ASIN.")
                break

            log(f"Iniciando Worker 1 para o ASIN {asin}.")
            resultado = capturar_vitrines(
                asin_inicial=asin,
                driver=driver,
                supabase=supabase,
                amazon_base_url=config.amazon_base_url,
            )

            log(f"Resultado do ASIN {asin}: {resultado}")

            if resultado.get("finalizado") is True:
                marcar_produto_inicial_como_finalizado(supabase, asin)
                log(f"ASIN {asin} marcado como finalizado.")
            else:
                log(f"ASIN {asin} continuara pendente para nova tentativa.")

    finally:
        on_driver(None)
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
            log("Selenium finalizado.")

    log("Executor 1: lote concluido.")
    return config.intervalo_apos_lote_segundos


def _extrair_asins(registros: list[dict[str, Any]]) -> list[str]:
    asins: list[str] = []

    for registro in registros:
        asin = str(registro.get("asin", "")).strip()
        if asin:
            asins.append(asin)

    return asins
