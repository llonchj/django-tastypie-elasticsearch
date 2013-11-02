from __future__ import with_statement

import urlparse

from django.core import exceptions, urlresolvers
from django.test import client, utils
from django.utils import simplejson as json

from tastypie import authorization as tastypie_authorization
from tastypie.test import ResourceTestCase, TestApiClient

from tastypie_elasticsearch import resources as tastypie_elasticsearch_resources

import elasticsearch

import resources

# TODO: Test set operations
# TODO: Test bulk operations
# TODO: Test ordering, filtering
# TODO: Use Tastypie's testcase class for tests?

@utils.override_settings(DEBUG=True)
class TastypieElasticsearchTest(ResourceTestCase):
    api_name = 'v1'

    def tearDown(self):
        #
        # ensure index is removed after running tests
        #
        self.resource_class = resources.TestResource
        es_server = resources.TestResource._meta.es_server
        index = self.resource_class._meta.index
        
        h, p = es_server.split(":")
        hosts = [{"host":h, "port":p}]
        self.es = elasticsearch.Elasticsearch(hosts, 
            timeout=30)

        self.es.indices.delete(index)

    def resourceListURI(self, resource_name):
        return urlresolvers.reverse('api_dispatch_list', kwargs={'api_name': self.api_name, 'resource_name': resource_name})
    
    def resourcePK(self, resource_uri):
        match = urlresolvers.resolve(resource_uri)
        return match.kwargs['pk']
    
    def resourceDetailURI(self, resource_name, resource_pk):
        return urlresolvers.reverse('api_dispatch_detail', kwargs={'api_name': self.api_name, 
            'resource_name': resource_name, 'pk': resource_pk})
    
    def fullURItoAbsoluteURI(self, uri):
        scheme, netloc, path, query, fragment = urlparse.urlsplit(uri)
        return urlparse.urlunsplit((None, None, path, query, fragment))
    

class BasicTest(TastypieElasticsearchTest):
    
    def testCRUD(self):
        # Testing POST
    
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)
        
        #create an object
        obj = dict(_id=1, first_name="John", last_name="Doe")
        
        response = self.api_client.post(base_url, format="json", data=obj)
        self.assertHttpCreated(response)
    
        obj_uri = response.get("Location")
        
        # get the list
        response = self.api_client.get(base_url)
        self.assertHttpOK(response)
    
        response = json.loads(response.content)
        self.assertEqual(len(response["objects"]), 1)
        
        #get the object
        response = self.api_client.get(obj_uri)
        self.assertHttpOK(response)
        
        # update object
        obj1 = json.loads(response.content)
        del obj1["resource_uri"]
        
        obj1["first_name"] = u"Person 1 UPDATED"
        response = self.api_client.post(base_url, format="json", data=obj1)
        self.assertHttpCreated(response)
    
        #get the *updated?* object
        response = self.api_client.get(obj_uri)
        self.assertHttpOK(response)
        #and compare it
        data = json.loads(response.content)
        for k, v in obj1.iteritems():
            self.assertEqual(data[k], v)
    
        #delete the object
        response = self.api_client.delete(obj_uri)
        self.assertHttpAccepted(response)
        
        #get the *already deleted* object, not found expected
        response = self.api_client.get(obj_uri)
        self.assertHttpNotFound(response)
        
    
    def test_bulk(self):
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)

        #add an object to be updated
        obj = dict(_id=9999999, first_name="John", last_name="Doe", untouched=1)
        response = self.api_client.post(base_url, format="json", data=obj)
        self.assertHttpCreated(response)
        obj_uri = response.get("Location")
        obj_uri = '/' + '/'.join(obj_uri.split('/')[3:])

        
        objects = []
        deleted_objects = []
        
        obj = {
            '_id': 9999999, 
            'first_name': 'John', 
            'last_name': 'Doe Updated',
            'updated': True,
            'resource_uri': obj_uri,
        }
        objects.append(obj)
        
        for i in range(5):
            obj = {
                "_id": (i+1000),
                "first_name": "Person %d" % (i+1000),
                "last_name": "Smith",
                "bulk": True,
            }
            objects.append(obj)
        
        data = {
            "objects":objects,
            "deleted_objects":deleted_objects,
        }

        response = self.api_client.patch(base_url, format="json", data=data)
        self.assertHttpAccepted(response)

    def test_ordering(self):
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)
    
        for i in range(100):
            response = self.api_client.post(base_url,
                format="json", data=dict(
                    name="Person %d" % (i + 1), number=i+1))
            self.assertHttpCreated(response)
    
        for key in ["number"]:
            for ordering in [key, "-%s" % key]:
    
                response = self.api_client.get(base_url, 
                    data={'order_by': ordering})
                self.assertEqual(response.status_code, 200)
    
                data = json.loads(response.content)
                
                sq = []
                objects = data.get("objects")
                if objects:
                    for obj in objects:
                        self.assertTrue(obj.has_key("number"))
                        number = obj.get("number")
                        sq.append(number)
    
                    ran = ([i for i in reversed(range(100 - (len(objects) - 1), 100 + 1))] 
                            if ordering.startswith("-") else range(1, len(objects) + 1))
                    self.assertEqual(sq, ran)
    
    def test_pagination(self):
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)
        
        count = 100
        
        for i in range(count):
            response = self.api_client.post(base_url,
                format="json", data=dict(name="Person %d" % (i + 1), number=i+1))
            self.assertEqual(response.status_code, 201)
        
        base_url = self.resourceListURI(resource_name)
    
        response = self.api_client.get(base_url,
            data={'offset': '42', 'limit': 7, "order_by": "number"})
        self.assertEqual(response.status_code, 200)
    
        response = json.loads(response.content)
        
        self.assertEqual(response['meta']['total_count'], 100)
        self.assertEqual(response['meta']['offset'], 42)
        self.assertEqual(response['meta']['limit'], 7)
        self.assertEqual(len(response['objects']), 7)
    
        for i, obj in enumerate(response['objects']):
            self.assertEqual(obj['name'], "Person %s" % (43 + i))
    
        offset = response['objects'][0]['number']
    
        response = self.api_client.get(
            self.resourceListURI(resource_name),
            data={'offset': offset, 'limit': 7, "order_by": "number"})
        self.assertEqual(response.status_code, 200)
        response = json.loads(response.content)
    
        self.assertEqual(response['meta']['total_count'], count)
        self.assertEqual(response['meta']['offset'], offset)
        self.assertEqual(response['meta']['limit'], 7)
        self.assertEqual(len(response['objects']), 7)
    
        for i, obj in enumerate(response['objects']):
            self.assertEqual(obj['name'], "Person %s" % (44 + i))
    
        # invalid limit parameter, fail
        response = self.api_client.get(
            self.resourceListURI(resource_name),
            data={'offset': offset, 'limit': -7, "order_by": "number"})
        self.assertEqual(response.status_code, 400)
    
    def test_percolator(self):
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)
    
        for i in range(100):
            response = self.api_client.post(base_url,
                format="json", data=dict(
                    name="Person %d" % (i + 1), number=i+1))
    
        
        #get the object
        response = self.api_client.post(base_url + 'percolate/', 
            format='json', data={"body":{"name":"python"}})
    
        self.assertHttpOK(response)
    
        result = json.loads(response.content)
    
        self.assertTrue("meta" in result.keys())
        meta = result.get("meta")
    
        self.assertTrue("matches" in meta)
        self.assertTrue(isinstance(meta.get('matches'), list))
    
        