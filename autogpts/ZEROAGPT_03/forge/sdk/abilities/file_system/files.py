from typing import List

from ..registry import ability


@ability(
    name="list_files",
    description="List files in a directory",
    parameters=[
        {
            "name": "path",
            "description": "Path to the directory",
            "type": "string",
            "required": True,
        }
    ],
    output_type="list[str]",
)
async def list_files(agent, task_id: str, path: str) -> List[str]:
    """
    List files in a workspace directory
    """
    return agent.workspace.list(task_id=task_id, path=path)


@ability(
    name="write_file",
    description="Write data to a file",
    parameters=[
        {
            "name": "file_path",
            "description": "Path to the file including file name",
            "type": "string",
            "required": True,
        },
        {
            "name": "data",
            "description": "Data to write to the file",
            "type": "bytes",
            "required": True,
        },
    ],
    output_type="None",
)
async def write_file(agent, task_id: str, file_path: str, data: bytes) -> None:
    """
    Write data to a file
    """
    if isinstance(data, str):
        data = data.encode()

    agent.workspace.write(task_id=task_id, path=file_path, data=data)

    agent.memory.add(
        task_id=task_id,
        document=str(data),
        metadatas={
            "file_name": file_path.split("/")[-1],
            "relative_path": file_path
        }
    )
    
    write_artifact = await agent.db.create_artifact(
        task_id=task_id,
        file_name=file_path.split("/")[-1],
        relative_path=file_path,
        agent_created=True,
    )

    # adding artifacts to task
    await agent.db.add_artifact_task(
        task_id=task_id, 
        artifact_id=write_artifact.artifact_id
    )


@ability(
    name="read_file",
    description="Read data from a file",
    parameters=[
        {
            "name": "file_path",
            "description": "Path to the file including file name",
            "type": "string",
            "required": True,
        },
    ],
    output_type="bytes",
)
async def read_file(agent, task_id: str, file_path: str) -> bytes:
    """
    Read data from a file
    """
    return agent.workspace.read(task_id=task_id, path=file_path)
