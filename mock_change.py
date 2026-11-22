"""Service de change SIMULÉ, lent et peu fiable, pour tester la résilience de Go Pay.

Lancement : uv run fastapi dev mock_change.py --port 8001
"""

import os
import random
import time
from decimal import Decimal

from fastapi import FastAPI, HTTPException

TAUX = {"EUR": Decimal("655.957"), "USD": Decimal("575.50")}  # EUR/XOF est une parité fixe
PANNE = float(os.environ.get("CHANGE_PANNE", "0.15"))  # part des réponses 503
LENTEUR = float(os.environ.get("CHANGE_LENTEUR", "0.15"))  # part des réponses en 3 secondes

app = FastAPI(title="Service de change simulé")


@app.get("/taux")
def taux(de: str, vers: str = "XOF") -> dict[str, str]:
    tirage = random.random()
    if tirage < PANNE:
        raise HTTPException(status_code=503, detail="Service surchargé", headers={"Retry-After": "1"})
    if tirage < PANNE + LENTEUR:
        time.sleep(3)  # plus long que le délai de Go Pay (2 s)
    if vers != "XOF" or de not in TAUX:
        raise HTTPException(status_code=404, detail=f"Paire {de}/{vers} inconnue")
    valeur = TAUX[de]
    if de == "USD":
        valeur += Decimal(random.randint(-200, 200)) / 100  # l'USD varie un peu
    return {"de": de, "vers": vers, "taux": str(valeur)}
