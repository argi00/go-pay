"""Marchand de DÉMONSTRATION : reçoit et vérifie les webhooks de Go Pay.

Lancement : MARCHAND_SECRET=<le secret reçu> uv run fastapi dev marchand_demo.py --port 8002
"""

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from gopay.webhooks import verifier

SECRET = os.environ.get("MARCHAND_SECRET", "")
deja_traites: set[str] = set()  # les event_id déjà reçus
recus: list[dict[str, Any]] = []

app = FastAPI(title="Boutique Ndiaye (démonstration)")


@app.post("/hooks/gopay")
async def recevoir(request: Request) -> dict[str, str]:
    corps = await request.body()  # les octets bruts, tels qu'ils ont été signés
    if not verifier(SECRET, corps, request.headers.get("GoPay-Signature", "")):
        raise HTTPException(status_code=401, detail="Signature invalide ou message trop ancien")
    evenement = json.loads(corps)
    if evenement["event_id"] in deja_traites:
        return {"statut": "deja_traite"}  # doublon : on répond 200 sans retraiter
    deja_traites.add(evenement["event_id"])
    recus.append(evenement)
    print(f"Paiement reçu : {evenement['montant']} FCFA du client {evenement['client_id']}")
    return {"statut": "recu"}


@app.get("/recus")
def lister() -> list[dict[str, Any]]:
    return recus
