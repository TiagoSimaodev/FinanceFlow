gi# FinanceFlow

Aplicação web de finanças pessoais para registrar receitas e despesas, importar extratos CSV, acompanhar indicadores e visualizar a evolução financeira. O projeto foi estruturado para execução local com SQLite e implantação serverless no Vercel com PostgreSQL.

> **Estado do produto:** cadastro, login, movimentações, importação CSV, dashboard e exportações estão implementados. A tabela de metas existe no schema, mas a interface e as operações de metas ainda não foram implementadas.

## Sumário

- [Funcionalidades](#funcionalidades)
- [Tecnologias e arquitetura](#tecnologias-e-arquitetura)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Fluxo dos dados](#fluxo-dos-dados)
- [Modelo de dados](#modelo-de-dados)
- [Instalação e execução local](#instalação-e-execução-local)
- [Configuração](#configuração)
- [Importação CSV](#importação-csv)
- [Dashboard e exportações](#dashboard-e-exportações)
- [API](#api)
- [Testes](#testes)
- [Deploy no Vercel](#deploy-no-vercel)
- [Segurança e limitações conhecidas](#segurança-e-limitações-conhecidas)

## Funcionalidades

- Cadastro e login com e-mail e senha.
- Registro de receitas e despesas em reais.
- Categorias predefinidas: Moradia, Alimentação, Transporte, Lazer, Água, Luz, Internet, Cartão de crédito, Carro, Moto, Compras do mês, Telefone, Streaming e Salário.
- Histórico filtrável por data, tipo e categoria.
- Dashboard com totais do mês, saldo do período, taxa de economia, variação mensal de despesas e gráficos.
- Alternância entre tema claro e escuro, com preferência guardada no navegador.
- Importação de CSV por mês ou ano, com validação, deduplicação, histórico e motivos de rejeição.
- Download de gráficos em PNG e exportação das movimentações filtradas em CSV e Excel (`.xlsx`).
- Isolamento dos dados por usuário autenticado.

## Tecnologias e arquitetura

| Camada | Tecnologia | Responsabilidade |
| --- | --- | --- |
| Interface | HTML, CSS e JavaScript | Páginas responsivas, formulários, filtros e interação |
| Gráficos | Chart.js 4 | Visualizações no navegador |
| Aplicação web | Flask | Rotas, autenticação, validação e composição da aplicação |
| Dados tabulares | Pandas | Leitura e normalização dos arquivos CSV importados |
| Banco local | SQLite | Desenvolvimento e testes locais |
| Banco de produção | PostgreSQL | Persistência em implantação no Vercel |
| Excel | openpyxl | Criação de arquivos `.xlsx` |
| Testes | unittest | Testes de integração e regras de negócio |

As rotas HTTP delegam validações e operações a serviços, que usam repositórios para acessar o banco. A camada de conexão abstrai diferenças entre SQLite e PostgreSQL, mantendo parâmetros SQL portáveis no código da aplicação. Consultas analíticas e agregações do dashboard são executadas no banco.

## Estrutura do projeto

```text
.
├── app.py                           # Entrada Flask usada localmente e pelo Vercel
├── pyproject.toml                    # Metadados e dependências do projeto
├── requirements.txt                  # Dependências instaladas pelo Vercel
├── README.md
├── public/
│   └── static/                       # Assets servidos no Vercel
├── src/
│   └── financeflow/
│       ├── __init__.py               # Factory create_app e configuração HTTP
│       ├── config.py                 # Configuração por ambiente
│       ├── db/
│       │   ├── connection.py         # Conexões e inicialização do schema
│       │   ├── schema.sql            # Schema SQLite
│       │   └── schema_postgresql.sql # Schema PostgreSQL
│       ├── repositories/             # Consultas e persistência
│       ├── routes/                   # Endpoints e páginas Flask
│       ├── services/                 # Regras de negócio e processamento
│       ├── templates/                # Templates Jinja/HTML
│       └── static/                   # CSS e JavaScript da aplicação
└── tests/                            # Testes automatizados
```

`public/static` contém cópias dos assets necessários à configuração estática do Vercel. Ao alterar CSS ou JavaScript servido pela aplicação, mantenha as cópias correspondentes sincronizadas.

## Fluxo dos dados

### Cadastro manual

1. A pessoa envia uma movimentação pelo formulário.
2. O JavaScript envia os campos para a API Flask.
3. O serviço valida tipo, data, valor, descrição e correspondência entre tipo e categoria.
4. O valor decimal é convertido para centavos inteiros.
5. O repositório grava a movimentação associada ao usuário da sessão.
6. O histórico e o dashboard consultam os dados persistidos no banco.

### Importação CSV

1. A pessoa escolhe o escopo mensal ou anual e envia o arquivo.
2. O pipeline valida tamanho, codificação, colunas e conteúdo.
3. Pandas lê e padroniza os dados de entrada.
4. Cada linha válida é carregada no banco; linhas rejeitadas mantêm o conteúdo original e o motivo.
5. O lote registra status, contagens e duração. O hash SHA-256 do arquivo impede importar novamente o mesmo conteúdo para a mesma conta.
6. As movimentações importadas passam a alimentar o histórico e os indicadores como os registros manuais.

## Modelo de dados

O schema cria as seguintes entidades:

- **`users`**: identidade, e-mail, nome e versão da sessão.
- **`password_credentials`**: hash da senha, separado da identidade.
- **`password_recovery_codes`**: hash do código de recuperação de uso único.
- **`categories`**: categorias compartilhadas, identificadas por nome e tipo.
- **`transactions`**: movimentações, valor em centavos, data, descrição, categoria, proprietário e origem.
- **`import_batches`**: histórico e métricas de cada arquivo processado.
- **`import_rejections`**: linha original e motivo de cada rejeição.
- **`goals`**: estrutura inicial para metas financeiras; ainda sem fluxo de interface/API.

As chaves estrangeiras e restrições protegem a integridade referencial. Há índices para consultas por usuário/data, categoria, tipo e lote de importação. O par categoria/tipo garante que uma receita não seja gravada com uma categoria exclusiva de despesa.

Valores são persistidos em centavos inteiros (`R$ 12,34` = `1234`) para evitar erros de ponto flutuante. Datas são validadas no formato ISO `AAAA-MM-DD`; SQLite as armazena como texto e PostgreSQL como `DATE`.

## Instalação e execução local

Requisitos: Python 3.10 ou superior e pip. No Windows, abra o PowerShell na pasta do projeto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Se não quiser ativar o ambiente virtual, use o executável diretamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

Inicie o servidor:

```powershell
python -m flask --app app run --debug
```

Abra `http://127.0.0.1:5000`. Na primeira inicialização, a aplicação cria `instance\financeflow.db`, o schema e as categorias predefinidas. Não são inseridas movimentações financeiras fictícias.

Para confirmar que a aplicação está respondendo:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

O resultado esperado é `status: ok`. Se a porta 5000 estiver ocupada, escolha outra, por exemplo `--port 5055`.

## Configuração

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `SECRET_KEY` | No Vercel | Segredo usado para assinar sessões Flask. Em desenvolvimento local, se omitido, é gerado um segredo temporário novo em cada inicialização. |
| `DATABASE_URL` | No Vercel | URL de conexão PostgreSQL. |
| `POSTGRES_URL` | Alternativa | URL PostgreSQL usada quando `DATABASE_URL` não estiver definida. |
| `FINANCEFLOW_DATABASE` | Não | Caminho para um arquivo SQLite local alternativo. |
| `VERCEL` | Definida pela plataforma | Quando igual a `1`, ativa configuração serverless, cookie seguro e limite de upload reduzido. |

Gere um segredo localmente no PowerShell:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Nunca inclua valores secretos ou URLs de banco em arquivos versionados. O `.gitignore` exclui o banco local, ambiente virtual e artefatos Python.

## Importação CSV

A tela **Importar CSV** permite importar por mês ou ano. O limite é 5 MB localmente e 4 MB no Vercel. Os modelos baixáveis usam o cabeçalho:

```csv
data;tipo;valor;categoria;descricao
10/10/2026;despesa;1.234,56;Alimentação;Compras do mês
2026-10-10;receita;3500.00;Salário;Pagamento
```

- `data`: `AAAA-MM-DD` ou `DD/MM/AAAA`.
- `tipo`: `receita` ou `despesa`.
- `valor`: valor positivo, com até duas casas decimais; aceita decimal com vírgula ou ponto.
- `categoria`: nome de categoria já existente e compatível com o tipo.
- `descricao`: opcional.

Linhas inválidas, fora do período selecionado ou repetidas dentro do arquivo não são descartadas silenciosamente: ficam registradas no lote com o conteúdo original e o motivo da rejeição. Importar o mesmo conteúdo novamente para a mesma conta retorna HTTP `409`.

## Dashboard e exportações

O Dashboard mostra os indicadores do mês selecionado:

- Receitas, despesas e saldo líquido (`receitas - despesas`).
- Percentual economizado: `(receitas - despesas) / receitas`.
- Variação das despesas em relação ao mês anterior.
- Evolução de receitas e despesas nos últimos seis meses.
- Distribuição mensal por categoria.

As somas e agrupamentos usam movimentações persistidas. Os filtros de tipo e categoria controlam os gráficos; os cards mantêm os totais completos do período. Percentuais sem base de comparação são retornados como `null`.

Cada gráfico pode ser baixado em PNG. Os botões **Baixar CSV** e **Baixar Excel** exportam as movimentações do mês e aplicam os filtros de tipo/categoria selecionados. O Excel inclui data formatada, valores numéricos em reais, cabeçalho fixo e filtro automático. Exportações são geradas somente com registros do usuário autenticado.

## API

Páginas privadas e APIs de dados exigem sessão autenticada. Sem sessão válida, as páginas redirecionam para login e endpoints de API retornam HTTP `401`. Operações de escrita são protegidas por CSRF.

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET`, `POST` | `/login` | Página e autenticação por e-mail/senha |
| `GET`, `POST` | `/register` | Cadastro de conta |
| `GET`, `POST` | `/forgot-password` | Redefinição de senha com código de recuperação |
| `POST` | `/auth/logout` | Encerrar sessão |
| `GET` | `/api/me` | Identidade da sessão atual |
| `GET` | `/api/health` | Verificação de saúde da aplicação |
| `GET` | `/api/categories?type=despesa` | Categorias, opcionalmente filtradas por tipo |
| `GET`, `POST` | `/api/transactions` | Consultar ou cadastrar movimentações |
| `GET` | `/api/dashboard?month=AAAA-MM` | Indicadores e dados dos gráficos |
| `GET` | `/api/dashboard/export?format=csv&month=AAAA-MM` | Baixar CSV do período/filtros |
| `GET` | `/api/dashboard/export?format=xlsx&month=AAAA-MM` | Baixar Excel do período/filtros |
| `GET`, `POST` | `/api/imports` | Consultar histórico ou importar CSV |
| `GET` | `/api/imports/template?period_type=month&period=AAAA-MM` | Baixar modelo de CSV |
| `GET` | `/api/imports/{id}/rejections` | Consultar rejeições de um lote próprio |

Exemplo de `POST /api/transactions`:

```json
{
  "type": "despesa",
  "amount": "42.90",
  "date": "2026-10-10",
  "category_id": 2,
  "description": "Almoço"
}
```

O identificador da categoria deve ser obtido em `GET /api/categories`; o exemplo não presume que o ID seja fixo. Valores inválidos retornam HTTP `400` com mensagem no campo `error`.

## Testes

Execute a suíte completa no ambiente virtual:

```powershell
python -m unittest discover -s tests -v
```

Os testes usam bancos SQLite temporários e cobrem autenticação, CSRF, isolamento de contas, restrições e inicialização do schema, filtros, indicadores, importações, rejeições e downloads CSV/Excel.

## Deploy no Vercel

O projeto usa `app.py` como entrada Flask. O filesystem da função Vercel não é persistente; portanto, SQLite não deve ser usado em produção.

1. Envie o projeto para um repositório Git e importe-o no Vercel.
2. Use a raiz do repositório como **Root Directory**. Deixe o build preset Python/Flask ser detectado pelo `app.py`.
3. Conecte um PostgreSQL gerenciado pelo Vercel Marketplace ou outro serviço PostgreSQL acessível.
4. Nas variáveis de ambiente de Production e Preview, configure:
   - `DATABASE_URL`: URL PostgreSQL.
   - `SECRET_KEY`: segredo aleatório forte, igual entre instâncias do mesmo ambiente.
5. Faça o deploy e confirme `https://SEU-DOMINIO/api/health`.

No Vercel, a aplicação exige `DATABASE_URL` ou `POSTGRES_URL` e `SECRET_KEY`. O schema e as categorias são inicializados na inicialização da aplicação. Isso **não migra automaticamente** os registros de um arquivo SQLite local para o PostgreSQL.

O `.vercelignore` exclui testes, ambiente virtual e banco local do pacote de deploy. `requirements.txt` lista as dependências usadas para instalação na plataforma.

## Segurança e limitações conhecidas

- As senhas são armazenadas com hash seguro via Werkzeug; não são persistidas em texto puro.
- O cadastro **não verifica o controle do endereço de e-mail**. O e-mail é um identificador da conta, não um fator de recuperação.
- Um código aleatório de recuperação é exibido uma única vez no cadastro. O banco armazena somente seu SHA-256. Guarde-o fora do aplicativo; se for perdido, não será possível recuperar a conta apenas com o e-mail.
- O código é de uso único. Ao redefinir a senha, o código anterior é invalidado, outro código é exibido e as sessões existentes são invalidadas.
- Cookies de sessão são HTTP-only, `SameSite=Lax` e `Secure` no Vercel. A duração da sessão é de sete dias.
- O `user_id` é obtido da sessão no servidor. Consultas e gravações de dados privados são restringidas ao usuário autenticado.
- Exportações e arquivos CSV podem conter informações financeiras: armazene-os e compartilhe-os com cuidado.
- O schema cria a estrutura de metas, mas não há ainda gerenciamento de metas na interface/API.
- O schema antigo pode conter identidades de login anteriores sem credencial de senha. A aplicação não associa automaticamente essas contas ao cadastro por e-mail; faça uma migração de identidade explícita e segura antes de reutilizar dados antigos.
- A inicialização atual aplica ajustes compatíveis para algumas estruturas legadas; não substitui um sistema formal de migrações versionadas para mudanças futuras de schema.
- A biblioteca Chart.js é carregada por CDN; a conexão à internet é necessária para exibir e baixar os gráficos gerados pelo navegador.

## Licença

Nenhuma licença de distribuição foi definida neste repositório. Defina uma licença antes de redistribuir o projeto como software open source.
