# Go Pay – Correction du TD2

Correction du TD2 « Go Pay robuste et connecté ». C'est le code que vous obtenez en suivant le document « TD2 pas à pas » jusqu'à l'étape 10. Il contient aussi tout le TD1.

## Lancer le projet

Prérequis : uv installé. Ouvrez deux terminaux dans ce dossier :

```bash
# Terminal 1 : l'API Go Pay
uv sync
uv run fastapi dev src/gopay/main.py

# Terminal 2 : le service de change simulé (lent et peu fiable, exprès)
uv run fastapi dev mock_change.py --port 8001
```

Ouvrez ensuite http://127.0.0.1:8000/docs. Les transferts et paiements demandent maintenant un en-tête `Idempotency-Key` (au moins 8 caractères).

## Vérifier

```bash
uv run pytest                    # 22 tests réussis
uv run ruff check .              # aucune erreur
uv run mypy src                  # aucune erreur
uv run python essai_concurrence.py   # 9 transferts réussis, solde final 550 FCFA
uv run python charge.py              # avec les deux serveurs en marche
```

## Où se trouve quoi

| Fichier | Étape du TD2 | Rôle |
| --- | --- | --- |
| `src/gopay/services.py` | 2, 4, 7, 8 | Règle d'arrondi (R8), verrous (R10), diaspora (R11), filtres |
| `src/gopay/idempotence.py` | 3 | Idempotency-Key (R9) |
| `src/gopay/repository.py` | 4, 8 | Verrou par wallet, latence simulée, filtres de l'historique |
| `src/gopay/change.py` | 6 | Client httpx avec délais et nouvelles tentatives (tenacity) |
| `src/gopay/routers/operations.py` | 3, 7 | Routes protégées par l'idempotence, route /v1/transferts-diaspora |
| `src/gopay/routers/wallets.py` | 8 | Historique filtré par type et par date |
| `mock_change.py` | 5 | Service de change simulé (port 8001) |
| `essai_concurrence.py` | 4 | Démonstration de la condition de concurrence |
| `charge.py` | 9 | Script de charge : double envoi, 20 transferts simultanés, diaspora |
| `bonus/change.py` | Bonus | Version du client qui respecte `Retry-After` sur 503 et 429 |
| `tests/test_api.py` | 9 | Tests du TD1 et du TD2 |

Pour essayer le bonus, copiez `bonus/change.py` à la place de `src/gopay/change.py`, puis relancez `charge.py` : la partie 3 donne presque toujours `{201: 10}`.

## Si vous êtes en retard

1. Copiez ce dossier à la place de votre projet `go-pay` (gardez votre dossier `.git` si vous en avez un).
2. Lancez `uv sync`, puis `uv run pytest` : 22 tests doivent réussir.
3. Faites un commit, posez le tag `td2`, puis commencez le TD3 à l'étape 1.

Faites au moins tourner `essai_concurrence.py` en retirant le verrou (étape 4.2 du document) : c'est la meilleure façon de comprendre pourquoi il est indispensable.
