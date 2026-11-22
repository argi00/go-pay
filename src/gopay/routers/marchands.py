"""Les routes des marchands : enregistrer l'adresse de leurs webhooks (R15)."""

from fastapi import APIRouter

from gopay.dependencies import Service
from gopay.schemas import WebhookIn, WebhookOut

router = APIRouter(prefix="/v1/marchands", tags=["Marchands"])


@router.put("/{marchand_id}/webhook")
def configurer_webhook(marchand_id: int, data: WebhookIn, service: Service) -> WebhookOut:
    secret = service.configurer_webhook(marchand_id, str(data.url))
    return WebhookOut(marchand_id=marchand_id, url=str(data.url), secret=secret)
