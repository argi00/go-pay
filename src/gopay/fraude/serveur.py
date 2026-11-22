"""Partie B : le service interne FraudCheck, en gRPC.

Lancement : uv run python -m gopay.fraude.serveur
"""

from collections.abc import Iterator
from concurrent import futures

import grpc

from gopay.fraude import fraud_pb2, fraud_pb2_grpc

SEUIL_BLOCAGE = 0.8  # R12
REGIONS_HABITUELLES = {"Dakar", "Thiès", "Diourbel"}


def noter(requete: fraud_pb2.TransfertRequest) -> fraud_pb2.Verdict:
    """Une règle simple pour commencer ; un modèle de ML la remplacera au weekend 2."""
    score = min(requete.montant / 2_000_000, 1.0)  # 2 millions de FCFA ou plus : score maximal
    raisons = []
    if requete.montant >= 1_000_000:
        raisons.append("montant élevé")
    if requete.region not in REGIONS_HABITUELLES:
        score = min(score + 0.1, 1.0)
        raisons.append("région inhabituelle")
    return fraud_pb2.Verdict(score=score, bloquer=score >= SEUIL_BLOCAGE, raison=", ".join(raisons))


class FraudCheck(fraud_pb2_grpc.FraudCheckServicer):
    def Evaluer(self, request: fraud_pb2.TransfertRequest, context: grpc.ServicerContext) -> fraud_pb2.Verdict:
        if request.montant <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Le montant doit être positif.")
        return noter(request)

    def Surveiller(
        self, request_iterator: Iterator[fraud_pb2.TransfertRequest], context: grpc.ServicerContext
    ) -> Iterator[fraud_pb2.Verdict]:
        for requete in request_iterator:  # un flux entrant, un flux sortant
            yield noter(requete)


def demarrer(port: int = 50051) -> grpc.Server:
    serveur = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    fraud_pb2_grpc.add_FraudCheckServicer_to_server(FraudCheck(), serveur)
    serveur.add_insecure_port(f"[::]:{port}")
    serveur.start()
    return serveur


if __name__ == "__main__":
    print("FraudCheck en écoute sur le port 50051")
    demarrer().wait_for_termination()
