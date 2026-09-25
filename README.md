# Ponto+ API

API REST do Ponto+, um sistema pessoal para registrar entrada, intervalo, retorno e saída. O servidor controla a ordem das batidas e usa seu próprio relógio. Este é um MVP acadêmico, não um sistema certificado de controle de ponto empresarial.

## Funcionalidades

- Cadastro/login com hash de senha e JWT de 24 horas.
- Perfil e meta diária persistida por usuário.
- Sequência de quatro batidas, histórico mensal e cálculo do tempo trabalhado.
- Desfazer somente a última batida do dia em até cinco segundos.
- Gravação atômica e revisão para tratar requisições simultâneas e conflitos entre abas.
- Swagger com entradas, saídas e erros das oito operações.
- Migração aditiva do banco existente, sem apagar registros.

## Tecnologias e estrutura

Flask mantém a API pequena; SQLite dispensa um servidor de banco separado. SQLAlchemy organiza a persistência; PyJWT valida as sessões; Werkzeug protege as senhas; Flask-CORS aceita a interface como arquivo local; Flasgger fornece o Swagger. Pytest e pytest-cov verificam regras e regressões.

```text
app/
├── routes/              # Entrada HTTP por domínio: autenticação, perfil e batidas
├── services/            # Regras da jornada, cálculos e transações
├── __init__.py          # Fábrica, extensões, CORS, Swagger e health
├── auth.py              # Emissão e validação do JWT
├── configuration.py     # Chave JWT local segura ou configuração externa
├── migrations.py        # Atualizações aditivas do banco
├── openapi.py           # Modelos das respostas do Swagger
├── validation.py        # Validações comuns dos corpos JSON
├── errors.py            # Contrato de erros em português
├── extensions.py        # Instância do banco
└── models.py            # User e Punch
tests/                   # Testes funcionais, concorrência e regressões
run.py                   # Inicialização local, sem depurador
```

## Instalação

Requer Python 3.11 ou superior. Na pasta deste repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Para apenas executar, `requirements.txt` contém as dependências de execução; `requirements-dev.txt` também inclui os testes. No Windows, a ativação equivalente é `.venv\Scripts\Activate.ps1`.

### Configuração e segurança

- Sem variável de ambiente, a primeira execução cria uma chave aleatória persistente em `instance/jwt-secret`. No macOS/Linux o arquivo é privado (permissão 0600).
- Opcionalmente, defina `JWT_SECRET_KEY` com uma chave própria aleatória de pelo menos 32 caracteres. Chaves curtas e valores de exemplo antigos são recusados. Não reutilize chaves de testes.
- `DATABASE_URL` pode apontar para outro banco **SQLite**, por exemplo `sqlite:////caminho/absoluto/ponto_plus.db`. O controle de concorrência deste MVP é específico do SQLite.
- Banco, backups, chave e arquivos `.env` são ignorados pelo Git. Nunca os publique.
- Não apague/troque a chave entre reinicializações: isso invalida tokens existentes. A correção da chave padrão antiga exige novo login, mas preserva contas e batidas.
- Exposição pública, HTTPS, limitação de tentativas e operação de produção não fazem parte desta entrega local.

## Execução

```bash
python run.py
```

- API: `http://127.0.0.1:5001`
- Swagger: `http://127.0.0.1:5001/apidocs`
- Especificação JSON: `http://127.0.0.1:5001/apispec_1.json`
- Banco local: `instance/ponto_plus.db`

Após alterações no back-end, encerre somente o processo desta API e execute-o novamente. Não recrie o banco: a inicialização acrescenta `daily_goal_minutes` e `punch_revision` em bancos antigos. Usuários anteriores recebem meta inicial de 480 minutos.

Com a API ativa, abra o `index.html` do projeto `ponto-web` diretamente por arquivo. Não é necessário servidor de front-end.

## Rotas e contrato

| Método | Rota | Uso |
|---|---|---|
| GET | `/api/health` | Confere a disponibilidade na abertura da SPA |
| POST | `/api/auth/register` | Cadastra e inicia a sessão |
| POST | `/api/auth/login` | Autentica e devolve um JWT |
| GET | `/api/profile` | Consulta o perfil autenticado |
| PATCH | `/api/profile` | Atualiza nome e/ou meta diária |
| GET | `/api/punches?month=YYYY-MM` | Lista histórico e estado atual |
| POST | `/api/punches` | Registra a próxima batida |
| DELETE | `/api/punches/{id}` | Desfaz a última batida em até cinco segundos |

As rotas protegidas recebem `Authorization: Bearer <token>`.

- Cadastro recebe JSON com `name` (2–120 caracteres), `email` válido (até 255) e `password` (6–256). Login recebe e-mail e senha. Senhas não são recortadas: espaços fazem parte da senha.
- Cadastro/login devolvem `token` e `user`. O usuário público contém `id`, `name`, `email`, `daily_goal_minutes` e `created_at`, nunca o hash.
- PATCH de perfil aceita `name` e/ou `daily_goal_minutes` (inteiro de 1 a 1439). E-mail e data de cadastro não são editáveis.
- Histórico aceita mês `YYYY-MM` entre `0001-01` e `9999-11`; omitido significa o mês atual de São Paulo. Retorna `month`, `punches`, `today` e `server_time`.
- `today` inclui data de São Paulo, todas as batidas do dia, revisão, estado, próxima ação, total trabalhado e permissão para bater ponto.
- POST de batida aceita opcionalmente `{"expected_revision": 3, "expected_date": "2026-09-15"}`. A SPA sempre os envia. Tipo e horário são definidos exclusivamente pelo servidor. Retorno `201`: `punch`, `today` e `server_time`.
- DELETE aceita `?expected_revision=4` e retorna `204` sem corpo.
- Consultas mensais e respostas de criação são snapshots coerentes. A revisão cresce na criação e no desfazer, inclusive ao remover e recriar uma batida.

Erros usam `{"error": {"code": "...", "message": "..."}}`: `400` entrada inválida; `401` sessão; `403` batida alheia; `404` inexistente; `409` revisão/data desatualizada, jornada encerrada ou desfazer não permitido; `500` erro interno sem expor detalhes ao cliente. Os modelos completos constam no Swagger.

## Modelo de dados e autenticação

- `User`: identidade, e-mail único sem distinção de caixa, hash da senha, meta diária, revisão das batidas e data de cadastro.
- `Punch`: id, usuário, tipo, instante UTC e data de criação. Um usuário tem várias batidas.
- O JWT dura 24 horas; `sub`, `iat` e `exp` são obrigatórios. A API valida assinatura, validade e existência do usuário.
- Cada consulta filtra pelo usuário do token. Logout na SPA elimina o token e os dados em memória. Como o JWT é sem estado, logout local não revoga uma cópia já emitida; ela expira em até 24h. Revogação remota está fora do escopo.

## Regras da jornada

1. Entrada (`clock_in`).
2. Início do intervalo (`break_start`).
3. Retorno (`break_end`).
4. Saída (`clock_out`).

A leitura da sequência, a criação e o aumento da revisão ocorrem na mesma transação SQLite. Chamadas simultâneas não criam dois tipos iguais nem uma quinta batida. Revisão ou data antigas retornam `409`; a interface atualiza os dados e aguarda um novo clique.

Somente a última batida do **dia atual** pode ser desfeita em até cinco segundos do horário do servidor. A quarta batida segue a mesma regra; após o prazo, aquela batida não permite edição retroativa.

O tempo trabalhado soma entrada → intervalo e retorno → saída. Trechos abertos avançam até o instante atual apenas na jornada de hoje. Intervalo e tempo após a saída não contam. Os instantes são armazenados em UTC e agrupados por `America/Sao_Paulo`.

O MVP não modela turnos atravessando meia-noite. No dia seguinte, batidas antigas ficam intactas; o front-end apresenta **Jornada incompleta** para 1–3 registros, soma somente trechos fechados, identifica o total como parcial e não fornece saldo final. Não se cria uma saída fictícia. A nova jornada fica livre para começar.

A meta padrão é 8h, editável por usuário. É uma preferência atual usada também nas comparações do histórico; não há histórico de alterações de meta. O front-end destaca o excedente sem alterar os registros.

## Testes

```bash
pytest -q
```

Os **94 testes** cobrem autenticação, entradas inválidas, isolamento de contas/metas, sequência, janela de desfazer, concorrência entre conexões SQLite, revisões, meia-noite, migração, chave JWT e Swagger. Usam bancos isolados em memória ou diretórios temporários; não alteram `instance/ponto_plus.db`.

A configuração exige **100% de cobertura das instruções Python de `app/`**, atingida nesta rodada. Isso não equivale a cobertura de todos os cenários nem substitui QA visual/integrado. O front-end possui sua própria suíte.

## Problemas comuns

- **Não conecta:** confirme que a API está ativa e que `/api/health` responde `{"status":"ok"}`.
- **Porta ocupada:** identifique o processo; não encerre serviços do sistema indiscriminadamente. A SPA deste MVP usa a porta 5001 para evitar conflito com o Receptor AirPlay do macOS na porta 5000.
- **Sessão inválida depois de atualizar:** entre novamente. A conta e o histórico não foram removidos.
- **Chave rejeitada:** remova a configuração de exemplo ou defina uma chave própria válida. Sem configuração externa, a API cria a chave local automaticamente.
- **Jornada desatualizada:** outra aba mudou as batidas ou virou o dia. Confira a sequência atual antes de clicar novamente.
- **Permissão no banco:** mantenha `instance` gravável e faça uma cópia de segurança antes de qualquer intervenção manual.

## Demonstração e entrega

Vídeo e publicação no GitHub foram adiados pelo usuário. Roteiro conjunto de até quatro minutos:

1. Apresente o problema e o propósito do Ponto+.
2. Mostre no Swagger ao menos quatro rotas, incluindo POST, entradas, respostas e autorização.
3. Mostre a interface usando as oito operações: health na abertura, cadastro/login, perfil/meta, histórico, batida e desfazer.

Notificações e recuperação de senha da interface são demonstrações sem endpoints reais. O projeto não envia e-mails nem notificações.
