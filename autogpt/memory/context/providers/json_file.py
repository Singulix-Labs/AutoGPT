from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
import orjson

from autogpt.config import Config
from autogpt.logs import logger

from ..memory_item import MemoryItem, MemoryItemRelevance
from ..utils import Embedding, get_embedding
from .abstract import ContextMemoryProvider


class JSONFileMemory(ContextMemoryProvider):
    """Memory backend that stores memories in a JSON file"""

    SAVE_OPTIONS = orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_SERIALIZE_DATACLASS

    file_path: Path
    memories: list[MemoryItem]

    def __init__(self, cfg: Config) -> None:
        """Initialize a class instance

        Args:
            cfg: Config object

        Returns:
            None
        """
        workspace_path = Path(cfg.workspace_path)
        self.file_path = workspace_path / f"{cfg.memory_index}.json"
        self.file_path.touch()
        logger.debug(f"Initialized {__name__} with index path {self.file_path}")

        self.memories = []
        self.save_index()

    def add(self, item: MemoryItem):
        self.memories.append(item)
        self.save_index()
        return len(self.memories)

    def get(self, query: str) -> MemoryItemRelevance | None:
        """
        Gets the data from the memory that is most relevant to the given query.

        Args:
            data: The data to compare to.

        Returns: The most relevant Memory
        """
        result = self.get_relevant(query, 1)
        return result[0] if result else None

    def get_relevant(self, query: str, k: int) -> list[MemoryItemRelevance]:
        """
        Returns the top-k most relevant memories for the given query

        Args:
            query: the query to compare stored memories to
            k: the number of relevant memories to fetch

        Returns:
            list[MemoryItemRelevance] containing the top [k] relevant memories
        """
        if len(self.memories) < 1:
            return []

        e_query: Embedding = get_embedding(query)

        logger.debug(f"Searching for {k} relevant items; {len(self.memories)} in index")

        relevances = [m.relevance_for(query, e_query) for m in self.memories]
        logger.debug(f"Memory match scores: {relevances}")

        # take last k items and reverse
        top_k_indices = np.argsort([r.score for r in relevances])[-k:][::-1]

        return [relevances[i] for i in top_k_indices]

    def get_stats(self) -> tuple[int, int]:
        """
        Returns: The stats of the local cache in a tuple (n_memories, n_chunks)
        """
        return len(self.memories), functools.reduce(
            lambda t, m: t + len(m.e_chunks), self.memories, 0
        )

    def clear(self):
        """Clears the data in memory."""
        self.memories = []
        self.save_index()

    def save_index(self):
        logger.debug(f"Saving memory index to file {self.file_path}")
        with self.file_path.open("wb") as f:
            return f.write(orjson.dumps(self.memories, option=self.SAVE_OPTIONS))
