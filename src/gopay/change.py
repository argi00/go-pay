"""Le client du service de change : délais explicites et nouvelles tentatives."""

from decimal import Decimal

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from gopay.errors import ServiceIndisponible

# Les erreurs passagères : une nouvelle tentative a des chances de réussir
PASSAGERES = (httpx.ConnectError, httpx.TimeoutException)


class ClientChange:
    def __init__(self, base_url: str, delai: float = 2.0) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=httpx.Timeout(delai, connect=1.0))

    @retry(
        retry=retry_if_exception_type(PASSAGERES),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(multiplier=0.2, max=2),
        reraise=True,
    )
    def _demander_taux(self, devise: str) -> Decimal:
        reponse = self._http.get("/taux", params={"de": devise, "vers": "XOF"})
        reponse.raise_for_status()
        return Decimal(reponse.json()["taux"])  # jamais float(...)

    def taux(self, devise: str) -> Decimal:
        """Le taux devise → XOF, ou une erreur 503 si le service reste injoignable."""
        try:
            return self._demander_taux(devise)
        except httpx.HTTPError as erreur:
            raise ServiceIndisponible(f"Service de change indisponible ({type(erreur).__name__}).") from erreur

    def fermer(self) -> None:
        self._http.close()
