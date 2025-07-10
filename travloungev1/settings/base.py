from pathlib import Path
import firebase_admin
from firebase_admin import credentials

BASE_DIR = Path(__file__).resolve().parent.parent

from decouple import config, Csv
import os

# Get the environment (default to local 'dev' if not set)
DJANGO_ENV = os.getenv('DJANGO_ENV', '.env.dev')

# Load environment variables from the appropriate .env file
from decouple import Config, RepositoryEnv
env_config = Config(RepositoryEnv(DJANGO_ENV))
SECRET_KEY = env_config('SECRET_KEY')

from datetime import timedelta
# Development-specific settings
DEBUG = env_config('DEBUG', default=False, cast=bool)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'secrets',
    'customer',
    'admin_app',
    'billing',
    'store_admin',
    'sleeping_pod',
    'django_crontab',
    'corsheaders',
    'listing',
    'django_elasticsearch_dsl',
    'vendor',
    'car_wash',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'utils.authentication.authentication.EmailBackend',  # Custom Email Authentication Backend
    'django.contrib.auth.backends.ModelBackend',  # Default Django Authentication Backend
]

WSGI_APPLICATION = 'travloungev1.wsgi.application'

ROOT_URLCONF = 'travloungev1.urls'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]



# Load aws s3 variables using decouple
AWS_ACCESS_KEY_ID = env_config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env_config('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env_config('AWS_STORAGE_BUCKET_NAME')
AWS_QUERYSTRING_AUTH = env_config('AWS_QUERYSTRING_AUTH', default=False, cast=bool)
AWS_REGION_NAME = env_config('AWS_REGION_NAME')

#elastic search
ELASTICSEARCH_HOST=env_config('ELASTICSEARCH_HOST')
ELASTICSEARCH_USER=env_config('ELASTICSEARCH_USER')
ELASTICSEARCH_PASSWORD=env_config('ELASTICSEARCH_PASSWORD')
ELASTICSEARCH_INDEX=env_config('ELASTICSEARCH_INDEX')


LANGUAGE_CODE = 'en-us'

# TIME_ZONE = 'UTC'
TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_REGION_NAME}.amazonaws.com'
# Default static settings
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Default media settings
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

FCM_SERVER_KEY = env_config('FCM_SERVER_KEY')
FCM_DJANGO_SETTINGS = {
    "FCM_SERVER_KEY": FCM_SERVER_KEY,
}

OLD_FIREBASE_DB_URL = env_config('OLD_FIREBASE_DB_URL')

# firebase initialize
FIREBASE_CREDENTIALS_PATH = os.path.join(
    BASE_DIR.parent, 
    env_config('FIREBASE_CREDENTIALS_PATH')
)

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)


RAZORPAY_WEBHOOK_SECRET = env_config('RAZORPAY_WEBHOOK_SECRET')

EXPO_PUSH_URL = env_config('EXPO_PUSH_URL')

MSG91_AUTH_KEY = env_config('MSG_91_AUTH_KEY')
MSG91_EMAIL_API_BASE_URL = env_config("MSG91_EMAIL_API_BASE_URL", "https://control.msg91.com/api/v5/email/send")
MSG91_FROM_EMAIL = env_config("MSG91_FROM_EMAIL", "no-reply@travlounge.in")
MSG91_DOMAIN = env_config("MSG91_DOMAIN", "no-reply.travlounge.in")
MSG91_BOOKING_TEMPLATE_ID = env_config("MSG91_BOOKING_TEMPLATE_ID", "bookingtemplate_2")
MSG91_OTP_BOOKING_TEMPLATE_ID = env_config("MSG91_OTP_BOOKING_TEMPLATE_ID", "global_otp")

MSG91_OTP_API_BASE_URL = env_config("MSG91_OTP_API_BASE_URL", "https://control.msg91.com/api/v5/otp")
MSG91_VERIFY_OTP_API_BASE_URL = env_config("MSG91_VERIFY_OTP_API_BASE_URL", "https://control.msg91.com/api/v5/otp/verify")
MSG91_OTP_TEMPLATE_ID = env_config("MSG91_OTP_TEMPLATE_ID")

# Default numbers that bypass msg91 service
DEFAULT_NUMBERS = env_config('DEFAULT_NUMBERS', default='9496715606,7012983899').split(',')
DEFAULT_OTP = env_config('DEFAULT_OTP', default='4422')

# Celery Configuration
CELERY_BROKER_URL = env_config('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

SLEEPING_POD_TAX_RATE = env_config('SLEEPING_POD_TAX_RATE', cast=float)



 