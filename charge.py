"""Script de charge : rejoue des requêtes et en lance en parallèle contre l'API qui tourne.

Lancement (l'API doit tourner sur le port 8000) : uv run python charge.py
"""

import random
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import httpx

API = "http://127.0.0.1:8000"
http = httpx.Client(base_url=API, timeout=10)


def nouveau_wallet(nom: str) -> int:
    tel = f"+22177{random.randint(0, 9_999_999):07d}"
    wallet_id: int = http.post("/v1/wallets", json={"nom": nom, "telephone": tel}).raise_for_status().json()["id"]
    return wallet_id


def transferer(wallet_id: int, montant: int, cle: str) -> httpx.Response:
    return http.post(
        "/v1/transferts",
        json={"beneficiaire_tel": "+221780000002", "montant": montant},
        headers={"X-Wallet-Id": str(wallet_id), "Idempotency-Key": cle},
    )


def solde(wallet_id: int) -> str:
    valeur: str = http.get(f"/v1/wallets/{wallet_id}").json()["solde"]
    return valeur


# 1. Double envoi : la même requête deux fois, avec la même clé
awa = nouveau_wallet("Awa")
http.post(f"/v1/wallets/{awa}/depots", json={"montant": 20000})
cle = str(uuid.uuid4())
r1, r2 = transferer(awa, 5000, cle), transferer(awa, 5000, cle)
print("1. Double envoi")
print(f"   codes HTTP : {r1.status_code} puis {r2.status_code}")
print(f"   même transfert : {r1.json().get('id') == r2.json().get('id')}")
print(f"   solde : {solde(awa)} FCFA (attendu : 14950)")

# 2. Vingt transferts simultanés de 1 000 FCFA sur un wallet de 10 000 FCFA
modou = nouveau_wallet("Modou")
http.post(f"/v1/wallets/{modou}/depots", json={"montant": 10000})
with ThreadPoolExecutor(max_workers=20) as pool:
    reponses = list(pool.map(lambda _: transferer(modou, 1000, str(uuid.uuid4())), range(20)))
codes = Counter(r.status_code for r in reponses)
print("2. Vingt transferts simultanés")
print(f"   réponses : {dict(codes)} (attendu : 9 × 201 et 11 × 422)")
print(f"   solde : {solde(modou)} FCFA (attendu : 550, jamais négatif)")

# 3. Transferts de la diaspora avec un service de change peu fiable
fatou = nouveau_wallet("Fatou")
codes_diaspora: Counter[int] = Counter()
for _ in range(10):
    r = http.post(
        "/v1/transferts-diaspora",
        json={"beneficiaire_tel": "+221780000002", "devise": "EUR", "montant_devise": "50"},
        headers={"X-Wallet-Id": str(fatou), "Idempotency-Key": str(uuid.uuid4())},
    )
    codes_diaspora[r.status_code] += 1
print("3. Dix transferts de la diaspora")
print(f"   réponses : {dict(codes_diaspora)} (201 : réussi, 503 : service de change indisponible)")
