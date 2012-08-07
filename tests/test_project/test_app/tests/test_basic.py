from __future__ import with_statement

import urlparse

from django.core import exceptions, urlresolvers
from django.test import client, utils
from django.utils import simplejson as json

from tastypie import authorization as tastypie_authorization
from tastypie.test import ResourceTestCase, TestApiClient

from tastypie_elasticsearch import resources as tastypie_elasticsearch_resources

import pyes

from test_project import test_runner
from test_project.test_app.models import *
from test_project.test_app.api import resources

# TODO: Test set operations
# TODO: Test bulk operations
# TODO: Test ordering, filtering
# TODO: Use Tastypie's testcase class for tests?

@utils.override_settings(DEBUG=True)
class BasicTest(ResourceTestCase):
    api_name = 'v1'
    
    def setUp(self):
        super(BasicTest, self).setUp()

        self.resource_class = resources.TestResource
        self.resource_class._meta.indices = ["test"]
        #self.resource_class._meta.cache = NoCache()
        
        #
        # ensure index is up and created
        #
        es_server = resources.TestResource._meta.es_server
        indices = self.resource_class._meta.indices
        
        self.es = pyes.ES(es_server)
        for index in indices:
            self.es.delete_index_if_exists(index)
            self.es.create_index_if_missing(index)
    
    #def tearDown(self):
    #    for index in self.tr._meta.indices:
    #        self.es.delete_index_if_exists(index)

    def resourceListURI(self, resource_name):
        return urlresolvers.reverse('api_dispatch_list', kwargs={'api_name': self.api_name, 'resource_name': resource_name})

    def resourcePK(self, resource_uri):
        match = urlresolvers.resolve(resource_uri)
        return match.kwargs['pk']

    def resourceDetailURI(self, resource_name, resource_pk):
        return urlresolvers.reverse('api_dispatch_detail', kwargs={'api_name': self.api_name, 'resource_name': resource_name, 'pk': resource_pk})

    def fullURItoAbsoluteURI(self, uri):
        scheme, netloc, path, query, fragment = urlparse.urlsplit(uri)
        return urlparse.urlunsplit((None, None, path, query, fragment))

    def test_basic(self):
        # Testing POST

        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)

        #create an object
        obj = dict(name="Person 1")
        
        response = self.api_client.post(base_url,
            format="json", data=obj)
        self.assertHttpCreated(response)

        obj_uri = response.get("Location")

        # get the list
        response = self.api_client.get(base_url)
        self.assertHttpOK(response)
        
        response = json.loads(response.content)

        #get the object
        response = self.api_client.get(obj_uri)
        self.assertHttpOK(response)

        # update object
        obj1 = json.loads(response.content)
        obj1["name"] = "Person 1 UPDATED"
        response = self.api_client.post(base_url, 
            format="json", data=obj1)
        self.assertHttpCreated(response)

        #delete the object
        response = self.api_client.delete(obj_uri)
        self.assertHttpAccepted(response)
        
        #get the *already deleted* object, not found expected
        response = self.api_client.get(obj_uri)
        self.assertHttpNotFound(response)
        

    def test_masscreation(self):
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)

        for i in range(1, 1000):
            #create an object
            obj = dict(name="Person %d" % i, number=i)
            response = self.api_client.post(base_url, 
                format="json", data=obj)
            self.assertHttpCreated(response)
        
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['name'], 'Person 1 PATCHED')
        # self.assertEqual(response['optional'], 'Optional PATCHED')
        # 
        # response = self.c.patch(customer2_uri, '{"person": "%s"}' % self.fullURItoAbsoluteURI(person1_uri), content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # response = self.c.get(customer2_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['person']['name'], 'Person 1 PATCHED')
        # self.assertEqual(response['person']['optional'], 'Optional PATCHED')
        # 
        # response = self.c.patch(embeddeddocumentfieldtest_uri, '{"customer": {"name": "Embedded person PATCHED"}}', content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # response = self.c.get(embeddeddocumentfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['customer']['name'], 'Embedded person PATCHED')
        # 
        # response = self.c.patch(dictfieldtest_uri, '{"dictionary": {"a": 42}}', content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # response = self.c.get(dictfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['dictionary']['a'], 42)
        # self.assertTrue('number' not in response['dictionary'])
        # 
        # response = self.c.patch(listfieldtest_uri, '{"intlist": [1, 2, 42]}', content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # response = self.c.get(listfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['intlist'], [1, 2, 42])
        # self.assertEqual(response['stringlist'], ['a', 'b', 'c', 'd'])
        # self.assertEqual(response['anytype'], [None, "1", 1])
        # 
        # response = self.c.patch(embeddedlistfieldtest_uri, '{"embeddedlist": [{"name": "Embedded person PATCHED"}]}', content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # response = self.c.get(embeddedlistfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['embeddedlist'][0]['name'], 'Embedded person PATCHED')
        # self.assertEqual(len(response['embeddedlist']), 1)
        # 
        # # Testing DELETE
        # 
        # response = self.c.delete(person1_uri)
        # self.assertEqual(response.status_code, 204)
        # 
        # response = self.c.get(person1_uri)
        # self.assertEqual(response.status_code, 404)
        # 
        
    # def test_schema(self):
    #     embeddeddocumentfieldtest_schema_uri = self.resourceListURI('embeddeddocumentfieldtest') + 'schema/'
    # 
    #     response = self.c.get(embeddeddocumentfieldtest_schema_uri)
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(len(response['fields']), 3)
    #     self.assertEqual(len(response['fields']['customer']['embedded']['fields']), 3)
    #     self.assertTrue('name' in response['fields']['customer']['embedded']['fields'])
    #     self.assertTrue('optional' in response['fields']['customer']['embedded']['fields'])
    #     self.assertTrue('resource_type' in response['fields']['customer']['embedded']['fields'])
    # 
    #     customer_schema_uri = self.resourceListURI('customer') + 'schema/'
    # 
    #     response = self.c.get(customer_schema_uri)
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(len(response['fields']), 3)
    #     self.assertEqual(response['fields']['person']['reference_uri'], self.resourceListURI('person'))
    # 
    #     listfieldtest_schema_uri = self.resourceListURI('listfieldtest') + 'schema/'
    # 
    #     response = self.c.get(listfieldtest_schema_uri)
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(len(response['fields']), 5)
    #     self.assertEqual(response['fields']['intlist']['content']['type'], 'int')
    #     self.assertEqual(response['fields']['stringlist']['content']['type'], 'string')
    #     self.assertTrue('content' not in response['fields']['anytype'])
    # 
    #     embeddedlistfieldtest_schema_uri = self.resourceListURI('embeddedlistfieldtest') + 'schema/'
    # 
    #     response = self.c.get(embeddedlistfieldtest_schema_uri)
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(len(response['fields']), 3)
    #     self.assertEqual(len(response['fields']['embeddedlist']['embedded']['fields']), 4)
    #     self.assertTrue('name' in response['fields']['embeddedlist']['embedded']['fields'])
    #     self.assertTrue('optional' in response['fields']['embeddedlist']['embedded']['fields'])
    #     self.assertTrue('resource_uri' in response['fields']['embeddedlist']['embedded']['fields'])
    #     self.assertTrue('resource_type' in response['fields']['embeddedlist']['embedded']['fields'])
    # 
    #     self.assertEqual(len(response['fields']['embeddedlist']['embedded']['resource_types']), 2)
    #     self.assertTrue('person' in response['fields']['embeddedlist']['embedded']['resource_types'])
    #     self.assertTrue('strangeperson' in response['fields']['embeddedlist']['embedded']['resource_types'])

    def test_invalid(self):
        # Invalid ObjectId
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)

        response = self.api_client.get(base_url + 'foobar/')
        self.assertEqual(response.status_code, 404)
    

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
                
                #    self.assertEqual(response['meta']['total_count'], 100)
                #    self.assertEqual(response['meta']['offset'], 42)
                #    self.assertEqual(response['meta']['limit'], 7)
                #    self.assertEqual(len(response['objects']), 7)
                sq = []
                objects = data.get("objects")
                if objects:
                    for obj in objects:
                        self.assertTrue(obj.has_key("number"))
                        number = obj.get("number")
                        sq.append(number)

                    ran = [i for i in reversed(range(100 - (len(objects) - 1), 100 + 1))] if ordering.startswith("-") else range(1, len(objects) + 1)
                    self.assertEqual(sq, ran)

    def test_pagination(self):
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)
        
        
        for i in range(100):
            response = self.api_client.post(base_url,
                format="json", data=dict(name="Person %d" % (i + 1), number=i+1))
            self.assertEqual(response.status_code, 201)
    
        base_url = self.resourceListURI(resource_name)
        response = self.api_client.get(base_url,
            data={'offset': '42', 'limit': 7})
        self.assertEqual(response.status_code, 200)
        response = json.loads(response.content)
    
        self.assertEqual(response['meta']['total_count'], 100)
        self.assertEqual(response['meta']['offset'], 42)
        self.assertEqual(response['meta']['limit'], 7)
        self.assertEqual(len(response['objects']), 7)
    
        for i, obj in enumerate(response['objects']):
            self.assertEqual(obj['name'], "Person %s" % (42 + i))
    
        offset = response['objects'][0]['id']
    
        response = self.api_client.get(
            self.resourceListURI(resource_name),
            data={'offset': offset, 'limit': 7})
        self.assertEqual(response.status_code, 200)
        response = json.loads(response.content)
    
        self.assertEqual(response['meta']['total_count'], 100)
        self.assertEqual(response['meta']['offset'], offset)
        self.assertEqual(response['meta']['limit'], 7)
        self.assertEqual(len(response['objects']), 7)
    
        for i, obj in enumerate(response['objects']):
            self.assertEqual(obj['name'], "Person %s" % (42 + i))
    
        response = self.c.get(self.resourceListURI(resource_name),
            data={'offset': offset, 'limit': -7})
        self.assertEqual(response.status_code, 200)
        response = json.loads(response.content)
    
        self.assertEqual(response['meta']['total_count'], 100)
        self.assertEqual(response['meta']['offset'], offset)
        self.assertEqual(response['meta']['limit'], -7)
        self.assertEqual(len(response['objects']), 7)
    
        for i, obj in enumerate(response['objects']):
            self.assertEqual(obj['name'], "Person %s" % (42 - i))
    
    