# Ponto+ API

API REST do Ponto+, um sistema pessoal para registrar entrada, intervalo, retorno e saída. O servidor controla a ordem das batidas e usa seu próprio relógio para impedir registros inconsistentes.

## Funcionalidades

- cadastro e login com senha protegida por hash e token JWT de 24 horas;
- consulta e alteração do nome do perfil autenticado;
- sequência diária obrigatória de quatro batidas;
- histórico mensal isolado por usuário;
- cálculo do tempo trabalhado sem contar o intervalo;
- exclusão somente da última batida, durante cinco segundos;
- documentação interativa com Swagger;
- respostas de erro padronizadas em português.

## Tecnologias

- Python e Flask para a API;
- Flask-SQLAlchemy e SQLite para persistência;
- PyJWT para autenticação sem estado no servidor;
- Flasgger para documentação Swagger/OpenAPI;
- Pytest para testes automatizados.

## Estrutura

```text
app/
├── routes/              # Entrada HTTP separada por domínio
├── services/            # Regras da jornada
├── __init__.py          # Fábrica e configuração da aplicação
├── auth.py              # Emissão e validação de JWT
├── errors.py            # Contrato uniforme de erros
├── extensions.py        # Instância do banco
└── models.py            # Tabelas User e Punch
tests/                   # Testes de autenticação, perfil e batidas
run.py                   # Inicialização local
```

## Instalação

Requer Python 3.11 ou superior.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Em produção, defina uma chave segura:

```bash
export JWT_SECRET_KEY="troque-por-uma-chave-longa-e-aleatoria"
```

## Execução

```bash
python run.py
```

- API: `http://127.0.0.1:5000`
- Swagger: `http://127.0.0.1:5000/apidocs`
- Banco local: `instance/ponto_plus.db`

## Rotas

| Método | Rota | Uso |
|---|---|---|
| GET | `/api/health` | Confere a disponibilidade da API |
| POST | `/api/auth/register` | Cadastra e inicia a sessão |
| POST | `/api/auth/login` | Autentica e devolve um JWT |
| GET | `/api/profile` | Consulta o perfil autenticado |
| PATCH | `/api/profile` | Atualiza o nome |
| GET | `/api/punches?month=YYYY-MM` | Lista o histórico e o estado atual |
| POST | `/api/punches` | Registra a próxima batida |
| DELETE | `/api/punches/{id}` | Desfaz a última batida em até 5 segundos |

As rotas protegidas recebem `Authorization: Bearer <token>`.

## Testes

```bash
pytest -q
```

Os 27 testes cobrem cadastro, validações, duplicidade de e-mail, login, tokens inválidos e expirados, perfil, isolamento entre usuários, sequência das quatro batidas, bloqueio da quinta, janela de desfazer e respostas globais de erro. A configuração exige 100% de cobertura de linhas e faz a suíte falhar se esse índice regredir.

## Demonstração no vídeo

1. Explique que o Ponto+ registra uma jornada sem planilhas.
2. Abra o Swagger e cadastre um usuário.
3. Autorize com o JWT e mostre perfil, histórico e uma batida.
4. Abra o front-end e repita o fluxo pela interface, indicando as rotas chamadas.
