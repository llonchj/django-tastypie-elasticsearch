# Django settings for test_project project

DEBUG = True

# We are not really using a relational database, but tests fail without
# defining it because flush command is being run, which expects it
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Make this unique, and don't share it with anybody
SECRET_KEY = 'sq=uf!nqw=aibl+y1&5pp=)b7pc=c$4hnh$om*_c48r)^t!ob)'

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'test_project.urls'

TEST_RUNNER = 'test_project.test_runner.ESEngineTestSuiteRunner'

INSTALLED_APPS = (
    'tastypie',
    'tastypie_elasticsearch',
    'test_project.test_app',
)

ES_INDEX_SERVER = "http://127.0.0.1:9200"
ES_INDEX_NAME = "test"

