"""Partie C : les agents en WebSocket (R14), le suivi d'un transfert en SSE."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from gopay.dependencies import get_repository
from gopay.errors import RessourceIntrouvable
from gopay.repository import MemoireRepository

router = APIRouter(tags=["Temps réel"])


class GestionnaireAgents:
    """Garde les connexions WebSocket ouvertes des agents."""

    def __init__(self) -> None:
        self.connexions: dict[int, set[WebSocket]] = {}

    async def connecter(self, agent_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.connexions.setdefault(agent_id, set()).add(ws)

    def deconnecter(self, agent_id: int, ws: WebSocket) -> None:
        self.connexions.get(agent_id, set()).discard(ws)

    async def diffuser(self, message: dict[str, Any]) -> None:
        """Envoie le message à tous les agents connectés."""
        for connexions in list(self.connexions.values()):
            for ws in list(connexions):
                await ws.send_json(message)


agents = GestionnaireAgents()


@router.websocket("/ws/agents/{agent_id}")
async def canal_agent(ws: WebSocket, agent_id: int) -> None:
    await agents.connecter(agent_id, ws)
    try:
        while True:
            message = await ws.receive_json()  # l'agent peut répondre : accusé de réception
            await ws.send_json({"type": "accuse", "recu": message})
    except WebSocketDisconnect:
        agents.deconnecter(agent_id, ws)


async def evenements(repo: MemoireRepository, transfert_id: int) -> AsyncIterator[str]:
    """Un événement à chaque changement de statut, pendant 60 secondes au plus."""
    dernier = None
    for numero in range(1, 121):
        transfert = repo.transferts[transfert_id]
        if transfert.statut != dernier:
            dernier = transfert.statut
            donnees = json.dumps({"transfert": transfert_id, "statut": transfert.statut})
            yield f"id: {numero}\nevent: statut\ndata: {donnees}\n\n"
        if transfert.statut == "retire":
            return  # fin du suivi
        await asyncio.sleep(0.5)


@router.get("/v1/transferts/{transfert_id}/suivi")
async def suivre(transfert_id: int, repo: Annotated[MemoireRepository, Depends(get_repository)]) -> StreamingResponse:
    if transfert_id not in repo.transferts:
        raise RessourceIntrouvable(f"Aucun transfert avec l'identifiant {transfert_id}.")
    return StreamingResponse(evenements(repo, transfert_id), media_type="text/event-stream")
