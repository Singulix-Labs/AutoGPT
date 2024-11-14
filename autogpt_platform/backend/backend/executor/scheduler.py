import logging
import os
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from autogpt_libs.utils.cache import thread_cached
from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy import MetaData, create_engine

from backend.data.block import BlockInput
from backend.executor.manager import ExecutionManager
from backend.util.service import AppService, expose, get_service_client
from backend.util.settings import Config


def _extract_schema_from_url(database_url) -> tuple[str, str]:
    """
    Extracts the schema from the DATABASE_URL and returns the schema and cleaned URL.
    """
    parsed_url = urlparse(database_url)
    query_params = parse_qs(parsed_url.query)

    # Extract the 'schema' parameter
    schema_list = query_params.pop("schema", None)
    schema = schema_list[0] if schema_list else "public"

    # Reconstruct the query string without the 'schema' parameter
    new_query = urlencode(query_params, doseq=True)
    new_parsed_url = parsed_url._replace(query=new_query)
    database_url_clean = str(urlunparse(new_parsed_url))

    return schema, database_url_clean


logger = logging.getLogger(__name__)


def log(msg, **kwargs):
    logger.warning("[ExecutionScheduler] " + msg, **kwargs)


def job_listener(event):
    """Logs job execution outcomes for better monitoring."""
    if event.exception:
        log(f"Job {event.job_id} failed.")
    else:
        log(f"Job {event.job_id} completed successfully.")


@thread_cached
def get_execution_client() -> ExecutionManager:
    return get_service_client(ExecutionManager)


def execute_graph(**kwargs):
    args = JobArgs(**kwargs)
    try:
        log(f"Executing recurring job for graph #{args.graph_id}")
        get_execution_client().add_execution(
            args.graph_id, args.input_data, args.user_id
        )
    except Exception as e:
        logger.exception(f"Error executing graph {args.graph_id}: {e}")


class JobArgs(BaseModel):
    graph_id: str
    input_data: BlockInput
    user_id: str
    graph_version: int
    cron: str


class JobInfo(JobArgs):
    id: str
    name: str
    next_run_time: str


class ExecutionScheduler(AppService):
    scheduler: BlockingScheduler

    @classmethod
    def get_port(cls) -> int:
        return Config().execution_scheduler_port

    @property
    @thread_cached
    def execution_client(self) -> ExecutionManager:
        return get_service_client(ExecutionManager)

    def run_service(self):
        load_dotenv()
        db_schema, db_url = _extract_schema_from_url(os.getenv("DATABASE_URL"))
        self.scheduler = BlockingScheduler(
            jobstores={
                "default": SQLAlchemyJobStore(
                    engine=create_engine(db_url),
                    metadata=MetaData(schema=db_schema),
                )
            }
        )
        self.scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self.scheduler.start()

    @expose
    def add_execution_schedule(
        self,
        graph_id: str,
        graph_version: int,
        cron: str,
        input_data: BlockInput,
        user_id: str,
    ) -> str:
        job_id = f"{user_id}_{graph_id}"
        job_args = JobArgs(
            graph_id=graph_id,
            input_data=input_data,
            user_id=user_id,
            graph_version=graph_version,
            cron=cron,
        )
        self.scheduler.add_job(
            execute_graph,
            CronTrigger.from_crontab(cron),
            id=job_id,
            kwargs=job_args.model_dump(),
            replace_existing=True,
        )
        log(f"Added job {job_id} with cron schedule '{cron}'")
        return job_id

    @expose
    def update_schedule(self, schedule_id: str, is_enabled: bool, user_id: str) -> str:
        job = self.scheduler.get_job(schedule_id)
        if not job:
            log(f"Job {schedule_id} not found.")
            return schedule_id

        job_args = JobArgs(**job.kwargs)
        if job_args.user_id != user_id:
            raise ValueError("User ID does not match the job's user ID.")

        if not is_enabled:
            log(f"Pausing job {schedule_id}")
            job.pause()
        else:
            log(f"Resuming job {schedule_id}")
            job.resume()

        return schedule_id

    @expose
    def get_execution_schedules(self, graph_id: str, user_id: str) -> list[JobInfo]:
        schedules = []
        for job in self.scheduler.get_jobs():
            job_args = JobArgs(**job.kwargs)
            if (
                job_args.graph_id == graph_id
                and job_args.user_id == user_id
                and job.next_run_time is not None
            ):
                schedules.append(
                    JobInfo(
                        id=job.id,
                        name=job.name,
                        next_run_time=job.next_run_time.isoformat(),
                        **job_args.model_dump(),
                    )
                )
        return schedules
