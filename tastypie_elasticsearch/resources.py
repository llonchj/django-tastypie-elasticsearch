import re
import sys
#import uuid

from django.conf import settings
from django.conf.urls.defaults import url

from tastypie.bundle import Bundle
from tastypie.resources import Resource, DeclarativeMetaclass
from tastypie.paginator import Paginator
from tastypie.exceptions import NotFound, ImmediateHttpResponse
from tastypie.utils import trailing_slash
from tastypie import http

import pyes

class FixedPaginator(Paginator):
    # WORKAROUND
    # https://github.com/toastdriven/django-tastypie/issues/510
    def _generate_uri(self, limit, offset):
        if self.resource_uri is None:
            return None

        try:
            # QueryDict has a urlencode method that can handle multiple values for the same key
            request_params = self.request_data.copy()
            if 'limit' in request_params:
                del request_params['limit']
            if 'offset' in request_params:
                del request_params['offset']
            request_params.update({'limit': limit, 'offset': offset})
            encoded_params = request_params.urlencode()
        except AttributeError:
            request_params = {}

            for k, v in self.request_data.items():
                if isinstance(v, unicode):
                    request_params[k] = v.encode('utf-8')
                else:
                    request_params[k] = v

            request_params.update({'limit': limit, 'offset': offset})
            encoded_params = urlencode(request_params)

        return '%s?%s' % (
            self.resource_uri,
            encoded_params
        )

class ESDeclarativeMetaclass(DeclarativeMetaclass):
    """
    This class has the same functionality as its supper ``ModelDeclarativeMetaclass``.
    Only thing it does differently is how it sets ``object_class`` and ``queryset`` attributes.

    This is an internal class and is not used by the end user of tastypie_mongoengine.
    """

    def __new__(self, name, bases, attrs):
        meta = attrs.get('Meta')

        new_class = super(ESDeclarativeMetaclass, self).__new__(self, name, bases, attrs)
        #include_fields = getattr(new_class._meta, 'fields', [])
        #excludes = getattr(new_class._meta, 'excludes', [])
        #field_names = new_class.base_fields.keys()
        
        setattr(new_class._meta, "es_server", getattr(settings, 
            "ES_INDEX_SERVER", "127.0.0.1:9500"))
        setattr(new_class._meta, "es_timeout", getattr(settings, 
            "ES_INDEX_SERVER_TIMEOUT", 30))
        setattr(new_class._meta, "object_class", dict)
        setattr(new_class._meta, "paginator_class", FixedPaginator)

        return new_class

class ESResource(Resource):
    """
    ElasticSearch Resource
    """
    
    __metaclass__ = ESDeclarativeMetaclass
        
    _es = None
    def es__get(self):
        if self._es is None:
            self._es = pyes.ES(server=self._meta.es_server, 
                timeout=self._meta.es_timeout)
        return self._es
    es = property(es__get)
    
    def prepend_urls(self):
        """
        ElasticSearch uses non w as ID
        Provide a better dispatch_detail pattern.
        """
        return [
            url(r"^(?P<resource_name>%s)/(?P<%s>.*?)%s$" % (
                self._meta.resource_name, self._meta.detail_uri_name, 
                trailing_slash()), self.wrap_view('dispatch_detail'), 
                name="api_dispatch_detail"),
        ]
    
    def build_schema(self):
        return self.es.get_mapping(
            doc_type=self._meta.doc_type, indices=self._meta.indices)
    
    def full_dehydrate(self, bundle):
        #print bundle.data
        #print bundle.obj, bundle.obj.__class__
        bundle = super(ESResource, self).full_dehydrate(bundle)
        bundle.data.update(bundle.obj)
        #bundle.data["_id"] = bundle.obj.get_id()
        
        return bundle
    
    def full_hydrate(self, bundle):
        bundle = super(ESResource, self).full_hydrate(bundle)
        bundle.obj.update(bundle.data)
        return bundle

    def get_resource_uri(self, bundle_or_obj=None):
        if bundle_or_obj is None:
            result = super(ESResource, self).get_resource_uri(bundle_or_obj)
            return result

        kwargs = {
            'resource_name': self._meta.resource_name,
        }

        obj = (bundle_or_obj.obj if 
            isinstance(bundle_or_obj, Bundle) else bundle_or_obj)
        #print obj, obj.__class__
        #print isinstance(obj, dict)
        #print
        
        kwargs[self._meta.detail_uri_name] = (obj.get_id() if 
            isinstance(obj, pyes.es.ElasticSearchModel) else obj.get("_id"))

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name

        return self._build_reverse_url("api_dispatch_detail", kwargs=kwargs)

    def get_object_list(self, request):
        offset = int(request.GET.get("offset", 0))
        limit = int(request.GET.get("limit", self._meta.limit))
        
        q = request.GET.get("q")

        if q:
            query = pyes.StringQuery(q)
        else:
            query = pyes.MatchAllQuery()

        search = pyes.query.Search(
            query=query, start=offset, size=limit + offset)

        # refresh the index before query
        self.es.refresh(self._meta.indices[0])
        
        results = self.es.search(search, indices=self._meta.indices)
        return results
            
    def obj_get_list(self, request=None, **kwargs):
        # Filtering disabled for brevity...
        return self.get_object_list(request)

    def obj_get(self, request=None, **kwargs):

        offset = int(request.GET.get("offset", 20))
        limit = int(request.GET.get("limit", 20))
        pk = kwargs.get(self._meta.detail_uri_name)
        
        # refresh the index before query
        self.es.refresh(self._meta.indices[0])

        search = pyes.query.IdsQuery(pk)
        results = self.es.search(search, indices=self._meta.indices)
        
        if results.total == 0:
            #raise http.HttpNotFound("Nothing found with id='%s'" % pk)
            raise ImmediateHttpResponse(
                response=http.HttpNotFound("Nothing found with id='%s'" % pk))

        return results[0]

    def obj_create(self, bundle, request=None, **kwargs):
        bundle.obj = dict(kwargs)
        bundle = self.full_hydrate(bundle)
        pk = kwargs.get("pk", bundle.obj.get("_id"))
            #bundle.obj.get("_id", str(uuid.uuid1())) )

        result = self.es.index(bundle.obj, index=self._meta.indices[0],
            doc_type=self._meta.doc_type, id=pk)
        result.update(bundle.obj)
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
        result = self.es.delete(index=self._meta.indices[0],
            doc_type=self._meta.doc_type, id=pk)
        return result
    
    def rollback(self, bundles):
        pass
    