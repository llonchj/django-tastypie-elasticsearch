import itertools, re, sys

from django.conf import settings

from tastypie.bundle import Bundle
from tastypie.resources import Resource
from tastypie.paginator import Paginator

import pyes

class ESResource(Resource):
    """
    ElasticSearch Resource
    """
    class Meta:
        es_server = getattr(settings, 
            "ES_INDEX_SERVER", "http://127.0.0.1:9200/")
        es_timeout = 20
        
        allowed_methods = ['get']
    
    def get_resource_uri(self, bundle_or_obj=None):
        if bundle_or_obj is None:
            result = super(ESResource, self).get_resource_uri(bundle_or_obj)
            print result
            return result

        kwargs = {
            'resource_name': self._meta.resource_name,
        }

        if isinstance(bundle_or_obj, Bundle):
            kwargs[self._meta.detail_uri_name] = bundle_or_obj.obj.get_id()
        else:
            kwargs[self._meta.detail_uri_name] = bundle_or_obj.get_id()

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name

        return self._build_reverse_url("api_dispatch_detail", kwargs=kwargs)

    def get_object_list(self, request):
        es = pyes.ES(self._meta.es_server, timeout=self._meta.es_timeout)

        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", self._meta.limit))

        query = pyes.StringQuery(request.GET.get("q", "*"))
        search = pyes.query.Search(
            query=query, start=offset, size=limit)

        results = es.search(search, indices=self._meta.indices)

        return results
            
    def obj_get_list(self, request=None, **kwargs):
        # Filtering disabled for brevity...
        return self.get_object_list(request)

    def obj_get(self, request=None, **kwargs):
        es = pyes.ES(self._meta.es_server, timeout=self._meta.es_timeout)

        offset = int(request.GET.get("offset", 20))
        limit = int(request.GET.get("limit", 20))
        id = kwargs.get(self._meta.detail_uri_name)
        search = pyes.query.IdsQuery(id)
        results = es.search(search, indices=self._meta.indices)
        return results[0]

        