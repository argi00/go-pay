"""Lance 20 transferts de 1 000 FCFA en même temps sur un wallet de 10 000 FCFA.

Lancement : uv run python essai_concurrence.py
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from gopay.errors import SoldeInsuffisant
from gopay.repository import MemoireRepository
from gopay.services import GoPayService

service = GoPayService(MemoireRepository(latence=0.01))
awa = service.ouvrir_wallet("Awa", "+221770000001", "client")
service.deposer(awa.id, Decimal("10000"))


def un_transfert(_: int) -> bool:
    try:
        service.transferer(awa, "+221780000002", Decimal("1000"))  # 1 050 FCFA avec les frais
        return True
    except SoldeInsuffisant:
        return False


with ThreadPoolExecutor(max_workers=20) as pool:
    reussis = sum(pool.map(un_transfert, range(20)))

print(f"Transferts réussis : {reussis} (attendu : 9)")
print(f"Argent sorti : {reussis * 1050} FCFA")
print(f"Solde final : {awa.solde} FCFA (attendu : 550)")
