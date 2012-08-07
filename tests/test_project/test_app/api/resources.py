from django.conf import settings

from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.authorization import DjangoAuthorization

from tastypie_elasticsearch import resources

from test_project.test_app.models import *

class TestResource(resources.ElasticSearch):
    #id = fields.CharField(attribute='get_id')

    class Meta:
        resource_name = 'test'

        indices = [getattr(settings, 
            "ES_INDEX_NAME", "test")]
            
        doc_type = "test"
        
        authentication = Authentication()
        authorization = DjangoAuthorization()

    def determine_format(self, request):
        return "application/json"
