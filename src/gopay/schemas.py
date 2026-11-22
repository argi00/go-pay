"""Les schémas Pydantic : ce que l'API accepte en entrée et renvoie en sortie."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

# Types réutilisables
Telephone = Annotated[str, Field(pattern=r"^\+2217[05678]\d{7}$", examples=["+221770000000"])]
Montant = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=0)]
MontantTransfert = Annotated[Decimal, Field(ge=100, max_digits=12, decimal_places=0)]  # R1


def nettoyer_telephone(valeur: object) -> object:
    """Accepte « +221 77 000 00 00 » en retirant les espaces."""
    if isinstance(valeur, str):
        return valeur.replace(" ", "")
    return valeur


# ---------- Wallets ----------
class WalletIn(BaseModel):
    nom: str = Field(min_length=2, max_length=100)
    telephone: Telephone
    type: Literal["client", "marchand"] = "client"

    @field_validator("telephone", mode="before")
    @classmethod
    def sans_espaces(cls, valeur: object) -> object:
        return nettoyer_telephone(valeur)


class WalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    telephone: str
    type: str
    solde: Decimal
    cree_le: datetime


class DepotIn(BaseModel):
    montant: Montant


# ---------- Transferts ----------
class TransfertIn(BaseModel):
    beneficiaire_tel: Telephone
    montant: MontantTransfert

    @field_validator("beneficiaire_tel", mode="before")
    @classmethod
    def sans_espaces(cls, valeur: object) -> object:
        return nettoyer_telephone(valeur)


class TransfertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expediteur_id: int
    beneficiaire_tel: str
    montant: Decimal
    frais: Decimal
    code_retrait: str
    statut: Literal["en_attente", "retire"]
    cree_le: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_debite(self) -> Decimal:
        return self.montant + self.frais


# ---------- Transferts de la diaspora ----------
class TransfertDiasporaIn(BaseModel):
    beneficiaire_tel: Telephone
    devise: Literal["EUR", "USD"]
    montant_devise: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]

    @field_validator("beneficiaire_tel", mode="before")
    @classmethod
    def sans_espaces(cls, valeur: object) -> object:
        return nettoyer_telephone(valeur)


class TransfertDiasporaOut(BaseModel):
    devise: str
    montant_devise: Decimal
    taux: Decimal
    transfert: TransfertOut


# ---------- Retraits ----------
class RetraitIn(BaseModel):
    code_retrait: str = Field(pattern=r"^\d{6}$")
    beneficiaire_tel: Telephone

    @field_validator("beneficiaire_tel", mode="before")
    @classmethod
    def sans_espaces(cls, valeur: object) -> object:
        return nettoyer_telephone(valeur)


class RetraitOut(BaseModel):
    transfert_id: int
    montant: Decimal
    statut: Literal["retire"]


# ---------- Paiements et historique ----------
class PaiementIn(BaseModel):
    marchand_id: int
    montant: Montant


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    type: str
    montant: Decimal
    frais: Decimal
    solde_apres: Decimal
    reference: str | None
    cree_le: datetime


class PageTransactions(BaseModel):
    items: list[TransactionOut]
    next_cursor: int | None
