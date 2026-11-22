"""Partie B : le client FraudCheck, utilisé par Go Pay avant chaque transfert."""

from dataclasses import dataclass

import grpc

from gopay.errors import OperationInterdite, ServiceIndisponible
from gopay.fraude import fraud_pb2, fraud_pb2_grpc


@dataclass
class Verdict:
    score: float
    bloquer: bool
    raison: str


class ClientFraude:
    def __init__(self, adresse: str = "localhost:50051", echeance: float = 0.2) -> None:
        self._stub = fraud_pb2_grpc.FraudCheckStub(grpc.insecure_channel(adresse))
        self._echeance = echeance  # 200 ms au plus : un transfert n'attend pas

    def evaluer(self, wallet_id: int, montant: int, beneficiaire_tel: str, region: str) -> Verdict:
        requete = fraud_pb2.TransfertRequest(
            wallet_id=wallet_id, montant=montant, beneficiaire_tel=beneficiaire_tel, region=region
        )
        try:
            reponse = self._stub.Evaluer(requete, timeout=self._echeance)
        except grpc.RpcError as erreur:
            code = erreur.code()
            if code == grpc.StatusCode.INVALID_ARGUMENT:
                raise OperationInterdite(f"FraudCheck : {erreur.details()}") from erreur
            raise ServiceIndisponible(f"FraudCheck injoignable ({code.name}).") from erreur
        return Verdict(score=reponse.score, bloquer=reponse.bloquer, raison=reponse.raison)
