# -*- coding: utf-8 -*-

# standard library
import os,mimetypes
from json import dumps
from django.shortcuts import  get_object_or_404
from django.http import  HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

try:
  from django.db.models import get_model
except: # django > 1.9
  from django.apps import apps
  def get_model(app,model):
    return apps.get_app_config(app).get_model(model)

from django.utils.encoding import smart_str
from django.http import Http404
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _

# flexport packet
from models import *
from utils_configure import *

############################# FUNCTION FOR AJAX REQUESTS #############################
@login_required
def js_models(request):
  MODELS = []
  if (request.GET):
    app = request.GET.get('app',None)
    if app!=None:
      for model in ContentType.objects.filter(app_label=app):
        MODELS.append(({'id':model.pk,'model_name':model.name}))
    data = {'models' : MODELS}
    return JsonResponse(data)
  else:
    raise Http404

@login_required
def js_related_models(request,id_extract):
    '''
    Esportazione JSON per avere la lista di modelli agganciati al modello base
    in ricorrenza fino alla profondità impostata
    '''
    EXPORT = get_object_or_404(Export,id=id_extract)
    MODEL  = get_model(EXPORT.app, EXPORT.model.model)
    if MODEL:
        JSON_DATA = []
        for models_array in get_related_models_recursive(MODEL,EXPORT.depth,EXPORT.exclude_models.all()):
            value = ''
            text  = ''
            for (model,field) in models_array:
                if value != '':
                  value = value+'.'
                value+= '%s' % field
                if text != '':
                  text = text+' -> '
                # mostro il link a quale campo è associato
                try: # per le traduzioni
                  text+= '%s (%s)' % (model._meta.verbose_name.title(),field)
                except:
                  text+= '%s (%s)' % (model._meta.verbose_name,field)
            JSON_DATA.append({'value':value,'text':text})
        data = {'models' : JSON_DATA}
        return JsonResponse(data)
    else:
        raise Exception(_('Model not found'))

@login_required
def js_attributes(request,id_extract,follow):
    '''
    Esportazione JSON della lista dei campi per l'ultimo modello che si intende
    raggiungere mediante la ricorrenza e profondità impostata
    '''
    EXPORT = get_object_or_404(Export,id=id_extract)
    MODEL  = get_model(EXPORT.app, EXPORT.model.model)
    if MODEL:
        LAST_MODEL = MODEL
        for field in follow.split('.'):
            if field!='None':# None serve per restare sullo stesso modello di partenza
                if hasattr(LAST_MODEL,field):
                    try:
                     # direct link
                     LAST_MODEL = getattr(LAST_MODEL,field).field.rel.to
                    except:
                     # inverse link
                     LAST_MODEL = getattr(LAST_MODEL,field).related.model
                else:
                    raise Exception(_('Attribute not found'))
        FIELDS = get_model_elements(LAST_MODEL)
        data = {'fields' : [{'value':field,'text':field} for field in FIELDS]}
        return JsonResponse(data)
    else:
        raise Exception(_('Model not found'))
  
@login_required
def create_extraction(request,id_extract,qs = None):
  EXPORT    = get_object_or_404(Export,id=id_extract)
  if not EXPORT.is_enabled(request):
    raise Http404
  filepath  = EXPORT.get_filepath()
  filename  = EXPORT.get_filename()
  if not qs:
    # filtro qs
    FILTER = None
    try: # provo a usare i filtri di MPA
      from filter.utils import get_where, get_count_sql
      from filter.utils import get_saved_layer_filter as FILTER
    except:
      pass
    try: # provo a usare i filtri di MPA
      from filter.utils import get_where, get_count_sql
      from layer.utils_high import get_saved_layer_filter2 as FILTER
    except:
      pass
#    except:
#      pass
    if FILTER != None:
      BASE_MODEL = get_model(EXPORT.app, EXPORT.model.model)
      qs = BASE_MODEL.objects.all()
      # listo i filtri
      filter = request.GET.get('filter',None)
      filters = []
      if filter: filters.append(filter)
      # guardo se ho filtri in sessione
      if request.GET.has_key('savedid'):
        filter = FILTER(request.GET['savedid'])
      if filter: filters.append(filter)
      # se ho filtri li applico
      if len(filters) > 0:
        filter_sql = '( ' + " ) and ( ".join(filters) + ' )'
        where = [get_where( EXPORT.app, EXPORT.model.model, filter_sql )]
        qs = qs.extra(where=where)

  EXPORT.extractor(filepath=filepath,qs=qs)

  f = open(filepath, 'rb')
  readcode = f.read()
  f.close()
  response = HttpResponse(content_type=mimetypes.guess_type(filepath)[0] or 'application/octet-stream')
  response['Content-Disposition'] = 'attachment; filename=%s' % filename
  response['Content-Length']      = os.path.getsize(filepath)
  response.write(readcode)
  return response

