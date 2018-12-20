import docker

from time import sleep, time
from decouple import config
from .. import settings
from celery_worker_on_demand import CeleryWorkerOnDemand
from celery_worker_on_demand import Agent
from celery_worker_on_demand import UpWorker
from celery_worker_on_demand import DownWorker


LABEL_KEY = 'bothub-nlp-wod.name'
EMPTY = 'empty-value'
ENV_LIST = [
    '{}={}'.format(var, config(var, default=EMPTY))
    for var in [
        'SECRET_KEY',
        'DEBUG',
        'DEVELOPMENT_MODE',
        'ALLOWED_HOSTS',
        'DEFAULT_DATABASE',
        'LANGUAGE_CODE',
        'TIME_ZONE',
        'EMAIL_HOST',
        'EMAIL_PORT',
        'DEFAULT_FROM_EMAIL',
        'SERVER_EMAIL',
        'EMAIL_HOST_USER',
        'EMAIL_HOST_PASSWORD',
        'EMAIL_USE_SSL',
        'EMAIL_USE_TLS',
        'ADMINS',
        'CSRF_COOKIE_DOMAIN',
        'CSRF_COOKIE_SECURE',
        'BOTHUB_WEBAPP_BASE_URL',
        'BOTHUB_NLP_BASE_URL',
        'CHECK_ACCESSIBLE_API_URL',
        'SEND_EMAILS',
        'SUPPORTED_LANGUAGES',
        'LOGGER_FORMAT',
        'LOGGER_LEVEL',
        'NLP_SENTRY_CLIENT',
        'CELERY_BROKER_URL',
        'CELERY_BACKEND_URL',
        'BOTHUB_NLP_WORKER_ON_DEMAND_PORT',
        'BOTHUB_NLP_DOCKER_CLIENT_BASE_URL',
        'BOTHUB_NLP_WORKER_DOCKER_IMAGE_NAME',
        'BOTHUB_NLP_WORKER_DOWN_TIME',
        'BOTHUB_NLP_WORKER_NETWORKS',
        'BOTHUB_NLP_AGROUP_LANGUAGE_QUEUE',
        'BOTHUB_NLP_WORKER_BLOCK_ON_SWARM_MANAGER',
    ]
]

docker_client = docker.DockerClient(
    base_url=settings.BOTHUB_NLP_DOCKER_CLIENT_BASE_URL,
)
running_services = {}
last_services_lookup = 0


def services_lookup():
    global running_services
    global last_services_lookup
    if (time() - last_services_lookup) < 5:
        return False
    running_services = {}
    for service in docker_client.services.list():
        service_labels = service.attrs.get('Spec', {}).get('Labels')
        if LABEL_KEY in service_labels:
            queue_name = service_labels.get(LABEL_KEY)
            running_services[queue_name] = service
    last_services_lookup = time()
    return True


class MyUpWorker(UpWorker):
    def run(self):
        global running_services
        services_lookup()
        service = running_services.get(self.queue.name)
        if not service:
            queue_language = self.queue.name.split(':')[1] \
                if ':' in self.queue.name else self.queue.name
            constraints = []
            if settings.BOTHUB_NLP_WORKER_BLOCK_ON_SWARM_MANAGER:
                constraints.append('node.role == worker')
            docker_client.services.create(
                f'{settings.BOTHUB_NLP_WORKER_DOCKER_IMAGE_NAME}:' +
                f'{queue_language}',
                [
                    'celery',
                    'worker',
                    '-A',
                    'bothub_nlp.core.celery',
                    '-c',
                    '1',
                    '-l',
                    'INFO',
                    '-E',
                    '-Q',
                    self.queue.name,
                ],
                env=list(
                    filter(
                        lambda v: not v.endswith(EMPTY),
                        ENV_LIST,
                    )
                ),
                labels={
                    LABEL_KEY: self.queue.name,
                },
                networks=settings.BOTHUB_NLP_WORKER_NETWORKS,
                constraints=constraints,
            )
        while not self.queue.has_worker:
            sleep(1)


class MyDownWorker(DownWorker):
    def run(self):
        global running_services
        services_lookup()
        service = running_services.get(self.queue.name)
        service.remove()
        running_services[self.queue.name] = None


class MyAgent(Agent):
    def flag_down(self, queue):
        global running_services
        if queue.size > 0:
            return False
        if not queue.has_worker:
            return False
        services_lookup()
        service = running_services.get(queue.name)
        if not service:
            return False
        last_interaction = 0
        for worker in queue.workers:
            last_interaction = sorted(
                [
                    last_interaction,
                    (worker.last_task_received_at or 0),
                    (worker.last_task_started_at or 0),
                    (worker.last_task_succeeded_at or 0),
                ],
                reverse=True,
            )[0]
        if last_interaction == 0:
            return False
        last_interaction_diff = time() - last_interaction
        if last_interaction_diff > (settings.BOTHUB_NLP_WORKER_DOWN_TIME * 60):
            return True
        return False


class MyDemand(CeleryWorkerOnDemand):
    Agent = MyAgent
    UpWorker = MyUpWorker
    DownWorker = MyDownWorker
