from autogpt_server.blocks import agent, sample, reddit, text, ai, wikipedia, discord, open_weather_map
from autogpt_server.data.block import Block

AVAILABLE_BLOCKS = {
    block.id: block
    for block in [v() for v in Block.__subclasses__()]
}

__all__ = ["agent", "ai", "sample", "reddit", "text", "AVAILABLE_BLOCKS", "wikipedia", "discord", "open_weather_map"]
