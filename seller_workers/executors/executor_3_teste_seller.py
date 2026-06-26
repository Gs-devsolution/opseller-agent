"""Executor 3: testa ASINs no Seller Central autenticado."""

from __future__ import annotations

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
) -> int:
    if should_stop():
        log("Executor 3: desligamento solicitado antes do ciclo.")
        return config.intervalo_orquestrador_segundos

    driver = get_seller_driver()
    if not driver:
        log("Executor 3: abra/login a Sessao Seller antes de ligar este executor.")
        return config.intervalo_orquestrador_segundos

    pendentes = buscar_produtos_capturados_pendentes(supabase)
    if not pendentes:
        log("Executor 3: nenhum produto capturado pendente encontrado.")
        return config.intervalo_sem_pendentes_segundos

    produtos = _extrair_produtos(pendentes)
    log(f"Executor 3: {len(produtos)} produto(s) capturado(s) pendente(s).")

    for produto in produtos:
        if should_stop():
            log("Executor 3: ciclo interrompido antes do proximo ASIN.")
            break

        asin_produto = produto["asin_produto"]
        teste_existente = buscar_teste_seller_por_asin(supabase, asin_produto)

        if teste_existente:
            marcar_produto_capturado_como_finalizado(supabase, asin_produto)
            log(
                f"ASIN {asin_produto} ja tem resultado em teste_seller. "
                "Produto capturado marcado como finalizado."
            )
            continue

        log(f"Iniciando teste Seller para o ASIN {asin_produto}.")
        resultado = testar_produto_seller(
            asin_produto=asin_produto,
            driver=driver,
            log=log,
        )

        log(f"Resultado Seller do ASIN {asin_produto}: {resultado}")

        if _sessao_seller_desautenticada(resultado):
            log(
                "Executor 3: Seller Central deslogado. "
                "Faca login manual na Sessao Seller e ligue/aguarde o proximo ciclo."
            )
            break

        if resultado.get("finalizado") is True:
            resultado_teste = str(resultado.get("resultado") or "").strip()
            motivo_teste = str(resultado.get("motivo") or "").strip()
            texto_resultado = f"{resultado_teste} | {motivo_teste}"
            status_teste_seller = _definir_status_teste_seller(resultado_teste)

            try:
                salvar_resultado_teste_seller(
                    supabase=supabase,
                    asin_produto=asin_produto,
                    resultado=texto_resultado,
                    status=status_teste_seller,
                )
                marcar_produto_capturado_como_finalizado(supabase, asin_produto)
                log(
                    f"Resultado do ASIN {asin_produto} gravado em teste_seller "
                    f"com status {status_teste_seller}; "
                    "produto capturado marcado como finalizado."
                )
            except Exception as exc:
                log(f"Erro ao gravar resultado do ASIN {asin_produto} em teste_seller: {exc}")
        else:
            log(f"ASIN {asin_produto} nao foi concluido. Nenhum resultado gravado.")

    log("Executor 3: lote concluido.")
    return config.intervalo_apos_lote_segundos


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
