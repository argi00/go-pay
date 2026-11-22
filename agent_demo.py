"""Un agent de DÉMONSTRATION : se connecte en WebSocket et affiche les alertes reçues.

Lancement (l'API doit tourner) : uv run python agent_demo.py
"""

import asyncio
import json

import websockets


async def ecouter(agent_id: int) -> None:
    async with websockets.connect(f"ws://127.0.0.1:8000/ws/agents/{agent_id}") as ws:
        print(f"Agent {agent_id} connecté, en attente d'alertes (Ctrl + C pour quitter)")
        async for message in ws:
            print("Alerte reçue :", json.loads(message))


asyncio.run(ecouter(7))
