"""Les routes des opérations : transferts, transferts de la diaspora, retraits, paiements."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks

from gopay.dependencies import Change, CleIdempotence, Envoyeur, Idempotence, Service, WalletCourant
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
from gopay.temps_reel import agents

router = APIRouter(prefix="/v1", tags=["Opérations"])


@router.post("/transferts", status_code=201)
def creer_transfert(
    data: TransfertIn,
    wallet: WalletCourant,
    service: Service,
    idem: Idempotence,
    cle: CleIdempotence,
    taches: BackgroundTasks,
) -> TransfertOut:
    def action() -> TransfertOut:
        transfert = service.transferer(wallet, data.beneficiaire_tel, data.montant)
        alerte = {"type": "transfert", "transfert_id": transfert.id, "montant": str(transfert.montant)}
        taches.add_task(agents.diffuser, alerte)  # R14 : jamais le code de retrait
        return TransfertOut.model_validate(transfert)

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
    data: PaiementIn,
    wallet: WalletCourant,
    service: Service,
    idem: Idempotence,
    cle: CleIdempotence,
    taches: BackgroundTasks,
    envoyeur: Envoyeur,
) -> TransactionOut:
    def action() -> TransactionOut:
        transaction = service.payer(wallet, data.marchand_id, data.montant)
        webhook = service.repo.webhooks.get(data.marchand_id)
        if webhook is not None:  # R15 : prévenir le marchand, après la réponse
            url, secret = webhook
            evenement = {
                "event_id": f"evt_{uuid.uuid4().hex[:12]}",
                "type": "paiement.recu",
                "montant": str(data.montant),
                "marchand_id": data.marchand_id,
                "client_id": wallet.id,
                "cree_le": datetime.now(UTC).isoformat(),
            }
            taches.add_task(envoyeur.envoyer, url, secret, evenement)
        return TransactionOut.model_validate(transaction)

    return TransactionOut.model_validate(idem.executer(f"paiements:{wallet.id}", cle, data, action))
