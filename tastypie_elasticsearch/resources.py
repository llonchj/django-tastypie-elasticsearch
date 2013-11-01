# -*- coding: utf-8 -*-
"""
tastypie.Resource definitions for Elasticsearch

"""

import re
import sys
import json
from copy import deepcopy

from django.conf import settings
from django.conf.urls import url
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned, ValidationError

from tastypie import http
from tastypie.bundle import Bundle
from tastypie.fields import NOT_PROVIDED
from tastypie.resources import Resource, DeclarativeMetaclass, convert_post_to_patch
from tastypie.exceptions import NotFound, ImmediateHttpResponse
from tastypie.utils import dict_strip_unicode_keys, trailing_slash

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
        """ Percolate call """
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)
        self.throttle_check(request)

        # Do the query.
        result = self.client.percolate(self._meta.index, self._meta.doc_type, 
                                        body=dict(doc=json.loads(request.body)))
        object_list = {
            'meta': result,
        }

        self.log_throttled_access(request)
        return self.create_response(request, object_list)

    def patch_list(self, request, **kwargs):
        """
        Updates a collection in-place.

        The exact behavior of ``PATCH`` to a list resource is still the matter of
        some debate in REST circles, and the ``PATCH`` RFC isn't standard. So the
        behavior this method implements (described below) is something of a
        stab in the dark. It's mostly cribbed from GData, with a smattering
        of ActiveResource-isms and maybe even an original idea or two.

        The ``PATCH`` format is one that's similar to the response returned from
        a ``GET`` on a list resource::

            {
              "objects": [{object}, {object}, ...],
              "deleted_objects": ["URI", "URI", "URI", ...],
            }

        For each object in ``objects``:

            * If the dict does not have a ``resource_uri`` key then the item is
              considered "new" and is handled like a ``POST`` to the resource list.

            * If the dict has a ``resource_uri`` key and the ``resource_uri`` refers
              to an existing resource then the item is a update; it's treated
              like a ``PATCH`` to the corresponding resource detail.

            * If the dict has a ``resource_uri`` but the resource *doesn't* exist,
              then this is considered to be a create-via-``PUT``.

        Each entry in ``deleted_objects`` referes to a resource URI of an existing
        resource to be deleted; each is handled like a ``DELETE`` to the relevent
        resource.

        In any case:

            * If there's a resource URI it *must* refer to a resource of this
              type. It's an error to include a URI of a different resource.

            * ``PATCH`` is all or nothing. If a single sub-operation fails, the
              entire request will fail and all resources will be rolled back.

          * For ``PATCH`` to work, you **must** have ``put`` in your
            :ref:`detail-allowed-methods` setting.

          * To delete objects via ``deleted_objects`` in a ``PATCH`` request you
            **must** have ``delete`` in your :ref:`detail-allowed-methods`
            setting.

        Substitute appropriate names for ``objects`` and
        ``deleted_objects`` if ``Meta.collection_name`` is set to something
        other than ``objects`` (default).
        """
        request = convert_post_to_patch(request)
        deserialized = self.deserialize(request, request.body, format=request.META.get('CONTENT_TYPE', 'application/json'))

        collection_name = self._meta.collection_name
        deleted_collection_name = 'deleted_%s' % collection_name
        if collection_name not in deserialized:
            raise BadRequest("Invalid data sent: missing '%s'" % collection_name)

        if len(deserialized[collection_name]) and 'put' not in self._meta.detail_allowed_methods:
            raise ImmediateHttpResponse(response=http.HttpMethodNotAllowed())

        bulk_commands = []
        
        bundles_seen = []

        def index(bundle, command='index'):
            command = {command:{'_id':bundle.data["_id"]}}
            bulk_commands.append(command)
            command = bundle.obj
            bulk_commands.append(command)

        for data in deserialized[collection_name]:
            # If there's a resource_uri then this is either an
            # update-in-place or a create-via-PUT.
            if "resource_uri" in data:
                try:
                    uri = data.pop('resource_uri')

                    obj = self.get_via_uri(uri, request=request)

                    # The object does exist, so this is an update-in-place.
                    bundle = self.build_bundle(obj=obj['_source'], request=request)
                    bundle.data.update(data)
                    bundle = self.full_hydrate(bundle)

                    bulk_commands.append({'update':{'_id':bundle.data["_id"]}})
                    bulk_commands.append({'doc':bundle.obj})
                    
                except (ObjectDoesNotExist, MultipleObjectsReturned):
                    # The object referenced by resource_uri doesn't exist,
                    # so this is a create-by-PUT equivalent.
                    data = self.alter_deserialized_detail_data(request, data)
                    bundle = self.build_bundle(data=dict_strip_unicode_keys(data), request=request)
                    #self.obj_create(bundle=bundle)
                    bundle = self.full_hydrate(bundle)
                    index(bundle)
            else:
                # There's no resource URI, so this is a create call just
                # like a POST to the list resource.
                data = self.alter_deserialized_detail_data(request, data)
                bundle = self.build_bundle(data=dict_strip_unicode_keys(data), request=request)
                #self.obj_create(bundle=bundle)
                bundle = self.full_hydrate(bundle)
                index(bundle)

            bundles_seen.append(bundle)

        deleted_collection = deserialized.get(deleted_collection_name, [])

        if deleted_collection:
            if 'delete' not in self._meta.detail_allowed_methods:
                raise ImmediateHttpResponse(response=http.HttpMethodNotAllowed())

            for uri in deleted_collection:
                obj = self.get_via_uri(uri, request=request)
                bundle = self.build_bundle(obj=obj['_source'], request=request)
                #self.obj_delete(bundle=bundle)
                command = {"delete":{'_id':bundle['pk']}}
                bulk_commands.append(command)

        if len(bulk_commands):
            try:
                result = self.client.bulk(bulk_commands, refresh=True,
                                          index=self._meta.index, 
                                          doc_type=self._meta.doc_type)
            except Exception, exc:
                response = http.HttpBadRequest(str(exc), content_type="text/plain")
                raise ImmediateHttpResponse(response)
            else:
                if not self._meta.always_return_data:
                    return http.HttpAccepted(json.dumps(result))
                else:
                    to_be_serialized = {}
                    to_be_serialized['objects'] = [self.full_dehydrate(bundle, for_list=True) for bundle in bundles_seen]
                    to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
                    return self.create_response(request, to_be_serialized, response_class=http.HttpAccepted)
        else:
            return http.HttpBadRequest()

