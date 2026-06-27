"""Camada simples de acesso ao Supabase."""

from __future__ import annotations

from typing import Any

from supabase import Client, create_client

from seller_workers.config import Config


def criar_cliente_supabase(config: Config) -> Client:
    return create_client(config.supabase_url, config.supabase_key)


def autenticar_cliente_supabase(
    config: Config,
    email: str,
    senha: str,
) -> tuple[Client, str]:
    cliente = criar_cliente_supabase(config)
    resposta = cliente.auth.sign_in_with_password(
        {
            "email": email,
            "password": senha,
        }
    )

    usuario = getattr(resposta, "user", None)
    sessao = getattr(resposta, "session", None)

    if not usuario or not sessao:
        raise RuntimeError("Login no Supabase nao retornou uma sessao valida.")

    email_usuario = str(getattr(usuario, "email", "") or email).strip()
    return cliente, email_usuario


def sair_cliente_supabase(supabase: Client | None) -> None:
    if supabase is None:
        return

    supabase.auth.sign_out()


def buscar_produtos_iniciais_pendentes(supabase: Client) -> list[dict[str, Any]]:
    resposta = (
        supabase.table("produtos_iniciais")
        .select("*")
        .eq("status", "pendente")
        .order("asin", desc=False)
        .execute()
    )
    return resposta.data or []


def marcar_produto_inicial_como_finalizado(supabase: Client, asin: str) -> None:
    (
        supabase.table("produtos_iniciais")
        .update({"status": "finalizado"})
        .eq("asin", asin)
        .execute()
    )


def buscar_vitrine_por_asin_e_nome(
    supabase: Client,
    asin_inicial: str,
    vitrine: str,
) -> dict[str, Any] | None:
    resposta = (
        supabase.table("vitrines")
        .select("*")
        .eq("vitrine", vitrine)
        .limit(1)
        .execute()
    )

    registros = resposta.data or []
    return registros[0] if registros else None


def inserir_vitrine(
    supabase: Client,
    asin_inicial: str,
    vitrine: str,
    status: str = "pendente",
) -> dict[str, Any] | None:
    resposta = (
        supabase.table("vitrines")
        .insert(
            {
                "asin_inicial": asin_inicial,
                "vitrine": vitrine,
                "status": status,
            }
        )
        .execute()
    )

    registros = resposta.data or []
    return registros[0] if registros else None


def inserir_vitrine_se_nao_existir(
    supabase: Client,
    asin_inicial: str,
    vitrine: str,
) -> bool:
    if buscar_vitrine_por_asin_e_nome(supabase, asin_inicial, vitrine):
        return False

    inserir_vitrine(supabase, asin_inicial, vitrine)
    return True


def buscar_vitrines_pendentes(supabase: Client) -> list[dict[str, Any]]:
    resposta = (
        supabase.table("vitrines")
        .select("*")
        .eq("status", "pendente")
        .execute()
    )
    return resposta.data or []


def marcar_vitrine_como_finalizada(supabase: Client, vitrine: str) -> None:
    (
        supabase.table("vitrines")
        .update({"status": "finalizado"})
        .eq("vitrine", vitrine)
        .execute()
    )


def buscar_produto_capturado(
    supabase: Client,
    asin_produto: str,
) -> dict[str, Any] | None:
    resposta = (
        supabase.table("produtos_capturados")
        .select("*")
        .eq("asin_produto", asin_produto)
        .limit(1)
        .execute()
    )

    registros = resposta.data or []
    return registros[0] if registros else None


def inserir_produto_capturado(
    supabase: Client,
    vitrine: str,
    asin_produto: str,
    status: str = "pendente",
) -> dict[str, Any] | None:
    resposta = (
        supabase.table("produtos_capturados")
        .insert(
            {
                "vitrine": vitrine,
                "asin_produto": asin_produto,
                "status": status,
            }
        )
        .execute()
    )

    registros = resposta.data or []
    return registros[0] if registros else None


def inserir_produto_capturado_se_nao_existir(
    supabase: Client,
    vitrine: str,
    asin_produto: str,
) -> bool:
    if buscar_produto_capturado(supabase, asin_produto):
        return False

    inserir_produto_capturado(supabase, vitrine, asin_produto)
    return True


def buscar_asins_produtos_capturados(supabase: Client) -> set[str]:
    resposta = (
        supabase.table("produtos_capturados")
        .select("asin_produto")
        .execute()
    )

    return {
        str(registro.get("asin_produto", "")).strip()
        for registro in resposta.data or []
        if registro.get("asin_produto")
    }


def inserir_produtos_capturados_em_lote(
    supabase: Client,
    vitrine: str,
    asins_produtos: list[str],
    status: str = "pendente",
) -> int:
    if not asins_produtos:
        return 0

    existentes = buscar_asins_produtos_capturados(supabase)
    asins_unicos: list[str] = []
    vistos: set[str] = set()

    for asin_produto in asins_produtos:
        asin_limpo = str(asin_produto).strip()
        if not asin_limpo or asin_limpo in existentes or asin_limpo in vistos:
            continue

        vistos.add(asin_limpo)
        asins_unicos.append(asin_limpo)

    if not asins_unicos:
        return 0

    registros = [
        {
            "vitrine": vitrine,
            "asin_produto": asin_produto,
            "status": status,
        }
        for asin_produto in asins_unicos
    ]

    resposta = supabase.table("produtos_capturados").insert(registros).execute()
    return len(resposta.data or [])


def buscar_produtos_capturados_pendentes(supabase: Client) -> list[dict[str, Any]]:
    resposta = (
        supabase.table("produtos_capturados")
        .select("*")
        .eq("status", "pendente")
        .execute()
    )
    return resposta.data or []


def marcar_produto_capturado_como_finalizado(
    supabase: Client,
    asin_produto: str,
) -> None:
    (
        supabase.table("produtos_capturados")
        .update({"status": "finalizado"})
        .eq("asin_produto", asin_produto)
        .execute()
    )


def buscar_teste_seller_por_asin(
    supabase: Client,
    asin_produto: str,
) -> dict[str, Any] | None:
    resposta = (
        supabase.table("teste_seller")
        .select("*")
        .eq("asin_produto", asin_produto)
        .limit(1)
        .execute()
    )

    registros = resposta.data or []
    return registros[0] if registros else None


def salvar_resultado_teste_seller(
    supabase: Client,
    asin_produto: str,
    resultado: str,
    status: str = "finalizado",
) -> None:
    (
        supabase.table("teste_seller")
        .upsert(
            {
                "asin_produto": asin_produto,
                "resultado": resultado,
                "status": status,
            },
            on_conflict="asin_produto",
        )
        .execute()
    )


def buscar_testes_seller_aprovados_pendentes(supabase: Client) -> list[dict[str, Any]]:
    resposta = (
        supabase.table("teste_seller")
        .select("*")
        .eq("status", "pendente")
        .execute()
    )
    return resposta.data or []


def marcar_teste_seller_como_finalizado(
    supabase: Client,
    asin_produto: str,
) -> None:
    (
        supabase.table("teste_seller")
        .update({"status": "finalizado"})
        .eq("asin_produto", asin_produto)
        .execute()
    )


def salvar_produto_minerado(
    supabase: Client,
    produto: dict[str, Any],
) -> None:
    (
        supabase.table("produtos_minerados")
        .upsert(produto, on_conflict="asin")
        .execute()
    )
