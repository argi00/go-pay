"""Les règles métier de Go Pay (R1 à R11). Aucun code HTTP ici."""

import secrets
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from gopay.change import ClientChange
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
MONTANT_MINIMUM = Decimal("100")  # R1
UN_FRANC = Decimal("1")
ARRONDI = ROUND_HALF_UP  # R8 : au franc le plus proche, une moitié vers le haut


def arrondir_au_franc(montant: Decimal) -> Decimal:
    """R8 : 50,50 donne 51 ; 50,49 donne 50."""
    return montant.quantize(UN_FRANC, rounding=ARRONDI)


def calculer_frais(montant: Decimal) -> Decimal:
    """R2 : 1 % du montant, arrondi au franc (R8), avec un minimum de 50 FCFA."""
    return max(arrondir_au_franc(montant * TAUX_FRAIS), FRAIS_MINIMUM)


class GoPayService:
    def __init__(self, repo: MemoireRepository) -> None:
        self.repo = repo

    # ----- Wallets -----
    def ouvrir_wallet(self, nom: str, telephone: str, type_: str, region: str = "Dakar") -> Wallet:
        if self.repo.wallet_par_telephone(telephone) is not None:
            raise TelephoneDejaUtilise(f"Le numéro {telephone} a déjà un wallet.")
        return self.repo.creer_wallet(nom, telephone, type_, region)


    def lire_wallet(self, wallet_id: int) -> Wallet:
        wallet = self.repo.wallet(wallet_id)
        if wallet is None:
            raise RessourceIntrouvable(f"Aucun wallet avec l'identifiant {wallet_id}.")
        return wallet

    def deposer(self, wallet_id: int, montant: Decimal) -> Transaction:
        wallet = self.lire_wallet(wallet_id)
        with self.repo.verrous(wallet.id):  # R10
            wallet.solde = self.repo.lire_solde(wallet) + montant
            return self.repo.ajouter_transaction(wallet, "depot", montant, Decimal("0"))

    # ----- Transferts (R1 à R5, R10) -----
    def transferer(self, expediteur: Wallet, beneficiaire_tel: str, montant: Decimal) -> Transfert:
        frais = calculer_frais(montant)  # R2
        total = montant + frais  # R3
        with self.repo.verrous(expediteur.id):  # R10 : un seul transfert à la fois par wallet
            solde = self.repo.lire_solde(expediteur)
            if solde < total:  # R4
                raise SoldeInsuffisant(
                    f"Solde de {solde} FCFA ; montant + frais : {total} FCFA.", solde=solde, requis=total
                )
            expediteur.solde = solde - total  # R3
            code = self._nouveau_code()  # R5
            transfert = self.repo.creer_transfert(expediteur.id, beneficiaire_tel, montant, frais, code)
            self.repo.ajouter_transaction(
                expediteur, "transfert", montant, frais, reference=f"transfert:{transfert.id}"
            )
            return transfert

    def _nouveau_code(self) -> str:
        """R5 : un code à 6 chiffres, tiré au hasard de façon sûre, jamais en double."""
        while True:
            code = f"{secrets.randbelow(1_000_000):06d}"
            if self.repo.transfert_par_code(code) is None:
                return code

    # ----- Transferts de la diaspora (R11) -----
    def transferer_depuis_diaspora(
        self, expediteur: Wallet, beneficiaire_tel: str, devise: str, montant_devise: Decimal, change: ClientChange
    ) -> tuple[Transfert, Decimal]:
        """Le paiement en devise est encaissé par un partenaire : aucun wallet n'est débité."""
        taux = change.taux(devise)
        montant = arrondir_au_franc(montant_devise * taux)  # R8
        if montant < MONTANT_MINIMUM:  # R1
            raise OperationInterdite(f"{montant_devise} {devise} font {montant} FCFA, sous le minimum de 100 FCFA.")
        frais = calculer_frais(montant)  # R2
        transfert = self.repo.creer_transfert(expediteur.id, beneficiaire_tel, montant, frais, self._nouveau_code())
        self.repo.ajouter_transaction(
            expediteur, "transfert_diaspora", montant, frais, reference=f"transfert:{transfert.id}"
        )
        return transfert, taux

    # ----- Retraits (R6) -----
    def retirer(self, code: str, beneficiaire_tel: str) -> Transfert:
        transfert = self.repo.transfert_par_code(code)
        if transfert is None or transfert.beneficiaire_tel != beneficiaire_tel:
            raise RessourceIntrouvable("Code de retrait inconnu pour ce numéro.")
        with self.repo.verrous(transfert.expediteur_id):  # deux agents ne paient pas le même code
            if transfert.statut == "retire":  # R6
                raise CodeDejaUtilise("Ce code de retrait a déjà été utilisé.")
            transfert.statut = "retire"
        return transfert

    # ----- Paiements marchands (R7, R10) -----
    def payer(self, client: Wallet, marchand_id: int, montant: Decimal) -> Transaction:
        marchand = self.repo.wallet(marchand_id)
        if marchand is None or marchand.type != "marchand":
            raise RessourceIntrouvable(f"Aucun marchand affilié avec l'identifiant {marchand_id}.")
        if marchand.id == client.id:
            raise OperationInterdite("Un marchand ne peut pas se payer lui-même.")
        with self.repo.verrous(client.id, marchand.id):  # R10 : les deux wallets changent
            solde = self.repo.lire_solde(client)
            if solde < montant:
                raise SoldeInsuffisant(
                    f"Solde de {solde} FCFA ; montant : {montant} FCFA.", solde=solde, requis=montant
                )
            client.solde = solde - montant
            marchand.solde = self.repo.lire_solde(marchand) + montant
            self.repo.ajouter_transaction(
                marchand, "paiement_recu", montant, Decimal("0"), reference=f"client:{client.id}"
            )
            return self.repo.ajouter_transaction(
                client, "paiement_envoye", montant, Decimal("0"), reference=f"marchand:{marchand.id}"
            )

    # ----- Historique -----
    def historique(
        self,
        wallet_id: int,
        cursor: int | None,
        limit: int,
        type_: str | None = None,
        du: date | None = None,
        au: date | None = None,
    ) -> tuple[list[Transaction], int | None]:
        self.lire_wallet(wallet_id)
        if du is not None and au is not None and du > au:
            raise OperationInterdite("La date « du » doit précéder la date « au ».")
        items = self.repo.transactions_du_wallet(wallet_id, cursor, limit + 1, type_, du, au)
        if len(items) > limit:  # il reste au moins une page
            return items[:limit], items[limit - 1].id
        return items, None
