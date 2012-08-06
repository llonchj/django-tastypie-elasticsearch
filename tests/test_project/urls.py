from django.conf.urls import patterns, include, url

from tastypie import api

from test_project.test_app.api import resources

v1_api = api.Api(api_name='v1')
v1_api.register(resources.TestResource())

urlpatterns = patterns('',
    url(r'^api/', include(v1_api.urls)),
)
