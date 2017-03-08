# -*- coding: utf-8 -*-

# standard library
from django.contrib.contenttypes.models import ContentType
from copy import copy
try:
  from django.contrib.gis.db import models
except:
  from django.db import models
from django.db.models import FieldDoesNotExist
 
def get_related_models(Model,exclude_models):
    '''
    Creazione della lista di attributi che consentono di raggiungere un altro
    modello a partire dal modello di entrata
    '''
    related_models = []
    # campi diretti
    for field in Model._meta.get_fields():
      if field.get_internal_type() in ['ForeignKey','OneToOneField','ManyToManyField']:
        if ContentType.objects.get_for_model(field.related_model) not in exclude_models:
          VAL = field.related_model,field.name
          related_models.append(VAL)
    return related_models

def get_related_models_recursive(FirstModel,depth,exclude_models): # non ciclare sul modello iniziale
    '''
    Crea degli array per raggiungere tutti i modelli legati al principale
    attraversando anche altri modelli
    '''
    # creo l'array base di partenza
    array_links = [[(FirstModel,None)]]+[[(FirstModel,None),item] for item in get_related_models(FirstModel,exclude_models)]
    # ciclo sulla base e continuo ad appendere dita fino al raggiungimento di modelli che non sono
    # nell'array e non hanno legami con altri modelli fuori dall'array
    pointer = 0
    while pointer < len(array_links):
        # prendo l'ultimo modello raggiunto
        (LastModel,field) = array_links[pointer][len(array_links[pointer])-1]
        # estraggo tutti i legami verso altri modelli
        for item in get_related_models(LastModel,exclude_models):
            # se gli altri modelli non sono nell'array li appendo creando un nuovo array
            (item_model,item_field) = item
            if item_model not in [model for (model,field) in array_links[pointer]] and len(array_links[pointer]) < depth:
                app_array_links = array_links[pointer][:] # devo copiarlo altrimenti usa il puntatore
                app_array_links.append(item)
                array_links.append(app_array_links)
        pointer += 1
    return array_links

def get_model_elements(MODEL,verbose=False):
    '''
    Estrae tutti gli attributi di un modello che contengono direttamente i valori: fields e properties
    (quindi non restituisce link ad altri modelli o funzioni)
    '''
    if MODEL == None:
        return []
    else:
        if verbose:
          fields     = [ field.verbose_name for field in MODEL._meta.get_fields() if field.get_internal_type() not in ['ForeignKey','OneToOneField','ManyToManyfield']] # NB escludo i link
        else:
          fields     = [ field.name for field in MODEL._meta.get_fields() if field.get_internal_type() not in ['ForeignKey','OneToOneField','ManyToManyfield'] and not hasattr(field,'upload_to')] # NB escludo i link
        # NB: le proprietà sono molto particolari e conviene usare un try catch -> anche se non è il massimo
        properties = []
        for prop in vars(MODEL):
          if prop not in [i.name for i in MODEL._meta.get_fields()]:
            if type(getattr(MODEL,prop)) == property:
              properties.append(prop)
        # virtual fields
        virtualfields = []
        if hasattr(MODEL,'_mpameta'):
          if hasattr(MODEL._mpameta,'virtual_fields'):
            if verbose:
              virtualfields     = [ field.verbose_name for field in MODEL._mpameta.virtual_fields ]
            else:
              virtualfields     = [ field.name for field in MODEL._mpameta.virtual_fields ]
            virtualfields.sort()
        fields.sort()
        properties.sort()
        return fields + properties + virtualfields

def get_model_elements_values(MODEL,MODEL_Istance):
    '''
    Estrae tutti gli valori degli attributi di un modello che contengono direttamente i valori: fields e properties
    '''
    OUTPUT = []
    for attr in get_model_elements(MODEL):
        if MODEL_Istance!=None:
            item = getattr(MODEL_Istance,attr)
            try:
              if MODEL_Istance._meta.get_field(attr)[0].choices and item!= None:
                item = dict(field.choices)[item]
            except: # c'è il problema delle proprietà :-)
                pass
        else:
            item = ''
        OUTPUT += [item]
    return OUTPUT

def get_all_available_elements(MODEL,depth,exclude_models):
    '''
    Unisce la lista dei modelli legati al modello di entrata con tutti gli attributi
    disponibili dei modelli ottenuti
    '''
    # prendo gli attributi diretti del modello di entrata fields + properties
    fields = [[(MODEL,field)] for field in get_model_elements(MODEL)]
    # prendo la lista dei modelli
    related = get_related_models_recursive(MODEL,depth,exclude_models)
    pointer = 0
    while pointer < len(related):
        app_array_links = copy(related[pointer])
        (rel_model,rel_field) = app_array_links[len(app_array_links)-1] # prendo l'ultimo modello
        for field in get_model_elements(rel_model): # e cerco i relativi attributi
          app_array_links = copy(related[pointer]) 
          app_array_links += [(None,field)]
        related[pointer] = app_array_links
        pointer += 1
    return fields + related

def print_all_available_elements(MODEL,depth):
    '''
    Utilita' per ottenere a monitor l'ouput del modulo di estrazione info
    verso tutti i modelli correlati a quello principale
    '''
    for array in get_all_available_elements(MODEL,depth):
        out = MODEL._meta.model_name
        for (model,field) in array:
            out+= '.' + field
        print out
