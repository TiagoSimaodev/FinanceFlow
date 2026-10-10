# FinanceFlow

Aplicativo de finanças pessoais em Flask. O FinanceFlow permite cadastrar e filtrar receitas e despesas, visualizar um dashboard mensal com indicadores calculados no banco, alternar entre tema claro e escuro e importar movimentações por CSV com validação e rastreabilidade. Usa SQLite localmente e pode usar PostgreSQL no Vercel.

## Requisitos

- Python 3.10 ou superior
- `pip`
- Conexão à internet para carregar os gráficos Chart.js via CDN

O SQLite acompanha o Python e não exige instalação separada. O driver PostgreSQL é instalado junto com as dependências do projeto.

## Instalação no Windows

No PowerShell, a partir da pasta do projeto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Se o PowerShell bloquear a ativação do ambiente virtual, execute os comandos usando `.\.venv\Scripts\python.exe` no lugar de `python`.

## Executar

```powershell
python -m flask --app app run --debug
```

Na primeira inicialização, o FinanceFlow cria `instance\financeflow.db` e insere as categorias padrão. Use a navegação para abrir o dashboard, **Movimentações** ou **Importar CSV**. O seletor de tema claro/escuro fica no cabeçalho e a preferência permanece salva neste navegador. Para apontar para outro arquivo local, configure `FINANCEFLOW_DATABASE`; para PostgreSQL, configure `DATABASE_URL`.

No dashboard, baixe cada gráfico como imagem PNG ou exporte as movimentações do mês e dos filtros selecionados em CSV ou Excel (`.xlsx`).

## Publicar no Vercel

O projeto está preparado para a detecção automática do Flask pelo arquivo `app.py` na raiz. Os arquivos públicos ficam em `public\static`, e `requirements.txt` instala as dependências definidas em `pyproject.toml`. Para respeitar o limite de payload das funções Vercel, o upload aceita CSV de até 4 MB nesse ambiente (5 MB localmente).

1. Publique o projeto em um repositório Git e importe esse repositório em **Add New → Project** no Vercel.
2. Use o preset Python/Flask detectado pelo arquivo `app.py` na raiz; deixe o Root Directory como `.`.
3. Crie/conecte um PostgreSQL gerenciado compatível com o Vercel Marketplace.
4. Configure as variáveis abaixo para Production e Preview, depois faça o deploy.
5. Confirme a inicialização em `https://SEU-DOMINIO/api/health`. A aplicação cria o schema e as categorias padrão na primeira inicialização.

Não configure um banco SQLite no Vercel: o sistema falha explicitamente se detectar ausência de `DATABASE_URL`/`POSTGRES_URL` ou `SECRET_KEY`, pois o disco local das funções não é persistente. O `.vercelignore` exclui o ambiente virtual local, testes e banco SQLite da pasta de instância. Em desenvolvimento local, sem URL PostgreSQL, o projeto continua usando SQLite.

Antes de enviar o código ao GitHub, confira o `.gitignore`: ele exclui o ambiente virtual, o banco SQLite, arquivos `.env` e artefatos locais.

### Cadastro, login e segurança

O FinanceFlow permite criar uma conta com nome, e-mail e senha, sem serviço externo de e-mail. A senha é armazenada com hash seguro. No cadastro, um código de recuperação é exibido uma única vez; guarde-o fora do aplicativo. O código não pode ser recuperado se for perdido. Ao redefinir a senha, o código anterior é invalidado e um novo é exibido. A sessão usa cookie HTTP-only, `SameSite=Lax`, HTTPS no Vercel, expiração de sete dias e tokens CSRF em formulários e operações que alteram dados.

Para redefinir a senha, informe o mesmo e-mail da conta, o código de recuperação e a nova senha. O banco guarda somente o hash do código; ele é de uso único, e a redefinição invalida as sessões já abertas. Como o cadastro não confirma o endereço, o e-mail funciona como identificador, mas não comprova controle daquela caixa postal: a recuperação depende de manter o código em segurança.

Configure as variáveis de ambiente:

```text
DATABASE_URL=<URL fornecida pelo PostgreSQL>
SECRET_KEY=<valor aleatório longo>
```

O banco possui a tabela `users`, vinculada às movimentações, metas e lotes de importação. Todas as páginas privadas e APIs de dados, incluindo categorias, dashboard, histórico e rejeições, exigem sessão autenticada. Leituras e gravações são filtradas pelo usuário da sessão no servidor; o frontend não escolhe o `user_id`. Tokens CSRF protegem as operações de escrita.

Gere `SECRET_KEY` localmente com `python -c "import secrets; print(secrets.token_hex(32))"`. No Vercel, configure os valores em **Project → Settings → Environment Variables**, junto com `DATABASE_URL`. Nunca versione segredos.

### Dados existentes e segurança

- A URL PostgreSQL deve ser mantida apenas nas variáveis de ambiente do Vercel; não a inclua em arquivos versionados ou no frontend.
- Cada conta possui movimentações, metas e importações isoladas. Categorias de referência são globais e compartilhadas.
- Contas antigas sem credencial de senha não recebem uma senha automaticamente por alguém informar o mesmo e-mail. Faça uma migração de identidade apropriada antes de usar dados dessas contas existentes.
- Ao atualizar uma base antiga, o schema adiciona `user_id` às tabelas existentes, mas preserva os registros anteriores com `user_id` nulo. Esses registros não aparecem para usuários autenticados e **não são atribuídos automaticamente** a ninguém. Faça backup antes de qualquer atribuição manual.
- A configuração PostgreSQL cria as tabelas, mas **não copia automaticamente** os dados do arquivo SQLite local para a nova base. Faça uma migração de dados separada somente se precisar preservar registros existentes.
- O endpoint de health verifica a aplicação; a criação/evolução do schema no início do processo também exige que o banco esteja acessível.

Verificação básica da aplicação:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
```

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes usam bancos temporários e verificam inicialização e migração do schema, isolamento por usuário, proteção de sessão/CSRF, categorias, restrições do banco, cadastro, código de recuperação, hash de senha, filtros, indicadores analíticos, importações CSV e endpoint de saúde.

## API de movimentações

- `GET /api/categories` lista as categorias. Use `?type=receita` ou `?type=despesa` para filtrar por tipo.
- `GET /api/me` retorna o usuário autenticado. Páginas e demais APIs redirecionam para o login ou retornam HTTP `401` sem uma sessão válida.
- `POST /api/transactions` cadastra uma movimentação via JSON. Exemplo:

  ```json
  {
    "type": "despesa",
    "amount": "42.90",
    "date": "2026-10-10",
    "category_id": 2,
    "description": "Almoço"
  }
  ```

- `GET /api/transactions` lista movimentações. Filtros opcionais: `start_date`, `end_date`, `type` e `category_id`. Datas usam o formato ISO `AAAA-MM-DD`.

O valor enviado deve ser positivo e ter no máximo duas casas decimais. O backend o converte para centavos inteiros antes de persistir. Respostas inválidas retornam status HTTP `400` e uma mensagem no campo `error`.

## Importação CSV

A tela **Importar CSV** aceita arquivos UTF-8 de até 5 MB localmente (4 MB no Vercel) e detecta o separador. Selecione mês ou ano antes de importar; linhas com datas fora desse período escolhido são preservadas como rejeições, com o motivo. Os botões de modelo baixam CSVs com o cabeçalho pronto (`data;tipo;valor;categoria;descricao`) para o período selecionado. A coluna `descricao` é opcional ao importar. Exemplo preenchido:

```csv
data;tipo;valor;categoria;descricao
10/10/2026;despesa;1.234,56;Alimentação;Mercado
2026-10-10;receita;3500.00;Salário;Pagamento
```

Datas aceitam `AAAA-MM-DD` ou `DD/MM/AAAA`; valores aceitam formato brasileiro com vírgula decimal ou ponto decimal. Use `receita` para o que entrou (por exemplo, categoria `Salário`) e `despesa` para o que saiu (por exemplo, `Alimentação` ou `Transporte`). A coluna `descricao` pode guardar o nome ou detalhe do lançamento. As categorias precisam existir e corresponder ao tipo. Linhas inválidas e repetições exatas dentro do mesmo arquivo são rejeitadas com linha, conteúdo original e motivo armazenados para revisão. Importar novamente o mesmo conteúdo retorna HTTP `409` e não cria outro lote. Lotes (incluindo os que falharam ao validar) registram status, contagens, duração e erro.

- `POST /api/imports`: envie `multipart/form-data` com campo `file`.
- `GET /api/imports`: lista lotes e quantidades processadas, aceitas e rejeitadas.
- `GET /api/imports/{id}/rejections`: consulta linhas rejeitadas e seus motivos.
- `GET /api/imports/template?period_type=month&period=AAAA-MM` ou `period_type=year&period=AAAA`: baixa o modelo do período solicitado.

## Dashboard

- `GET /api/dashboard` retorna os indicadores do mês atual; `?month=AAAA-MM` seleciona outro mês já iniciado.
- `type=receita|despesa` e `category_id={id}` filtram a evolução mensal e a distribuição por categoria nos gráficos. A seleção de categoria, como `Salário` ou `Alimentação`, ajusta automaticamente o tipo. Os cards continuam mostrando os totais do período completo, sem filtro.
- As somas e agrupamentos são calculados em SQL a partir das movimentações armazenadas. O saldo é o fluxo líquido do período (receitas menos despesas), não um saldo bancário com abertura de conta.
- A taxa de economia é `(receitas - despesas) / receitas`. A variação compara as despesas do mês selecionado com o mês anterior. Quando não há base para calcular um percentual (por exemplo, receita ou despesas no mês anterior iguais a zero), a API retorna `null`.
- O gráfico mensal exibe os seis meses até o período selecionado. A distribuição por categoria mostra despesas por padrão e entradas ao filtrar receitas.
- Os gráficos utilizam Chart.js 4 via CDN; para carregá-los é necessária conexão à internet. Os indicadores e a API são servidos pelo Flask.

## Decisões de persistência

- Valores monetários serão armazenados como inteiros em centavos (`R$ 12,34` = `1234`), evitando imprecisão de ponto flutuante.
- Datas são persistidas no formato ISO (`AAAA-MM-DD`); SQLite usa texto validado e PostgreSQL usa o tipo `DATE`.
- O schema equivalente para SQLite e PostgreSQL restringe tipos, valores positivos, datas e relações entre movimentações, categorias e importações.
- Chaves estrangeiras são habilitadas em cada conexão SQLite e impostas pelo PostgreSQL.
- As categorias iniciais são apenas dados de referência para desenvolvimento; não há movimentações financeiras fictícias pré-carregadas.
