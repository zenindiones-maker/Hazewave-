"""FYAHREAPER ReaHub: authenticated REST/WS boundary for the running REAPER host.

Run as a standalone workstation process; do not start Uvicorn inside ReaScript.
"""
from __future__ import annotations

import asyncio
import hmac
import os
from threading import RLock
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Note(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pitch: int = Field(ge=0, le=127)
    start: float = Field(ge=0, le=3600, allow_inf_nan=False)
    duration: float = Field(gt=0, le=3600, allow_inf_nan=False)
    velocity: int = Field(default=100, ge=1, le=127)


class MidiRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    notes: list[Note] = Field(min_length=1, max_length=2048)


class TrackPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mute: bool | None = None
    solo: bool | None = None
    armed: bool | None = None
    volume: float | None = Field(default=None, ge=0.0, le=4.0, allow_inf_nan=False)

    @model_validator(mode='after')
    def not_empty(self):
        if all(value is None for value in (self.mute, self.solo, self.armed, self.volume)):
            raise ValueError('EMPTY_TRACK_UPDATE')
        return self


def app_factory(studio, token: str) -> FastAPI:
    if len(token) < 24:
        raise ValueError('FYAH_REMOTE_TOKEN must contain at least 24 characters')
    app = FastAPI(title='FyahReaper ReaHub', version='0.1.0')
    lock = RLock()

    def authenticate(authorization: Annotated[str | None, Header()] = None):
        expected = 'Bearer ' + token
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(401, 'UNAUTHORIZED', headers={'WWW-Authenticate':'Bearer'})

    def guarded(method, *args):
        with lock:
            try:
                return method(*args)
            except KeyError as exc:
                raise HTTPException(404, 'TRACK_NOT_FOUND') from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(503, str(exc) or 'REAPER_NOT_READY') from exc
            except OSError as exc:
                raise HTTPException(503, 'REAPER_CONNECTION_LOST') from exc

    @app.get('/health', dependencies=[Depends(authenticate)])
    async def health():
        return await run_in_threadpool(guarded, studio.health)

    @app.get('/api/tracks', dependencies=[Depends(authenticate)])
    async def tracks():
        return await run_in_threadpool(guarded, studio.tracks)

    @app.patch('/api/tracks/{guid}', dependencies=[Depends(authenticate)])
    async def set_track(guid: str, patch: TrackPatch):
        return await run_in_threadpool(guarded, studio.set_track, guid, patch.model_dump(exclude_none=True))

    @app.post('/api/transport/{action}', dependencies=[Depends(authenticate)])
    async def transport(action: Literal['play', 'stop', 'rec']):
        return await run_in_threadpool(guarded, studio.transport, action)

    @app.post('/api/project/create_midi', dependencies=[Depends(authenticate)])
    async def create_midi(payload: MidiRequest):
        return await run_in_threadpool(guarded, studio.create_midi, payload)

    @app.websocket('/ws')
    async def feedback(socket: WebSocket):
        given = socket.headers.get('authorization', '')
        if not hmac.compare_digest(given, 'Bearer ' + token):
            await socket.close(code=1008)
            return
        await socket.accept()
        try:
            while True:
                status = await run_in_threadpool(guarded, studio.health)
                await socket.send_json({'type': 'transport', **status})
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    return app


def build_app() -> FastAPI:
    token = os.environ.get('FYAH_REMOTE_TOKEN', '')
    from reaper_bridge import ReaperBridge
    return app_factory(ReaperBridge(), token)


# Lazy REAPER initialization: importing this module in tests never starts a DAW.
# Uvicorn factory: `uvicorn reahub_server:build_app --factory ...`.
