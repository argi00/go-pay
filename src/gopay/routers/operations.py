"""Les routes des opérations : transferts, retraits, paiements."""

from fastapi import APIRouter

from gopay.dependencies import Service, WalletCourant
from gopay.schemas import PaiementIn, RetraitIn, RetraitOut, TransactionOut, TransfertIn, TransfertOut

router = APIRouter(prefix="/v1", tags=["Opérations"])


@router.post("/transferts", status_code=201)
def creer_transfert(data: TransfertIn, wallet: WalletCourant, service: Service) -> TransfertOut:
    transfert = service.transferer(wallet, data.beneficiaire_tel, data.montant)
    return TransfertOut.model_validate(transfert)


@router.post("/retraits", status_code=201)
def retirer(data: RetraitIn, service: Service) -> RetraitOut:
    transfert = service.retirer(data.code_retrait, data.beneficiaire_tel)
    return RetraitOut(transfert_id=transfert.id, montant=transfert.montant, statut="retire")


@router.post("/paiements", status_code=201)
def payer(data: PaiementIn, wallet: WalletCourant, service: Service) -> TransactionOut:
    return TransactionOut.model_validate(service.payer(wallet, data.marchand_id, data.montant))
