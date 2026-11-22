"""Les routes /v1/wallets : ouvrir, consulter, déposer, historique."""

from typing import Annotated

from fastapi import APIRouter, Query

from gopay.dependencies import Service
from gopay.schemas import DepotIn, PageTransactions, TransactionOut, WalletIn, WalletOut

router = APIRouter(prefix="/v1/wallets", tags=["Wallets"])


@router.post("", status_code=201)
def ouvrir_wallet(data: WalletIn, service: Service) -> WalletOut:
    wallet = service.ouvrir_wallet(data.nom, data.telephone, data.type)
    return WalletOut.model_validate(wallet)


@router.get("/{wallet_id}")
def lire_wallet(wallet_id: int, service: Service) -> WalletOut:
    return WalletOut.model_validate(service.lire_wallet(wallet_id))


@router.post("/{wallet_id}/depots", status_code=201)
def deposer(wallet_id: int, data: DepotIn, service: Service) -> TransactionOut:
    return TransactionOut.model_validate(service.deposer(wallet_id, data.montant))


@router.get("/{wallet_id}/transactions")
def historique(
    wallet_id: int,
    service: Service,
    cursor: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageTransactions:
    items, suivant = service.historique(wallet_id, cursor, limit)
    return PageTransactions(items=[TransactionOut.model_validate(t) for t in items], next_cursor=suivant)
