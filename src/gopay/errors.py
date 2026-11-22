"""Les erreurs métier de Go Pay et leur conversion au format Problem Details (RFC 9457)."""

from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

BASE_TYPE = "https://api.gopay.example/erreurs/"


class GoPayError(Exception):
    """Classe mère de toutes les erreurs métier."""

    status = 400
    code = "erreur"
    titre = "Erreur"

    def __init__(self, detail: str, **extras: object) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extras = extras


class RessourceIntrouvable(GoPayError):
    status, code, titre = 404, "introuvable", "Ressource introuvable"


class TelephoneDejaUtilise(GoPayError):
    status, code, titre = 409, "telephone-deja-utilise", "Téléphone déjà utilisé"


class SoldeInsuffisant(GoPayError):
    status, code, titre = 422, "solde-insuffisant", "Solde insuffisant"


class CodeDejaUtilise(GoPayError):
    status, code, titre = 409, "code-deja-utilise", "Code de retrait déjà utilisé"


class OperationInterdite(GoPayError):
    status, code, titre = 422, "operation-interdite", "Opération interdite"


class CleDejaUtilisee(GoPayError):
    status, code, titre = 422, "idempotency-key-reutilisee", "Idempotency-Key déjà utilisée"


class TraitementEnCours(GoPayError):
    status, code, titre = 409, "traitement-en-cours", "Traitement en cours"


class ServiceIndisponible(GoPayError):
    status, code, titre = 503, "service-indisponible", "Service indisponible"


def probleme(request: Request, status: int, code: str, titre: str, detail: str, **extras: object) -> JSONResponse:
    corps = {
        "type": BASE_TYPE + code,
        "title": titre,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        **extras,
    }
    return JSONResponse(
        jsonable_encoder(corps, custom_encoder={Decimal: str}),
        status_code=status,
        media_type="application/problem+json",
    )


def installer_gestionnaires(app: FastAPI) -> None:
    @app.exception_handler(GoPayError)
    async def erreur_metier(request: Request, exc: GoPayError) -> JSONResponse:
        return probleme(request, exc.status, exc.code, exc.titre, exc.detail, **exc.extras)

    @app.exception_handler(RequestValidationError)
    async def erreur_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return probleme(
            request,
            422,
            "validation",
            "Requête invalide",
            "Un ou plusieurs champs sont invalides.",
            errors=exc.errors(),
        )
