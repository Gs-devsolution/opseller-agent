# Documentacao EXE - OpSeller Agent

Este documento descreve a realidade atual do agente local em Python, que futuramente sera empacotado em EXE.

O OpSeller Agent abre uma GUI local para ligar e desligar executores. Cada executor consulta o Supabase, identifica tarefas pendentes e aciona seu worker correspondente.

Por padrao, todos os executores iniciam desligados. Os executores so podem ser ligados depois que o usuario autenticar no Supabase Auth pela GUI.

## Visao Geral Do Fluxo

1. `produtos_iniciais`
   - Entrada manual ou via painel.
   - Contem ASINs iniciais que disparam a mineracao.

2. `vitrines`
   - Gerada pelo Executor 1.
   - Contem vitrines/lojas encontradas a partir dos ASINs iniciais.

3. `produtos_capturados`
   - Gerada pelo Executor 2.
   - Contem ASINs de produtos encontrados nas vitrines.
   - Regra atual: deve existir apenas 1 linha por `asin_produto`.

4. `teste_seller`
   - Gerada pelo Executor 3.
   - Contem o resultado do teste do produto no Seller Central.

5. `produtos_minerados`
   - Gerada pelo Executor 4.
   - Contem o enriquecimento dos produtos aprovados.

## GUI Local

A GUI possui:

- login no Supabase Auth;
- botoes para ligar/desligar cada executor;
- logs em tempo real;
- botao para abrir/login no Seller Central;
- botao para fechar a sessao Seller.

O banco usa RLS com permissoes de `select`, `insert` e `update` somente para `authenticated`. A publishable key do Supabase inicia o cliente, mas nao libera acesso as tabelas sem login.

Ao clicar em `Desligar` em um executor que usa Selenium proprio, o sistema solicita parada e tenta fechar o Selenium ativo.

Executores com Selenium proprio:

- Executor 1;
- Executor 2;
- Executor 4.

Executor 3 pode usar auto-login e perfis dedicados `teste_seller_N`. Quando `SELLER_AUTO_LOGIN_ENABLED=true`, o proprio Executor 3 abre e autentica os testers. Quando `false`, usa a sessao Seller manual aberta pela area `Sessao Seller` da GUI.

## Configuracoes De Intervalo

Configuradas no `.env`:

```env
INTERVALO_ORQUESTRADOR_SEGUNDOS=5
INTERVALO_SEM_PENDENTES_SEGUNDOS=3600
INTERVALO_APOS_LOTE_SEGUNDOS=1200
MAX_PAGINAS_POR_VITRINE=0
SELLER_AUTO_LOGIN_ENABLED=true
TESTE_SELLER_SESSION_COUNT=2
TESTE_SELLER_SESSION_MAX=4
EXECUTOR_3_BATCH_SIZE=100
```

Significados:

- `INTERVALO_ORQUESTRADOR_SEGUNDOS`: intervalo curto usado em estados de orquestracao, erro ou pausa.
- `INTERVALO_SEM_PENDENTES_SEGUNDOS`: tempo de espera quando nao ha tarefa pendente.
- `INTERVALO_APOS_LOTE_SEGUNDOS`: tempo de espera apos processar um lote.
- `MAX_PAGINAS_POR_VITRINE`: limite de paginas por vitrine no Worker 2. `0` significa sem limite.
- `SELLER_AUTO_LOGIN_ENABLED`: liga/desliga auto-login do Executor 3.
- `TESTE_SELLER_SESSION_COUNT`: quantidade de testers Seller em paralelo.
- `TESTE_SELLER_SESSION_MAX`: limite maximo de testers Seller.
- `EXECUTOR_3_BATCH_SIZE`: quantidade maxima de ASINs por ciclo do Executor 3.

## Executor 1 - Captura De Vitrines

Funcao:

- consultar `produtos_iniciais`;
- buscar registros com `status = 'pendente'`;
- iniciar Selenium quando houver ASIN pendente;
- chamar Worker 1 para cada ASIN;
- finalizar o ASIN inicial somente quando o Worker 1 retornar `finalizado = true`.

Fluxo:

1. Consulta `produtos_iniciais` com status `pendente`.
2. Se nao houver pendentes:
   - nao abre Selenium;
   - aguarda `INTERVALO_SEM_PENDENTES_SEGUNDOS`;
   - volta ao loop.
3. Se houver pendentes:
   - armazena a lista de ASINs;
   - abre Selenium com perfil `executor_1`;
   - percorre os ASINs da lista;
   - chama Worker 1 com `asin_inicial + driver`;
   - se o retorno for `finalizado = true`, marca o ASIN em `produtos_iniciais` como `finalizado`;
   - se o retorno for `finalizado = false`, mantem o ASIN como `pendente`.
4. Ao terminar o lote:
   - fecha Selenium;
   - aguarda `INTERVALO_APOS_LOTE_SEGUNDOS`;
   - volta ao loop.

Observacao:

Se o Selenium cair no meio da captura, o worker retorna erro e o ASIN fica pendente para nova tentativa.

## Worker 1 - Captura De Vitrines

Entrada:

- `asin_inicial`;
- driver Selenium;
- cliente Supabase.

Acao:

1. Acessa a pagina do produto inicial na Amazon.
2. Abre/lista ofertas quando disponivel.
3. Captura vitrines/lojas/fornecedores relacionados ao ASIN inicial.
4. Insere em `vitrines` somente se a combinacao `asin_inicial + vitrine` ainda nao existir.
5. Retorna:

```python
{
    "finalizado": true | false,
    "total_vitrines": int,
    "novas_vitrines": int,
    "vitrines_duplicadas": int,
    "erro": str | None
}
```

## Executor 2 - Captura De Produtos Em Vitrines

Funcao:

- consultar `vitrines`;
- buscar registros com `status = 'pendente'`;
- capturar produtos de cada vitrine;
- gravar ASINs unicos em `produtos_capturados`;
- finalizar a vitrine somente se a varredura da loja for completa.

Fluxo:

1. Consulta `vitrines` com status `pendente`.
2. Se nao houver pendentes:
   - nao abre Selenium;
   - aguarda `INTERVALO_SEM_PENDENTES_SEGUNDOS`;
   - volta ao loop.
3. Se houver pendentes:
   - abre Selenium com perfil `executor_2`;
   - percorre a lista de vitrines;
   - chama Worker 2 para cada vitrine;
   - se o retorno for `finalizado = true`, marca a vitrine como `finalizado`;
   - se o retorno for `finalizado = false`, mantem a vitrine como `pendente`.
4. Ao terminar o lote:
   - fecha Selenium;
   - aguarda `INTERVALO_APOS_LOTE_SEGUNDOS`;
   - volta ao loop.

Regra importante:

`produtos_capturados` agora deve ter apenas uma linha por `asin_produto`. Se o mesmo ASIN aparecer em outra vitrine, ele e ignorado como duplicado.

## Worker 2 - Captura De Produtos

Entrada:

- `vitrine`;
- driver Selenium;
- cliente Supabase.

Acao:

1. Acessa a vitrine.
2. Detecta a quantidade total de paginas.
3. Percorre da pagina 1 ate a ultima pagina.
4. A cada produto encontrado:
   - extrai o ASIN;
   - grava imediatamente em `produtos_capturados`;
   - se o ASIN ja existir globalmente, ignora como duplicado.
5. Se todas as paginas forem processadas, retorna `finalizado = true`.
6. Se houver erro, interrupcao ou pagina incompleta, retorna `finalizado = false`.

Retorno:

```python
{
    "finalizado": true | false,
    "total_produtos": int,
    "novos_produtos": int,
    "produtos_duplicados": int,
    "total_paginas": int,
    "paginas_processadas": list[int],
    "paginas_com_erro": list[int],
    "total_produtos_unicos": int,
    "erro": str | None
}
```

## Executor 3 - Teste Seller

Funcao:

- consumir `produtos_capturados`;
- testar cada `asin_produto` no Seller Central autenticado;
- gravar o resultado em `teste_seller`;
- marcar o produto capturado como finalizado apos o teste ser concluido.

Com `SELLER_AUTO_LOGIN_ENABLED=true`, este executor cria Selenium proprio para cada tester dedicado:

- `chrome_profile/teste_seller_1`;
- `chrome_profile/teste_seller_2`;
- `chrome_profile/teste_seller_3`;
- `chrome_profile/teste_seller_4`.

Com `SELLER_AUTO_LOGIN_ENABLED=false`, ele usa a sessao Seller manual aberta pela GUI.

Antes de ligar com auto-login:

1. Configure `SELLER_EMAIL`, `SELLER_PASSWORD` e `SELLER_TOTP_SECRET` no `.env`.
2. Ligue o Executor 3.
3. O executor abre e autentica as sessoes `teste_seller_N`.

Antes de ligar em modo manual:

1. Configure `SELLER_AUTO_LOGIN_ENABLED=false`.
2. Clique em `Abrir/Login` na area `Sessao Seller`.
3. Faca login manual se necessario.
4. Depois ligue o Executor 3.

Fluxo:

1. Consulta `produtos_capturados` com status `pendente`, limitado por `EXECUTOR_3_BATCH_SIZE`.
2. Se auto-login estiver ligado:
   - abre/prepara os testers `teste_seller_N`;
   - faz login automatico quando necessario;
   - distribui os ASINs em uma fila interna;
   - cada tester consome ASINs em paralelo.
3. Se auto-login estiver desligado:
   - verifica se existe sessao Seller manual aberta;
   - processa os ASINs de forma serial.
4. Para cada ASIN:
   - verifica se ja existe resultado em `teste_seller`;
   - se ja existe, marca `produtos_capturados` como `finalizado`;
   - se nao existe, executa o Worker 3.
5. Se o Worker 3 retornar `finalizado = true`:
   - grava/atualiza `teste_seller`;
   - marca `produtos_capturados` como `finalizado`.
6. Se retornar `finalizado = false`:
   - nao grava `teste_seller`;
   - nao finaliza `produtos_capturados`.

Se a conta deslogar:

- o Worker 3 detecta a tela de login;
- no auto-login, o proximo ciclo tenta autenticar novamente;
- no modo manual, o Executor 3 para o ciclo;
- nada e gravado;
- nenhum produto e finalizado indevidamente;
- pode ser necessario fazer login manual se a Amazon exigir desafio nao suportado.

## Worker 3 - Teste Seller

Entrada:

- `asin_produto`;
- driver da sessao Seller autenticada, manual ou `teste_seller_N`.

Acao:

1. Acessa a busca de produto no Seller Central.
2. Pesquisa o ASIN.
3. Analisa a resposta do Seller.
4. Retorna:

```python
{
    "finalizado": true | false,
    "resultado": "Aprovado" | "Desqualificado" | "Erro" | "",
    "motivo": str,
    "erro": str | None
}
```

Mapeamento atual:

- `Aprovado | Sem restricoes`
  - grava em `teste_seller`;
  - `teste_seller.status = 'pendente'`;
  - segue para o Executor 4.

- `Desqualificado | Requer Aprovacao`
  - grava em `teste_seller`;
  - `teste_seller.status = 'finalizado'`;
  - nao segue para enriquecimento.

- `Desqualificado | Erro 5886`
  - grava em `teste_seller`;
  - `teste_seller.status = 'finalizado'`;
  - nao segue para enriquecimento.

- Falha operacional ou sessao deslogada
  - nao grava em `teste_seller`;
  - mantem `produtos_capturados.status = 'pendente'`.

## Executor 4 - Enriquecimento De Produtos

Funcao:

- consumir produtos aprovados no Seller;
- acessar a Amazon fora do Seller;
- capturar dados detalhados do produto;
- gravar em `produtos_minerados`;
- finalizar a fila em `teste_seller`.

Fluxo:

1. Consulta `teste_seller` com `status = 'pendente'`.
2. Abre Selenium com perfil `executor_4`.
3. Para cada ASIN aprovado:
   - chama Worker 4;
   - se `finalizado = true`, grava em `produtos_minerados`;
   - marca `teste_seller.status = 'finalizado'`.
4. Se houver erro:
   - nao finaliza `teste_seller`;
   - o ASIN permanece pendente para nova tentativa.

## Worker 4 - Enriquecimento

Entrada:

- `asin_produto`;
- driver Selenium;
- cliente Supabase.

Captura atual:

- `asin`;
- `nome_do_produto`;
- `preco`;
- `enviado_por_amazon`;
- `vendido_por_amazon`;
- `qtd_concorrentes`;
- `ranking_1`;
- `ranking_2`;
- `ranking_3`.

Regras importantes:

- Ranking pode nao existir. Nesse caso, `ranking_1`, `ranking_2`, `ranking_3` ficam `null`.
- O scraper limita ranking a 3 posicoes.
- `qtd_concorrentes` vem do bloco "Outros vendedores na Amazon".
  - Exemplo: "Comparar outras 2 ofertas" grava `2`.
  - Se nao houver bloco, grava `1`.
- Se o produto for enviado pela Amazon, `enviado_por_amazon = true`.
- Se o produto for vendido pela Amazon, `vendido_por_amazon = true`.

## Regras De Status Por Tabela

### produtos_iniciais

- `pendente`: ASIN inicial ainda precisa minerar vitrines.
- `finalizado`: Worker 1 concluiu a captura de vitrines para o ASIN.

### vitrines

- `pendente`: vitrine ainda precisa ter produtos capturados.
- `finalizado`: Worker 2 varreu todas as paginas da vitrine.

### produtos_capturados

- `pendente`: ASIN ainda precisa ser testado no Seller.
- `finalizado`: ASIN ja foi testado ou ja tinha resultado em `teste_seller`.

Regra atual:

- `asin_produto` e chave primaria.
- Nao pode haver duplicidade do mesmo ASIN.

### teste_seller

- `pendente`: produto foi aprovado e precisa seguir para enriquecimento.
- `finalizado`: produto foi desqualificado ou ja foi enriquecido.

Observacao:

Aqui `pendente` nao significa "nao testado". Significa "aprovado no Seller e pendente de enriquecimento".

### produtos_minerados

- `pendente`: produto enriquecido, aguardando etapa futura de margem/operacao.
- `reprovado por margem`: reservado para modulo futuro.
- `aprovado por margem`: reservado para modulo futuro.
- `em operacao`: reservado para modulo futuro.

## Deduplicacao De Produtos Capturados

A regra atual e:

- uma linha por `asin_produto`;
- se o mesmo ASIN aparecer em varias vitrines, apenas o primeiro registro e mantido;
- o teste Seller ocorre uma unica vez por ASIN.

Conferencia:

```sql
select
    count(*) as linhas,
    count(distinct asin_produto) as asins_unicos
from public.produtos_capturados;
```

Os dois valores devem ser iguais.

## Comportamento Ao Desligar

Quando clicar em `Desligar`:

- o executor recebe sinal de parada;
- se houver Selenium proprio aberto, o Selenium e fechado;
- o worker pode encerrar a operacao em andamento com erro controlado;
- registros parcialmente concluidos nao devem ser marcados como finalizados.

No Worker 2, os produtos encontrados antes da parada podem ja ter sido inseridos, pois a gravacao e feita produto a produto para manter idempotencia.

## Idempotencia

O sistema foi desenhado para poder ser interrompido e retomado.

Regras:

- Worker 1 verifica duplicidade antes de inserir vitrine.
- Worker 2 verifica duplicidade global por ASIN antes de inserir produto capturado.
- Worker 3 verifica se ja existe teste Seller antes de testar novamente.
- Worker 4 usa upsert em `produtos_minerados`.

## Comando Para Rodar

Dentro da pasta `OpSeller Agent`:

```powershell
python -m seller_workers.main
```

## Variaveis Principais Do `.env`

```env
SUPABASE_URL=
SUPABASE_KEY=

EXECUTOR_1_VITRINES_ENABLED=false
EXECUTOR_2_PRODUTOS_ENABLED=false
EXECUTOR_3_TESTE_SELLER_ENABLED=false
EXECUTOR_4_PRODUTOS_ENABLED=false

INTERVALO_ORQUESTRADOR_SEGUNDOS=5
INTERVALO_SEM_PENDENTES_SEGUNDOS=3600
INTERVALO_APOS_LOTE_SEGUNDOS=1200
MAX_PAGINAS_POR_VITRINE=0

SELENIUM_PROFILE_DIR=chrome_profile
SELLER_CENTRAL_URL=https://sellercentral.amazon.com.br/product-search
SELLER_AUTO_LOGIN_ENABLED=true
SELLER_EMAIL=
SELLER_PASSWORD=
SELLER_TOTP_SECRET=
TESTE_SELLER_SESSION_COUNT=2
TESTE_SELLER_SESSION_MAX=4
EXECUTOR_3_BATCH_SIZE=100
```
