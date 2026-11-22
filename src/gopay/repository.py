"""Le stockage des données. Aujourd'hui en mémoire ; demain PostgreSQL."""

import threading
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import date
from decimal import Decimal

from gopay.models import Transaction, Transfert, Wallet


class MemoireRepository:
    def __init__(self, latence: float = 0.0) -> None:
        self.wallets: dict[int, Wallet] = {}
        self.transferts: dict[int, Transfert] = {}
        self.transactions: dict[int, Transaction] = {}
        self.webhooks: dict[int, tuple[str, str]] = {}  # marchand_id → (url, secret)
        self._compteurs = {"wallet": 0, "transfert": 0, "transaction": 0}
        self._latence = latence  # simule le temps de réponse d'une vraie base de données
        self._verrous: dict[int, threading.Lock] = {}
        self._verrou_global = threading.Lock()

    def _prochain_id(self, nom: str) -> int:
        with self._verrou_global:
            self._compteurs[nom] += 1
            return self._compteurs[nom]

    # ----- Verrous (R10) -----
    @contextmanager
    def verrous(self, *wallet_ids: int) -> Iterator[None]:
        """Verrouille un ou plusieurs wallets, toujours dans le même ordre pour éviter l'interblocage."""
        with ExitStack() as pile:
            for wallet_id in sorted(set(wallet_ids)):
                with self._verrou_global:
                    verrou = self._verrous.setdefault(wallet_id, threading.Lock())
                pile.enter_context(verrou)
            yield

    def lire_solde(self, wallet: Wallet) -> Decimal:
        """Lit le solde comme le ferait une base de données : la réponse arrive quelques ms plus tard."""
        solde = wallet.solde
        time.sleep(self._latence)
        return solde

    # ----- Wallets -----
    def creer_wallet(self, nom: str, telephone: str, type_: str, region: str = "Dakar") -> Wallet:
        wallet = Wallet(id=self._prochain_id("wallet"), nom=nom, telephone=telephone, type=type_, region=region)
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

    def transactions_du_wallet(
        self,
        wallet_id: int,
        avant: int | None,
        limite: int,
        type_: str | None = None,
        du: date | None = None,
        au: date | None = None,
    ) -> list[Transaction]:
        """Les transactions du wallet, de la plus récente à la plus ancienne, filtrées."""
        resultat = []
        for t in sorted(self.transactions.values(), key=lambda t: t.id, reverse=True):
            jour = t.cree_le.date()
            if t.wallet_id != wallet_id:
                continue
            if avant is not None and t.id >= avant:
                continue
            if type_ is not None and t.type != type_:
                continue
            if du is not None and jour < du:
                continue
            if au is not None and jour > au:
                continue
            resultat.append(t)
        return resultat[:limite]
