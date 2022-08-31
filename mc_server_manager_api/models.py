from dataclasses import dataclass
from typing import Union, Optional
from mc_server_interaction.server_manger.models import WorldGenerationSettings

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
    server_id: str
    name: str
    version: str
    status: str


class GetServersResponse(BaseModel):
    servers: list = Field(..., title="List of servers",
                          description="A list containing all servers")

    class Config:
        schema_extra = {
            "example": {
                "servers": [
                    SimpleMinecraftServer("1", "server1", "1.18.1", "RUNNING").__dict__,
                    SimpleMinecraftServer("2", "server2", "1.16.2", "STOPPED").__dict__
                ]
            }
        }


class ServerCreationData(BaseModel):
    name: str = Field(..., title="Display name of the server")
    version: str = Field(..., title="Server version to install",
                         description="The Minecraft version of this server."
                                     "\n\nFormat: 1.x.x")
    world_generation_settings: Optional[WorldGenerationSettings] = Field(None, title="World generation settings")

    class Config:
        schema_extra = {
            "example": {
                "name": "My Minecraft Server",
                "version": "1.19.2",
                "world_generation_settings": WorldGenerationSettings().__dict__
            }
        }


class ServerCreatedModel(BaseModel):
    message: str = Field(..., title="Message", description="Message to show the user")
    sid: str = Field(..., title="Sid of the server")

    class Config:
        schema_extra = {
            "example": {
                "message": "Server will be created shortly",
                "sid": "42"
            }
        }


class MinecraftServerModel(BaseModel):
    name: str = Field(..., title="Name of the server")
    sid: str = Field(..., title="Sid of the server")
    version: str = Field(..., title="Minecraft version of the server")
    status: str = Field(..., title="Status of the server")


class ServerCommand(BaseModel):
    command: str = Field(..., title="Server command")

    class Config:
        schema_extra = {
            "example": {
                "command": "say hello world"
            }
        }
