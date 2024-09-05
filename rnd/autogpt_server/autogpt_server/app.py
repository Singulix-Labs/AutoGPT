from typing import TYPE_CHECKING

from .util.logging import configure_logging

if TYPE_CHECKING:
    from autogpt_server.util.process import AppProcess


def run_processes(*processes: "AppProcess", **kwargs):
    """
    Execute all processes in the app. The last process is run in the foreground.
    """
    try:
        configure_logging()

        for process in processes[:-1]:
            process.start(background=True, **kwargs)

        # Run the last process in the foreground
        processes[-1].start(background=False, **kwargs)
    except Exception as e:
        for process in processes:
            process.stop()
        raise e


def main(**kwargs):
    """
    Run all the processes required for the AutoGPT-server (REST and WebSocket APIs).
    """

    from autogpt_server.executor import ExecutionManager, ExecutionScheduler
    from autogpt_server.server import AgentServer, WebsocketServer
    from autogpt_server.util.service import PyroNameServer

    run_processes(
        PyroNameServer(),
        ExecutionManager(),
        ExecutionScheduler(),
        WebsocketServer(),
        AgentServer(),
        **kwargs,
    )


if __name__ == "__main__":
    main()
