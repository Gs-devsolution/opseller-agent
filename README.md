# OpSeller Agent

OpSeller Agent e o worker local do ecossistema OpSeller. Ele roda na maquina do usuario, consulta um Supabase proprio, controla sessoes Selenium e alimenta o banco que depois sera consumido por um painel web.

Neste momento, o foco do projeto e mineracao Amazon:

- receber ASINs iniciais;
- descobrir vitrines/lojas relacionadas;
- capturar produtos dessas vitrines;
- testar se os produtos podem ser vendidos no Seller Central;
- enriquecer produtos aprovados com dados publicos da Amazon.

Futuramente, o mesmo conceito de agente local pode ser expandido para monitoramento de vendas, compras, envios e outras automacoes da operacao Amazon.

## Estado Atual

O projeto possui uma GUI local em Python para ligar e desligar executores. Todos os executores iniciam desligados por padrao.

O acesso ao banco usa Supabase Auth. A `SUPABASE_KEY` deve ser a publishable key, mas as tabelas usam RLS liberando `select`, `insert` e `update` apenas para usuarios `authenticated`.

O Seller Central precisa de login manual em uma sessao Selenium persistente. Essa sessao e usada pelo Executor 3.

## Tecnologias

- Python
- Tkinter
- Selenium
- Supabase
- Supabase Auth
- python-dotenv
- webdriver-manager

## Estrutura Da Pasta

```txt
OpSeller Agent/
|-- seller_workers/          # Codigo principal da aplicacao
|   |-- executors/           # Orquestradores dos ciclos de trabalho
|   |-- workers/             # Workers chamados pelos executores
|   |-- scrapers/            # Scrapers especializados
|   |-- config.py            # Leitura e gravacao de configuracoes
|   |-- database.py          # Funcoes de acesso ao Supabase
|   |-- gui.py               # Interface local de controle
|   |-- main.py              # Entrada da aplicacao
|   |-- selenium_factory.py  # Criacao dos drivers Selenium
|   `-- seller_session.py    # Sessao persistente do Seller Central
|-- db/
|   `-- schema.sql           # Estrutura completa para criar um banco novo
|-- DOCUMENTACAO_EXE.md      # Documentacao operacional detalhada
|-- requirements.txt         # Dependencias Python
|-- .env.example             # Modelo de configuracao
|-- .env                     # Configuracao local real, nao versionar
`-- chrome_profile/          # Perfis Selenium locais, criado automaticamente
```

## Banco De Dados

Para uma instalacao nova, use apenas:

```txt
db/schema.sql
```

Esse arquivo cria toda a estrutura atual do banco:

- `produtos_iniciais`
- `vitrines`
- `produtos_capturados`
- `teste_seller`
- `produtos_minerados`

Tambem cria constraints, indices, RLS e policies para usuarios autenticados.

## Fluxo Das Tabelas

1. `produtos_iniciais`
   - Entrada inicial da mineracao.
   - Contem ASINs que ainda precisam gerar vitrines.

2. `vitrines`
   - Gerada pelo Executor 1.
   - Contem lojas/vitrines encontradas a partir dos ASINs iniciais.

3. `produtos_capturados`
   - Gerada pelo Executor 2.
   - Contem ASINs encontrados nas vitrines.
   - `asin_produto` e chave primaria, entao nao deve haver duplicidade global.

4. `teste_seller`
   - Gerada pelo Executor 3.
   - Contem o resultado do teste no Seller Central.
   - Produtos aprovados ficam `pendente` para seguir ao enriquecimento.
   - Produtos desqualificados ficam `finalizado`.

5. `produtos_minerados`
   - Gerada pelo Executor 4.
   - Contem os dados enriquecidos do produto aprovado.

## Executores

### Executor 1 - Captura De Vitrines

Consome `produtos_iniciais` com `status = 'pendente'`.

Para cada ASIN inicial, abre a pagina do produto na Amazon, captura vitrines/lojas relacionadas e grava em `vitrines`. Quando o worker conclui, marca o ASIN inicial como `finalizado`.

### Executor 2 - Captura De Produtos

Consome `vitrines` com `status = 'pendente'`.

Para cada vitrine, detecta paginas, percorre a loja e grava cada ASIN encontrado imediatamente em `produtos_capturados`. Se o mesmo ASIN ja existir, ignora como duplicado. A vitrine so vira `finalizado` quando a varredura completa termina sem erro.

### Executor 3 - Teste Seller

Consome `produtos_capturados` com `status = 'pendente'`.

Usa a sessao autenticada do Seller Central para testar cada produto. Quando o teste termina, grava o resultado em `teste_seller` e marca o registro em `produtos_capturados` como `finalizado`.

Regras principais:

- `Aprovado | Sem restricoes`: grava em `teste_seller` com `status = 'pendente'`.
- `Desqualificado | Requer Aprovacao`: grava em `teste_seller` com `status = 'finalizado'`.
- `Desqualificado | Erro 5886`: grava em `teste_seller` com `status = 'finalizado'`.
- Erro operacional ou Seller deslogado: nao grava resultado e mantem o produto capturado como `pendente`.

### Executor 4 - Enriquecimento De Produtos

Consome `teste_seller` com `status = 'pendente'`.

Abre a pagina publica do produto na Amazon, captura dados detalhados e grava em `produtos_minerados`.

Campos atuais:

- `asin`
- `nome_do_produto`
- `preco`
- `enviado_por_amazon`
- `vendido_por_amazon`
- `qtd_concorrentes`
- `ranking_1`
- `ranking_2`
- `ranking_3`
- `status`

## Instalacao Passo A Passo

### 1. Instalar Pre-Requisitos

Instale na maquina:

- Python 3.11 ou superior;
- Git;
- Google Chrome;
- uma conta/projeto no Supabase.

Confirme no PowerShell:

```powershell
python --version
git --version
```

### 2. Clonar O Repositorio

Escolha uma pasta onde o projeto vai ficar e rode:

```powershell
git clone https://github.com/Gs-devsolution/opseller-agent.git
cd "opseller-agent"
```

Se o repositorio estiver privado, faca login no GitHub antes ou use uma credencial/token com acesso ao repositorio.

### 3. Criar Ambiente Virtual

Recomendado para isolar as dependencias do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativacao, rode uma vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Depois ative novamente:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Instalar Dependencias

Com o ambiente virtual ativo:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Criar O Banco No Supabase

Crie um projeto novo no Supabase.

Depois, no painel do Supabase:

1. Abra `SQL Editor`.
2. Crie uma nova query.
3. Copie o conteudo de `db/schema.sql`.
4. Execute o SQL.

Esse arquivo cria as tabelas, constraints, indices, RLS e policies necessarias para uma instalacao nova.

### 6. Criar Usuario No Supabase Auth

No painel do Supabase:

1. Acesse `Authentication`.
2. Acesse `Users`.
3. Crie um usuario com email e senha.

Esse email e senha serao usados na GUI do OpSeller Agent para autenticar no banco.

### 7. Pegar URL E Publishable Key Do Supabase

No painel do Supabase:

1. Acesse `Project Settings`.
2. Acesse `API`.
3. Copie:
   - Project URL;
   - publishable key.

Nao use a `service_role key` no OpSeller Agent.

### 8. Primeira Execucao Do Agent

Dentro da pasta do projeto, com o ambiente virtual ativo:

```powershell
python -m seller_workers.main
```

Na primeira execucao, a GUI vai permitir preencher:

- `SUPABASE_URL`: Project URL do Supabase;
- `SUPABASE_KEY`: publishable key do Supabase.

Clique em `Salvar configuracao`.

O projeto vai criar o arquivo `.env` local automaticamente.

### 9. Login No Supabase Pela GUI

Na area `Supabase` da GUI:

1. Clique em `Login`.
2. Informe o email e senha criados no Supabase Auth.
3. Confirme o login.

Depois do login, os botoes dos executores ficam liberados.

### 10. Login No Seller Central

Esse passo so e necessario para o Executor 3.

Na area `Sessao Seller`:

1. Clique em `Abrir/Login`.
2. Faca login manual no Seller Central no navegador aberto pelo Selenium.
3. Depois de autenticado, volte para a GUI e ligue o Executor 3 quando precisar.

### 11. Inserir ASINs Iniciais

Para iniciar a mineracao, adicione ASINs na tabela `produtos_iniciais` com status `pendente`.

Exemplo no SQL Editor do Supabase:

```sql
insert into public.produtos_iniciais (asin, status)
values
    ('B0EXEMPLO01', 'pendente'),
    ('B0EXEMPLO02', 'pendente')
on conflict (asin) do nothing;
```

### 12. Ligar Os Executores

Na GUI:

1. Ligue o Executor 1 para capturar vitrines dos ASINs iniciais.
2. Ligue o Executor 2 para capturar produtos das vitrines.
3. Abra/login a sessao Seller e ligue o Executor 3 para testar produtos.
4. Ligue o Executor 4 para enriquecer produtos aprovados.

Os executores podem ser ligados/desligados pela GUI. Por padrao, todos iniciam desligados.

### 13. Executar Novamente Depois

Nas proximas vezes:

```powershell
cd "CAMINHO\opseller-agent"
.\.venv\Scripts\Activate.ps1
python -m seller_workers.main
```

## Configuracao

O arquivo `.env` pode ser criado manualmente a partir do `.env.example`, mas a GUI tambem permite preencher `SUPABASE_URL` e `SUPABASE_KEY` na primeira execucao.

Variaveis principais:

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
```

Significados:

- `EXECUTOR_*_ENABLED`: define se algum executor inicia ligado. O recomendado para distribuicao e `false`.
- `INTERVALO_ORQUESTRADOR_SEGUNDOS`: intervalo curto usado em estados de orquestracao, erro ou pausa.
- `INTERVALO_SEM_PENDENTES_SEGUNDOS`: espera quando nao ha tarefa pendente.
- `INTERVALO_APOS_LOTE_SEGUNDOS`: espera apos concluir um lote.
- `MAX_PAGINAS_POR_VITRINE`: limite de paginas por vitrine no Executor 2. `0` significa sem limite.
- `SELENIUM_PROFILE_DIR`: pasta local onde ficam os perfis do Chrome.
- `SELLER_CENTRAL_URL`: URL inicial da sessao Seller.

## Arquivos Que Nao Devem Ser Distribuidos

Nao envie estes itens preenchidos:

```txt
.env
chrome_profile/
```

Motivos:

- `.env` contem URL e chave publica do projeto Supabase do usuario.
- `chrome_profile/` pode conter cookies, sessoes e dados de login.

O sistema cria `chrome_profile/` automaticamente quando necessario.

## Observacoes Operacionais

- O agente foi pensado para ser idempotente.
- Se um worker for interrompido, os registros pendentes devem continuar pendentes para nova tentativa.
- Produtos capturados sao deduplicados globalmente por ASIN.
- Vitrines sao deduplicadas globalmente por URL.
- O Executor 3 depende de login manual no Seller Central.
- Se o Seller Central deslogar, o Executor 3 nao deve finalizar produtos indevidamente.

## Prompt Para IA

Use este prompt para contextualizar outra IA sobre o projeto:

```txt
Voce esta trabalhando no projeto OpSeller Agent.

O OpSeller Agent e uma aplicacao local em Python que funciona como worker/agent para sellers da Amazon. Ele roda na maquina do usuario, abre uma GUI local em Tkinter, conecta em um Supabase proprio do usuario e controla executores Selenium que alimentam o banco usado por um painel web.

O produto final sera dividido entre:
- Agent local: este projeto, responsavel por automacoes locais, Selenium, scraping, login Seller Central e alimentacao do banco.
- Painel web: outro projeto, futuramente desenvolvido em Lovable, que consumira o Supabase para mostrar e controlar a operacao.

Objetivo atual:
O escopo atual e mineracao de ASINs abertos na Amazon. O fluxo comeca com ASINs iniciais, captura vitrines/lojas relacionadas, captura produtos dessas vitrines, testa os produtos no Seller Central e enriquece os produtos aprovados com dados publicos da Amazon.

Tecnologias:
- Python
- Tkinter para GUI local
- Selenium para navegacao automatizada
- webdriver-manager para driver Chrome
- Supabase para banco
- Supabase Auth para autenticar o usuario
- python-dotenv para configuracao local

Banco Supabase:
Use o arquivo db/schema.sql para criar um banco novo do zero. Nao assuma migracoes antigas. As tabelas atuais sao:
- produtos_iniciais
- vitrines
- produtos_capturados
- teste_seller
- produtos_minerados

Seguranca:
O agente usa SUPABASE_URL e SUPABASE_KEY no .env. A chave deve ser a publishable key, nunca service_role. As tabelas usam RLS e policies apenas para authenticated. Portanto o usuario precisa fazer login via Supabase Auth na GUI antes de ligar executores.

GUI:
A GUI local permite:
- configurar SUPABASE_URL e SUPABASE_KEY na primeira execucao;
- autenticar no Supabase;
- ligar/desligar Executor 1, 2, 3 e 4;
- abrir/fechar sessao Seller Central;
- visualizar logs.

Selenium:
Executores 1, 2 e 4 usam Selenium proprio. O Executor 3 usa uma sessao Seller persistente, aberta pela GUI, porque precisa de login manual no Seller Central. Perfis Chrome ficam em chrome_profile/ e nao devem ser versionados nem distribuidos preenchidos.

Fluxo:
1. Executor 1 consome produtos_iniciais pendentes, acessa paginas de produtos Amazon e grava vitrines encontradas em vitrines. Finaliza o ASIN inicial quando conclui.
2. Executor 2 consome vitrines pendentes, percorre todas as paginas da loja, grava ASINs em produtos_capturados produto a produto e finaliza a vitrine apenas quando a varredura completa termina.
3. Executor 3 consome produtos_capturados pendentes, testa cada ASIN no Seller Central autenticado e grava o resultado em teste_seller. Depois marca produtos_capturados como finalizado. Se houver erro operacional ou sessao deslogada, nao grava resultado e mantem pendente.
4. Executor 4 consome teste_seller pendente, abre a pagina publica Amazon, enriquece o produto e grava em produtos_minerados.

Regras de idempotencia:
- produtos_iniciais tem chave primaria asin.
- vitrines tem URL unica.
- produtos_capturados tem chave primaria asin_produto, sem duplicidade global.
- teste_seller tem chave primaria asin_produto.
- produtos_minerados tem chave primaria asin.
- Nao marcar registros como finalizados quando o worker nao concluir de verdade.
- Inserts devem verificar duplicidade/upsert quando fizer sentido.

Status:
- produtos_iniciais: pendente, finalizado.
- vitrines: pendente, finalizado.
- produtos_capturados: pendente, finalizado.
- teste_seller: pendente significa aprovado e aguardando enriquecimento; finalizado significa desqualificado ou ja enriquecido.
- produtos_minerados: pendente, reprovado por margem, aprovado por margem, em operacao.

Tabela produtos_minerados:
Campos atuais:
- asin
- nome_do_produto
- preco
- enviado_por_amazon
- vendido_por_amazon
- qtd_concorrentes
- ranking_1
- ranking_2
- ranking_3
- status

Importante:
- Nao criar interface web neste projeto.
- Nao usar service_role key no agent.
- Nao versionar .env nem chrome_profile/.
- Preferir codigo simples e modular.
- Antes de alterar scraping, verificar os seletores atuais em seller_workers/scrapers/.
- Antes de alterar fluxo de banco, verificar seller_workers/database.py e db/schema.sql.
```
