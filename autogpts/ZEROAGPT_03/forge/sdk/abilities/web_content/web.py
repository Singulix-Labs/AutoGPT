"""
web content abilities
"""
import requests
from bs4 import BeautifulSoup

from ..registry import ability


@ability(
    name="html_to_file",
    description="get html from website and output to file",
    parameters=[
        {
            "name": "url",
            "description": "Website's url",
            "type": "string",
            "required": True,
        },
        {
            "name": "file_path",
            "description": "Path to the file",
            "type": "string",
            "required": True,
        },
    ],
    output_type="None",
)
async def html_to_file(agent, task_id: str, url: str, file_path: str) -> None:
    """
    html_to_file

    takes a string URL and returns HTML
    then writes HTML to file
    """
    try:
        req = requests.get(url)
        data = req.text.encode()

        agent.workspace.write(task_id=task_id, path=file_path, data=data)

        agent.memory.add(
            task_id=task_id,
            document=str(data),
            metadatas={
                "url": url,
                "file_name": file_path.split("/")[-1],
                "relative_path": file_path
            }
        )

        await agent.db.create_artifact(
            task_id=task_id,
            file_name=file_path.split("/")[-1],
            relative_path=file_path,
            agent_created=True,
        )
    except Exception as e:
        raise e


@ability(
    name="html_to_text_file",
    description="get html from website, convert it to text and output to file",
    parameters=[
        {
            "name": "url",
            "description": "Website's url",
            "type": "string",
            "required": True,
        },
        {
            "name": "file_path",
            "description": "Path to the file",
            "type": "string",
            "required": True,
        },
    ],
    output_type="None",
)
async def html_to_text_file(agent, task_id: str, url: str, file_path: str) -> None:
    """
    html_to_text_file

    takes a string URL and returns HTML
    then removes html and writes text to file
    """
    try:
        req = requests.get(url)

        html_soap = BeautifulSoup(req.text, "html.parser")

        agent.workspace.write(
            task_id=task_id, path=file_path, data=html_soap.get_text().encode()
        )

        agent.memory.add(
            ask_id=task_id,
            document=html_soap.get_text(),
            metadatas={
                "url": url,
                "file_name": file_path.split("/")[-1],
                "relative_path": file_path
            }
        )

        await agent.db.create_artifact(
            task_id=task_id,
            file_name=file_path.split("/")[-1],
            relative_path=file_path,
            agent_created=True,
        )
    except Exception as e:
        raise e


@ability(
    name="fetch_webpage",
    description="Retrieve the content of a webpage",
    parameters=[
        {
            "name": "url",
            "description": "Webpage URL",
            "type": "string",
            "required": True,
        }
    ],
    output_type="string",
)
async def fetch_webpage(agent, task_id: str, url: str) -> str:
    response = requests.get(url)

    agent.memory.add(
        task_id=task_id,
        document=response.text,
        metadatas={
            "url": url
        }
    )
    
    return response.text
