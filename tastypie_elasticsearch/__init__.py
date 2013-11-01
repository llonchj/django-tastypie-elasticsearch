# -*- coding: utf-8 -*-
import pkg_resources
VERSION = pkg_resources.get_distribution('django-tastypie-elasticsearch').version

__version__ = ".".join(map(str, VERSION[0:3])) + "".join(VERSION[3:])
__author__ = "Jordi Llonch"
__contact__ = "llonchj@gmail.com"
__homepage__ = "http://github.com/llonchj/django-tastypie-elasticsearch"
__docformat__ = "restructuredtext"

from elasticsearch.connection import *
from .resources import ElasticsearchResource
