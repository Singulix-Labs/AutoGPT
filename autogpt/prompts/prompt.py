from colorama import Fore

from autogpt.api_manager import ApiManager
from autogpt.config.ai_config import AIConfig
from autogpt.config.config import Config
from autogpt.logs import logger
from autogpt.prompts.generator import PromptGenerator
from autogpt.setup import prompt_user
from autogpt.utils import clean_input
from autogpt.project.project_manager import ProjectManager

CFG = Config()


def build_default_prompt_generator() -> PromptGenerator:
    """
    This function generates a prompt string that includes various constraints,
        commands, resources, and performance evaluations.

    Returns:
        str: The generated prompt string.
    """

    # Initialize the PromptGenerator object
    prompt_generator = PromptGenerator()

    # Add constraints to the PromptGenerator object
    prompt_generator.add_constraint(
        "~4000 word limit for short term memory. Your short term memory is short, so"
        " immediately save important information to files."
    )
    prompt_generator.add_constraint(
        "If you are unsure how you previously did something or want to recall past"
        " events, thinking about similar events will help you remember."
    )
    prompt_generator.add_constraint("No user assistance")
    prompt_generator.add_constraint(
        'Exclusively use the commands listed in double quotes e.g. "command name"'
    )

    # Define the command list
    commands = [
        ("Do Nothing", "do_nothing", {"reason": "<reason>"}),
        ("Task Complete (Shutdown)", "task_complete", {"reason": "<reason>"}),
    ]

    # Add commands to the PromptGenerator object
    for command_label, command_name, args in commands:
        prompt_generator.add_command(command_label, command_name, args)

    # Add resources to the PromptGenerator object
    prompt_generator.add_resource(
        "Internet access for searches and information gathering."
    )
    prompt_generator.add_resource("Long Term memory management.")
    prompt_generator.add_resource(
        "GPT-3.5 powered Agents for delegation of simple tasks."
    )
    prompt_generator.add_resource("File output.")

    # Add performance evaluations to the PromptGenerator object
    prompt_generator.add_performance_evaluation(
        "Continuously review and analyze your actions to ensure you are performing to"
        " the best of your abilities."
    )
    prompt_generator.add_performance_evaluation(
        "Constructively self-criticize your big-picture behavior constantly."
    )
    prompt_generator.add_performance_evaluation(
        "Reflect on past decisions and strategies to refine your approach."
    )
    prompt_generator.add_performance_evaluation(
        "Every command has a cost, so be smart and efficient. Aim to complete tasks in"
        " the least number of steps."
    )
    prompt_generator.add_performance_evaluation("Write all code to a file.")
    return prompt_generator


def construct_main_ai_config() -> AIConfig:
    """Construct the prompt for the AI to respond to

    Returns:
        str: The prompt string
    """
    config = AIConfig.load(CFG.ai_session)
    if CFG.skip_project and config.project_name:
        logger.typewriter_log("Project:", Fore.GREEN, config.project_name)
        logger.typewriter_log("AI Name:", Fore.GREEN, config.ai_name)
        logger.typewriter_log("AI Role:", Fore.GREEN, config.ai_role)
        logger.typewriter_log("AI Goals:", Fore.GREEN, f"{config.ai_goals}")
        logger.typewriter_log(
            "API Budget:",
            Fore.GREEN,
            "infinite" if config.api_budget <= 0 else f"${config.api_budget}",
        )
    elif config.project_name:
        logger.typewriter_log(
            "Welcome back! ",
            Fore.GREEN,
            f"Would you like to continue working on {config.project_name}?",
            speak_text=True,
        )
        should_continue = clean_input(
            f"""Continue with the last session?
Project: {config.project_name}
AI Name: {config.ai_name}
AI Role: {config.ai_role}
AI Goals: {config.ai_goals}
Continue (y/n): """
        )
        if should_continue.lower() == "n":
            config = AIConfig()
    else:
        if CFG.skip_reprompt and config.ai_name:
            logger.typewriter_log("Name :", Fore.GREEN, config.ai_name)
            logger.typewriter_log("Role :", Fore.GREEN, config.ai_role)
            logger.typewriter_log("Goals:", Fore.GREEN, f"{config.ai_goals}")
            logger.typewriter_log(
                "API Budget:",
                Fore.GREEN,
                "infinite" if config.api_budget <= 0 else f"${config.api_budget}",
            )
        elif config.ai_name:
            logger.typewriter_log(
                "Welcome back! ",
                Fore.GREEN,
                f"Continue with the last session as {config.ai_name}?",
                speak_text=True,
            )
            
            should_continue = clean_input(
                f"""Role:  {config.ai_role}
Goals: {config.ai_goals}
API Budget: {"infinite" if config.api_budget <= 0 else f"${config.api_budget}"}
Continue (y/n): """
            )
            if should_continue.lower() == "n":
                config = AIConfig()

    if not config.ai_name:
        configs = prompt_user()
        
        for config in configs:
            config.save()
    
    print("this CONFIG", config)
    if config.project_name:
        ProjectManager.project_agents(config.project_name)

    # set the total api budget
    api_manager = ApiManager()
    api_manager.set_total_budget(config.api_budget)

    # Agent Created, print message
    logger.typewriter_log(
        config.ai_name,
        Fore.LIGHTBLUE_EX,
        "has been created with the following details:",
        speak_text=True,
    )

    # Print the ai config details
    # Name
    logger.typewriter_log("Name:", Fore.GREEN, config.ai_name, speak_text=False)
    # Role
    logger.typewriter_log("Role:", Fore.GREEN, config.ai_role, speak_text=False)
    # Goals
    logger.typewriter_log("Goals:", Fore.GREEN, "", speak_text=False)
    for goal in config.ai_goals:
        logger.typewriter_log("-", Fore.GREEN, goal, speak_text=False)

    return config
