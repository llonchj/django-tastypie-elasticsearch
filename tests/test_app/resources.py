from django.conf import settings

from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.authorization import DjangoAuthorization

from tastypie_elasticsearch import resources

class TestResource(resources.ElasticsearchResource):
    #id = fields.CharField(attribute='get_id')

    class Meta:
        resource_name = 'test'

        index = "test"
        doc_type = "test"
        
        authentication = Authentication()
        authorization = DjangoAuthorization()
        
        create_if_missing = True
        index_settings = {
            'settings': {
                'number_of_shards': 2,
                'number_of_replicas': 0,
            },
            'mappings':{
                'test': {
                    'first_name':{'type':'string', 'store':'yes'},
                }
            },
        }

    def determine_format(self, request):
        return "application/json"

