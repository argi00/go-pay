"""Point d'entrée : crée l'application et branche les routes."""

from fastapi import FastAPI

from gopay.errors import installer_gestionnaires
from gopay.graphql_api import graphql_router
from gopay.routers import operations, wallets

app = FastAPI(
    title="Go Pay API",
    version="1.0.0",
    description="API de transfert d'argent du wallet vers le cash (TD1, ISM Dakar).",
)

installer_gestionnaires(app)
app.include_router(wallets.router)
app.include_router(operations.router)
app.include_router(graphql_router, prefix="/graphql")


@app.get("/health", tags=["Supervision"])
def health() -> dict[str, str]:
    return {"statut": "ok"}
