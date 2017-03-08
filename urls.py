# -*- coding: utf-8 -*-

from django.conf.urls import url, include

from django.contrib import admin
import flexport.views

admin.autodiscover()
try:
  from flexport.add_export_actions import patch_admin_site_actions
  patch_admin_site_actions() 
except:
  pass

from flexport.views import js_models, js_attributes, js_related_models, create_extraction

urlpatterns = [
  url(r'^js/models/?$',                                        js_models,         name='flexport_js_models'),
  url(r'^js/attributes/(?P<id_extract>\d*)/(?P<follow>.*)/?$', js_attributes,     name='flexport_js_attributes'),
  url(r'^js/related_models/(?P<id_extract>\d*)/?$',            js_related_models, name='flexport_js_related_models'),
  url(r'^extract/(?P<id_extract>\d*)/?$',                      create_extraction, name='flexport_create_extraction'),
  ]
