# -*- coding: utf-8 -*-
"""
tastypie.Resource definitions for Elasticsearch

"""

from tastypie.bundle import Bundle
from tastypie.paginator import Paginator
#from tastypie.resources import Resource, DeclarativeMetaclass
#from tastypie.exceptions import NotFound
#from tastypie.utils import trailing_slash
#from tastypie import http


class ElasticsearchResult(list):
    def __init__(self, result, query=None):
        super(ElasticsearchResult, self).__init__(result["hits"]["hits"])

        self.shards = result["_shards"]
        self.took = result["took"]
        self.timed_out = result["timed_out"]
        self.total = result["hits"]["total"]
        self.max_score = result["hits"]["max_score"]
        self.facets = result.get("facets", [])
        self.query = query

class ElasticsearchPaginator(Paginator):

    add_search_info = False

    def get_count(self):
        return self.objects.total

    def get_slice(self, limit, offset):
        """
        Slices the result set to the specified ``limit`` & ``offset``.
        """
        return self.objects

    def page(self):
        output = super(ElasticsearchPaginator, self).page()

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
    
