import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mc_server_interaction.server_manger import ServerManager
from starlette.middleware.cors import CORSMiddleware

from mc_server_manager_api.models import SimpleMinecraftServer, AvailableVersionsResponse, GetServersResponse, \
    ServerCreationData, ServerCreatedModel, MinecraftServerModel, ServerCommand

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

manager = ServerManager()


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
    servers = manager.get_servers()
    resp_model = {
        "servers": [
            SimpleMinecraftServer(sid, server.server_config.name, server.server_config.version,
                                  status=server.get_status().name).__dict__ for sid, server
            in servers.items()
        ]
    }
    return JSONResponse(resp_model, 200)


@app.get("/available_versions", response_model=AvailableVersionsResponse)
async def get_available_versions():
    return JSONResponse(
        {
            "available_versions": list(manager.available_versions.available_versions.keys())
        }, 200)


@app.post("/servers", response_model=ServerCreatedModel)
async def create_server(server: ServerCreationData):
    try:
        sid, server = await manager.create_new_server(server.name, server.version)
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
        status=server.get_status().name
    )


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
