#!/usr/bin/env python3
# =============================================================
#  SoundBridge – FastAPI Backend
#  Path: api/main.py
#  Main application entry point
#
#  Run
#  ---
#  uvicorn api.main:app --reload --port 8000
#  – or –
#  python api/main.py
#
#  Endpoints
#  ---------
#  POST /morse          Accept event or legacy word payload
#  GET  /morse          List all stored messages
#  GET  /morse/{id}     Retrieve a single message
#  GET  /health         Liveness probe
#
#  Stop with Ctrl-C.
# =============================================================
"""
Ponto de entrada da aplicação SoundBridge.

Este módulo inicializa a aplicação FastAPI, configura o sistema de logging,
regista o router de endpoints Morse e arranca o servidor de desenvolvimento.
Responsável por orquestrar o carregamento de variáveis de ambiente, a criação
da instância principal da aplicação e a ligação entre as camadas de configuração,
base de dados e rotas HTTP.

Para executar em desenvolvimento::

    uvicorn api.main:app --reload --port 8000

Ou diretamente::

    python api/main.py
"""

from fastapi import FastAPI

# Carrega as variáveis de ambiente a partir do ficheiro .env antes de qualquer
# outro import que possa depender delas (ex: DatabaseConfig lê DB_HOST, DB_PORT, etc.)
from dotenv import load_dotenv
load_dotenv()

from api.core.config import setup_logging, AppConfig
from api.db.connection import lifespan
from api.routes.morse import router as morse_router


# Inicializa o sistema de logging antes de criar a instância FastAPI,
# garantindo que todos os eventos de startup são capturados nos logs.
setup_logging()


# Cria a instância principal da aplicação FastAPI com os metadados definidos
# em AppConfig e associa o lifespan para gerir o ciclo de vida do pool de conexões.
app = FastAPI(
    title=AppConfig.TITLE,
    description=AppConfig.DESCRIPTION,
    version=AppConfig.VERSION,
    lifespan=lifespan,
)


# Regista o router de Morse com a tag "morse", agrupando os endpoints
# na documentação automática gerada pelo FastAPI (Swagger UI / ReDoc).
app.include_router(morse_router, tags=["morse"])


# =============================================================
#  Development runner
# =============================================================

if __name__ == "__main__":
    # Bloco de execução direta: arranca o servidor Uvicorn em modo de desenvolvimento
    # com hot-reload ativo. Não deve ser usado em produção — usar o comando uvicorn
    # diretamente ou um gestor de processos como Gunicorn.
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)