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
            "ES_INDEX_SERVER", "127.0.0.1:9500")
        es_timeout = 20
        
        allowed_methods = ('get', 'post', 'delete')
    
    _es = None
    def es__get(self):
        if self._es is None:
            self._es = pyes.ES(server=self._meta.es_server, 
                timeout=self._meta.es_timeout)
        return self._es
    es = property(es__get)
    
    def full_dehydrate(self, bundle):
        bundle.data.update(bundle.obj)
        bundle.data["_id"] = bundle.obj.get_id()
        return bundle
    
    def full_hydrate(self, bundle):
        bundle.obj.update(bundle.data)
        return bundle

    def get_resource_uri(self, bundle_or_obj=None):
        if bundle_or_obj is None:
            result = super(ESResource, self).get_resource_uri(bundle_or_obj)
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
        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", self._meta.limit))

        query = pyes.StringQuery(request.GET.get("q", "*"))
        search = pyes.query.Search(
            query=query, start=offset, size=limit)

        results = self.es.search(search, indices=self._meta.indices)

        return results
            
    def obj_get_list(self, request=None, **kwargs):
        # Filtering disabled for brevity...
        return self.get_object_list(request)

    def obj_get(self, request=None, **kwargs):

        offset = int(request.GET.get("offset", 20))
        limit = int(request.GET.get("limit", 20))
        id = kwargs.get(self._meta.detail_uri_name)
        search = pyes.query.IdsQuery(id)
        results = self.es.search(search, indices=self._meta.indices)
        return results[0]

    def obj_create(self, bundle, request=None, **kwargs):
        bundle.obj = dict(kwargs)
        bundle = self.full_hydrate(bundle)
        pk = kwargs.get("pk", None)

        result = self.es.index(bundle.obj.to_dict(), id=pk)

        return result
    
    def obj_update(self, bundle, request=None, **kwargs):
        return self.obj_create(bundle, request, **kwargs)

    #def obj_delete_list(self, request=None, **kwargs):
    #    bucket = self._bucket()
    #
    #    for key in bucket.get_keys():
    #        obj = bucket.get(key)
    #        obj.delete()
    
    def obj_delete(self, request=None, **kwargs):
        pk = kwargs.get("pk")
        return self.es.delete(id=pk)
    
    def rollback(self, bundles):
        pass
    