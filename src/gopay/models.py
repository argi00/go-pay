"""Les objets métier de Go Pay, tels qu'ils sont stockés en interne."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal


def maintenant() -> datetime:
    return datetime.now(UTC)


@dataclass
class Wallet:
    id: int
    nom: str
    telephone: str
    type: str  # "client" ou "marchand"
    solde: Decimal = Decimal("0")
    cree_le: datetime = field(default_factory=maintenant)


@dataclass
class Transfert:
    id: int
    expediteur_id: int
    beneficiaire_tel: str
    montant: Decimal
    frais: Decimal
    code_retrait: str
    statut: str = "en_attente"  # "en_attente" puis "retire"
    cree_le: datetime = field(default_factory=maintenant)


@dataclass
class Transaction:
    id: int
    wallet_id: int
    type: str  # "depot", "transfert", "paiement_envoye", "paiement_recu"
    montant: Decimal
    frais: Decimal
    solde_apres: Decimal
    reference: str | None = None
    cree_le: datetime = field(default_factory=maintenant)
