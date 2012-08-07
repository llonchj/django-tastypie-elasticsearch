from __future__ import with_statement

import urlparse

from django.core import exceptions, urlresolvers
from django.test import client, utils
from django.utils import simplejson as json

from tastypie import authorization as tastypie_authorization

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
class BasicTest(test_runner.ESTestCase):
    api_name = 'v1'
    c = client.Client()
    
    def setUp(self):
        super(BasicTest, self).setUp()

        self.resource_class = resources.TestResource
        self.resource_class._meta.indices = ["test"]
        #self.resource_class._meta.cache = NoCache()
        
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
        
        response = self.c.post(base_url, 
            json.dumps(obj), 
            content_type='application/json')
        obj_uri = response.get("Location")
        self.assertEqual(response.status_code, 201)

        # get the list
        response = self.c.get(base_url)
        self.assertEqual(response.status_code, 200)
        response = json.loads(response.content)

        #get the object
        response = self.c.get(obj_uri)
        self.assertEqual(response.status_code, 200)

        # update object
        obj1 = json.loads(response.content)
        obj1["name"] = "Person 1 UPDATED"
        response = self.c.post(base_url, 
            json.dumps(obj1),
            content_type='application/json')
        self.assertEqual(response.status_code, 201)

        #delete the object
        response = self.c.delete(obj_uri)
        self.assertEqual(response.status_code, 204)
        
        #get the *already deleted* object, not found expected
        response = self.c.get(obj_uri)
        self.assertEqual(response.status_code, 404)
        

    def test_masscreation(self):
        resource_name = 'test'
        base_url = self.resourceListURI(resource_name)

        for i in range(1, 1000):
            #create an object
            obj = dict(name="Person %d" % i, number=i)
        
            response = self.c.post(base_url, 
                json.dumps(obj), 
                content_type='application/json')
            self.assertEqual(response.status_code, 201)
        
        # 
        # person1_uri = response['location']
        # 
        # response = self.c.get(person1_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['name'], 'Person 1')
        # self.assertEqual(response['optional'], None)
        # 
        # # Covered by Tastypie
        # response = self.c.post(self.resourceListURI('person'), '{"name": null}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Covered by Tastypie
        # response = self.c.post(self.resourceListURI('person'), '{}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Covered by Tastypie
        # response = self.c.post(self.resourceListURI('person'), '{"optional": "Optional"}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Covered by MongoEngine validation
        # response = self.c.post(self.resourceListURI('person'), '{"name": []}', content_type='application/json')
        # self.assertContains(response, 'only accepts string values', status_code=400)
        # 
        # # Covered by MongoEngine validation
        # response = self.c.post(self.resourceListURI('person'), '{"name": {}}', content_type='application/json')
        # self.assertContains(response, 'only accepts string values', status_code=400)
        # 
        # response = self.c.post(self.resourceListURI('person'), '{"name": "Person 2", "optional": null}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # response = self.c.post(self.resourceListURI('person'), '{"name": "Person 2", "optional": "Optional"}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # person2_uri = response['location']
        # 
        # response = self.c.get(person2_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['name'], 'Person 2')
        # self.assertEqual(response['optional'], 'Optional')
        # 
        # # Tastypie ignores additional field
        # response = self.c.post(self.resourceListURI('person'), '{"name": "Person 3", "additional": "Additional"}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # # Referenced resources can be matched through fields if they match uniquely
        # response = self.c.post(self.resourceListURI('customer'), '{"person": {"name": "Person 1"}}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # customer1_uri = response['location']
        # 
        # response = self.c.get(customer1_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['person']['name'], 'Person 1')
        # self.assertEqual(response['person']['optional'], None)
        # self.assertEqual(response['person']['resource_uri'], self.fullURItoAbsoluteURI(person1_uri))
        # 
        # person1_id = response['person']['id']
        # 
        # # Referenced resources can be even updated at the same time
        # response = self.c.post(self.resourceListURI('customer'), '{"person": {"id": "%s", "name": "Person 1 UPDATED"}}' % person1_id, content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # customer2_uri = response['location']
        # 
        # response = self.c.get(customer2_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['person']['name'], 'Person 1 UPDATED')
        # self.assertEqual(response['person']['optional'], None)
        # self.assertEqual(response['person']['resource_uri'], self.fullURItoAbsoluteURI(person1_uri))
        # 
        # response = self.c.post(self.resourceListURI('customer'), '{"person": "%s"}' % self.fullURItoAbsoluteURI(person1_uri), content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # customer3_uri = response['location']
        # 
        # response = self.c.get(customer3_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['person']['name'], 'Person 1 UPDATED')
        # self.assertEqual(response['person']['optional'], None)
        # self.assertEqual(response['person']['resource_uri'], self.fullURItoAbsoluteURI(person1_uri))
        # 
        # response = self.c.get(self.resourceListURI('person'))
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(len(response['objects']), 4)
        # 
        # # Referenced resources can also be created automatically
        # response = self.c.post(self.resourceListURI('customer'), '{"person": {"name": "Person does not YET exist"}}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # customer4_uri = response['location']
        # 
        # response = self.c.get(customer4_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['person']['name'], 'Person does not YET exist')
        # self.assertEqual(response['person']['optional'], None)
        # 
        # person5_uri = response['person']['resource_uri']
        # 
        # response = self.c.get(person5_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['name'], 'Person does not YET exist')
        # self.assertEqual(response['optional'], None)
        # 
        # response = self.c.get(self.resourceListURI('person'))
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(len(response['objects']), 5)
        # 
        # response = self.c.post(self.resourceListURI('embeddeddocumentfieldtest'), '{"customer": {"name": "Embedded person 1"}}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # embeddeddocumentfieldtest_uri = response['location']
        # 
        # response = self.c.get(embeddeddocumentfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['customer']['name'], 'Embedded person 1')
        # 
        # # Covered by MongoEngine validation
        # response = self.c.post(self.resourceListURI('dictfieldtest'), '{"dictionary": {}}', content_type='application/json')
        # self.assertContains(response, 'required and cannot be empty', status_code=400)
        # 
        # # Covered by Tastypie
        # response = self.c.post(self.resourceListURI('dictfieldtest'), '{"dictionary": null}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Covered by MongoEngine validation
        # response = self.c.post(self.resourceListURI('dictfieldtest'), '{"dictionary": false}', content_type='application/json')
        # self.assertContains(response, 'dictionaries may be used', status_code=400)
        # 
        # response = self.c.post(self.resourceListURI('dictfieldtest'), '{"dictionary": {"a": "abc", "number": 34}}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # dictfieldtest_uri = response['location']
        # 
        # response = self.c.get(dictfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['dictionary']['a'], 'abc')
        # self.assertEqual(response['dictionary']['number'], 34)
        # 
        # response = self.c.post(self.resourceListURI('listfieldtest'), '{"intlist": [1, 2, 3, 4], "stringlist": ["a", "b", "c"], "anytype": ["a", 1, null, 2]}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # listfieldtest_uri = response['location']
        # 
        # response = self.c.get(listfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['intlist'], [1, 2, 3, 4])
        # self.assertEqual(response['stringlist'], ['a', 'b', 'c'])
        # self.assertEqual(response['anytype'], ['a', 1, None, 2])
        # 
        # # Field is not required
        # response = self.c.post(self.resourceListURI('embeddedlistfieldtest'), '{"embeddedlist": []}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # response = self.c.post(self.resourceListURI('embeddedlistfieldtest'), '{"embeddedlist": [{"name": "Embedded person 1"}, {"name": "Embedded person 2"}]}', content_type='application/json')
        # self.assertEqual(response.status_code, 201)
        # 
        # embeddedlistfieldtest_uri = response['location']
        # 
        # response = self.c.get(embeddedlistfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['embeddedlist'][0]['name'], 'Embedded person 1')
        # self.assertEqual(response['embeddedlist'][1]['name'], 'Embedded person 2')
        # self.assertEqual(len(response['embeddedlist']), 2)
        # 
        # response = self.c.post(self.resourceListURI('embeddedlistfieldtest'), '{"embeddedlist": ["%s"]}' % self.fullURItoAbsoluteURI(person1_uri), content_type='application/json')
        # self.assertContains(response, 'was not given a dictionary-alike data', status_code=400)
        # 
        # # Testing PUT
        # 
        # response = self.c.put(person1_uri, '{"name": "Person 1z"}', content_type='application/json')
        # self.assertEqual(response.status_code, 204)
        # 
        # # Covered by Tastypie
        # response = self.c.put(person1_uri, '{"name": null}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Covered by Tastypie
        # response = self.c.put(person1_uri, '{}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Covered by Tastypie
        # response = self.c.put(person1_uri, '{"optional": "Optional ZZZ"}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Covered by MongoEngine validation
        # response = self.c.put(person1_uri, '{"name": []}', content_type='application/json')
        # self.assertContains(response, 'only accepts string values', status_code=400)
        # 
        # # Covered by MongoEngine validation
        # response = self.c.put(person1_uri, '{"name": {}}', content_type='application/json')
        # self.assertContains(response, 'only accepts string values', status_code=400)
        # 
        # response = self.c.get(person1_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['name'], 'Person 1z')
        # 
        # response = self.c.put(customer2_uri, '{"person": "%s"}' % self.fullURItoAbsoluteURI(person2_uri), content_type='application/json')
        # self.assertEqual(response.status_code, 204)
        # 
        # response = self.c.get(customer2_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['person']['name'], 'Person 2')
        # self.assertEqual(response['person']['optional'], 'Optional')
        # 
        # response = self.c.put(embeddeddocumentfieldtest_uri, '{"customer": {"name": "Embedded person 1a"}}', content_type='application/json')
        # self.assertEqual(response.status_code, 204)
        # 
        # response = self.c.get(embeddeddocumentfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['customer']['name'], 'Embedded person 1a')
        # 
        # response = self.c.put(dictfieldtest_uri, '{"dictionary": {"a": 341, "number": "abcd"}}', content_type='application/json')
        # self.assertEqual(response.status_code, 204)
        # 
        # response = self.c.get(dictfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['dictionary']['number'], 'abcd')
        # self.assertEqual(response['dictionary']['a'], 341)
        # 
        # response = self.c.put(listfieldtest_uri, '{"intlist": [1, 2, 4], "stringlist": ["a", "b", "c", "d"], "anytype": [null, "1", 1]}', content_type='application/json')
        # self.assertEqual(response.status_code, 204)
        # 
        # response = self.c.get(listfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['intlist'], [1, 2, 4])
        # self.assertEqual(response['stringlist'], ['a', 'b', 'c', 'd'])
        # self.assertEqual(response['anytype'], [None, "1", 1])
        # 
        # response = self.c.put(embeddedlistfieldtest_uri, '{"embeddedlist": [{"name": "Embedded person 1a"}, {"name": "Embedded person 2a"}]}', content_type='application/json')
        # self.assertEqual(response.status_code, 204)
        # 
        # response = self.c.get(embeddedlistfieldtest_uri)
        # self.assertEqual(response.status_code, 200)
        # response = json.loads(response.content)
        # 
        # self.assertEqual(response['embeddedlist'][0]['name'], 'Embedded person 1a')
        # self.assertEqual(response['embeddedlist'][1]['name'], 'Embedded person 2a')
        # self.assertEqual(len(response['embeddedlist']), 2)
        # 
        # response = self.c.put(embeddedlistfieldtest_uri, '{"embeddedlist": [{"name": "Embedded person 123"}, {}]}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Testing PATCH
        # 
        # response = self.c.patch(person1_uri, '{"name": "Person 1 PATCHED"}', content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # # Covered by Tastypie
        # response = self.c.patch(person1_uri, '{"name": null}', content_type='application/json')
        # self.assertContains(response, 'field has no data', status_code=400)
        # 
        # # Should not do anything, but succeed
        # response = self.c.patch(person1_uri, '{}', content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # # Tastypie ignores additional field, should not do anything, but succeed
        # response = self.c.patch(person1_uri, '{"additional": "Additional"}', content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # # Covered by Tastypie
        # response = self.c.patch(person1_uri, '{"optional": "Optional PATCHED"}', content_type='application/json')
        # self.assertEqual(response.status_code, 202)
        # 
        # # Covered by MongoEngine validation
        # response = self.c.patch(person1_uri, '{"name": []}', content_type='application/json')
        # self.assertContains(response, 'only accepts string values', status_code=400)
        # 
        # # Covered by MongoEngine validation
        # response = self.c.patch(person1_uri, '{"name": {}}', content_type='application/json')
        # self.assertContains(response, 'only accepts string values', status_code=400)
        # 
        # response = self.c.get(person1_uri)
        # self.assertEqual(response.status_code, 200)
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

    #def test_invalid(self):
    #    # Invalid ObjectId
    #    response = self.c.get(self.resourceListURI('customer') + 'foobar/')
    #    self.assertEqual(response.status_code, 404)
    #

    # def test_ordering(self):
    #     response = self.c.post(self.resourceListURI('embeddedlistfieldtest'), '{"embeddedlist": [{"name": "Embedded person 1"}, {"name": "Embedded person 2", "optional": "Optional"}]}', content_type='application/json')
    #     self.assertEqual(response.status_code, 201)
    # 
    #     mainresource1_uri = response['location']
    # 
    #     response = self.c.post(self.resourceListURI('embeddedlistfieldtest'), '{"embeddedlist": [{"name": "Embedded person 1a"}, {"name": "Embedded person 2a", "optional": "Optional"}]}', content_type='application/json')
    #     self.assertEqual(response.status_code, 201)
    # 
    #     mainresource2_uri = response['location']
    # 
    #     # MongoDB IDs are monotonic so this will sort it in the creation order
    #     response = self.c.get(self.resourceListURI('embeddedlistfieldtest'), {'order_by': 'id'})
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(response['objects'][0]['resource_uri'], self.fullURItoAbsoluteURI(mainresource1_uri))
    #     self.assertEqual(response['objects'][1]['resource_uri'], self.fullURItoAbsoluteURI(mainresource2_uri))
    # 
    #     # MongoDB IDs are monotonic so this will sort it in reverse of the creation order
    #     response = self.c.get(self.resourceListURI('embeddedlistfieldtest'), {'order_by': '-id'})
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(response['objects'][0]['resource_uri'], self.fullURItoAbsoluteURI(mainresource2_uri))
    #     self.assertEqual(response['objects'][1]['resource_uri'], self.fullURItoAbsoluteURI(mainresource1_uri))
    # 
    #     embeddedresource1_uri = self.fullURItoAbsoluteURI(mainresource1_uri) + 'embeddedlist/'
    #     embedded1_uri = self.fullURItoAbsoluteURI(mainresource1_uri) + 'embeddedlist/0/'
    #     embedded2_uri = self.fullURItoAbsoluteURI(mainresource1_uri) + 'embeddedlist/1/'
    # 
    #     response = self.c.get(embeddedresource1_uri, {'order_by': 'name'})
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(response['objects'][0]['resource_uri'], embedded1_uri)
    #     self.assertEqual(response['objects'][1]['resource_uri'], embedded2_uri)
    # 
    #     response = self.c.get(embeddedresource1_uri, {'order_by': '-name'})
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(response['objects'][0]['resource_uri'], embedded2_uri)
    #     self.assertEqual(response['objects'][1]['resource_uri'], embedded1_uri)
    # 
    #     response = self.c.get(self.resourceListURI('embeddedlistfieldtest'), {'order_by': 'embeddedlist__name'})
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(response['objects'][0]['resource_uri'], self.fullURItoAbsoluteURI(mainresource1_uri))
    #     self.assertEqual(response['objects'][1]['resource_uri'], self.fullURItoAbsoluteURI(mainresource2_uri))
    # 
    #     response = self.c.get(self.resourceListURI('embeddedlistfieldtest'), {'order_by': '-embeddedlist__name'})
    #     self.assertEqual(response.status_code, 200)
    #     response = json.loads(response.content)
    # 
    #     self.assertEqual(response['objects'][0]['resource_uri'], self.fullURItoAbsoluteURI(mainresource2_uri))
    #     self.assertEqual(response['objects'][1]['resource_uri'], self.fullURItoAbsoluteURI(mainresource1_uri))

    #def test_pagination(self):
    #    for i in range(100):
    #        response = self.c.post(self.resourceListURI('person'), '{"name": "Person %s"}' % i, content_type='application/json')
    #        self.assertEqual(response.status_code, 201)
    #
    #    response = self.c.get(self.resourceListURI('person'), {'offset': '42', 'limit': 7})
    #    self.assertEqual(response.status_code, 200)
    #    response = json.loads(response.content)
    #
    #    self.assertEqual(response['meta']['total_count'], 100)
    #    self.assertEqual(response['meta']['offset'], 42)
    #    self.assertEqual(response['meta']['limit'], 7)
    #    self.assertEqual(len(response['objects']), 7)
    #
    #    for i, obj in enumerate(response['objects']):
    #        self.assertEqual(obj['name'], "Person %s" % (42 + i))
    #
    #    offset = response['objects'][0]['id']
    #
    #    response = self.c.get(self.resourceListURI('person'), {'offset': offset, 'limit': 7})
    #    self.assertEqual(response.status_code, 200)
    #    response = json.loads(response.content)
    #
    #    self.assertEqual(response['meta']['total_count'], 100)
    #    self.assertEqual(response['meta']['offset'], offset)
    #    self.assertEqual(response['meta']['limit'], 7)
    #    self.assertEqual(len(response['objects']), 7)
    #
    #    for i, obj in enumerate(response['objects']):
    #        self.assertEqual(obj['name'], "Person %s" % (42 + i))
    #
    #    response = self.c.get(self.resourceListURI('person'), {'offset': offset, 'limit': -7})
    #    self.assertEqual(response.status_code, 200)
    #    response = json.loads(response.content)
    #
    #    self.assertEqual(response['meta']['total_count'], 100)
    #    self.assertEqual(response['meta']['offset'], offset)
    #    self.assertEqual(response['meta']['limit'], -7)
    #    self.assertEqual(len(response['objects']), 7)
    #
    #    for i, obj in enumerate(response['objects']):
    #        self.assertEqual(obj['name'], "Person %s" % (42 - i))
    #
    #