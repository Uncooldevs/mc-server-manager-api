import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mc_server_interaction.server_manger import ServerManager
from starlette.middleware.cors import CORSMiddleware

from mc_server_manager_api.models import SimpleMinecraftServer, AvailableVersionsResponse, GetServersResponse, \
    ServerCreationData, ServerCreationAccepted

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


@app.get("/servers", response_model=GetServersResponse)
async def get_servers():
    servers = manager.get_servers()
    resp_model = {
        "servers": [
            SimpleMinecraftServer(id, server.server_config.name, server.server_config.version).__dict__ for id, server
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


@app.post("/servers", response_model=ServerCreationAccepted)
async def create_server(server: ServerCreationData):
    asyncio.create_task(manager.create_new_server(server.name, server.version))
    return JSONResponse({"message": "Server will created shortly"}, 202)
