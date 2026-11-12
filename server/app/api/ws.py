"""WebSocket da partida ao vivo: ``/campaigns/{id}/ws?since=N``.

Caminho NOVO (aditivo): o polling ``GET /events?since=N`` continua valendo.
Cada mensagem enviada e um ``Event`` com EXATAMENTE o mesmo JSON do polling.

Fluxo:
  1. o front conecta (opcionalmente com ``since`` = ultimo ``seq`` que ja tem);
  2. o servidor envia os eventos atrasados e depois empurra cada evento novo;
  3. apos ``campaign_finished`` o servidor fecha com codigo 1000.

So leitura: aprovar, negar e parar continuam como POST (mesmas regras/auditoria).

Seguranca:
- WebSocket NAO e protegido por CORS: a origem e checada aqui contra a mesma
  lista da tela (``CORS_ORIGINS``). Origem estranha -> fecha com 1008.
- Mensagens vindas do cliente sao ignoradas (sem comandos pelo socket).
- Limite de conexoes simultaneas.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import cors_origins
from app.models import CampaignState, EventType

router = APIRouter()

MAX_CONNECTIONS = 50
IDLE_CHECK_S = 1.0  # rede de seguranca: rele o banco mesmo sem aviso
_FINAL = {CampaignState.FINISHED, CampaignState.STOPPED, CampaignState.FAILED}

# Codigos de fechamento (o front le em event.code)
CLOSE_DONE = 1000  # partida terminou
CLOSE_POLICY = 1008  # origem nao autorizada
CLOSE_BUSY = 1013  # muitas conexoes; tente de novo / use polling
CLOSE_NOT_FOUND = 4404  # campanha nao existe

_active = 0


def _origin_allowed(websocket: WebSocket) -> bool:
    allowed = cors_origins()
    if "*" in allowed:  # CORS_ORIGINS=* libera qualquer origem
        return True
    origin = websocket.headers.get("origin")
    if origin is None:  # clientes fora do navegador (scripts, testes) nao sofrem CSWSH
        return True
    return origin.rstrip("/") in allowed


@router.websocket("/campaigns/{campaign_id}/ws")
async def campaign_ws(
    websocket: WebSocket, campaign_id: str, since: int = Query(0, ge=0)
) -> None:
    global _active
    if not _origin_allowed(websocket):
        await websocket.close(code=CLOSE_POLICY)  # recusa o handshake
        return
    if _active >= MAX_CONNECTIONS:
        await websocket.close(code=CLOSE_BUSY)
        return

    ctx = websocket.app.state.ctx
    await websocket.accept()
    _active += 1
    reader = asyncio.create_task(_drain(websocket))
    try:
        if await ctx.db.get_campaign(campaign_id) is None:
            await websocket.close(code=CLOSE_NOT_FOUND, reason="Campanha nao encontrada.")
            return
        await _stream(websocket, ctx, campaign_id, since, reader)
    except WebSocketDisconnect:
        pass
    finally:
        _active -= 1
        reader.cancel()
        with contextlib.suppress(BaseException):
            await reader


async def _stream(websocket: WebSocket, ctx, campaign_id: str, last_seq: int, reader: asyncio.Task) -> None:
    idle_final = 0
    while not reader.done():  # cliente ainda conectado
        signal = ctx.coordinator.signal(campaign_id)  # pegar ANTES de ler (nao perde aviso)
        events = await ctx.db.list_events(campaign_id, since_seq=last_seq)
        for ev in events:
            await websocket.send_json(ev.model_dump(mode="json"))
            last_seq = max(last_seq, ev.seq)
            if ev.type is EventType.CAMPAIGN_FINISHED:
                await websocket.close(code=CLOSE_DONE)
                return

        if not events and await ctx.db.get_state(campaign_id) in _FINAL:
            idle_final += 1
            if idle_final >= 2:  # terminou sem evento final (ex.: motor caiu)
                await websocket.close(code=CLOSE_DONE)
                return
        else:
            idle_final = 0

        waiter = asyncio.create_task(signal.wait())
        done, _ = await asyncio.wait({waiter, reader}, timeout=IDLE_CHECK_S,
                                     return_when=asyncio.FIRST_COMPLETED)
        if waiter not in done:
            waiter.cancel()


async def _drain(websocket: WebSocket) -> None:
    """Le e descarta o que o cliente mandar; termina quando ele desconecta."""
    with contextlib.suppress(WebSocketDisconnect, RuntimeError):
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
