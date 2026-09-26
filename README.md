# Ponto+ API

API REST do Ponto+, um sistema pessoal para registrar e acompanhar a jornada de trabalho. O projeto oferece cadastro, login, perfil, registro de ponto e histórico mensal.

## Requisitos

- Python 3.11 ou superior
- `pip`

## Instalação

Na pasta do projeto, crie e ative um ambiente virtual.

### macOS e Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

Não é necessária configuração adicional. Na primeira execução, a aplicação cria automaticamente o banco de dados e uma chave local de autenticação.

## Execução

Com o ambiente virtual ativo, execute:

```bash
python run.py
```

A aplicação ficará disponível em:

- API: `http://127.0.0.1:5001`
- Documentação Swagger: `http://127.0.0.1:5001/apidocs`