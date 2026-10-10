# FinanceFlow — Gestão Financeira Pessoal

Aplicação web de finanças pessoais desenvolvida com Python e Flask, com foco em organização financeira, processamento de dados, consultas analíticas e visualização de indicadores.

**Status: Em produção e em utilização.**

🌐 **Acesse a aplicação:** https://finance-flow-gt3d.vercel.app/

O FinanceFlow permite registrar receitas e despesas, importar extratos financeiros em CSV, acompanhar indicadores em um dashboard interativo e exportar movimentações para CSV e Excel. A aplicação utiliza SQLite no ambiente local e PostgreSQL no ambiente de produção, hospedado com deploy serverless na Vercel.

O projeto também explora práticas de organização em camadas, validação de dados, isolamento entre usuários, integridade referencial, consultas analíticas no banco de dados e automação de tarefas de processamento.

---

## Sumário

- [Demonstração](#demonstração)
- [Funcionalidades](#funcionalidades)
- [Tecnologias](#tecnologias)
- [Arquitetura](#arquitetura)
- [Fluxo de processamento de dados](#fluxo-de-processamento-de-dados)
- [Modelo de dados](#modelo-de-dados)
- [Dashboard e indicadores](#dashboard-e-indicadores)
- [Importação e qualidade dos dados](#importação-e-qualidade-dos-dados)
- [API](#api)
- [Segurança e integridade](#segurança-e-integridade)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Execução local](#execução-local)
- [Configuração por ambiente](#configuração-por-ambiente)
- [Testes](#testes)
- [Deploy e produção](#deploy-e-produção)
- [Limitações conhecidas](#limitações-conhecidas)
- [Licença](#licença)

---

## Demonstração

**Aplicação em produção:** https://finance-flow-gt3d.vercel.app/

O sistema está publicado e sendo utilizado. A implantação permite executar a aplicação em ambiente de produção com banco de dados PostgreSQL gerenciado, separando a persistência dos dados do ambiente serverless da Vercel.

A aplicação foi desenvolvida para oferecer um fluxo integrado entre cadastro financeiro, processamento de arquivos, persistência relacional e visualização de indicadores.

## Funcionalidades

### Gestão financeira

- Cadastro e autenticação de usuários por e-mail e senha.
- Registro de receitas e despesas em reais.
- Histórico de movimentações com filtros por data, tipo e categoria.
- Categorias financeiras predefinidas.
- Isolamento das movimentações por usuário autenticado.
- Alternância entre temas claro e escuro, com preferência armazenada no navegador.

### Processamento e importação de dados

- Importação de extratos financeiros em CSV.
- Leitura e normalização de dados tabulares com Pandas.
- Validação de colunas, datas, valores, categorias e períodos.
- Identificação de registros inválidos, duplicados ou fora do período selecionado.
- Registro dos motivos de rejeição para facilitar a análise dos dados.
- Histórico dos lotes de importação, incluindo status, contagens e duração.
- Identificação de arquivos previamente importados por meio de hash SHA-256.

### Análise e visualização

- Dashboard financeiro com indicadores mensais.
- Gráficos de evolução das receitas e despesas.
- Distribuição de despesas por categoria.
- Comparação de despesas entre períodos.
- Exportação de movimentações filtradas para CSV e Excel.
- Download dos gráficos em formato PNG.

### Categorias disponíveis

Moradia, Alimentação, Transporte, Lazer, Água, Luz, Internet, Cartão de crédito, Carro, Moto, Compras do mês, Telefone, Streaming e Salário.

## Tecnologias

| Tecnologia | Aplicação no projeto |
|---|---|
| Python | Lógica de negócio, validação e processamento |
| Flask | Backend, rotas HTTP e composição da aplicação |
| SQL | Consultas, agregações e persistência relacional |
| PostgreSQL | Banco de dados do ambiente de produção |
| SQLite | Banco de dados local e ambiente de testes |
| Pandas | Leitura, padronização e validação de arquivos CSV |
| HTML, CSS e JavaScript | Interface e interações do usuário |
| Chart.js 4 | Visualização gráfica dos indicadores |
| openpyxl | Geração de arquivos Excel `.xlsx` |
| Werkzeug | Hash seguro de senhas |
| unittest | Testes automatizados |
| Vercel | Hospedagem e execução serverless |
| Neon | PostgreSQL gerenciado para produção |
| Git e GitHub | Versionamento e manutenção do código |

## Arquitetura

A aplicação foi organizada em camadas para separar responsabilidades e facilitar manutenção, testes e evolução do sistema.

**Interface → Rotas → Serviços → Repositórios → Banco de dados**

- **Interface:** formulários, filtros, dashboard e interação com o usuário.
- **Rotas:** recebem requisições HTTP, aplicam controles de acesso e encaminham operações.
- **Serviços:** concentram regras de negócio, validações e processamento.
- **Repositórios:** encapsulam consultas e operações de persistência.
- **Camada de conexão:** abstrai diferenças entre SQLite e PostgreSQL.
- **Banco de dados:** mantém usuários, movimentações, categorias e registros de importação.

A aplicação utiliza uma factory `create_app()` para construir a instância Flask e aplicar as configurações do ambiente.

A camada de persistência mantém compatibilidade com os dois bancos utilizados no projeto. As consultas e agregações do dashboard são executadas no banco de dados, evitando depender exclusivamente do processamento no navegador.

A arquitetura pode ser representada pelo seguinte fluxo:

```text
Usuário
   |
   v
Interface Web
HTML / CSS / JavaScript
   |
   v
Rotas Flask / API
   |
   v
Serviços de negócio
   |
   +--------------------+
   |                    |
   v                    v
Repositórios       Pandas
   |             Processamento
   v                 de CSV
Camada de conexão
   |
   +--------------------+
   |                    |
   v                    v
SQLite local       PostgreSQL
                   Produção
```

## Fluxo de processamento de dados

### 1. Cadastro manual

1. O usuário envia uma movimentação pela interface.
2. O JavaScript encaminha os dados à API Flask.
3. O serviço valida tipo, data, valor, descrição e categoria.
4. O valor monetário é convertido para centavos inteiros.
5. O repositório grava a movimentação associada ao usuário autenticado.
6. O histórico e o dashboard consultam os registros persistidos.

### 2. Importação de extratos CSV

1. O usuário seleciona o período e envia um arquivo.
2. A aplicação valida tamanho, codificação, estrutura e conteúdo.
3. O Pandas lê e padroniza os dados tabulares.
4. As linhas são verificadas conforme as regras de negócio.
5. Os registros válidos são persistidos no banco de dados.
6. As linhas rejeitadas são registradas com o conteúdo original e o motivo da rejeição.
7. O lote de importação recebe informações de processamento, contagens e status.
8. As movimentações importadas passam a compor o histórico e os indicadores financeiros.

O sistema utiliza SHA-256 para identificar arquivos já importados pela mesma conta, evitando o reprocessamento do mesmo conteúdo.

### 3. Consulta e análise

Os dados persistidos alimentam consultas SQL utilizadas nos indicadores e gráficos. Os filtros selecionados controlam os registros apresentados nas visualizações e nas exportações, respeitando as permissões do usuário autenticado.

## Modelo de dados

O schema relacional contempla as seguintes entidades:

| Entidade | Responsabilidade |
|---|---|
| `users` | Identidade, e-mail, nome e versão da sessão |
| `password_credentials` | Armazenamento de hashes de credenciais |
| `password_recovery_codes` | Códigos de recuperação armazenados por hash |
| `categories` | Categorias financeiras e seus tipos |
| `transactions` | Receitas e despesas dos usuários |
| `import_batches` | Histórico e métricas dos lotes importados |
| `import_rejections` | Linhas rejeitadas e respectivos motivos |
| `goals` | Estrutura inicial para futuras funcionalidades de metas |

### Integridade e representação monetária

- Chaves estrangeiras e restrições para preservar a integridade referencial.
- Índices para consultas por usuário, data, categoria, tipo e lote.
- Validação da compatibilidade entre categoria e tipo de movimentação.
- Valores monetários armazenados como centavos inteiros para evitar imprecisões de ponto flutuante.
- Datas validadas no formato ISO `AAAA-MM-DD`.
- Consultas de dados privados restringidas ao usuário autenticado.

Exemplo de representação monetária:

```text
R$ 12,34 → 1234 centavos
```

No SQLite, as datas são armazenadas como texto; no PostgreSQL, são utilizadas colunas do tipo `DATE`.

## Dashboard e indicadores

O dashboard apresenta informações financeiras do período selecionado.

| Indicador | Regra de cálculo |
|---|---|
| Receitas | Soma das receitas do período |
| Despesas | Soma das despesas do período |
| Saldo líquido | Receitas − despesas |
| Taxa de economia | (Receitas − despesas) / Receitas |
| Variação das despesas | Comparação com o mês anterior |
| Evolução financeira | Receitas e despesas dos últimos seis meses |
| Distribuição por categoria | Agrupamento das despesas por categoria |

Os cálculos são baseados nos dados persistidos. Quando não existe uma base válida para determinada comparação, o sistema retorna um valor nulo em vez de apresentar uma porcentagem enganosa.

Os gráficos são construídos com Chart.js e podem ser baixados em PNG. As exportações CSV e Excel respeitam os filtros de movimentações selecionados.

O arquivo Excel inclui cabeçalho, filtros automáticos, datas formatadas e valores numéricos em reais.

## Importação e qualidade dos dados

A importação CSV é um dos componentes centrais do projeto, combinando tratamento tabular, regras de validação e persistência estruturada.

### Formato esperado

```csv
data;tipo;valor;categoria;descricao
10/10/2026;despesa;1234,56;Alimentação;Compras do mês
2026-10-10;receita;3500.00;Salário;Pagamento
```

### Regras de validação

- Datas nos formatos `AAAA-MM-DD` ou `DD/MM/AAAA`.
- Tipos permitidos: `receita` e `despesa`.
- Valores positivos com até duas casas decimais.
- Valores decimais com vírgula ou ponto.
- Categorias existentes e compatíveis com o tipo de movimentação.
- Verificação do período selecionado.
- Detecção de linhas duplicadas no arquivo.
- Registro das rejeições para permitir rastreabilidade do processamento.
- Limite de 5 MB em execução local e 4 MB no ambiente Vercel.

A aplicação diferencia registros aceitos e rejeitados, evitando descartar silenciosamente informações que não atendem às regras de negócio.

A importação do mesmo conteúdo pela mesma conta retorna HTTP 409.

## API

As páginas privadas e as APIs de dados exigem sessão autenticada. Os endpoints de escrita são protegidos por CSRF.

| Método | Rota | Descrição |
|---|---|---|
| GET, POST | `/login` | Página e autenticação |
| GET, POST | `/register` | Cadastro de usuários |
| GET, POST | `/forgot-password` | Fluxo de recuperação de senha |
| POST | `/auth/logout` | Encerramento da sessão |
| GET | `/api/me` | Identidade da sessão atual |
| GET | `/api/health` | Verificação de saúde da aplicação |
| GET | `/api/categories` | Consulta de categorias |
| GET, POST | `/api/transactions` | Consulta e cadastro de movimentações |
| GET | `/api/dashboard` | Indicadores e dados dos gráficos |
| GET | `/api/dashboard/export` | Exportação CSV ou XLSX |
| GET, POST | `/api/imports` | Histórico e importação de arquivos |
| GET | `/api/imports/template` | Download de modelo CSV |
| GET | `/api/imports/{id}/rejections` | Consulta das rejeições de um lote próprio |

### Exemplo de requisição

`POST /api/transactions`

```json
{
  "type": "despesa",
  "amount": "42.90",
  "date": "2026-10-10",
  "category_id": 2,
  "description": "Almoço"
}
```

O identificador da categoria deve ser obtido pela API de categorias; o valor apresentado é ilustrativo.

A aplicação valida os dados recebidos e retorna HTTP 400 quando a requisição contém valores inválidos. Endpoints privados sem sessão válida retornam HTTP 401.

## Segurança e integridade

O projeto implementa controles de segurança voltados à proteção de contas e movimentações financeiras.

- Senhas armazenadas com hash seguro via Werkzeug.
- Códigos de recuperação armazenados por hash SHA-256.
- Códigos de recuperação de uso único.
- Invalidação de sessões existentes após redefinição de senha.
- Proteção CSRF nas operações de escrita.
- Cookies de sessão `HttpOnly`, `SameSite=Lax` e `Secure` em produção.
- Sessões com duração de sete dias.
- Isolamento das movimentações por usuário autenticado.
- Validação de entradas e restrições de integridade no banco.
- Segredos e credenciais configurados por variáveis de ambiente.

Os arquivos exportados podem conter informações financeiras e devem ser armazenados e compartilhados com cuidado.

## Estrutura do projeto

```text
FinanceFlow/
├── app.py
├── pyproject.toml
├── requirements.txt
├── README.md
├── public/
│   └── static/
├── src/
│   └── financeflow/
│       ├── __init__.py
│       ├── config.py
│       ├── db/
│       │   ├── connection.py
│       │   ├── schema.sql
│       │   └── schema_postgresql.sql
│       ├── repositories/
│       ├── routes/
│       ├── services/
│       ├── templates/
│       └── static/
└── tests/
```

`public/static/` contém cópias dos assets utilizados pela configuração estática da Vercel. Alterações em CSS e JavaScript servidos pela aplicação devem manter essas cópias sincronizadas, conforme a configuração atual do projeto.

## Execução local

### Requisitos

- Python 3.10 ou superior.
- pip.
- Git, para clonar o repositório.

### Instalação

No Windows, abra o PowerShell na pasta do projeto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Inicie a aplicação:

```powershell
python -m flask --app app run --debug
```

Acesse:

http://127.0.0.1:5000

Na primeira inicialização, a aplicação cria o banco SQLite local, aplica o schema e registra as categorias predefinidas. Não são inseridas movimentações financeiras fictícias.

### Verificação de saúde

Com o servidor em execução:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

O resultado esperado é um status `ok`.

## Configuração por ambiente

| Variável | Obrigatória | Finalidade |
|---|---|---|
| `SECRET_KEY` | Sim em produção | Assinatura segura das sessões Flask |
| `DATABASE_URL` | Sim em produção | URL de conexão PostgreSQL |
| `POSTGRES_URL` | Alternativa | URL PostgreSQL quando `DATABASE_URL` não está definida |
| `FINANCEFLOW_DATABASE` | Não | Caminho alternativo para o SQLite local |
| `VERCEL` | Definida pela plataforma | Ativa configurações específicas de produção |

Para gerar uma chave secreta localmente, com Python instalado:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Nunca versione segredos, senhas ou URLs de conexão com credenciais. Em produção, utilize as variáveis de ambiente configuradas na plataforma de hospedagem.

## Testes

O projeto utiliza `unittest` para validar regras de negócio e integração.

Execute a suíte de testes:

```powershell
python -m unittest discover -s tests -v
```

Os testes utilizam bancos SQLite temporários e cobrem funcionalidades como:

- Autenticação e proteção CSRF.
- Isolamento de contas.
- Integridade e inicialização do schema.
- Filtros e indicadores financeiros.
- Importação de CSV e registros rejeitados.
- Exportações CSV e Excel.

Os testes automatizados ajudam a verificar o comportamento da aplicação durante alterações e correções.

## Deploy e produção

O FinanceFlow está publicado na Vercel e utiliza PostgreSQL gerenciado pelo Neon para persistência dos dados em produção.

**URL de produção:** https://finance-flow-gt3d.vercel.app/

A configuração utiliza:

- `app.py` como ponto de entrada Flask.
- Vercel para hospedagem serverless.
- Neon PostgreSQL como banco de produção.
- `DATABASE_URL` para conexão com o banco.
- `SECRET_KEY` para assinatura das sessões.
- Inicialização do schema e das categorias pela aplicação.

### Considerações de implantação

O filesystem das funções serverless da Vercel não deve ser tratado como armazenamento persistente. Por isso, o SQLite é destinado ao ambiente local e aos testes, enquanto o PostgreSQL é utilizado em produção.

O endpoint `/api/health` permite verificar se a aplicação está respondendo:

```text
https://finance-flow-gt3d.vercel.app/api/health
```

O deploy não migra automaticamente dados de um banco SQLite local para o PostgreSQL. Essa migração exige um processo explícito de transferência e validação.

O schema atual possui inicialização e ajustes compatíveis com algumas estruturas legadas, mas ainda não utiliza um sistema formal de migrações versionadas.

## Limitações conhecidas e evolução

- O schema contém a tabela `goals`, mas a interface e as operações da API para gerenciamento de metas ainda não foram implementadas.
- O cadastro não verifica a posse do endereço de e-mail.
- O código de recuperação é exibido uma única vez e precisa ser guardado fora da aplicação.
- Estruturas legadas de identidade podem exigir migração explícita antes da reutilização de contas antigas.
- A inicialização do schema ainda não substitui um sistema formal de migrações.
- Os gráficos dependem do carregamento da biblioteca Chart.js por CDN, exigindo conexão à internet para sua visualização.
- A aplicação ainda pode evoluir com monitoramento, observabilidade, rotinas de backup, migrações versionadas e melhorias adicionais de automação e processamento.

Esses pontos representam oportunidades concretas de evolução técnica do produto.

## Licença

Nenhuma licença de distribuição foi definida neste repositório. Uma licença deverá ser escolhida antes de redistribuir o projeto como software de código aberto.
