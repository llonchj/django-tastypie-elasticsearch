=====
Usage
=====

Usage for simple cases is very similar as with Tastypie. You should read
their tutorial_ first.

.. _tutorial: http://django-tastypie.readthedocs.org/en/latest/tutorial.html

The main difference is when you are defining API resource files. There you must use ``tastypie_elasticsearch.resources.ElasticSearch`` instead of ``ModelResource`` or ``Resource``.

Simple Example
==============

::
    from django.conf import settings

    from tastypie import authorization
    from tastypie_elasticsearch import resources
    from test_app import documents
    
    class PersonResource(resources.ElasticSearch):
        class Meta:

            es_server = getattr(settings, 
                "ES_INDEX_SERVER", "http://127.0.0.1:9200/")
            es_timeout = 20
        
            indices = ["my_elasticsearch_index"]

