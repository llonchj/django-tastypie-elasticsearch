#!/usr/bin/env python

import os
import re
from setuptools import setup, find_packages

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.test_project.settings")

def parse_requirements(file_name):
    requirements = []
    for line in open(file_name, 'r').read().split('\n'):
        if re.match(r'(\s*#)|(\s*$)', line):
            continue
        if re.match(r'\s*-e\s+', line):
            # TODO support version numbers
            requirements.append(re.sub(r'\s*-e\s+.*#egg=(.*)$', r'\1', line))
        elif re.match(r'\s*-f\s+', line):
            pass
        else:
            requirements.append(line)

    return requirements

setup(
    name = 'django-tastypie-elasticsearch',
    version = '0.3.0',
    description = "ElasticSearch Resource for django-tastypie.",
    long_description = open(os.path.join(os.path.dirname(__file__), 'README.md')).read(),
    author = 'Jordi Llonch',
    author_email = 'llonchj@gmail.com',
    url = 'https://github.com/llonchj/django-tastypie-elasticsearch',
    keywords = "REST RESTful tastypie elasticsearch django",
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
    install_requires=parse_requirements('requirements.txt'),
    tests_require=parse_requirements('requirements-test.txt'),
    test_suite = 'tests.runtests.runtests',
)
