# -*- coding: utf-8 -*-
"""
tastypie.Resource definitions for Elasticsearch

"""

import re
import sys
from copy import deepcopy

from django.conf import settings
from django.conf.urls import url

from tastypie import http
from tastypie.bundle import Bundle
from tastypie.fields import NOT_PROVIDED
from tastypie.resources import Resource, DeclarativeMetaclass
from tastypie.exceptions import NotFound, ImmediateHttpResponse
from tastypie.utils import trailing_slash

import elasticsearch
import elasticsearch.exceptions
from elasticsearch.connection import Urllib3HttpConnection

from paginator import ElasticsearchResult, ElasticsearchPaginator

class ElasticsearchDeclarativeMetaclass(DeclarativeMetaclass):
    """
    This class has the same functionality as its supper ``ModelDeclarativeMetaclass``.
    Changing only some Elasticsearch intrinsics
    """

    def __new__(self, name, bases, attrs):
        meta = attrs.get('Meta')

        new_class = super(ElasticsearchDeclarativeMetaclass, 
            self).__new__(self, name, bases, attrs)

        override = {
            'object_class': dict,
            'include_mapping_fields': True,
            'paginator_class': ElasticsearchPaginator,
        }
        defaults = {
            'es_server': getattr(settings, "ES_SERVER", "127.0.0.1:9200"),
            'es_connection_class': Urllib3HttpConnection,
            'es_timeout': 30,
        }
        for k,v in override.iteritems():
            setattr(new_class._meta, k, v)

        for k,v in defaults.iteritems():
            if not hasattr(new_class._meta, k):
                setattr(new_class._meta, k, v)

        return new_class

class ElasticsearchResource(Resource):
    """
    Elasticsearch Base Resource
    
    """
    
    __metaclass__ = ElasticsearchDeclarativeMetaclass

    _es = None
    def es__get(self):
        if self._es is None:
            hosts = []
            for server in self._meta.es_server.split(","):
                host, port = server.strip().split(":")
                hosts.append({"host":host, "port":port})

            self._es = elasticsearch.Elasticsearch(hosts=hosts, 
                                                   connection_class=self._meta.es_connection_class,
                                                   timeout=self._meta.es_timeout)
        return self._es
    client = property(es__get)

    def prepend_urls(self):
        """Override Resource url map to fit search Id syntax"""
        resource_name = self._meta.resource_name
        tr = trailing_slash()
        return [
            # percolate implementation
            url(r"^(?P<resource_name>%s)/percolate%s$" % (resource_name, tr), 
                self.wrap_view('get_percolate'), name="api_get_percolate"),

            # default implementation
            url(r"^(?P<resource_name>%s)%s$" % (resource_name, tr), 
                self.wrap_view('dispatch_list'), name="api_dispatch_list"),
            url(r"^(?P<resource_name>%s)/schema%s$" % (resource_name, tr), 
                self.wrap_view('get_schema'), name="api_get_schema"),
            url(r"^(?P<resource_name>%s)/set/(?P<%s_list>.*?)%s$" % (resource_name, 
                self._meta.detail_uri_name, tr), self.wrap_view('get_multiple'), 
                name="api_get_multiple"),
            url(r"^(?P<resource_name>%s)/(?P<%s>.*?)%s$" % (resource_name, 
                self._meta.detail_uri_name, tr), self.wrap_view('dispatch_detail'), 
                name="api_dispatch_detail"),
            
        ]

    def build_schema(self):
        schema = super(ElasticsearchResource, self).build_schema()
        
        if self._meta.include_mapping_fields:
            mapping = self.client.indices.get_mapping(self._meta.index, self._meta.doc_type)
            mapping_fields = mapping[self._meta.doc_type]["properties"]

            fields = schema["fields"]

            for key, v in mapping_fields.iteritems():
                if key not in fields:
                    fields[key] = {
                        "blank": v.get("default", True),
                        "default": v.get("default", None),
                        "help_text": v.get("help_text", key),
                        "nullable": v.get("nullable", "unknown"),
                        "readonly": v.get("readonly", True),
                        "unique": v.get("unique", key in ["id",]),
                        "type": v.get("type", "unknown"),
                    }
            schema["fields"] = fields

        return schema
    
    def full_dehydrate(self, bundle, for_list=False):
        bundle = super(ElasticsearchResource, self).full_dehydrate(bundle, for_list)

        kwargs = dict(resource_name=self._meta.resource_name, pk=bundle.obj.get("_id"))
        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name
        bundle.data["resource_uri"] = self._build_reverse_url('api_dispatch_detail', kwargs=kwargs)

        bundle.data.update(bundle.obj.get("_source", bundle.obj.get("fields")))
        return bundle
    
    def full_hydrate(self, bundle):
        bundle = super(ElasticsearchResource, self).full_hydrate(bundle)
        bundle.obj.update(bundle.data)
        return bundle

    def get_resource_uri(self, bundle_or_obj=None):
        if bundle_or_obj is None:
            result = super(ElasticsearchResource, self).get_resource_uri(bundle_or_obj)
            return result
    
        obj = (bundle_or_obj.obj if 
            isinstance(bundle_or_obj, Bundle) else bundle_or_obj)

        kwargs = {
            'resource_name': self._meta.resource_name,
            'pk': obj.get('_id'),
        }
        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name
            
        return self._build_reverse_url("api_dispatch_detail", kwargs=kwargs)

    def get_sorting(self, request, key="order_by"):
        order_by = request.GET.get(key)
        if order_by:
            l = []
            
            items = [i.strip() for i in order_by.split(",")]
            for item in items:
                order = "asc"
                if item.startswith("-"):
                    item = item[1:]
                    order = "desc"
                l.append({item:order})
            return l
        return None
    
    def build_query(self, request):
        sort = self.get_sorting(request)
        query = []

        for key, value in request.GET.items():
            if key not in ["offset", "limit", "query_type", "format", 'order_by']:
                q = {".".join([self._meta.doc_type, key]): value}
                query.append({"text":q})

        if len(query) is 0:
            # show all
            query.append({"match_all": {}})

        return {
            "query": {
                "bool": {
                    "must": query,
                },
            },
            "from": long(request.GET.get("offset", 0)),
            "size": long(request.GET.get("limit", self._meta.limit)),
            "sort": sort or [],
        }
        
    
    def get_object_list(self, request):
        try:
            kwargs = dict()
            kwargs['body'] = self.build_query(request)
            result = self.client.search(self._meta.index, self._meta.doc_type, **kwargs)
        except Exception, exc:
            response = http.HttpBadRequest(str(exc), content_type="text/plain")
            raise ImmediateHttpResponse(response)
        else:
            return ElasticsearchResult(result, kwargs)
            
    def obj_get_list(self, request=None, **kwargs):
        # Filtering disabled for brevity...
        return self.get_object_list(kwargs['bundle'].request)

    def obj_get(self, request=None, **kwargs):
        pk = kwargs.get("pk")
        try:
            result =  self.client.get(self._meta.index, pk, self._meta.doc_type)
        except elasticsearch.exceptions.NotFoundError, exc:
            response = http.HttpNotFound("Not found", content_type="text/plain")
            raise ImmediateHttpResponse(response)
        except Exception, exc:
            msg = "%s(%s)" % (exc.__class__.__name__, exc)
            response = http.HttpApplicationError(msg, content_type="text/plain")
            raise ImmediateHttpResponse(response)
        else:
            return result

    def obj_create(self, bundle, request=None, **kwargs):
        bundle.obj = dict(kwargs)
        bundle = self.full_hydrate(bundle)
        pk = kwargs.get("pk", bundle.obj.get("_id"))

        result = self.client.index(self._meta.index, self._meta.doc_type, bundle.obj, 
                                   id=pk, refresh=True)
        result.update(bundle.obj)
        return result
    
    def obj_update(self, bundle, request=None, **kwargs):
        bundle.obj = dict(kwargs)
        bundle = self.full_hydrate(bundle)
        pk = kwargs.get('pk', bundle.obj.get('_id'))

        result = self.client.update(self._meta.index, self._meta.doc_type, bundle.obj, 
                                    id=pk, refresh=True)
        result.update(bundle.obj)
        return result
    
    def obj_delete_list(self, request=None, **kwargs):
        pk = kwargs.get('pk')
        query = {}
        result = self.client.delete_by_query(self._meta.index, self._meta.doc_type, query)
        return result

    def obj_delete(self, request=None, **kwargs):
        pk = kwargs.get('pk')
        result = self.client.delete(self._meta.index, self._meta.doc_type, id=pk)
        return result

    def get_percolate(self, request, **kwargs):
        """Search interface"""
        return 1

    def get_search(self, request, **kwargs):
        """Search interface"""
        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)
        self.throttle_check(request)

        result = self.get_object_list(request)
        paginator = self._meta.paginator_class(request.GET, result, 
            resource_uri=self.get_resource_uri(), limit=self._meta.limit, 
            max_limit=self._meta.max_limit, collection_name=self._meta.collection_name)

        to_be_serialized = paginator.page()

        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle, for_list=True))

        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        return self.create_response(request, to_be_serialized)
