import os
from decouple import config
from celery import Celery
from dotenv import load_dotenv

# Set the default Django settings module for the 'celery' program.
dotenv_file = os.getenv('DJANGO_ENV', '.env.dev')
load_dotenv(dotenv_file)
django_env = config('DJANGO_ENVIRONMENT', default='dev')  # default is 'dev' if not set

os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'travloungev1.settings.{django_env}')
print("celeryEnv", django_env)

app = Celery('travloungev1')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')