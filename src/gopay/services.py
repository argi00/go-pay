"""Les règles métier de Go Pay (R1 à R7). Aucun code HTTP ici."""

import secrets
from decimal import ROUND_HALF_UP, Decimal

from gopay.errors import (
    CodeDejaUtilise,
    OperationInterdite,
    RessourceIntrouvable,
    SoldeInsuffisant,
    TelephoneDejaUtilise,
)
from gopay.models import Transaction, Transfert, Wallet
from gopay.repository import MemoireRepository

TAUX_FRAIS = Decimal("0.01")  # R2 : 1 %
FRAIS_MINIMUM = Decimal("50")  # R2 : 50 FCFA minimum


def calculer_frais(montant: Decimal) -> Decimal:
    """R2 : 1 % du montant, arrondi au franc, avec un minimum de 50 FCFA."""
    frais = (montant * TAUX_FRAIS).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(frais, FRAIS_MINIMUM)


class GoPayService:
    def __init__(self, repo: MemoireRepository) -> None:
        self.repo = repo

    # ----- Wallets -----
    def ouvrir_wallet(self, nom: str, telephone: str, type_: str) -> Wallet:
        if self.repo.wallet_par_telephone(telephone) is not None:
            raise TelephoneDejaUtilise(f"Le numéro {telephone} a déjà un wallet.")
        return self.repo.creer_wallet(nom, telephone, type_)

    def lire_wallet(self, wallet_id: int) -> Wallet:
        wallet = self.repo.wallet(wallet_id)
        if wallet is None:
            raise RessourceIntrouvable(f"Aucun wallet avec l'identifiant {wallet_id}.")
        return wallet

    def deposer(self, wallet_id: int, montant: Decimal) -> Transaction:
        wallet = self.lire_wallet(wallet_id)
        wallet.solde += montant
        return self.repo.ajouter_transaction(wallet, "depot", montant, Decimal("0"))

    # ----- Transferts (R1 à R5) -----
    def transferer(self, expediteur: Wallet, beneficiaire_tel: str, montant: Decimal) -> Transfert:
        # R1 est déjà garantie par le schéma (montant >= 100)
        frais = calculer_frais(montant)  # R2
        total = montant + frais  # R3
        if expediteur.solde < total:  # R4
            raise SoldeInsuffisant(
                f"Solde de {expediteur.solde} FCFA ; montant + frais : {total} FCFA.",
                solde=expediteur.solde,
                requis=total,
            )
        code = self._nouveau_code()  # R5
        expediteur.solde -= total  # R3
        transfert = self.repo.creer_transfert(expediteur.id, beneficiaire_tel, montant, frais, code)
        self.repo.ajouter_transaction(expediteur, "transfert", montant, frais, reference=f"transfert:{transfert.id}")
        return transfert

    def _nouveau_code(self) -> str:
        """R5 : un code à 6 chiffres, tiré au hasard de façon sûre, jamais en double."""
        while True:
            code = f"{secrets.randbelow(1_000_000):06d}"
            if self.repo.transfert_par_code(code) is None:
                return code

    # ----- Retraits (R6) -----
    def retirer(self, code: str, beneficiaire_tel: str) -> Transfert:
        transfert = self.repo.transfert_par_code(code)
        if transfert is None or transfert.beneficiaire_tel != beneficiaire_tel:
            raise RessourceIntrouvable("Code de retrait inconnu pour ce numéro.")
        if transfert.statut == "retire":  # R6
            raise CodeDejaUtilise("Ce code de retrait a déjà été utilisé.")
        transfert.statut = "retire"
        return transfert

    # ----- Paiements marchands (R7) -----
    def payer(self, client: Wallet, marchand_id: int, montant: Decimal) -> Transaction:
        marchand = self.repo.wallet(marchand_id)
        if marchand is None or marchand.type != "marchand":
            raise RessourceIntrouvable(f"Aucun marchand affilié avec l'identifiant {marchand_id}.")
        if marchand.id == client.id:
            raise OperationInterdite("Un marchand ne peut pas se payer lui-même.")
        if client.solde < montant:
            raise SoldeInsuffisant(
                f"Solde de {client.solde} FCFA ; montant : {montant} FCFA.", solde=client.solde, requis=montant
            )
        client.solde -= montant
        marchand.solde += montant
        self.repo.ajouter_transaction(marchand, "paiement_recu", montant, Decimal("0"), reference=f"client:{client.id}")
        return self.repo.ajouter_transaction(
            client, "paiement_envoye", montant, Decimal("0"), reference=f"marchand:{marchand.id}"
        )

    # ----- Historique -----
    def historique(self, wallet_id: int, cursor: int | None, limit: int) -> tuple[list[Transaction], int | None]:
        self.lire_wallet(wallet_id)
        items = self.repo.transactions_du_wallet(wallet_id, avant=cursor, limite=limit + 1)
        if len(items) > limit:  # il reste au moins une page
            return items[:limit], items[limit - 1].id
        return items, None
