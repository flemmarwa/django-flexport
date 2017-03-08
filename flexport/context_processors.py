# -*- coding: utf-8 -*-
from django.conf import settings

def flexport_prefix(request):
  return {
    'flexport_views_prefix': settings.FLEXPORT_VIEWS_PREFIX 
     }
