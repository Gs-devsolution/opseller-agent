-- Estrutura inicial do OpSeller Agent.
-- Rode este arquivo no SQL Editor do Supabase.

create table if not exists public.produtos_iniciais (
    asin text not null,
    status text not null default 'pendente',

    constraint produtos_iniciais_status_check
        check (status in ('pendente', 'finalizado')),

    constraint produtos_iniciais_pkey
        primary key (asin)
);

create table if not exists public.vitrines (
    asin_inicial text not null,
    vitrine text not null,
    status text not null default 'pendente',

    constraint vitrines_status_check
        check (status in ('pendente', 'finalizado')),

    constraint vitrines_vitrine_unique
        unique (vitrine)
);

create index if not exists idx_vitrines_asin_inicial
on public.vitrines (asin_inicial);

create table if not exists public.produtos_capturados (
    vitrine text not null,
    asin_produto text not null,
    status text not null default 'pendente',

    constraint produtos_capturados_status_check
        check (status in ('pendente', 'finalizado')),

    constraint produtos_capturados_pkey
        primary key (asin_produto)
);

create index if not exists idx_produtos_capturados_vitrine
on public.produtos_capturados (vitrine);

create table if not exists public.teste_seller (
    asin_produto text not null primary key,
    resultado text,
    status text not null default 'pendente',

    constraint teste_seller_status_check
        check (status in ('pendente', 'finalizado'))
);

create table if not exists public.produtos (
    asin text not null primary key,
    nome_do_produto text,
    preco text,
    enviado_por_amazon boolean not null default false,
    vendido_por_amazon boolean not null default false,
    qtd_concorrentes integer,
    ranking_1 text,
    ranking_2 text,
    ranking_3 text,
    fornecedor text,
    link text,
    custo text,
    preco_minimo_lucrativo text,
    alerta text,
    status text not null default 'pendente',

    constraint produtos_alerta_check
        check (
            alerta is null
            or alerta in ('VENDIDO POR AMAZON', 'ENVIADO POR AMAZON')
        ),

    constraint produtos_status_check
        check (
            status in (
                'pendente',
                'reprovado por margem',
                'aprovado por margem',
                'em operacao'
            )
        )
);

revoke all on public.produtos_iniciais from anon;
revoke all on public.vitrines from anon;
revoke all on public.produtos_capturados from anon;
revoke all on public.teste_seller from anon;
revoke all on public.produtos from anon;

grant select, insert, update on public.produtos_iniciais to authenticated;
grant select, insert, update on public.vitrines to authenticated;
grant select, insert, update on public.produtos_capturados to authenticated;
grant select, insert, update on public.teste_seller to authenticated;
grant select, insert, update on public.produtos to authenticated;

alter table public.produtos_iniciais enable row level security;
alter table public.vitrines enable row level security;
alter table public.produtos_capturados enable row level security;
alter table public.teste_seller enable row level security;
alter table public.produtos enable row level security;

drop policy if exists "permitir select produtos iniciais" on public.produtos_iniciais;
create policy "permitir select produtos iniciais"
on public.produtos_iniciais
for select
to authenticated
using (true);

drop policy if exists "permitir insert produtos iniciais" on public.produtos_iniciais;
create policy "permitir insert produtos iniciais"
on public.produtos_iniciais
for insert
to authenticated
with check (true);

drop policy if exists "permitir update produtos iniciais" on public.produtos_iniciais;
create policy "permitir update produtos iniciais"
on public.produtos_iniciais
for update
to authenticated
using (true)
with check (true);

drop policy if exists "permitir select vitrines" on public.vitrines;
create policy "permitir select vitrines"
on public.vitrines
for select
to authenticated
using (true);

drop policy if exists "permitir insert vitrines" on public.vitrines;
create policy "permitir insert vitrines"
on public.vitrines
for insert
to authenticated
with check (true);

drop policy if exists "permitir update vitrines" on public.vitrines;
create policy "permitir update vitrines"
on public.vitrines
for update
to authenticated
using (true)
with check (true);

drop policy if exists "permitir select produtos capturados" on public.produtos_capturados;
create policy "permitir select produtos capturados"
on public.produtos_capturados
for select
to authenticated
using (true);

drop policy if exists "permitir insert produtos capturados" on public.produtos_capturados;
create policy "permitir insert produtos capturados"
on public.produtos_capturados
for insert
to authenticated
with check (true);

drop policy if exists "permitir update produtos capturados" on public.produtos_capturados;
create policy "permitir update produtos capturados"
on public.produtos_capturados
for update
to authenticated
using (true)
with check (true);

drop policy if exists "permitir select teste seller" on public.teste_seller;
create policy "permitir select teste seller"
on public.teste_seller
for select
to authenticated
using (true);

drop policy if exists "permitir insert teste seller" on public.teste_seller;
create policy "permitir insert teste seller"
on public.teste_seller
for insert
to authenticated
with check (true);

drop policy if exists "permitir update teste seller" on public.teste_seller;
create policy "permitir update teste seller"
on public.teste_seller
for update
to authenticated
using (true)
with check (true);

drop policy if exists "permitir select produtos" on public.produtos;
create policy "permitir select produtos"
on public.produtos
for select
to authenticated
using (true);

drop policy if exists "permitir insert produtos" on public.produtos;
create policy "permitir insert produtos"
on public.produtos
for insert
to authenticated
with check (true);

drop policy if exists "permitir update produtos" on public.produtos;
create policy "permitir update produtos"
on public.produtos
for update
to authenticated
using (true)
with check (true);
