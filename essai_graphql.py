"""Compte les lectures de wallets pour une requête GraphQL sur 100 transactions.

Lancement : uv run python essai_graphql.py
"""

import asyncio
from decimal import Decimal

from gopay.graphql_api import Contexte, schema
from gopay.repository import MemoireRepository
from gopay.services import GoPayService

repo = MemoireRepository()
service = GoPayService(repo)
for i in range(5):  # 5 wallets, 20 dépôts chacun : 100 transactions
    wallet = service.ouvrir_wallet(f"Client {i}", f"+22177000000{i}", "client")
    for _ in range(20):
        service.deposer(wallet.id, Decimal("1000"))

contexte = Contexte(repo)
requete = "{ transactions(limite: 100) { montant wallet { nom } } }"
resultat = asyncio.run(schema.execute(requete, context_value=contexte))
print(f"Transactions renvoyées : {len(resultat.data['transactions']) if resultat.data else 0}")
print(f"Lectures de wallets : {contexte.lectures_wallets}")
