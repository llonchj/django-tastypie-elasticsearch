from django.conf import settings

from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.authorization import DjangoAuthorization

from tastypie_elasticsearch import resources

from test_project.test_app.models import *

class TestResource(resources.ESResource):
    id = fields.CharField(attribute='get_id')

    class Meta:
        resource_name = 'test'

        es_server = getattr(settings, 
            "ES_INDEX_SERVER", "127.0.0.1:9500")
        es_timeout = 30

        indices = [getattr(settings, 
            "ES_INDEX_NAME", "test")]
            
        doc_type = "test"
        
        object_class = dict
        
        authentication = Authentication()
        authorization = DjangoAuthorization()

    def determine_format(self, request):
        return "application/json"
