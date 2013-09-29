# -*- coding: utf-8 -*-
"""
tastypie.Resource definitions for ElasticSearch

"""

import re
import sys

from django.conf import settings
from django.conf.urls.defaults import url
from django.core.paginator import Paginator, InvalidPage
from django.http import HttpResponse

from tastypie.fields import NOT_PROVIDED
from tastypie.bundle import Bundle
from tastypie.resources import Resource, DeclarativeMetaclass
from tastypie.paginator import Paginator
from tastypie.exceptions import NotFound, ImmediateHttpResponse
from tastypie.utils import trailing_slash
from tastypie import http

import elasticsearch
import elasticsearch.exceptions

class ElasticSearchResult(list):
    def __init__(self, result, query=None):
        super(ElasticSearchResult, self).__init__(
            map(lambda s:s["_source"], result["hits"]["hits"]))

        self.shards = result["_shards"]
        self.took = result["took"]
        self.timed_out = result["timed_out"]
        self.total = result["hits"]["total"]
        self.max_score = result["hits"]["max_score"]
        self.facets = result.get("facets", [])
        self.query = query

class ElasticSearchPaginator(Paginator):

    add_search_info = False

    def get_count(self):
        return self.objects.total

    def get_slice(self, limit, offset):
        """
        Slices the result set to the specified ``limit`` & ``offset``.
        """
        return self.objects

    def page(self):
        output = super(ElasticSearchPaginator, self).page()

        objects = self.objects
        
        if self.add_search_info:
            search = dict(
                took=objects.took,
                max_score=objects.max_score,
                shards=objects.shards,
            )
            if objects.timed_out:
                search['timed_out'] = objects.timed_out
            if objects.query:
                search['query'] = objects.query
            
            output['meta']['search'] = search
        else:
            output['meta']['took'] = objects.took
        if len(objects.facets):
            output["facets"] = objects.facets
        return output
    

class ElasticSearchDeclarativeMetaclass(DeclarativeMetaclass):
    """
    This class has the same functionality as its supper ``ModelDeclarativeMetaclass``.
    Changing only some ElasticSearch intrinsics
    """

    def __new__(self, name, bases, attrs):
        meta = attrs.get('Meta')

        new_class = super(ElasticSearchDeclarativeMetaclass, 
            self).__new__(self, name, bases, attrs)

        setattr(new_class._meta, "es_server", getattr(settings, 
            "ES_SERVER", "127.0.0.1:9500"))
        setattr(new_class._meta, "es_timeout", getattr(settings, 
            "ES_TIMEOUT", 30))

        setattr(new_class._meta, "object_class", dict)

        setattr(new_class._meta, "include_mapping_fields", True)

        setattr(new_class._meta, "paginator_class", ElasticSearchPaginator)

        #setattr(new_class._meta, "doc_type", )
        #setattr(new_class._meta, "index", )

        return new_class

class ElasticSearch(Resource):
    """
    ElasticSearch Base Resource
    
    """
    
    __metaclass__ = ElasticSearchDeclarativeMetaclass

    _es = None
    def es__get(self):
        if self._es is None:
            host, port = self._meta.es_server.split(":")
            hosts = {host, port}
            self._es = elasticsearch.Elasticsearch(hosts, 
                                                    timeout=self._meta.es_timeout)
        return self._es
    client = property(es__get)
    
    def prepend_urls(self):
        """Override Resource url map to fit ElasticSearch Id syntax"""
        resource_name = self._meta.resource_name
        tr = trailing_slash()
        return [
            #
            # search implementation
            #
            url(r"^(?P<resource_name>%s)/search%s$" % (resource_name, tr), 
                self.wrap_view('get_search'), name="api_get_search"),

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
        schema = super(ElasticSearch, self).build_schema()
        
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
        bundle = super(ElasticSearch, self).full_dehydrate(bundle, for_list)

        kwargs = dict(resource_name=self._meta.resource_name, pk=bundle.obj.get("id"))
        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name
        bundle.data["resource_uri"] = self._build_reverse_url('api_dispatch_detail', kwargs=kwargs)
        
        bundle.data.update(bundle.obj)
        return bundle
    
    def full_hydrate(self, bundle):
        bundle = super(ElasticSearch, self).full_hydrate(bundle)
        bundle.obj.update(bundle.data)
        return bundle

    def obj_get(self, request=None, **kwargs):
        pk = kwargs.get("pk")
        try:
            result =  self.client.get(self._meta.index, pk, self._meta.doc_type)
        except elasticsearch.exceptions.NotFoundError, exc:
            response = http.HttpNotFound("Not found", content_type="text/plain")
            raise ImmediateHttpResponse(response)
        except Exception, exc:
            response = http.HttpNotFound(str(exc), content_type="text/plain")
            raise ImmediateHttpResponse(response)
        else:
            return result.get("_source")

    def get_resource_uri(self, bundle_or_obj=None):
        if bundle_or_obj is None:
            result = super(ElasticSearch, self).get_resource_uri(bundle_or_obj)
            return result
    
        kwargs = {
            'resource_name': self._meta.resource_name,
        }
    
        obj = (bundle_or_obj.obj if 
            isinstance(bundle_or_obj, Bundle) else bundle_or_obj)
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
    
    
    def build_search_query(self, request):
        offset = long(request.GET.get("offset", 0))
        limit = long(request.GET.get("limit", self._meta.limit))

        sort = self.get_sorting(request)
        query = []

        for key, value in request.GET.items():
            if key not in ["offset", "limit", "query_type", "format"]:
                q = {".".join([self._meta.doc_type, key]): value}
                query.append({"text":q})

        if len(query) is 0:
            # show all
            query.append({"match_all": {}})

        start = offset + (2 if offset>=limit else 1)

        return {
            "query": {
                "bool": {
                    "must": query,
                },
            },
            "from": start,
            "size": limit,
            "sort": sort or [],
        }
        
    
    def get_object_list(self, request):
        query = self.build_search_query(request)
        try:
            result = self.client.search(self._meta.index, self._meta.doc_type, query)
        except Exception, exc:
            response = http.HttpNotFound(str(exc), content_type="text/plain")
            raise ImmediateHttpResponse(response)
        else:
            return ElasticSearchResult(result, query)
            
    def obj_get_list(self, request=None, **kwargs):
        # Filtering disabled for brevity...
        return self.get_object_list(kwargs['bundle'].request)

    def obj_create(self, bundle, request=None, **kwargs):
        raise NotImplemented
        bundle.obj = dict(kwargs)
        bundle = self.full_hydrate(bundle)
        pk = kwargs.get("pk", bundle.obj.get("_id"))
        result = self.client.index(self._meta.index, self._meta.doc_type, bundle.obj, id=pk)
        result.update(bundle.obj)
        return result
    
    def obj_update(self, bundle, request=None, **kwargs):
        raise NotImplemented
        bundle.obj = dict(kwargs)
        bundle = self.full_hydrate(bundle)
        pk = kwargs.get("pk", bundle.obj.get("_id"))
            #bundle.obj.get("_id", str(uuid.uuid1())) )
    
        result = self.client.update(self._meta.index, self._meta.doc_type, bundle.obj, id=pk)
        result.update(bundle.obj)
        return result
    
    def obj_delete_list(self, request=None, **kwargs):
        raise NotImplemented
        pk = kwargs.get("pk")
        query = {}
        result = self.client.delete_by_query(self._meta.index, self._meta.doc_type, query)
        return result

    def obj_delete(self, request=None, **kwargs):
        raise NotImplemented
        pk = kwargs.get("pk")
        result = self.client.delete(self._meta.index, self._meta.doc_type, id=pk)
        return result

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

    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        """
        Extracts the common "which-format/serialize/return-response" cycle.

        Mostly a useful shortcut/hook.
        """
        desired_format = self.determine_format(request)
        serialized = self.serialize(request, data, desired_format)
        
        format = (format if 'charset' in desired_format else 
                "%s; charset=%s" % (desired_format, 'utf-8'))
        
        return response_class(content=serialized, content_type=format, **response_kwargs)
