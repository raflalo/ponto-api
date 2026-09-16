"""Ponto de entrada local da API Ponto+."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
