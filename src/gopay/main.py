"""Point d'entrée : crée l'application."""
from fastapi import FastAPI

app = FastAPI(title="Go Pay API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"statut": "ok"}

