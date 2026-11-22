"""Le stockage des données. Aujourd'hui en mémoire ; demain PostgreSQL."""

from decimal import Decimal

from gopay.models import Transaction, Transfert, Wallet


class MemoireRepository:
    def __init__(self) -> None:
        self.wallets: dict[int, Wallet] = {}
        self.transferts: dict[int, Transfert] = {}
        self.transactions: dict[int, Transaction] = {}
        self._compteurs = {"wallet": 0, "transfert": 0, "transaction": 0}

    def _prochain_id(self, nom: str) -> int:
        self._compteurs[nom] += 1
        return self._compteurs[nom]

    # ----- Wallets -----
    def creer_wallet(self, nom: str, telephone: str, type_: str) -> Wallet:
        wallet = Wallet(id=self._prochain_id("wallet"), nom=nom, telephone=telephone, type=type_)
        self.wallets[wallet.id] = wallet
        return wallet

    def wallet(self, wallet_id: int) -> Wallet | None:
        return self.wallets.get(wallet_id)

    def wallet_par_telephone(self, telephone: str) -> Wallet | None:
        for wallet in self.wallets.values():
            if wallet.telephone == telephone:
                return wallet
        return None

    # ----- Transferts -----
    def creer_transfert(
        self, expediteur_id: int, beneficiaire_tel: str, montant: Decimal, frais: Decimal, code: str
    ) -> Transfert:
        transfert = Transfert(
            id=self._prochain_id("transfert"),
            expediteur_id=expediteur_id,
            beneficiaire_tel=beneficiaire_tel,
            montant=montant,
            frais=frais,
            code_retrait=code,
        )
        self.transferts[transfert.id] = transfert
        return transfert

    def transfert_par_code(self, code: str) -> Transfert | None:
        for transfert in self.transferts.values():
            if transfert.code_retrait == code:
                return transfert
        return None

    # ----- Transactions -----
    def ajouter_transaction(
        self, wallet: Wallet, type_: str, montant: Decimal, frais: Decimal, reference: str | None = None
    ) -> Transaction:
        transaction = Transaction(
            id=self._prochain_id("transaction"),
            wallet_id=wallet.id,
            type=type_,
            montant=montant,
            frais=frais,
            solde_apres=wallet.solde,
            reference=reference,
        )
        self.transactions[transaction.id] = transaction
        return transaction

    def transactions_du_wallet(self, wallet_id: int, avant: int | None, limite: int) -> list[Transaction]:
        """Les transactions du wallet, de la plus récente à la plus ancienne."""
        resultat = [
            t
            for t in sorted(self.transactions.values(), key=lambda t: t.id, reverse=True)
            if t.wallet_id == wallet_id and (avant is None or t.id < avant)
        ]
        return resultat[:limite]
