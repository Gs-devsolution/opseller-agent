"""Executor 3: testa ASINs no Seller Central autenticado."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable

from selenium.webdriver.remote.webdriver import WebDriver
from supabase import Client

from seller_workers.config import Config
from seller_workers.database import (
    buscar_produtos_capturados_pendentes,
    buscar_teste_seller_por_asin,
    marcar_produto_capturado_como_finalizado,
    salvar_resultado_teste_seller,
)
from seller_workers.workers.worker_3_teste_seller import testar_produto_seller

LogFn = Callable[[str], None]
StopFn = Callable[[], bool]
DriverFn = Callable[[Any | None], None]
SellerDriverFn = Callable[[], WebDriver | None]
TesteSellerSessionsFn = Callable[[StopFn], list[Any]]


def executar_executor_3() -> None:
    raise RuntimeError(
        "Use a GUI do OpSeller Agent. "
        "Os executores precisam de uma sessao Supabase autenticada."
    )


def rodar_ciclo_executor_3(
    config: Config,
    supabase: Client,
    log: LogFn = print,
    should_stop: StopFn = lambda: False,
    on_driver: DriverFn = lambda driver: None,
    get_seller_driver: SellerDriverFn = lambda: None,
    get_teste_seller_sessions: TesteSellerSessionsFn = lambda should_stop: [],
) -> int:
    if should_stop():
        log("Executor 3: desligamento solicitado antes do ciclo.")
        return config.intervalo_orquestrador_segundos

    pendentes = buscar_produtos_capturados_pendentes(
        supabase,
        limite=max(1, config.executor_3_batch_size),
    )
    if not pendentes:
        log("Executor 3: nenhum produto capturado pendente encontrado.")
        return config.intervalo_sem_pendentes_segundos

    produtos = _extrair_produtos(pendentes)
    log(f"Executor 3: {len(produtos)} produto(s) capturado(s) pendente(s).")

    if config.seller_auto_login_enabled:
        _processar_produtos_em_paralelo(
            config=config,
            supabase=supabase,
            produtos=produtos,
            log=log,
            should_stop=should_stop,
            get_teste_seller_sessions=get_teste_seller_sessions,
        )
    else:
        driver = get_seller_driver()
        if not driver:
            log("Executor 3: abra/login a Sessao Seller antes de ligar este executor.")
            return config.intervalo_orquestrador_segundos

        _processar_produtos_serial(
            supabase=supabase,
            produtos=produtos,
            driver=driver,
            log=log,
            should_stop=should_stop,
        )

    log("Executor 3: lote concluido.")
    return config.intervalo_apos_lote_segundos


def _processar_produtos_serial(
    supabase: Client,
    produtos: list[dict[str, str]],
    driver: WebDriver,
    log: LogFn,
    should_stop: StopFn,
) -> None:
    for produto in produtos:
        if should_stop():
            log("Executor 3: ciclo interrompido antes do proximo ASIN.")
            break

        continuar = _processar_um_produto(
            supabase=supabase,
            asin_produto=produto["asin_produto"],
            driver=driver,
            nome_sessao="seller_manual",
            log=log,
            db_lock=None,
        )

        if not continuar:
            log(
                "Executor 3: Seller Central deslogado. "
                "Faca login manual na Sessao Seller e ligue/aguarde o proximo ciclo."
            )
            break


def _processar_produtos_em_paralelo(
    config: Config,
    supabase: Client,
    produtos: list[dict[str, str]],
    log: LogFn,
    should_stop: StopFn,
    get_teste_seller_sessions: TesteSellerSessionsFn,
) -> None:
    sessoes = get_teste_seller_sessions(should_stop)
    sessoes = [sessao for sessao in sessoes if getattr(sessao, "driver", None)]

    if not sessoes:
        log("Executor 3: nenhuma sessao teste_seller autenticada disponivel.")
        return

    fila: queue.Queue[str] = queue.Queue()
    asins_unicos: list[str] = []
    vistos: set[str] = set()

    for produto in produtos:
        asin = produto["asin_produto"]
        if asin in vistos:
            continue
        vistos.add(asin)
        asins_unicos.append(asin)
        fila.put(asin)

    db_lock = threading.Lock()
    log(
        "Executor 3: processando "
        f"{len(asins_unicos)} ASIN(s) com {len(sessoes)} tester(s)."
    )

    def worker(sessao: Any) -> None:
        nome_sessao = str(getattr(sessao, "nome", "teste_seller"))
        driver = getattr(sessao, "driver", None)
        if not driver:
            return

        while not should_stop():
            try:
                asin_produto = fila.get_nowait()
            except queue.Empty:
                return

            try:
                garantir_autenticacao = getattr(sessao, "garantir_autenticacao", None)
                if callable(garantir_autenticacao):
                    try:
                        if not garantir_autenticacao(should_stop):
                            setattr(sessao, "status", "deslogada")
                            log(f"{nome_sessao}: nao autenticou; tester pausado.")
                            return
                    except Exception as exc:
                        setattr(sessao, "status", "erro")
                        log(f"{nome_sessao}: erro ao reautenticar sessao: {exc}")
                        return

                continuar = _processar_um_produto(
                    supabase=supabase,
                    asin_produto=asin_produto,
                    driver=driver,
                    nome_sessao=nome_sessao,
                    log=log,
                    db_lock=db_lock,
                )

                if not continuar:
                    setattr(sessao, "status", "deslogada")
                    log(f"{nome_sessao}: sessao deslogada; tester pausado.")
                    return
            except Exception as exc:
                setattr(sessao, "status", "erro")
                log(f"{nome_sessao}: erro inesperado ao testar {asin_produto}: {exc}")
                return
            finally:
                fila.task_done()

    threads = [
        threading.Thread(target=worker, args=(sessao,), daemon=True)
        for sessao in sessoes[: max(1, config.teste_seller_session_max)]
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()


def _processar_um_produto(
    supabase: Client,
    asin_produto: str,
    driver: WebDriver,
    nome_sessao: str,
    log: LogFn,
    db_lock: threading.Lock | None,
) -> bool:
    inicio = time.perf_counter()

    def com_lock(fn: Callable[[], Any]) -> Any:
        if not db_lock:
            return fn()

        with db_lock:
            return fn()

    teste_existente = com_lock(lambda: buscar_teste_seller_por_asin(supabase, asin_produto))

    if teste_existente:
        com_lock(lambda: marcar_produto_capturado_como_finalizado(supabase, asin_produto))
        log(
            f"{nome_sessao}: ASIN {asin_produto} ja tem resultado em teste_seller. "
            "Produto capturado marcado como finalizado."
        )
        return True

    log(f"{nome_sessao}: iniciando teste Seller para o ASIN {asin_produto}.")
    resultado = testar_produto_seller(
        asin_produto=asin_produto,
        driver=driver,
        log=lambda mensagem: log(f"{nome_sessao}: {mensagem}"),
    )

    duracao = time.perf_counter() - inicio
    log(f"{nome_sessao}: resultado do ASIN {asin_produto}: {resultado} ({duracao:.1f}s)")

    if _sessao_seller_desautenticada(resultado):
        return False

    if resultado.get("finalizado") is True:
        resultado_teste = str(resultado.get("resultado") or "").strip()
        motivo_teste = str(resultado.get("motivo") or "").strip()
        texto_resultado = f"{resultado_teste} | {motivo_teste}"
        status_teste_seller = _definir_status_teste_seller(resultado_teste)

        try:
            com_lock(
                lambda: salvar_resultado_teste_seller(
                    supabase=supabase,
                    asin_produto=asin_produto,
                    resultado=texto_resultado,
                    status=status_teste_seller,
                )
            )
            com_lock(lambda: marcar_produto_capturado_como_finalizado(supabase, asin_produto))
            log(
                f"{nome_sessao}: resultado do ASIN {asin_produto} gravado "
                f"com status {status_teste_seller}; produto capturado finalizado."
            )
        except Exception as exc:
            log(f"{nome_sessao}: erro ao gravar resultado do ASIN {asin_produto}: {exc}")
    else:
        log(f"{nome_sessao}: ASIN {asin_produto} nao foi concluido. Nenhum resultado gravado.")

    return True


def _extrair_produtos(registros: list[dict[str, Any]]) -> list[dict[str, str]]:
    produtos: list[dict[str, str]] = []

    for registro in registros:
        vitrine = str(registro.get("vitrine", "")).strip()
        asin = str(registro.get("asin_produto", "")).strip()
        if vitrine and asin:
            produtos.append({"vitrine": vitrine, "asin_produto": asin})

    return produtos


def _definir_status_teste_seller(resultado: str) -> str:
    if resultado.strip().lower() == "aprovado":
        return "pendente"

    return "finalizado"


def _sessao_seller_desautenticada(resultado: dict[str, Any]) -> bool:
    motivo = str(resultado.get("motivo") or "").lower()
    return "sessao seller nao autenticada" in motivo
