#!/usr/bin/env python

import os
from setuptools import setup, find_packages

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.test_project.settings")

import tastypie_elasticsearch

if __name__ == '__main__':
    setup(
        name = 'django-tastypie-elasticsearch',
        version = tastypie_elasticsearch.__version__,
        description = "ElasticSearch support for django-tastypie.",
        long_description = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read(),
        author = 'Jordi Llonch',
        author_email = 'llonchj@gmail.com',
        url = 'https://github.com/llonchj/django-tastypie-elasticsearch',
        keywords = "REST RESTful tastypie pyes elasticsearch django",
        license = 'AGPLv3',
        packages = find_packages(exclude=('*.tests', '*.tests.*', 'tests.*', 'tests')),
        classifiers = (
            'Development Status :: 4 - Beta',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: GNU Affero General Public License v3',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Framework :: Django',
        ),
        zip_safe = True,
        install_requires = (
            'Django>=1.4',
            'django-tastypie>=0.9.11',
            'pyes>=0.19.1',
        ),
        test_suite = 'tests.runtests.runtests',
        tests_require = (
            'Django>=1.4',
            'django-tastypie>=0.9.11',
            'pyes>=0.19.1',
        ),
    )
