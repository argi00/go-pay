"""Les dépendances injectées dans les routes avec Depends."""

from typing import Annotated

from fastapi import Depends, Header

from gopay.models import Wallet
from gopay.repository import MemoireRepository
from gopay.services import GoPayService

_repo = MemoireRepository()  # une seule « base » en mémoire pour toute l'application


def get_repository() -> MemoireRepository:
    return _repo


def get_service(repo: Annotated[MemoireRepository, Depends(get_repository)]) -> GoPayService:
    return GoPayService(repo)


Service = Annotated[GoPayService, Depends(get_service)]


def wallet_courant(service: Service, x_wallet_id: Annotated[int, Header()]) -> Wallet:
    """Le wallet de l'utilisateur, lu dans l'en-tête X-Wallet-Id (remplacé par un jeton JWT plus tard)."""
    return service.lire_wallet(x_wallet_id)


WalletCourant = Annotated[Wallet, Depends(wallet_courant)]
