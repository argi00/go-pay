"""Bonus : envoie un flux de transferts à FraudCheck et affiche les verdicts au fil de l'eau.

Lancement (FraudCheck doit tourner) : uv run python essai_flux.py
"""

import random
from collections.abc import Iterator

import grpc

from gopay.fraude import fraud_pb2, fraud_pb2_grpc

REGIONS = ["Dakar", "Thiès", "Diourbel", "Kédougou", "Ziguinchor"]


def transferts(nombre: int) -> Iterator[fraud_pb2.TransfertRequest]:
    for i in range(nombre):
        yield fraud_pb2.TransfertRequest(
            wallet_id=i, montant=random.randint(1_000, 2_000_000), region=random.choice(REGIONS)
        )


stub = fraud_pb2_grpc.FraudCheckStub(grpc.insecure_channel("localhost:50051"))
bloques = 0
for verdict in stub.Surveiller(transferts(100)):  # un flux part, un flux revient
    bloques += verdict.bloquer
print(f"100 transferts évalués, {bloques} bloqués")
