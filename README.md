# Go Pay

Go Pay est une API REST de portefeuille électronique développée avec **FastAPI**. Elle modélise les opérations principales d’un service fintech : création de wallets, dépôts, transferts d’argent avec code de retrait, retraits et paiements auprès de marchands.

> Projet pédagogique — TD1, ISM Dakar. Les données sont actuellement conservées en mémoire et sont perdues au redémarrage de l’application.

## Fonctionnalités

- Création et consultation de wallets `client` ou `marchand`
- Dépôt d’argent sur un wallet
- Transfert vers un numéro de téléphone avec génération d’un code de retrait à 6 chiffres
- Retrait sécurisé par couple `code_retrait` / numéro bénéficiaire
- Paiement d’un marchand depuis un wallet client
- Historique des transactions avec pagination par curseur
- Erreurs métier au format **Problem Details** (`application/problem+json`)
- Documentation interactive FastAPI avec Swagger UI et ReDoc

## Règles métier

- Un numéro de téléphone ne peut être associé qu’à un seul wallet.
- Les numéros sénégalais sont acceptés au format `+2217XXXXXXXX` ; les espaces sont automatiquement supprimés.
- Un transfert doit être d’au moins **100 FCFA**.
- Les frais de transfert sont de **1 %**, arrondis au franc, avec un minimum de **50 FCFA**.
- Le solde est débité du montant du transfert **plus les frais**.
- Un code de retrait est composé de 6 chiffres et ne peut être utilisé qu’une seule fois.
- Un paiement ne peut être effectué que vers un wallet de type `marchand`.

## Prérequis

- Python 3.12 ou supérieur
- [uv](https://docs.astral.sh/uv/) recommandé pour gérer l’environnement et les dépendances

## Installation et lancement

```bash
uv sync
uv run fastapi dev src/gopay/main.py
```

L’API est ensuite disponible à l’adresse `http://127.0.0.1:8000`.

- Swagger UI : [`/docs`](http://127.0.0.1:8000/docs)
- ReDoc : [`/redoc`](http://127.0.0.1:8000/redoc)
- Vérification de disponibilité : [`/health`](http://127.0.0.1:8000/health)

## Exemple rapide

Créer un wallet puis effectuer un dépôt :

```bash
curl -X POST http://127.0.0.1:8000/v1/wallets \\
  -H 'Content-Type: application/json' \\
  -d '{"nom":"Awa","telephone":"+221770000001","type":"client"}'

curl -X POST http://127.0.0.1:8000/v1/wallets/1/depots \\
  -H 'Content-Type: application/json' \\
  -d '{"montant":20000}'
```

Effectuer un transfert depuis le wallet courant :

```bash
curl -X POST http://127.0.0.1:8000/v1/transferts \\
  -H 'Content-Type: application/json' \\
  -H 'X-Wallet-Id: 1' \\
  -d '{"beneficiaire_tel":"+221780000002","montant":5000}'
```

La réponse contient notamment `frais`, `total_debite` et `code_retrait`.

## Endpoints principaux

| Méthode | Route | Description |
| --- | --- | --- |
| `GET` | `/health` | Vérifier que l’API fonctionne |
| `POST` | `/v1/wallets` | Créer un wallet |
| `GET` | `/v1/wallets/{wallet_id}` | Consulter un wallet |
| `POST` | `/v1/wallets/{wallet_id}/depots` | Effectuer un dépôt |
| `GET` | `/v1/wallets/{wallet_id}/transactions` | Consulter l’historique paginé |
| `POST` | `/v1/transferts` | Créer un transfert (`X-Wallet-Id` requis) |
| `POST` | `/v1/retraits` | Retirer un transfert avec son code |
| `POST` | `/v1/paiements` | Payer un marchand (`X-Wallet-Id` requis) |

Pour les requêtes authentifiées, l’en-tête `X-Wallet-Id` identifie temporairement le wallet courant. Il sera remplacé par une authentification adaptée dans une prochaine version.

## Tests et qualité

Lancer les tests :

```bash
uv run pytest
```

La configuration du projet inclut également Ruff pour le linting et mypy en mode strict :

```bash
uv run ruff check .
uv run mypy src
```

## Structure du projet

```text
src/gopay/
├── main.py                 # Création de l’application FastAPI
├── routers/                # Routes HTTP des wallets et opérations
├── schemas.py              # Schémas d’entrée et de sortie Pydantic
├── services.py             # Règles métier R1 à R7
├── repository.py           # Stockage en mémoire
├── models.py               # Objets métier
├── dependencies.py         # Injection du repository et du wallet courant
└── errors.py               # Erreurs métier et Problem Details

tests/test_api.py           # Tests fonctionnels de l’API
```

## Évolution prévue

Le repository mémoire est volontairement simple pour le prototype. Les prochaines étapes pourront inclure une persistance PostgreSQL, une authentification JWT, la gestion de la concurrence et une séparation plus complète entre les domaines wallet, transfert et paiement.
