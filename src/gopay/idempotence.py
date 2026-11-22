"""R9 : rejouer une requête avec la même Idempotency-Key ne la traite qu'une fois."""

import hashlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from gopay.errors import CleDejaUtilisee, TraitementEnCours


@dataclass
class Entree:
    empreinte: str
    reponse: dict[str, Any] | None = None  # None : traitement en cours


class StockIdempotence:
    def __init__(self) -> None:
        self._entrees: dict[str, Entree] = {}
        self._verrou = threading.Lock()

    def executer(self, portee: str, cle: str, donnees: BaseModel, action: Callable[[], BaseModel]) -> dict[str, Any]:
        """Exécute `action` une seule fois par clé ; renvoie la réponse (stockée ou nouvelle) en JSON."""
        cle_complete = f"{portee}:{cle}"
        empreinte = hashlib.sha256(donnees.model_dump_json().encode()).hexdigest()

        with self._verrou:  # vérifier puis réserver, en une seule opération
            deja = self._entrees.get(cle_complete)
            if deja is not None:
                if deja.empreinte != empreinte:
                    raise CleDejaUtilisee("Cette Idempotency-Key a déjà servi pour une autre requête.")
                if deja.reponse is None:
                    raise TraitementEnCours("Une requête avec cette Idempotency-Key est en cours.")
                return deja.reponse  # requête rejouée : aucun nouveau traitement
            self._entrees[cle_complete] = Entree(empreinte)

        try:
            reponse = action().model_dump(mode="json")
        except Exception:
            with self._verrou:
                del self._entrees[cle_complete]  # échec : le client pourra réessayer avec la même clé
            raise
        with self._verrou:
            self._entrees[cle_complete].reponse = reponse
        return reponse
