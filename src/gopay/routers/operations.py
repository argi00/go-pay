"""Les routes des opérations : transferts, transferts de la diaspora, retraits, paiements."""

from fastapi import APIRouter

from gopay.dependencies import Change, CleIdempotence, Idempotence, Service, WalletCourant
from gopay.schemas import (
    PaiementIn,
    RetraitIn,
    RetraitOut,
    TransactionOut,
    TransfertDiasporaIn,
    TransfertDiasporaOut,
    TransfertIn,
    TransfertOut,
)

router = APIRouter(prefix="/v1", tags=["Opérations"])


@router.post("/transferts", status_code=201)
def creer_transfert(
    data: TransfertIn, wallet: WalletCourant, service: Service, idem: Idempotence, cle: CleIdempotence
) -> TransfertOut:
    def action() -> TransfertOut:
        return TransfertOut.model_validate(service.transferer(wallet, data.beneficiaire_tel, data.montant))

    return TransfertOut.model_validate(idem.executer(f"transferts:{wallet.id}", cle, data, action))


@router.post("/transferts-diaspora", status_code=201)
def creer_transfert_diaspora(
    data: TransfertDiasporaIn,
    wallet: WalletCourant,
    service: Service,
    idem: Idempotence,
    cle: CleIdempotence,
    change: Change,
) -> TransfertDiasporaOut:
    def action() -> TransfertDiasporaOut:
        transfert, taux = service.transferer_depuis_diaspora(
            wallet, data.beneficiaire_tel, data.devise, data.montant_devise, change
        )
        return TransfertDiasporaOut(
            devise=data.devise,
            montant_devise=data.montant_devise,
            taux=taux,
            transfert=TransfertOut.model_validate(transfert),
        )

    return TransfertDiasporaOut.model_validate(idem.executer(f"diaspora:{wallet.id}", cle, data, action))


@router.post("/retraits", status_code=201)
def retirer(data: RetraitIn, service: Service) -> RetraitOut:
    transfert = service.retirer(data.code_retrait, data.beneficiaire_tel)
    return RetraitOut(transfert_id=transfert.id, montant=transfert.montant, statut="retire")


@router.post("/paiements", status_code=201)
def payer(
    data: PaiementIn, wallet: WalletCourant, service: Service, idem: Idempotence, cle: CleIdempotence
) -> TransactionOut:
    def action() -> TransactionOut:
        return TransactionOut.model_validate(service.payer(wallet, data.marchand_id, data.montant))

    return TransactionOut.model_validate(idem.executer(f"paiements:{wallet.id}", cle, data, action))
