import os
from decouple import config
from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv

# Load the environment file specified by DJANGO_ENV (default to .env)
dotenv_file = os.getenv('DJANGO_ENV', '.env.dev')
load_dotenv(dotenv_file)

print("dotenv_file", dotenv_file)

# Dynamically set the settings module based on the DJANGO_ENVIRONMENT variable
django_env = config('DJANGO_ENVIRONMENT', default='dev')  # default is 'dev' if not set
print("DJANGO_ENVIRONMENT from env", django_env)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'travloungev1.settings.{django_env}')

# Initialize the WSGI application
application = get_wsgi_application()
