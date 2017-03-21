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

xlate ={0xc0:'A', 0xc1:'A', 0xc2:'A', 0xc3:'A', 0xc4:'A', 0xc5:'A',
        0xc6:'Ae', 0xc7:'C',
        0xc8:'E', 0xc9:'E', 0xca:'E', 0xcb:'E',
        0xcc:'I', 0xcd:'I', 0xce:'I', 0xcf:'I',
        0xd0:'Th', 0xd1:'N',
        0xd2:'O', 0xd3:'O', 0xd4:'O', 0xd5:'O', 0xd6:'O', 0xd8:'O',
        0xd9:'U', 0xda:'U', 0xdb:'U', 0xdc:'U',
        0xdd:'Y', 0xde:'th', 0xdf:'ss',
        0xe0:'a', 0xe1:'a', 0xe2:'a', 0xe3:'a', 0xe4:'a', 0xe5:'a',
        0xe6:'ae', 0xe7:'c',
        0xe8:'e', 0xe9:'e', 0xea:'e', 0xeb:'e',
        0xec:'i', 0xed:'i', 0xee:'i', 0xef:'i',
        0xf0:'th', 0xf1:'n',
        0xf2:'o', 0xf3:'o', 0xf4:'o', 0xf5:'o', 0xf6:'o', 0xf8:'o',
        0xf9:'u', 0xfa:'u', 0xfb:'u', 0xfc:'u',
        0xfd:'y', 0xfe:'th', 0xff:'y',
        0xa1:'!', 0xa2:'{cent}', 0xa3:'{pound}', 0xa4:'{currency}',
        0xa5:'{yen}', 0xa6:'|', 0xa7:'{section}', 0xa8:'{umlaut}',
        0xa9:'{C}', 0xaa:'{^a}', 0xab:'<<', 0xac:'{not}',
        0xad:'-', 0xae:'{R}', 0xaf:'_', 0xb0:'{degrees}',
        0xb1:'{+/-}', 0xb2:'{^2}', 0xb3:'{^3}', 0xb4:"'",
        0xb5:'{micro}', 0xb6:'{paragraph}', 0xb7:'*', 0xb8:'{cedilla}',
        0xb9:'{^1}', 0xba:'{^o}', 0xbb:'>>', 
        0xbc:'{1/4}', 0xbd:'{1/2}', 0xbe:'{3/4}', 0xbf:'?',
        0xd7:'*', 0xf7:'/'
        }
def force_to_unicode (unicrap):
    '''
    Force strign to unicode
    '''
    r = ''
    for i in unicrap:
        if xlate.has_key(ord(i)):
            r += xlate[ord(i)]
        elif ord(i) >= 0x80:
            r += ' '
        else:
            r += str(i)
    return r

################################## UTIL FUNCTIONS ##################################

import copy
import pandas as pd
from string import ascii_lowercase

#-------------------------- COSTRUZIONE STRUTTURA ------------------------------------

def build_nested_structure(base_model_origin,paths):
  '''
  Serve per realizzare un dizionario di sintesi con tutti i path impostati nell'esportazione
  '''
  OUT = {'fields':[],'children':{}}
  for path in paths:
    base_model = base_model_origin
    current_level = OUT # carico quello iniziale e appendo tutti i percorsi
    __path = path['model'].split('.')
    for j,part in enumerate(__path):
      if part != 'None':
        #base_model = base_model._meta.get_field(part).related_model # su django 1.10 
        try:   # seguo FK DIRETTE
          base_model = base_model._meta.get_field_by_name(part.replace('_set',''))[0].rel.to
        except:
          try: # seguo FK INVERSE
            base_model = base_model._meta.get_field_by_name(part.replace('_set',''))[0].model
          except:  # link diretto (non so se serve) -> basta provare con un print da shell su un export complesso
            base_model = getattr(base_model,part.replace('_set','')).model
      if part not in current_level['children']:
        current_level['children'][part] = {'fields':[],'children':{},'model':  base_model}
      if len(__path) == j+1: # se sono in fondo al path
        if path['field'] not in [None,'',u'']:
          fields_name = [path['field']]
        else:
          fields_name = [_field.attname for _field in base_model._meta.fields]
        for field_name in fields_name:
          _obj = base_model()
          if getattr(_obj,field_name+'_keys',None)!=None:
            header = getattr(_obj,field_name+'_keys')
          else:
            header = path['field_header']
          current_level['children'][part]['fields'].append({'name':   field_name,
                                                            'order':  path['order'],
                                                            'header': header,
                                                            'style_column_id': path['style_column_id'],
                                                            'style_field_id':  path['style_field_id'],
                                                            'style_model_id':  path['style_model_id'],
                                                            })
      current_level = current_level['children'][part]
  return OUT

#-------------------------- ESTRAZIONE DATI TREE ------------------------------------

def _get_instances(instance,part):
  '''
  Funzione di utilità per l'estrazione delle istanze del path
  '''
  if instance==None:
    return []
  try: # seguo FK INVERSE
    _instances = getattr(instance,part).all()
  except: # seguo FK DIRETTE
    try:
      _instances = [getattr(instance,part)]
    except: # esempio per ONETOONE non avvalorate
      _instances = []
  return list(_instances)

def get_fields(instance,structure):
  FIELDS = []
  for field in structure['fields']:
    if instance == None:
      _value = None
    else:
      _value = rgetattr(instance,field['name'])
    # prova presenza keys -> dict
    #print field
    
    if field['header'] not in ['',u'',None]:
      header = field['header'] # questo può essere una list
    else:
      try:
        header = structure['model']._meta.get_field(field['name']).verbose_name.capitalize()
      except:
        header = (field['name'].replace('_',' ')).capitalize() # TODO

    FIELDS.append({field['name']:{'value':  _value,
                                  'order':  field['order'],
                                  'header': header,
                                  'style_column_id': field['style_column_id'],
                                  'style_field_id':  field['style_field_id'],
                                  'style_model_id':  field['style_model_id'],
                                  }})
  return FIELDS

def build_nested_data(instance,structure): # structure = {'children':DICT, 'fields': []}
  children = {}
  for key, value in structure['children'].iteritems():
    _instances = _get_instances(instance,key) # sono tutte le istanze data dalla singola chiave del children
    children[key] = []
    for _instance in _instances:
      children[key].append( build_nested_data(_instance,value))
    if len(children[key])== 0: # creo la struttura con none come valore dell'elemento
      children[key].append( build_nested_data(None,value))
  return {
    'children': children,
    'fields':   get_fields(instance,structure)
    }

#-------------------------- RICSOTRUZIONE DATI FLAT ---------------------------------- 

def appendi_destra(fields_groups,new_fields): # almeno [[]] , [[]]
  #print fields_groups,new_fields
  if len(new_fields)== 0:
    return fields_groups
  if len(fields_groups)==0:
    return new_fields
  OUT = []
  for fields_group in fields_groups:
    for new_field in new_fields:
      OUT.append(fields_group+new_field)
  return OUT

def add_field(OUT,_field):
 # print '#',_field,'#'
  key,field = [i for i in _field.iteritems()][0]
  val = field['value']

  if (type(field['header']) != types.ListType) and (type(val) not in [types.DictionaryType,types.ListType]):
    #print 'tipo 1',field
    OUT = appendi_destra(OUT,[[field]])


  elif type(val) == types.ListType:
    _OUTPUT = []

    if len(val) > 0 and type(val[0]) != types.DictionaryType:
      #print 'tipo 3 A',field
      for j,_val in enumerate(val):
        header =  field['header'] if (field['header'] not in ['',u'',None]) else key.replace('_',' ').capitalize()
        _OUTPUT.append([{
                  'value':  _val, 
                  'order':  field['order'],
                  'header': header,
                  'style_column_id': field['style_column_id'],
                  'style_field_id':  field['style_field_id'],
                  'style_model_id':  field['style_model_id'],
                  }])
      OUT = appendi_destra(OUT,_OUTPUT)
 
    if len(val) > 0 and type(val[0]) == types.DictionaryType: # QUESTA E' L'ULTIMA COSA DA SISTEMARE....
      #print '---------------------------'
      #print 'tipo 3 B',field
      for j,_val in enumerate(val):
       # ***
        __OUTPUT = []
        if field['header']==None:
          keys = [key in val.keys()]
        else:
          keys = field['header']
        for key in keys:
          values_by_keys = []
          try:
           _value = _val[key]
          except:
            _value = None
          __OUTPUT.append(
                     {
                       'value':  _val.get(key,None), 
                       'order':  field['order'],
                       'header': key.replace('_',' ').capitalize(),
                       'style_column_id': field['style_column_id'],
                       'style_field_id':  field['style_field_id'],
                       'style_model_id':  field['style_model_id'],
                       })
        _OUTPUT.append(__OUTPUT)
      #print
      #print _OUTPUT
      #print
      #print '---------------------------'
      OUT = appendi_destra(OUT,_OUTPUT)
      
      
      
  elif (type(val) == types.DictionaryType) or (type(field['header']) == types.ListType): # *** prima era or
    print 'tipo 2',field
    
    if field['header'] in ['',u'',None]:
      keys = list(val.keys())
    else:
      keys = field['header']
    for key in keys:
      OUT = appendi_destra(OUT,[[{
              'value':  val.get(key,None) if val!=None else None, 
              'order':  field['order'],
              'header': key.replace('_',' ').capitalize(),
              'style_column_id': field['style_column_id'],
              'style_field_id':  field['style_field_id'],
              'style_model_id':  field['style_model_id'],
              }]])


  return OUT

def get_flat_fields(data,OUT = []):# NOTA: ritorna [[A,B,C]] oppure [[A,B,C1],[A,B,C2]] nel caso in cui uno o piu campi ritona piu valori
  # NOTA: questo attraversa in modo opportuno tutta la struttura creata contente i dati... ora deve farli flat
  # NOTA : attenzione -> qui devo anche duplicare le righe e appendere dentro dati (solo su quel percorso)
  for field in data['fields']:
    OUT = add_field(OUT,field) # questo lavora con campi dict, list, list(dict), ecc.
  for key, child in data['children'].iteritems(): # ogni children ha una chiave -> se ho [] faccio spazio, altrimenti duplico le righe se > 1
    _OUT = []
    for _c in child:
      _OUT += get_flat_fields(_c)
    OUT = appendi_destra(OUT,_OUT)
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
  # IMPOSTO L'ESPORTAZIONE
  if os.path.exists(filepath):
    try:
      os.unlink(filepath)
    except:
      raise Exception(_('Cannot delete old temporary file: %(filepath)s') % ({'filepath':filepath}))
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
        data_flat = get_flat_fields(data)
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
      #print _header_columns
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
  elif export.file_type == 'html':
    f = open(filepath, "w")
    # NOTA: qui uso l'ultimo df
    html = render_to_string(os.path.basename(export.template.template.name), {
             'COLUMNS_HEADER': df.columns, # NOTA: lavorare sul porting dell'html
             'ROWS_RESTORED':  df,
             })
    f.write(html)
    f.close()
  elif export.file_type == 'pdf':
    payload_out = {
      'attachment': True, 
      'filename':   filepath,
      'html':       html
      }
    create_pdf(payload_out,save=True)
  else:
    raise Exception(_('No filetype found for saving'))
    