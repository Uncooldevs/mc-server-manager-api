from dataclasses import dataclass
from typing import Union

from pydantic import BaseModel, Field


class AvailableVersionsResponse(BaseModel):
    available_versions: list = Field(..., title="Supported Minecraft server versions",
                           description="A list containing all supported minecraft server versions")

    class Config:
        schema_extra = {
            "example": {
                "available_versions": ["1.18.1, 1.18, 1.17.1", "1.16.2-pre3"]
            }
        }

@dataclass
class SimpleMinecraftServer:
    server_id: int
    name: str
    version: str



class GetServersResponse(BaseModel):
    servers: list = Field(..., title="List of servers",
                          description="A list containing all servers")

    class Config:
        schema_extra = {
            "example": {
                "servers": [
                    SimpleMinecraftServer(1, "server1", "1.18.1").__dict__,
                    SimpleMinecraftServer(2, "server2", "1.16.2").__dict__
                ]
            }
        }


class ServerCreationData(BaseModel):
    name: str = Field(..., title="Display name of the server")
    version: str = Field(..., title="Server version to install",
                         description="The Minecraft version of this server."
                                     "\n\nFormat: 1.x.x")

    class Config:
        schema_extra = {
            "example": {
                "name": "My Minecraft Server",
                "version": "1.19.2",
            }
        }


class ServerCreationAccepted(BaseModel):
    message: str = Field(..., title="Message", description="Message to show the user")

    class Config:
        schema_extra = {
            "example": {
                "message": "Server will be created shortly"
            }
        }
