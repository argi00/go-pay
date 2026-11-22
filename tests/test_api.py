"""Tests du TD1 : ils reprennent les critères de réussite."""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from gopay.dependencies import get_repository
from gopay.main import app
from gopay.repository import MemoireRepository
from gopay.services import calculer_frais

TEL_AWA = "+221770000001"
TEL_MODOU = "+221780000002"
TEL_BOUTIQUE = "+221760000003"


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Un client de test avec une base vide, neuve pour chaque test."""
    repo = MemoireRepository()
    app.dependency_overrides[get_repository] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def ouvrir(client: TestClient, nom: str, tel: str, type_: str = "client", depot: int = 0) -> int:
    wallet_id: int = client.post("/v1/wallets", json={"nom": nom, "telephone": tel, "type": type_}).json()["id"]
    if depot:
        client.post(f"/v1/wallets/{wallet_id}/depots", json={"montant": depot})
    return wallet_id


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"statut": "ok"}


@pytest.mark.parametrize(("montant", "frais"), [(15000, 150), (3000, 50), (100, 50), (5050, 51), (5049, 50)])
def test_calcul_des_frais(montant: int, frais: int) -> None:
    assert calculer_frais(Decimal(montant)) == Decimal(frais)


def test_transfert_debite_montant_plus_frais(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    r = client.post(
        "/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": "15000"}, headers={"X-Wallet-Id": str(awa)}
    )
    assert r.status_code == 201
    corps = r.json()
    assert corps["frais"] == "150"
    assert corps["total_debite"] == "15150"
    assert len(corps["code_retrait"]) == 6
    assert client.get(f"/v1/wallets/{awa}").json()["solde"] == "4850"


def test_montant_sous_le_minimum(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    r = client.post(
        "/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 99}, headers={"X-Wallet-Id": str(awa)}
    )
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"


def test_solde_insuffisant(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=10000)
    r = client.post(
        "/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 10000}, headers={"X-Wallet-Id": str(awa)}
    )
    assert r.status_code == 422
    assert r.json()["type"].endswith("solde-insuffisant")
    assert client.get(f"/v1/wallets/{awa}").json()["solde"] == "10000"


def test_code_de_retrait_utilisable_une_seule_fois(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    code = client.post(
        "/v1/transferts", json={"beneficiaire_tel": TEL_MODOU, "montant": 5000}, headers={"X-Wallet-Id": str(awa)}
    ).json()["code_retrait"]
    retrait = {"code_retrait": code, "beneficiaire_tel": TEL_MODOU}
    assert client.post("/v1/retraits", json=retrait).status_code == 201
    assert client.post("/v1/retraits", json=retrait).status_code == 409


def test_paiement_marchand(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA, depot=20000)
    boutique = ouvrir(client, "Boutique Ndiaye", TEL_BOUTIQUE, type_="marchand")
    r = client.post("/v1/paiements", json={"marchand_id": boutique, "montant": 7500}, headers={"X-Wallet-Id": str(awa)})
    assert r.status_code == 201
    assert client.get(f"/v1/wallets/{awa}").json()["solde"] == "12500"
    assert client.get(f"/v1/wallets/{boutique}").json()["solde"] == "7500"


def test_historique_pagine(client: TestClient) -> None:
    awa = ouvrir(client, "Awa", TEL_AWA)
    for _ in range(5):
        client.post(f"/v1/wallets/{awa}/depots", json={"montant": 1000})
    page1 = client.get(f"/v1/wallets/{awa}/transactions", params={"limit": 2}).json()
    assert len(page1["items"]) == 2
    page2 = client.get(f"/v1/wallets/{awa}/transactions", params={"limit": 2, "cursor": page1["next_cursor"]}).json()
    assert page2["items"][0]["id"] < page1["items"][-1]["id"]
