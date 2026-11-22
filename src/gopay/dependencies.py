"""Les dépendances injectées dans les routes avec Depends."""

import os
from typing import Annotated

from fastapi import Depends, Header

from gopay.change import ClientChange
from gopay.fraude.client import ClientFraude 
from gopay.idempotence import StockIdempotence
from gopay.models import Wallet
from gopay.repository import MemoireRepository
from gopay.services import AntiFraude, GoPayService

_repo = MemoireRepository(latence=0.005)  # 5 ms, comme une vraie base de données
_idempotence = StockIdempotence()
_change = ClientChange(os.environ.get("GOPAY_CHANGE_URL", "http://127.0.0.1:8001"))
_antifraude = ClientFraude(os.environ.get("GOPAY_FRAUDE_ADRESSE", "localhost:50051"))

def get_repository() -> MemoireRepository:
    return _repo


def get_antifraude() -> AntiFraude:
    return _antifraude


def get_service(
    repo: Annotated[MemoireRepository, Depends(get_repository)],
    antifraude: Annotated[AntiFraude, Depends(get_antifraude)],
) -> GoPayService:
    return GoPayService(repo, antifraude)


def get_idempotence() -> StockIdempotence:
    return _idempotence


def get_change() -> ClientChange:
    return _change


Service = Annotated[GoPayService, Depends(get_service)]
Idempotence = Annotated[StockIdempotence, Depends(get_idempotence)]
Change = Annotated[ClientChange, Depends(get_change)]
CleIdempotence = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)]


def wallet_courant(service: Service, x_wallet_id: Annotated[int, Header()]) -> Wallet:
    """Le wallet de l'utilisateur, lu dans l'en-tête X-Wallet-Id (remplacé par un jeton JWT plus tard)."""
    return service.lire_wallet(x_wallet_id)


WalletCourant = Annotated[Wallet, Depends(wallet_courant)]
