from dataclasses import dataclass
from typing import Optional

from mc_server_interaction.interaction.models import Player
from mc_server_interaction.manager.models import WorldGenerationSettings

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
    sid: str
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
                "world_generation_settings": WorldGenerationSettings().__dict__,
            }
        }


class WorldGenerationData(BaseModel):
    name: str = Field(..., title="Name of the new world")
    data: Optional[WorldGenerationSettings] = Field(None, title="World generation settings")

    class Config:
        schema_extra = {
            "example": {
                "name": "New world",
                "data": WorldGenerationSettings().__dict__
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
    worlds: list = Field(..., title="Worlds")
    properties: dict = Field(..., title="Properties of the Minecraft server")
    backups: dict = Field(..., title="List of backups")

    class Config:
        schema_extra = {
            "example": {
                "name": "MyServer",
                "sid": "42",
                "version": "1.19.2",
                "status": "RUNNING",
                "worlds": [
                    {
                        "name": "world",
                        "path": "/path/to/servers/MyServer42/worlds/world",
                        "version": None,
                        "type": None
                    }
                ],
                "properties": {
                    "allow-flight": False,
                    "allow-nether": True,
                    "difficulty": "easy"
                },
                "backups": [
                    {
                        "time": 12345.54,
                        "world": "MyWorld",
                        "version": "1.19.2"
                    }
                ]
            }
        }


class ServerCommand(BaseModel):
    command: str = Field(..., title="Server command")

    class Config:
        schema_extra = {
            "example": {
                "command": "say hello world"
            }
        }


class PlayersResponse(BaseModel):
    online_players: list = Field(..., title="List of players that are currently online")
    op_players: list = Field(..., title="List of players that are op but currently not online")
    banned_players: list = Field(..., title="List of players that are banned")

    class Config:
        schema_extra = {
            "example": {

            }
        }


class AllWorldsResponse(BaseModel):
    world: dict = Field(..., title="Dict of sids with the respective lists of worlds")

    class Config:
        schema_extra = {
            "example": {
                1: [
                    {
                        "name": "My World",
                        "path": "/path/to/the/world",
                        "version": "1.19.2",
                        "type": "Default"
                    }
                ]
            }
        }


class ServerWorldsResponse(BaseModel):
    worlds: list = Field(..., title="List with all worlds of the server")

    class Config:
        schema_extra = {
            "example": {
                "worlds": [
                    {
                        "name": "My World",
                        "path": "/path/to/the/world",
                        "version": "1.19.2",
                        "type": "Default"
                    }
                ]
            }
        }


class WorldUploadResponse(BaseModel):
    message: str = Field(..., title="success")

    class Config:
        schema_extra = {
            "example": {
                "meesage": "success",
            }
        }


class ErrorModel(BaseModel):
    error: str = Field(..., title="Error message")


class PropertyModel(BaseModel):
    properties: dict = Field(..., title="Dict of updated properties")

    class Config:
        schema_extra = {
            "example": {
                "properties": {
                    "ram": 2048,
                    "generate-structures": True,
                    "...": "value"
                },
            }
        }


class PropertyResponse(BaseModel):
    fails: dict = Field(..., title="Dict of failed properties (Wrong type etc)")

    class Config:
        schema_extra = {
            "example": {
                "fails": {
                    "ram": "ValueError: invalid literal for int() with base 10: 'abc'"
                },
            }
        }


class WhitelistResponse(BaseModel):
    whitelisted_players: list = Field(..., title="List of whitelisted players")

    class Config:
        schema_extra = {
            "example": {
                "whitelisted_players": [
                    Player("ObiWanKenobi").__dict__,
                    Player("CountDooku", is_banned=True).__dict__
                ]
            }
        }


class CreateBackupModel(BaseModel):
    world_name: str = Field(..., title="Name of the world")