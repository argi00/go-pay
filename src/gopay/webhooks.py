"""Partie C : webhooks signés en HMAC-SHA256 (R15)."""

import hashlib
import hmac
import json
import time
from typing import Any

import httpx


def signer(secret: str, corps: bytes, horodatage: int) -> str:
    """La signature porte sur l'horodatage ET le corps : on ne peut changer ni l'un ni l'autre."""
    message = f"{horodatage}.".encode() + corps
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verifier(secret: str, corps: bytes, entete: str, tolerance: int = 300) -> bool:
    """Côté marchand : signature correcte ET message de moins de 5 minutes."""
    try:
        parties = dict(p.split("=", 1) for p in entete.split(","))
        horodatage = int(parties["t"])
        signature = parties["v1"]
    except (KeyError, ValueError):
        return False  # en-tête absent ou mal formé
    if abs(time.time() - horodatage) > tolerance:
        return False  # trop ancien : rejeu probable
    attendu = signer(secret, corps, horodatage)
    return hmac.compare_digest(attendu, signature)  # comparaison en temps constant


class EnvoyeurWebhooks:
    def __init__(self, delai: float = 5.0, tentatives: int = 3) -> None:
        self._http = httpx.Client(timeout=delai)
        self._tentatives = tentatives

    def envoyer(self, url: str, secret: str, evenement: dict[str, Any]) -> bool:
        """POST signé ; renvoie True dès qu'un essai reçoit une réponse 2xx."""
        corps = json.dumps(evenement).encode()
        for essai in range(self._tentatives):
            horodatage = int(time.time())
            entetes = {
                "Content-Type": "application/json",
                "GoPay-Signature": f"t={horodatage},v1={signer(secret, corps, horodatage)}",
            }
            try:
                if self._http.post(url, content=corps, headers=entetes).is_success:
                    return True
            except httpx.HTTPError:
                pass  # marchand injoignable : on réessaie
            time.sleep(0.5 * 2**essai)  # 0,5 s, puis 1 s, puis 2 s
        return False
