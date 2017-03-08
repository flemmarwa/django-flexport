# -*- coding: utf-8 -*-

# django core import
from django.contrib import admin
from functools import wraps
import copy
from django.contrib.contenttypes.models import ContentType
# custom import 
from models import Export
from views import create_extraction
from django.template import RequestContext

def export_actions_for_model(model,request):
  model_ct = ContentType.objects.get(model=model._meta.model_name,app_label=model._meta.app_label)
  actions = []
  def action_builder(EXP):
    action = lambda modeladmin, request, qs: create_extraction(request, EXP.id,qs)
    action.func_name = 'EXP_action_%s' % EXP.id
    action.short_description = EXP.action_name
    return action
  for EXP in  Export.objects.filter(model = model_ct, active=True):
    if EXP.is_enabled(request):
      actions.append(action_builder(EXP))
      
  return actions

def patch_admin_site_actions():
  def wrapper(m,func):
    @wraps(func)
    def wrapped(request,*args,**kwargs):
      actions = func(request,*args,**kwargs)
      for action in export_actions_for_model(m,request):
        actions.update({action.func_name: (action,action.func_name,action.short_description)}) 
#        actions.insert(0, action.func_name, (action,action.func_name,action.short_description)) #.append(action) # <- non funziona perchè è un SortedDict()e non un array
      return actions
    wrapped._already_wrapped = True
    return wrapped
  admin.autodiscover() #make sure that all admin models are registered

  for m,a in admin.site._registry.items():
    if not getattr(a.get_actions,'_already_wrapped',False): #do not wrap the same function twice
      a.get_actions = wrapper(m,a.get_actions)
