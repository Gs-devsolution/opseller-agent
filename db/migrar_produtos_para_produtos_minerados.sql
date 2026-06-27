-- Migra banco existente da tabela public.produtos para public.produtos_minerados.
-- Use somente em instalacoes que ja tinham a tabela produtos antiga.

begin;

do $$
begin
    if to_regclass('public.produtos') is not null
       and to_regclass('public.produtos_minerados') is null then
        alter table public.produtos rename to produtos_minerados;
    end if;
end $$;

alter table if exists public.produtos_minerados
    drop column if exists fornecedor,
    drop column if exists link,
    drop column if exists custo,
    drop column if exists preco_minimo_lucrativo,
    drop column if exists alerta;

alter table if exists public.produtos_minerados
    drop constraint if exists produtos_alerta_check,
    drop constraint if exists produtos_status_check,
    drop constraint if exists produtos_minerados_status_check;

alter table public.produtos_minerados
    add constraint produtos_minerados_status_check
    check (
        status in (
            'pendente',
            'reprovado por margem',
            'aprovado por margem',
            'em operacao'
        )
    );

revoke all on public.produtos_minerados from anon;
grant select, insert, update on public.produtos_minerados to authenticated;

alter table public.produtos_minerados enable row level security;

drop policy if exists "permitir select produtos" on public.produtos_minerados;
drop policy if exists "permitir insert produtos" on public.produtos_minerados;
drop policy if exists "permitir update produtos" on public.produtos_minerados;
drop policy if exists "permitir select produtos minerados" on public.produtos_minerados;
drop policy if exists "permitir insert produtos minerados" on public.produtos_minerados;
drop policy if exists "permitir update produtos minerados" on public.produtos_minerados;

create policy "permitir select produtos minerados"
on public.produtos_minerados
for select
to authenticated
using (true);

create policy "permitir insert produtos minerados"
on public.produtos_minerados
for insert
to authenticated
with check (true);

create policy "permitir update produtos minerados"
on public.produtos_minerados
for update
to authenticated
using (true)
with check (true);

commit;
