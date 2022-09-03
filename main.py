import _hashlib
import asyncio
import dataclasses
import io
import os
import zipfile
from pathlib import Path

import mc_server_interaction.paths
from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import JSONResponse
from mc_server_interaction.exceptions import ServerRunningException
from mc_server_interaction.server_manger import ServerManager
from starlette.middleware.cors import CORSMiddleware

from mc_server_manager_api import utils
from mc_server_manager_api.models import SimpleMinecraftServer, AvailableVersionsResponse, GetServersResponse, \
    ServerCreationData, ServerCreatedModel, MinecraftServerModel, ServerCommand, PlayersResponse, WorldUploadResponse, \
    ErrorModel

world_upload_path = mc_server_interaction.paths.cache_dir / "uploaded_worlds"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

manager = ServerManager()


def _get_servers():
    servers = manager.get_servers()
    resp = {
        "servers": [
            SimpleMinecraftServer(sid, server.server_config.name, server.server_config.version,
                                  status=server.status.name).__dict__ for sid, server
            in servers.items()
        ]
    }
    return resp


# do some load on startup
@app.on_event("startup")
async def startup():
    await manager.available_versions.load()


@app.on_event("shutdown")
async def shutdown():
    await manager.stop_all_servers()
    manager.config.save()


@app.get("/servers", response_model=GetServersResponse)
async def get_servers():
    resp = _get_servers()
    return JSONResponse(resp, 200)


@app.websocket("/servers")
async def get_servers_websocket(websocket: WebSocket):
    await websocket.accept()
    old_resp = {}
    try:
        while True:
            resp = _get_servers()
            if resp != old_resp:
                await websocket.send_json(resp)
                old_resp = resp
            await asyncio.sleep(5)
    except Exception:
        return


@app.get("/available_versions", response_model=AvailableVersionsResponse)
async def get_available_versions():
    return JSONResponse(
        {
            "available_versions": list(manager.available_versions.available_versions.keys())
        }, 200)


@app.post("/servers", response_model=ServerCreatedModel)
async def create_server(server: ServerCreationData):
    world_path = None
    if server.world_id:
        path = world_upload_path / server.world_id
        directory = os.listdir(str(path))[0]
        if path.exists() and utils.is_map_directory(path / directory):
            world_path = str(path / directory)

    try:
        sid, server = await manager.create_new_server(name=server.name, version=server.version, world_path=world_path,
                                                      world_generation_settings=server.world_generation_settings)
    except Exception as e:
        return JSONResponse({
            "error": e
        })
    asyncio.create_task(manager.install_server(sid))
    return ServerCreatedModel(message="Lol", sid=sid)


@app.get("/servers/{sid}")
async def get_server(sid: str):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    return MinecraftServerModel(
        name=server.server_config.name,
        sid=sid,
        version=server.server_config.version,
        status=server.status.name
    )


@app.get("/servers/{sid}/players", response_model=PlayersResponse)
async def get_players(sid: str):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)

    players = server.players
    resp = {
        "online_players": [dataclasses.asdict(player) for player in players["online_players"]],
        "op_players": [dataclasses.asdict(player) for player in players["op_players"]],
        "banned_players": [dataclasses.asdict(player) for player in players["banned_players"]]
    }
    return JSONResponse(resp, 200)


@app.post("/servers/{sid}/start")
async def start_server(sid: str):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    if not server.server_config.installed:
        return JSONResponse({"error": "Server is not installed yet"}, 400)
    if server.is_running:
        return JSONResponse({"error": "Server is running"})

    try:
        await server.start()
    except Exception as e:
        return JSONResponse({"error": e}, 500)

    return JSONResponse({"message": "Server is starting"}, 200)


@app.post("/servers/{sid}/stop")
async def stop_server(sid: str):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)

    if not server.is_running:
        return JSONResponse({"error": "Server is not running"}, 400)
    asyncio.create_task(server.stop())
    return JSONResponse({"message": "Server is stopping"})


@app.post("/servers/{sid}/command")
async def send_command(sid: str, command: ServerCommand):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    if not server.is_running:
        return JSONResponse({"error": "Server is not running"}, 400)

    await server.send_command(command.command)

    return 200


@app.websocket("/servers/{sid}/websocket")
async def websocket_stream(websocket: WebSocket, sid: str):
    server = manager.get_server(sid)
    if not server:
        return
    await websocket.accept()

    callback_installed = False

    async def json_wrap(output: str):
        await websocket.send_json({"type": "output", "output": output})

    try:
        await json_wrap(server.logs)
        while True:
            if not callback_installed and server.is_running:
                server.process.callbacks.stdout.add_callback(json_wrap)
                callback_installed = True
            if callback_installed and not server.is_running:
                callback_installed = False
            await websocket.send_json({"type": "metrics", "metrics": server.system_load})
            await asyncio.sleep(1)
    except Exception:
        return


@app.delete("/servers/{sid}")
async def delete_server(sid: str):
    try:
        manager.delete_server(sid)
    except ServerRunningException:
        return JSONResponse({"message": "Server is running"}, 400)

    return JSONResponse({"message": "Server deleted"}, 200)


@app.post("/upload_world", summary="Upload a world for later use", responses={
    201: {"model": WorldUploadResponse, "description": "Default response. Uploaded and saved the world"},
    200: {"model": WorldUploadResponse, "description": "World exists with the same id"},
    400: {"model": ErrorModel, "description": "Something is wrong with the file"}
})
async def upload_world(in_file: UploadFile = File(...)):
    """
    This takes an uploaded zip file with a single directory, which contains the world and returns a unique id of the uploaded world.
    Save the id and use it when creating a new server (Not implemented)
    """
    if not in_file.filename.endswith(".zip"):
        return ErrorModel(error="File must be a zip file"), 400

    folder_name = _hashlib.openssl_md5(in_file.filename.encode()).hexdigest()

    # Maybe we should use a new cache directory for api
    out_file_path = world_upload_path / folder_name

    # for debugging
    # out_file_path = Path().cwd() / "uploaded_worlds" / folder_name

    if not out_file_path.exists():
        os.makedirs(str(out_file_path))

    if out_file_path.exists() and out_file_path.is_dir() and len(os.listdir(out_file_path)) > 0:
        # This is not bad, the world just exists, and we generate name by hash
        # Maybe override
        return WorldUploadResponse(message="World exists", world_id=str(out_file_path))

    # find a better async option
    with zipfile.ZipFile(io.BytesIO(await in_file.read()), 'r') as zip_file:
        zip_file.extractall(str(out_file_path))

    return WorldUploadResponse(message="success", world_id=str(folder_name)), 201
