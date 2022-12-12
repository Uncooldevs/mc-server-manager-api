import asyncio
import dataclasses
import io
import os
import zipfile
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Union

from starlette.staticfiles import StaticFiles

import mc_server_interaction.paths
from fastapi import FastAPI, WebSocket, UploadFile, File, APIRouter
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from mc_server_interaction.exceptions import ServerRunningException, WorldExistsException
from mc_server_interaction.manager import ServerManager
from starlette.middleware.cors import CORSMiddleware

from mc_server_manager_api.models import *

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

router = APIRouter(
    prefix="/api",
    responses={404: {"description": "Not found"}},
)

if os.path.isdir("./web/static"):
    app.mount("/static", StaticFiles(directory="web/static"), name="static")
    app.mount("/", StaticFiles(directory="web/"), name="")


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


def _get_worlds(server):
    worlds = server.worlds
    ret = []
    for world in worlds:
        ret.append(world.to_dict())
    return ret


# do some load on startup
@app.on_event("startup")
async def startup():
    await manager.available_versions.load()


@app.on_event("shutdown")
async def shutdown():
    await manager.stop_all_servers()
    manager.config.save()


@app.get("/")
def index():
    if os.path.exists("./web/index.html"):
        return FileResponse(
            "web/index.html",
            200
        )
    else:
        return RedirectResponse("/docs")


@router.get("/servers", response_model=GetServersResponse)
async def get_servers():
    resp = _get_servers()
    return JSONResponse(resp, 200)


@router.websocket("/servers")
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


@router.get("/available_versions", response_model=AvailableVersionsResponse)
async def get_available_versions():
    return JSONResponse(
        {
            "available_versions": ["latest"] + list(manager.available_versions.available_versions.keys())
        }, 200)


@router.post("/servers", response_model=ServerCreatedModel)
async def create_server(server: ServerCreationData):

    try:
        sid, server = await manager.create_new_server(name=server.name, version=server.version,
                                                      world_generation_settings=server.world_generation_settings)
    except Exception as e:
        return JSONResponse({
            "error": str(e)
        }, 500)
    asyncio.create_task(manager.install_server(sid))
    return ServerCreatedModel(message="Lol", sid=sid)


@router.get("/worlds", response_model=AllWorldsResponse)
async def get_worlds():
    worlds_dict = {}
    for sid in manager.get_servers():
        server = manager.get_server(sid)
        worlds_dict[sid] = _get_worlds(server)
    return JSONResponse({"worlds": worlds_dict}, 200)


@router.get("/servers/{sid}", response_model=MinecraftServerModel)
async def get_server(sid: str):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    return MinecraftServerModel(
        name=server.server_config.name,
        sid=sid,
        version=server.server_config.version,
        status=server.status.name,
        worlds=_get_worlds(server),
        properties=server.properties.to_dict(),
        backups=manager.backup_manager.get_backups_for_server(sid)
    )


@router.get("/servers/{sid}/players", response_model=PlayersResponse)
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


@router.post("/servers/{sid}/start")
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


@router.post("/servers/{sid}/stop")
async def stop_server(sid: str):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)

    if not server.is_running:
        return JSONResponse({"error": "Server is not running"}, 400)
    asyncio.create_task(server.stop())
    return JSONResponse({"message": "Server is stopping"})


@router.post("/servers/{sid}/command")
async def send_command(sid: str, command: ServerCommand):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    if not server.is_running:
        return JSONResponse({"error": "Server is not running"}, 400)

    await server.send_command(command.command)

    return 200


@router.get("/servers/{sid}/worlds", response_model=ServerWorldsResponse)
async def get_worlds(sid: str):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    return JSONResponse({"worlds": _get_worlds(server)}, 200)


@router.post("/servers/{sid}/copy_world")
async def copy_world(sid: str, dest: str = None, world_name: str = None, override: bool = False):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    if not dest:
        return JSONResponse({"error": "Query parameter dest is required"}, 400)
    if not world_name:
        return JSONResponse({"error": "Query parameter world_name is required"}, 400)
    dest_server = manager.get_server(dest)
    if not dest_server:
        return JSONResponse({"error": "Destination server not found"}, 404)
    world = server.get_world(world_name)
    if not world:
        return JSONResponse({"error": "World not found"}, 404)
    try:
        await world.copy_to_server(dest_server, override=override)
    except [IsADirectoryError, NotADirectoryError, OSError]:
        return JSONResponse({"message": "Failed to copy world, directory already exists"})
    return JSONResponse({"message": "Copied world to server"}, 200)


@router.post("/servers/{sid}/create_world")
async def create_world(sid: str, world_generation_settings: WorldGenerationData):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    try:
        await server.create_new_world(world_generation_settings.name, world_generation_settings.data)
    except WorldExistsException:
        return JSONResponse({"error": "A world with this name does already exist"})
    asyncio.create_task(server.set_active_world(world_generation_settings.name, new=True))
    return JSONResponse({"message": "The new world will be created after restart"}, 202)


@router.post("/servers/{sid}/change_world")
async def change_world(sid: str, world_name: str):
    server = manager.get_server(sid)
    if not server:
        return JSONResponse({"error": "Server not found"}, 404)
    asyncio.create_task(server.set_active_world(world_name))
    return JSONResponse({"message": f"Set active world to {world_name}"}, 202)


@router.websocket("/servers/{sid}/websocket")
async def websocket_stream(websocket: WebSocket, sid: str):
    server = manager.get_server(sid)
    if not server:
        return
    await websocket.accept()

    async def wrap_json(output: Union[str, dict], callback_name: str):
        if callback_name == "status":
            output = output.name
        await websocket.send_json({"type": callback_name, "value": output})

    server.callbacks.system_metrics.add_callback(partial(wrap_json, callback_name="system_metrics"))
    server.callbacks.properties.add_callback(partial(wrap_json, callback_name="properties"))
    server.callbacks.output.add_callback(partial(wrap_json, callback_name="output"))
    server.callbacks.players.add_callback(partial(wrap_json, callback_name="players"))
    server.callbacks.status.add_callback(partial(wrap_json, callback_name="status"))

    try:
        await wrap_json(server.logs, "output")
        players = server.players
        players = {
            "online_players": [dataclasses.asdict(player) for player in players["online_players"]],
            "op_players": [dataclasses.asdict(player) for player in players["op_players"]],
            "banned_players": [dataclasses.asdict(player) for player in players["banned_players"]]
        }
        await wrap_json(players, "players")
        await wrap_json(server.system_load, "system_metrics")
        while True:
            await asyncio.sleep(1)
    except Exception:
        return


@router.delete("/servers/{sid}")
async def delete_server(sid: str):
    try:
        manager.delete_server(sid)
    except ServerRunningException:
        return JSONResponse({"message": "Server is running"}, 400)

    return JSONResponse({"message": "Server deleted"}, 200)


@router.post("/servers/{sid}/upload_world", summary="Upload a world for later use", responses={
    201: {"model": WorldUploadResponse, "description": "Default response. Uploaded and saved the world"},
    200: {"model": WorldUploadResponse, "description": "World exists with the same id"},
    400: {"model": ErrorModel, "description": "Something is wrong with the file"}
})
async def upload_world(sid: str, in_file: UploadFile = File(...)):
    """
    This takes an uploaded zip file with a single directory, which contains the world and returns a unique id of the uploaded world.
    Save the id and use it when creating a new server (Not implemented)
    """
    if not in_file.filename.endswith(".zip"):
        return ErrorModel(error="File must be a zip file"), 400

    server = manager.get_server(sid)
    if not server:
        return 404

    dir_name = in_file.filename.replace(".zip", "")
    dir_name = "".join(c for c in dir_name if c.isalnum() or c in "_- !()[]{}")

    if not dir_name:
        return JSONResponse({"error": "Invalid world name"}, 400)

    out_file_path = Path(server.server_config.path) / "worlds" / dir_name

    if not out_file_path.exists():
        os.makedirs(str(out_file_path))

    if out_file_path.exists() and out_file_path.is_dir() and len(os.listdir(out_file_path)) > 0:
        # This is not bad, the world just exists, and we generate name by hash
        # Maybe override
        return WorldUploadResponse(message="World exists")

    # find a better async option
    with zipfile.ZipFile(io.BytesIO(await in_file.read()), 'r') as zip_file:
        zip_file.extractall(str(out_file_path))

    server.load_worlds()

    return WorldUploadResponse(message="success"), 201


@router.post("/servers/{sid}/backup")
async def create_backup(sid: str, body: CreateBackupModel):
    server = manager.get_server(sid)
    if not server:
        return 404

    world = server.get_world(body.world_name)
    if not world:
        return 404

    asyncio.create_task(manager.backup_manager.create_backup(sid, body.world_name))

    return 200


@router.get("/servers/backups/{bid}")
def download_backup(bid: str):
    backup = manager.backup_manager.get_backup(bid)
    if not backup:
        return JSONResponse({"message": "Backup not found"}, 404)

    return FileResponse(backup.path, 200)


@router.post("/servers/backups/{bid}/restore")
async def restore_backup(bid: str):
    backup = manager.backup_manager.get_backup(bid)
    if not backup:
        return JSONResponse({"message": "Backup not found"}, 404)

    asyncio.create_task(manager.backup_manager.restore_backup(bid))

    return 202


@router.post("/servers/backups/{bid}/delete")
async def delete_backup(bid: str):
    backup = manager.backup_manager.get_backup(bid)
    if not backup:
        return JSONResponse({"message": "Backup not found"}, 404)

    manager.backup_manager.delete_backup(bid)

    return 200


app.include_router(router)
