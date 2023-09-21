from .registry import ability
from ..forge_log import ForgeLogger

logger = ForgeLogger(__name__)

@ability(
    name="finish",
    description="Use this to shut down once you have accomplished all of your goals,"
                " or when there are insurmountable problems that make it impossible"
                " for you to finish your task.",
    parameters=[
        {
            "name": "reason",
            "description": "A summary to the user of how the goals were accomplished",
            "type": "string",
            "required": True,
        }
    ],
    output_type="None"
)
def finish(agent, task_id: str, reason: str,) -> str:
    """
    A function that takes in a string and exits the program

    Parameters:
        reason (str): A summary to the user of how the goals were accomplished.
    Returns:
        A result string from create chat completion. A list of suggestions to
            improve the code.
    """
    logger.info(reason, extra={"title": "Shutting down...\n"})
    return reason
