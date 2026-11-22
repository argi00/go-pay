"""Tests du TD1 et du TD2 : ils reprennent les critères de réussite."""

import asyncio
import json
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import marchand_demo
from gopay.dependencies import get_antifraude, get_change, get_envoyeur, get_idempotence, get_repository
from gopay.errors import ServiceIndisponible
from gopay.fraude.client import ClientFraude, Verdict
from gopay.fraude.serveur import demarrer
from gopay.graphql_api import Contexte, schema
from gopay.idempotence import StockIdempotence
from gopay.main import app
from gopay.repository import MemoireRepository
from gopay.services import GoPayService, calculer_frais
from gopay.webhooks import signer, verifier

TEL_AWA = "+221770000001"
TEL_MODOU = "+221780000002"
TEL_BOUTIQUE = "+221760000003"


class FauxChange:
    """Remplace le vrai service de change : réponse immédiate et connue."""

    def __init__(self, en_panne: bool = False) -> None:
        self.en_panne = en_panne

    def taux(self, devise: str) -> Decimal:
        if self.en_panne:
            raise ServiceIndisponible("Service de change indisponible (test).")
        return {"EUR": Decimal("655.957"), "USD": Decimal("575.50")}[devise]


class FauxAntiFraude:
    """Bloque à partir de 1 000 000 FCFA ; peut simuler une panne."""

    def __init__(self, en_panne: bool = False) -> None:
        self.en_panne = en_panne

    def evaluer(self, wallet_id: int, montant: int, beneficiaire_tel: str, region: str) -> Verdict:
        if self.en_panne:
            raise ServiceIndisponible("FraudCheck injoignable (test).")
        return Verdict(score=0.9 if montant >= 1_000_000 else 0.1, bloquer=montant >= 1_000_000, raison="test")


class FauxEnvoyeur:
    """Enregistre les webhooks au lieu de les envoyer."""

    def __init__(self) -> None:
        self.envois: list[tuple[str, str, dict[str, object]]] = []

    def envoyer(self, url: str, secret: str, evenement: dict[str, object]) -> bool:
        self.envois.append((url, secret, evenement))
        return True


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Un client de test avec une base vide, neuve pour chaque test."""
    repo = MemoireRepository()
    idem = StockIdempotence()
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_idempotence] = lambda: idem
    app.dependency_overrides[get_change] = lambda: FauxChange()
    app.dependency_overrides[get_antifraude] = lambda: FauxAntiFraude()
    yield TestClient(app)
    app.dependency_overrides.clear()


def entetes(wallet_id: int, cle: str | None = None) -> dict[str, str]:
    """Les en-têtes d'une opération : le wallet et une Idempotency-Key (nouvelle par défaut)."""
    return {"X-Wallet-Id": str(wallet_id), "Idempotency-Key": cle or str(uuid.uuid4())}


def ouvrir(client: TestClient, nom: str, tel: str, type_: str = "client", depot: int = 0) -> int:
    wallet_id: int = client.post("/v1/wallets", json={"nom": nom, "telephone": tel, "type": type_}).json()["id"]
    if depot:
        client.post(f"/v1/wallets/{wallet_id}/depots", json={"montant": depot})
    return wallet_id


def solde(client: TestClient, wallet_id: int) -> str:
    valeur: str = client.get(f"/v1/wallets/{wallet_id}").json()["solde"]
    return valeur


# ---------- TD1 ----------
def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"statut": "ok"}


@pytest.mark.parametrize(
    ("montant", "frais"), [(15000, 150), (3000, 50), (100, 50), (5050, 51), (5049, 50), (12345, 123)]
)
def test_calcul_des_frais(montant: int, frais: int) -> None:
    assert calculer_frais(Decimal(montant)) == Decimal(frais)


def test_transfert_debite_montant_plus_frais(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    r = client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": "15000"}, headers=entetes(awa))
    assert r.status_code == 201
    assert r.json()["total_debite"] == "15150"
    assert solde(client, awa) == "4850"


def test_montant_sous_le_minimum(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    r = client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 99}, headers=entetes(awa))
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"


def test_solde_insuffisant(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=10000)
    r = client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 10000}, headers=entetes(awa))
    assert r.status_code == 422
    assert r.json()["type"].endswith("solde-insuffisant")
    assert solde(client, awa) == "10000"


def test_code_de_retrait_utilisable_une_seule_fois(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    corps = {"beneficiaire_tel": TEL_MODOU, "montant": 5000}
    code = client.post("/v1/transferts", json=corps, headers=entetes(awa)).json()["code_retrait"]
    retrait = {"code_retrait": code, "beneficiaire_tel": TEL_MODOU}
    assert client.post("/v1/retraits", json=retrait).status_code == 201
    assert client.post("/v1/retraits", json=retrait).status_code == 409


def test_paiement_marchand(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    boutique = ouvrir(client, "Boutique Ndiaye", TEL_BOUTIQUE, type_="marchand")
    r = client.post("/v1/paiements", json={"marchand_id": boutique, "montant": 7500}, headers=entetes(awa))
    assert r.status_code == 201
    assert solde(client, awa) == "12500"
    assert solde(client, boutique) == "7500"


def test_historique_pagine(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA)
    for _ in range(5):
        client.post(f"/v1/wallets/{awa}/depots", json={"montant": 1000})
    page1 = client.get(f"/v1/wallets/{awa}/transactions", params={"limit": 2}).json()
    assert len(page1["items"]) == 2
    page2 = client.get(f"/v1/wallets/{awa}/transactions", params={"limit": 2, "cursor": page1["next_cursor"]}).json()
    assert page2["items"][0]["id"] < page1["items"][-1]["id"]


# ---------- TD2 : idempotence (R9) ----------
def test_idempotency_key_obligatoire(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    r = client.post(
        "/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 1000}, headers={"X-Wallet-Id": str(awa)}
    )
    assert r.status_code == 422


def test_requete_rejouee_debitee_une_seule_fois(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    corps = {"beneficiaire_tel": TEL_MODOU, "montant": 5000}
    cle = entetes(awa, "cle-test-0001")
    premiere = client.post("/v1/transferts", json=corps, headers=cle)
    seconde = client.post("/v1/transferts", json=corps, headers=cle)
    assert premiere.status_code == seconde.status_code == 201
    assert premiere.json() == seconde.json()  # même transfert, même code
    assert solde(client, awa) == "14950"  # 20 000 - 5 050, une seule fois


def test_meme_cle_autre_corps_refusee(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    cle = entetes(awa, "cle-test-0002")
    client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 5000}, headers=cle)
    r = client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 6000}, headers=cle)
    assert r.status_code == 422
    assert r.json()["type"].endswith("idempotency-key-reutilisee")


def test_echec_non_memorise(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=1000)
    corps = {"beneficiaire_tel": TEL_MODOU, "montant": 5000}
    cle = entetes(awa, "cle-test-0003")
    assert client.post("/v1/transferts", json=corps, headers=cle).status_code == 422  # solde insuffisant
    client.post(f"/v1/wallets/{awa}/depots", json={"montant": 10000})
    assert client.post("/v1/transferts", json=corps, headers=cle).status_code == 201  # même clé, réussite


# ---------- TD2 : concurrence (R10) ----------
def test_transferts_simultanes_jamais_de_solde_negatif() -> None:
    repo = MemoireRepository(latence=0.01)
    service = GoPayService(repo)
    awa = service.ouvrir_wallet("Awa", TEL_AWA, "client")
    service.deposer(awa.id, Decimal("10000"))

    def un_transfert(_: int) -> bool:
        try:
            service.transferer(awa, TEL_MODOU, Decimal("1000"))  # 1 050 FCFA avec les frais
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        reussis = sum(pool.map(un_transfert, range(20)))

    assert reussis == 9  # 9 × 1 050 = 9 450 ≤ 10 000 < 10 × 1 050
    assert awa.solde == Decimal("550")


# ---------- TD2 : diaspora (R11) ----------
def test_transfert_diaspora_en_euros(client: TestClient) -> None:
    fatou = ouvrir(client, "Fatou", "+221750000004")
    corps = {"beneficiaire_tel": TEL_MODOU, "devise": "EUR", "montant_devise": "100"}
    r = client.post("/v1/transferts-diaspora", json=corps, headers=entetes(fatou))
    assert r.status_code == 201
    assert r.json()["transfert"]["montant"] == "65596"  # 100 × 655,957 arrondi au franc
    assert r.json()["transfert"]["frais"] == "656"


def test_service_de_change_en_panne(client: TestClient) -> None:
    app.dependency_overrides[get_change] = lambda: FauxChange(en_panne=True)
    fatou = ouvrir(client, "Fatou", "+221750000004")
    corps = {"beneficiaire_tel": TEL_MODOU, "devise": "USD", "montant_devise": "50"}
    r = client.post("/v1/transferts-diaspora", json=corps, headers=entetes(fatou))
    assert r.status_code == 503


# ---------- TD2 : filtres de l'historique ----------
def test_historique_filtre_par_type(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 1000}, headers=entetes(awa))
    items = client.get(f"/v1/wallets/{awa}/transactions", params={"type": "transfert"}).json()["items"]
    assert [t["type"] for t in items] == ["transfert"]


def test_historique_dates_inversees(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA)
    r = client.get(f"/v1/wallets/{awa}/transactions", params={"du": "2026-12-31", "au": "2026-01-01"})
    assert r.status_code == 422


# ---------- TD3 partie A : GraphQL ----------
def test_graphql_dataloader_une_seule_lecture() -> None:
    repo = MemoireRepository()
    service = GoPayService(repo)
    for i in range(5):
        wallet = service.ouvrir_wallet(f"Client {i}", f"+22177000000{i}", "client")
        for _ in range(20):
            service.deposer(wallet.id, Decimal("1000"))
    contexte = Contexte(repo)
    resultat = asyncio.run(
        schema.execute("{ transactions(limite: 100) { montant wallet { nom } } }", context_value=contexte)
    )
    assert resultat.errors is None
    assert resultat.data is not None and len(resultat.data["transactions"]) == 100
    assert contexte.lectures_wallets == 1  # 100 transactions, 5 wallets, UNE seule lecture groupée


def test_graphql_par_http(client: TestClient) -> None:
    ouvrir(client, "Awa", TEL_AWA, depot=20000)
    r = client.post("/graphql", json={"query": "{ wallets { nom solde region } }"})
    assert r.json()["data"]["wallets"] == [{"nom": "Awa", "solde": "20000", "region": "Dakar"}]


# ---------- TD3 partie B : gRPC (R12, R13) ----------
def test_transfert_bloque_par_antifraude(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=3_000_000)
    r = client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 1_900_000}, headers=entetes(awa))
    assert r.status_code == 422
    assert solde(client, awa) == "3000000"


def test_antifraude_injoignable(client: TestClient) -> None:
    app.dependency_overrides[get_antifraude] = lambda: FauxAntiFraude(en_panne=True)
    awa = ouvrir(client, "Awa", TEL_AWA, depot=200_000)
    petit = client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 10_000}, headers=entetes(awa))
    gros = client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 60_000}, headers=entetes(awa))
    assert petit.status_code == 201  # sous 50 000 FCFA : on laisse passer
    assert gros.status_code == 503  # au-dessus : on refuse


def test_vrai_serveur_grpc() -> None:
    serveur = demarrer(port=50071)
    try:
        client_fraude = ClientFraude("localhost:50071")
        assert client_fraude.evaluer(1, 15_000, TEL_MODOU, "Dakar").bloquer is False
        assert client_fraude.evaluer(1, 1_900_000, TEL_MODOU, "Dakar").bloquer is True
    finally:
        serveur.stop(0)
    with pytest.raises(ServiceIndisponible):
        ClientFraude("localhost:50071").evaluer(1, 15_000, TEL_MODOU, "Dakar")


# ---------- TD3 partie C : temps réel et webhooks (R14, R15) ----------
def test_agent_prevenu_sans_code_de_retrait(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    with client.websocket_connect("/ws/agents/7") as ws:
        client.post("/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 5000}, headers=entetes(awa))
        message = ws.receive_json()
    assert message["type"] == "transfert"
    assert message["montant"] == "5000"
    assert "code_retrait" not in message


def test_suivi_sse(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    corps = {"beneficiaire_tel": TEL_MODOU, "montant": 5000}
    transfert = client.post("/v1/transferts", json=corps, headers=entetes(awa)).json()
    client.post("/v1/retraits", json={"code_retrait": transfert["code_retrait"], "beneficiaire_tel": TEL_MODOU})
    with client.stream("GET", f"/v1/transferts/{transfert['id']}/suivi") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        lignes = [ligne for ligne in r.iter_lines() if ligne.startswith("data:")]
    assert json.loads(lignes[-1].removeprefix("data: "))["statut"] == "retire"


def test_signature_webhook() -> None:
    corps = b'{"event_id": "evt_1", "montant": "45000"}'
    t = int(time.time())
    entete = f"t={t},v1={signer('secret', corps, t)}"
    assert verifier("secret", corps, entete)
    assert not verifier("secret", corps.replace(b"45000", b"95000"), entete)  # corps modifié
    assert not verifier("autre-secret", corps, entete)  # mauvais secret
    vieux = t - 600
    assert not verifier("secret", corps, f"t={vieux},v1={signer('secret', corps, vieux)}")  # trop ancien


def test_paiement_declenche_un_webhook(client: TestClient) -> None:
    envoyeur = FauxEnvoyeur()
    app.dependency_overrides[get_envoyeur] = lambda: envoyeur
    awa = ouvrir(client, "Awa", TEL_AWA, depot=50000)
    boutique = ouvrir(client, "Boutique Ndiaye", TEL_BOUTIQUE, type_="marchand")
    config = client.put(f"/v1/marchands/{boutique}/webhook", json={"url": "http://127.0.0.1:8002/hooks/gopay"}).json()
    client.post("/v1/paiements", json={"marchand_id": boutique, "montant": 45000}, headers=entetes(awa))
    assert len(envoyeur.envois) == 1
    url, secret, evenement = envoyeur.envois[0]
    assert url == "http://127.0.0.1:8002/hooks/gopay"
    assert secret == config["secret"]
    assert evenement["type"] == "paiement.recu" and evenement["montant"] == "45000"


def test_marchand_demo_verifie_et_dedoublonne(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(marchand_demo, "SECRET", "secret-test")
    marchand = TestClient(marchand_demo.app)
    corps = json.dumps({"event_id": "evt_test_1", "montant": "45000", "client_id": 1}).encode()
    t = int(time.time())
    entetes_ok = {"GoPay-Signature": f"t={t},v1={signer('secret-test', corps, t)}"}
    assert marchand.post("/hooks/gopay", content=corps, headers=entetes_ok).json() == {"statut": "recu"}
    assert marchand.post("/hooks/gopay", content=corps, headers=entetes_ok).json() == {"statut": "deja_traite"}
    faux = {"GoPay-Signature": f"t={t},v1=0000"}
    assert marchand.post("/hooks/gopay", content=corps, headers=faux).status_code == 401
