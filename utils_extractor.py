# -*- coding: utf-8 -*-

# standard library
import os, types, string,datetime
from xlwt import *

try:
  from django.db.models import get_model
except: # django > 1.9
  from django.apps import apps
  def get_model(app,model):
    return apps.get_app_config(app).get_model(model)
  
from django.utils.translation import ugettext as _

# flexport packet
from utils_configure import get_model_elements, get_model_elements_values, get_all_available_elements
from logging_flexport import init_logger
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.db.models import Q
try:
  from admintools.views.pdf import create_pdf
except:
  # TODO
  def create_pdf():
    pass
from exceptions import IndexError

################################## UTILS FUNCTIONS ##################################
def rgetattr(instance=None,field=''):
  '''
  Custom robust getattr because Istance can be None
  '''
  if instance==None or field=='':
    return None
  else:
    try:
      out = instance
      for lnk in field.split('.'):
        out = getattr(out,lnk)
      return out
    except:
      return None

################################## UTIL FUNCTIONS ##################################

import copy
import pandas as pd
from string import ascii_lowercase

def _get_instances(instance,part):
  '''
  Funzione di utilità per l'estrazione delle istanze del path
  '''

  try: # seguo FK INVERSE
    _instances = getattr(instance,part).all()
  except: # seguo FK DIRETTE
    try:
      _instances = [getattr(instance,part)]
    except: # esempio per ONETOONE non avvalorate
      _instances = []
  return list(_instances)

def build_nested_structure(base_model_origin,paths):
  '''
  Serve per realizzare un dizionario di sintesi con tutti i path impostati nell'esportazione
  '''
  OUT = {'fields':[],'children':{}}
  for path in paths:
    base_model = base_model_origin
    current_level = OUT
    __path = path['model'].split('.')
    for j,part in enumerate(__path):
      if part != 'None':
        base_model = base_model._meta.get_field(part).related_model
      if part not in current_level['children']:
        current_level['children'][part] = {'fields':[],'children':{},'model':  base_model}
      if len(__path) == j+1: # se sono in fondo al path
        if path['field'] not in [None,'',u'']:
          fields_name = [path['field']]
        else:
          fields_name = [_field.attname for _field in base_model._meta.fields]
        for field_name in fields_name:
          current_level['children'][part]['fields'].append({'name':   field_name,
                                                            'order':  path['order'],
                                                            'header': path['field_header'],
                                                            'style_column_id': path['style_column_id'],
                                                            'style_field_id':  path['style_field_id'],
                                                            'style_model_id':  path['style_model_id'],
                                                            })
      current_level = current_level['children'][part]
  return OUT

def build_nested_data(instance,structure):
  '''
  Funzione principale di ricostruzione dei dati nella struttura dizionario che sintetizza l'estrazione
  '''
  children = []
  for key, value in structure['children'].iteritems():
    _instances = _get_instances(instance,key)
    if len(_instances) > 0:
      for _instance in _instances:
        children.append(build_nested_data(_instance,value))
    else:
      children.append(build_nested_data(None,value)) # quando non ho figli devo avvalorare le colonne con valore = None
  FIELDS = []
  for field in structure['fields']:
    if instance == None:
      _value = None
    else:
      _value = rgetattr(instance,field['name'])

    if field['header'] not in ['',None]:
      header = field['header'].capitalize()
    else:
      try:
        header = structure['model']._meta.get_field(field['name']).verbose_name.capitalize()
      except:
        header = field['header'].capitalize()
    FIELDS.append({field['name']:{'value':  _value,
                                  'order':  field['order'],
                                  'header': header,
                                  'style_column_id': field['style_column_id'],
                                  'style_field_id':  field['style_field_id'],
                                  'style_model_id':  field['style_model_id'],
                                  }})
  return {
    'instance': instance,
    'model':    structure['model'],
    'children': children,
    'fields':   FIELDS}

from random import randint
def traverse_nested_data(node):
  '''
  Funzione ricorsiva per ricostruire la struttura FLAT di output a partire dai dati estratti dentro il dizionario
  NOTA: avendo A->B A->C1 e A->C2 allora l'output deve essere [[A,B,C1],[A,B,C2]]
  '''
  code = randint(0,10000)
  flat_fields_lists = get_flat_fields(node)
  OUT = flat_fields_lists
  print 'YYYYYY',flat_fields_lists,'YYYYYY',node['model']
  if len(node['children']) != 0:
    model_seen = []
    for child in sorted(node['children'], key=lambda child: child.keys()[0]): # vanno ordinati!!!
      child_fields_groups = traverse_nested_data(child)
      if child['model'] not in model_seen: # appendo
        PREV_DATA = copy.deepcopy(OUT)
        model_seen.append(child['model'])
        if OUT == []: # controllo per vedere se ho ancora dati vuoti
          OUT = child_fields_groups
        else:
          for j_group,child_fields_group in enumerate(child_fields_groups):
            if j_group == 0: # se il gruppo è il primo
              for j,el in enumerate(OUT):
                for fields in child_fields_group:
                  OUT[j].append(fields)
            else: # altrimenti duplico
              for j,el in enumerate(copy.deepcopy(PREV_DATA)):
                for fields in child_fields_group:
                  OUT.append(el+[fields])
      else : #duplico le righe
        for child_fields_group in child_fields_groups:
          for el in copy.deepcopy(PREV_DATA):
            for fields in child_fields_group:
              OUT.append(el+[fields])
  return OUT

def appendi_destra(fields_groups,new_fields): # almeno [[]] , [[]]
  if len(new_fields)== 0:
    return fields_groups
  if len(fields_groups)==0:
    return new_fields
  OUT = []
  for fields_group in fields_groups:
    for new_field in new_fields:
      OUT.append(fields_group+new_field)
  return OUT

def get_flat_fields(node):# NOTA: ritorna [[A,B,C]] oppure [[A,B,C1],[A,B,C2]] nel caso in cui uno o piu campi ritona piu valori
  OUT = []
  for _field in node['fields']:
    field_name,field = _field.items()[0]
    val = field['value']
    if type(val) not in [types.DictionaryType,types.ListType]:
      OUT = appendi_destra(OUT,[[field]])
    if type(val) == types.DictionaryType:
      keys = rgetattr(node['instance'],field_name+'_keys')
      for key in keys:
        values_by_keys = []
        try:
         _value = val[key]
        except:
          _value = None
        OUT = appendi_destra(OUT,[[{key:{'value':  val.get(key,None), 
                           'order':  field['order'],
                           'header': field['header'] if (field['header'] not in ['',None]) else key.replace('_',' ').capitalize(),
                           'style_column_id': field['style_column_id'],
                           'style_field_id':  field['style_field_id'],
                           'style_model_id':  field['style_model_id'],
                           }}]])
    if type(val) == types.ListType:
      _OUTPUT = []
      for j,_val in enumerate(val):
        if type(_val) != types.DictionaryType:
          _OUTPUT.append([{field_name:{'value':  val, 
                           'order':  field['order'],
                           'header': field['header'] if (field['header'] not in ['',None]) else key.replace('_',' ').capitalize(),
                           'style_column_id': field['style_column_id'],
                           'style_field_id':  field['style_field_id'],
                           'style_model_id':  field['style_model_id'],
                           }}])
        else:
          __OUTPUT = []
          keys = rgetattr(node['instance'],field_name+'_keys')
          for key in keys:
            values_by_keys = []
            try:
             _value = _val[key]
            except:
              _value = None
            __OUTPUT.append({key:{'value':  _val.get(key,None), 
                               'order':  field['order'],
                               'header': field['header'] if (field['header'] not in ['',None]) else key.replace('_',' ').capitalize(),
                               'style_column_id': field['style_column_id'],
                               'style_field_id':  field['style_field_id'],
                               'style_model_id':  field['style_model_id'],
                               }})
          _OUTPUT.append(__OUTPUT)
      OUT = appendi_destra(_OUTPUT)
  print OUT
  return OUT

################################## MAIN FUNCTION ##################################

def extractor(export,filepath=None,qs=None):
  '''
  Funzione per esportazione configurabile di attributi di istenze dei modelli
  '''
  df = pd.DataFrame() # serve come patch
  base_model = get_model(export.app, export.model.model)
  if not qs:
    qs = base_model.objects.all()
  if filepath==None:
    filepath = export.get_filepath()

  ############################# EXCEL HEADER #############################
  if export.file_type in ['xlsx','xls']:
    if export.file_type == 'xls':
      writer    = pd.ExcelWriter(filepath, engine='xlwt',options={'encoding':'utf-8'})
    else: # default xlsx
      writer    = pd.ExcelWriter(filepath, engine='xlsxwriter')
    workbook  = writer.book
    STILI = {}
    from .models import StyleExport # se lo metto in cima al file da problemi perchè urls risolve prima questo url a causa di action dinamiche prima dei models
    # AGGIUNGO STILI SCELTI
    for style in StyleExport.objects.filter(Q(id__in=[#rgetattr(export.style_field,'id'),
                                                      rgetattr(export.style_model,'id'),
                                                      rgetattr(export.style_column,'id')])|
                                         #   Q(id__in=export.fieldexport_set.values_list('style_field__id'))|
                                            Q(id__in=export.fieldexport_set.values_list('style_model__id'))|
                                            Q(id__in=export.fieldexport_set.values_list('style_column__id'))
                                            ).distinct().order_by('id'):
      STILI[style.id] = workbook.add_format(style.css)
  ##########################################################
  # ELABORO OGNI SHEET
  dfs = []
  for sheet in export.sheetexport_set.all():
    # CREAZIONE STRUTTURA DICT DELLA CONFIGURAZIONE
    paths     = sheet.fieldexport_set.values('model','field','order','field_header','style_column_id','style_field_id','style_model_id').distinct()
    structure = build_nested_structure(base_model,paths)['children']['None']
    ROWS_OUT  = []
    # ELABORO IL QUERYSET
    if qs.count() > 0:
      for j,instance in enumerate(qs):
        # CREAZIONE DATI
        data      = build_nested_data(instance,structure)
       #raise Exception(data)
        data_flat = traverse_nested_data(data)
        for a in data_flat:
          ROWS_OUT.append([i['value'] for i in a])
        # CREAZIONE HEADER
        if j==0:
          num_colonne = len(data_flat)
          num_righe   = len(data_flat[0])
          _header_columns = [i['header'] for i in data_flat[0]]
          _header_order   = [i['header'] for i in sorted(data_flat[0], key=lambda k: k['order']) ]
      # CARICO I DATI NELLO SHEET
      df = pd.DataFrame(ROWS_OUT)
      df.columns = _header_columns
      # RIORDINO LE COLONNE
      df = df[_header_order]
      ############################# EXCEL EXPORT #############################
      if export.file_type in ['xlsx','xls']:
        # ESPORTO I DATI
        df.to_excel(writer,sheet_name=sheet.sheet_name,index=False)
        # APPLICO GLI STILI DELLO SHEET
        worksheet = writer.sheets[sheet.sheet_name]
        for j,col in enumerate(data_flat[0]):
          #print j
          column_style_id = col['style_column_id'] or rgetattr(export.style_model,'id')
          if column_style_id > 0:
            worksheet.conditional_format(1,j,num_colonne+1,j, {'type': 'no_errors','format': STILI[column_style_id]})
          model_style_id = col['style_model_id'] or rgetattr(export.style_model,'id')
          if model_style_id > 0:
            worksheet.conditional_format(0,j,0,j, {'type': 'no_errors','format': STILI[model_style_id]})
      else:
        dfs.append(df)
  ##########################################################
  if filepath: # BUG: scrive nel filesystem con lo stesso nome => problema concorrenza
    if os.path.exists(filepath):
      try:
        os.unlink(filepath)
      except:
        raise Exception(_('Cannot delete old temporary file: %(filepath)s') % ({'filepath':filepath}))
  ############################# SAVE FILE #############################
  if export.file_type in ['xlsx','xls']:
    writer.save()
  elif export.file_type == 'html': # occhio che qui ci deve essere solo uno sheet
    f = open(filepath, "w")
    # NOTA: qui uso l'ultimo df
    html = render_to_string(os.path.basename(export.template.template.name), {
             'datas': [{
             'COLUMNS_HEADER': df.columns, # NOTA: lavorare sul porting dell'html
             'ROWS_RESTORED':  df
             } for df in dfs
           })
    f.write(html)
    f.close()
  elif export.file_type == 'pdf': # occhio che qui ci deve essere solo uno sheet
    html = render_to_string(os.path.basename(export.template.template.name), {
             'datas': [{
             'COLUMNS_HEADER': df.columns, # NOTA: lavorare sul porting dell'html
             'ROWS_RESTORED':  df
             } for df in dfs
           })
    payload_out = {
      'attachment': True, 
      'filename':   filepath,
      'html':       html
      }
    create_pdf(payload_out,save=True)
  else:
    raise Exception(_('No filetype found for saving'))
