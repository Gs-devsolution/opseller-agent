"""Executor 4: enriquece produtos aprovados no teste Seller."""

from __future__ import annotations

from typing import Any, Callable

from supabase import Client

from seller_workers.config import Config
from seller_workers.database import (
    buscar_testes_seller_aprovados_pendentes,
    marcar_teste_seller_como_finalizado,
)
from seller_workers.selenium_factory import criar_driver
from seller_workers.workers.worker_4_produtos import enriquecer_produto

LogFn = Callable[[str], None]
StopFn = Callable[[], bool]
DriverFn = Callable[[Any | None], None]
SellerDriverFn = Callable[[], Any | None]


def executar_executor_4() -> None:
    raise RuntimeError(
        "Use a GUI do OpSeller Agent. "
        "Os executores precisam de uma sessao Supabase autenticada."
    )


def rodar_ciclo_executor_4(
    config: Config,
    supabase: Client,
    log: LogFn = print,
    should_stop: StopFn = lambda: False,
    on_driver: DriverFn = lambda driver: None,
    get_seller_driver: SellerDriverFn = lambda: None,
    get_teste_seller_sessions: Callable[[StopFn], list[Any]] = lambda should_stop: [],
) -> int:
    if should_stop():
        log("Executor 4: desligamento solicitado antes do ciclo.")
        return config.intervalo_orquestrador_segundos

    pendentes = buscar_testes_seller_aprovados_pendentes(supabase)
    if not pendentes:
        log("Executor 4: nenhum produto aprovado pendente encontrado.")
        return config.intervalo_sem_pendentes_segundos

    asins = _extrair_asins(pendentes)
    log(f"Executor 4: {len(asins)} produto(s) aprovado(s) pendente(s).")

    driver = None
    try:
        driver = criar_driver(profile_name="executor_4")
        on_driver(driver)

        for asin_produto in asins:
            if should_stop():
                log("Executor 4: ciclo interrompido antes do proximo ASIN.")
                break

            log(f"Iniciando Worker 4 para o ASIN {asin_produto}.")
            resultado = enriquecer_produto(
                asin_produto=asin_produto,
                driver=driver,
                supabase=supabase,
                amazon_base_url=config.amazon_base_url,
                log=log,
            )

            log(f"Resultado do enriquecimento {asin_produto}: {resultado}")

            if resultado.get("finalizado") is True:
                marcar_teste_seller_como_finalizado(supabase, asin_produto)
                log(f"ASIN {asin_produto} finalizado na fila teste_seller.")
            else:
                log(f"ASIN {asin_produto} continuara pendente para nova tentativa.")

    finally:
        on_driver(None)
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
            log("Selenium finalizado.")

    log("Executor 4: lote concluido.")
    return config.intervalo_apos_lote_segundos


def _extrair_asins(registros: list[dict[str, Any]]) -> list[str]:
    asins: list[str] = []

    for registro in registros:
        asin = str(registro.get("asin_produto", "")).strip()
        if asin:
            asins.append(asin)

    return asins
