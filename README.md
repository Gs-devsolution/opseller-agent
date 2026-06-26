# OpSeller Agent

Aplicacao local em Python para controlar executores Selenium que consultam o Supabase e processam filas de mineracao Amazon.

## Estrutura Da Pasta

```txt
OpSeller Agent/
|-- seller_workers/          # Codigo da aplicacao
|-- db/                      # SQLs para criar/ajustar o banco Supabase
|-- DOCUMENTACAO_EXE.md      # Documentacao operacional dos executores/workers
|-- requirements.txt         # Dependencias Python
|-- .env.example             # Modelo de configuracao
|-- .env                     # Configuracao local real, nao distribuir
`-- chrome_profile/          # Criado automaticamente pelo Selenium, nao distribuir preenchido
```

## Como Preparar Em Outra Maquina

1. Instale Python 3.11+.

2. Abra o PowerShell dentro desta pasta:

```powershell
cd "CAMINHO\OpSeller Agent"
```

3. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

4. Crie o arquivo `.env` a partir do exemplo:

```powershell
copy .env.example .env
```

5. Preencha no `.env`:

```env
SUPABASE_URL=
SUPABASE_KEY=
```

6. Configure o banco no Supabase usando o SQL da pasta `db/`.

Rode no SQL Editor do Supabase:

```txt
db/schema.sql
```

7. Crie um usuario no Supabase Auth.

No painel do Supabase, acesse `Authentication > Users` e crie o usuario que sera usado pelo dono da instalacao.

8. Inicie a aplicacao:

```powershell
python -m seller_workers.main
```

9. Na GUI, faca login na area `Supabase`.

Os executores so ficam liberados depois que o login no Supabase for concluido.

## Sessao Seller Central

O Executor 3 precisa de login manual no Seller Central.

1. Abra a GUI.
2. Clique em `Abrir/Login` na area `Sessao Seller`.
3. Faca login manual no navegador.
4. Depois ligue o Executor 3.

O perfil autenticado fica salvo localmente em:

```txt
chrome_profile/seller/
```

## O Que Nao Distribuir

Para entregar a aplicacao a outro usuario, nao envie estes itens preenchidos:

```txt
.env
chrome_profile/
```

Motivos:

- `.env` contem chave do Supabase.
- `chrome_profile/` pode conter cookies, sessoes e dados de login.

O sistema cria `chrome_profile/` automaticamente na primeira execucao.

## Autenticacao Supabase

O `.env` usa a publishable key do Supabase apenas para iniciar o cliente e autenticar o usuario.

As tabelas do `schema.sql` nao permitem operacoes para `anon`; elas permitem `select`, `insert` e `update` somente para `authenticated`.

Nao use a `service_role key` no OpSeller Agent nem no painel web.

## SQLs Disponiveis

- `db/schema.sql`
  - cria a estrutura atual do banco para uma instalacao nova.

## Comando Principal

```powershell
python -m seller_workers.main
```
