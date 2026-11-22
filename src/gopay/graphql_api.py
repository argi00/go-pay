"""Partie A : l'API GraphQL de Go Pay, en lecture seule, pour les analystes."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

import strawberry
from fastapi import Depends
from strawberry.dataloader import DataLoader
from strawberry.fastapi import BaseContext, GraphQLRouter

from gopay import models
from gopay.dependencies import get_repository
from gopay.repository import MemoireRepository

LIMITE_MAX = 100


class Contexte(BaseContext):
    """Créé pour chaque requête GraphQL : le repository et les DataLoaders."""

    def __init__(self, repo: MemoireRepository) -> None:
        super().__init__()
        self.repo = repo
        self.lectures_wallets = 0  # pour vérifier que le DataLoader regroupe bien les lectures
        self.wallets = DataLoader(load_fn=self.charger_wallets)

    async def charger_wallets(self, ids: list[int]) -> list[Wallet]:
        """Appelée UNE fois par requête, avec tous les identifiants demandés."""
        self.lectures_wallets += 1
        return [Wallet.depuis(self.repo.wallets[i]) for i in ids]


Info = strawberry.Info[Contexte, None]


@strawberry.type
class Wallet:
    id: int
    nom: str
    type: str
    region: str
    solde: Decimal

    @classmethod
    def depuis(cls, w: models.Wallet) -> Wallet:
        return cls(id=w.id, nom=w.nom, type=w.type, region=w.region, solde=w.solde)

    @strawberry.field
    def transactions(self, info: Info, limite: int = 10) -> list[Transaction]:
        items = info.context.repo.transactions_du_wallet(self.id, None, min(limite, LIMITE_MAX))
        return [Transaction.depuis(t) for t in items]


@strawberry.type
class Transaction:
    id: int
    type: str
    montant: Decimal
    frais: Decimal
    wallet_id: strawberry.Private[int]  # utile à nos résolveurs, absent du schéma

    @classmethod
    def depuis(cls, t: models.Transaction) -> Transaction:
        return cls(id=t.id, type=t.type, montant=t.montant, frais=t.frais, wallet_id=t.wallet_id)

    @strawberry.field
    async def wallet(self, info: Info) -> Wallet:
        return await info.context.wallets.load(self.wallet_id)


@strawberry.type
class Query:
    @strawberry.field
    def wallets(self, info: Info, limite: int = 20) -> list[Wallet]:
        return [Wallet.depuis(w) for w in list(info.context.repo.wallets.values())[: min(limite, LIMITE_MAX)]]

    @strawberry.field
    def transactions(self, info: Info, type: str | None = None, limite: int = 20) -> list[Transaction]:
        items = [t for t in info.context.repo.transactions.values() if type is None or t.type == type]
        return [Transaction.depuis(t) for t in items[: min(limite, LIMITE_MAX)]]


def get_contexte(repo: Annotated[MemoireRepository, Depends(get_repository)]) -> Contexte:
    return Contexte(repo)  # le même repository que l'API REST


schema = strawberry.Schema(query=Query)
graphql_router: GraphQLRouter[Contexte, None] = GraphQLRouter(schema, context_getter=get_contexte)
