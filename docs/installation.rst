Installation
============

Using pip_ simply by doing::

    pip install django-tastypie-elasticsearch
    
or by installing from source with::
    
    python setup.py install

.. _pip: http://pypi.python.org/pypi/pip

In your settings.py add ``tastypie`` and ``tastypie_elasticsearch`` to ``INSTALLED_APPS``::

    INSTALLED_APPS += (
        'tastypie',
        'tastypie_elasticsearch',
    )

You must also add in your settings::

    ES_INDEX_SERVER = 'http://127.0.0.1:9200/'

