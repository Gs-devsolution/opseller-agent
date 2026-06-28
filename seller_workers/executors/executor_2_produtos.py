"""Executor 2: consulta vitrines pendentes e aciona o Worker 2."""

from __future__ import annotations

from typing import Any, Callable

from supabase import Client

from seller_workers.config import Config
from seller_workers.database import (
    buscar_vitrines_pendentes,
    marcar_vitrine_como_finalizada,
)
from seller_workers.selenium_factory import criar_driver
from seller_workers.workers.worker_2_captura_produtos import capturar_produtos

LogFn = Callable[[str], None]
StopFn = Callable[[], bool]
DriverFn = Callable[[Any | None], None]
SellerDriverFn = Callable[[], Any | None]


def executar_executor_2() -> None:
    raise RuntimeError(
        "Use a GUI do OpSeller Agent. "
        "Os executores precisam de uma sessao Supabase autenticada."
    )


def rodar_ciclo_executor_2(
    config: Config,
    supabase: Client,
    log: LogFn = print,
    should_stop: StopFn = lambda: False,
    on_driver: DriverFn = lambda driver: None,
    get_seller_driver: SellerDriverFn = lambda: None,
    get_teste_seller_sessions: Callable[[StopFn], list[Any]] = lambda should_stop: [],
) -> int:
    if should_stop():
        log("Executor 2: desligamento solicitado antes do ciclo.")
        return config.intervalo_orquestrador_segundos

    pendentes = buscar_vitrines_pendentes(supabase)

    if not pendentes:
        log("Executor 2: nenhuma vitrine pendente encontrada.")
        return config.intervalo_sem_pendentes_segundos

    vitrines = _extrair_vitrines(pendentes)
    log(f"Executor 2: {len(vitrines)} vitrine(s) pendente(s).")

    driver = None
    try:
        driver = criar_driver(profile_name="executor_2")
        on_driver(driver)

        for vitrine in vitrines:
            if should_stop():
                log("Executor 2: ciclo interrompido antes da proxima vitrine.")
                break

            log(f"Iniciando Worker 2 para a vitrine {vitrine}.")
            resultado = capturar_produtos(
                vitrine=vitrine,
                driver=driver,
                supabase=supabase,
                max_paginas=config.max_paginas_por_vitrine,
                log=log,
                should_stop=should_stop,
            )

            log(f"Resultado da vitrine {vitrine}: {resultado}")

            if resultado.get("finalizado") is True:
                marcar_vitrine_como_finalizada(supabase, vitrine)
                log("Vitrine marcada como finalizada.")
            else:
                log("Vitrine continuara pendente para nova tentativa.")

    finally:
        on_driver(None)
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
            log("Selenium finalizado.")

    log("Executor 2: lote concluido.")
    return config.intervalo_apos_lote_segundos


def _extrair_vitrines(registros: list[dict[str, Any]]) -> list[str]:
    vitrines: list[str] = []

    for registro in registros:
        vitrine = str(registro.get("vitrine", "")).strip()
        if vitrine:
            vitrines.append(vitrine)

    return vitrines
