# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

logger = logging.getLogger(__name__)

import pkg_resources
VERSION = pkg_resources.get_distribution('django-tastypie-elasticsearch').version

__version__ = ".".join(map(str, VERSION[0:3])) + "".join(VERSION[3:])
__author__ = "Jordi Llonch"
__contact__ = "llonchj@gmail.com"
__homepage__ = "http://github.com/llonchj/django-tastypie-elasticsearch"
__docformat__ = "restructuredtext"

from .resources import ElasticSearch
