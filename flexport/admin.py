# -*- coding: utf-8 -*-

# standard library
import re
from django.contrib import admin
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.conf import settings

# flexport packet
from models import Export, SheetExport, FieldExport, StyleExport, ExportTemplate
from forms import ExportForm,SheetExportForm

from django.contrib.contenttypes.models import ContentType
admin.site.register(ContentType)

############################ INLINE ############################
from django import forms
class InvoiceOrderInlineFormset(forms.models.BaseInlineFormSet):
  def clean(self):
    # get forms that actually have valid data
    count = 0
    for form in self.forms:
      try:
        if form.cleaned_data:
          count += 1
      except AttributeError:
        # annoyingly, if a subform is invalid Django explicity raises
        # an AttributeError for cleaned_data
        pass
    if count < 1:
      raise forms.ValidationError('You must have at least one order')

#try:
    #https://github.com/btaylordesign/django-admin-sortable
#from adminsortable.admin import SortableTabularInline
#except:
#    from django.contrib.admin import TabularInline as SortableTabularInline
from django import forms
from django.contrib.admin import TabularInline as SortableTabularInline

class SheetExportInline(SortableTabularInline):
  form    = SheetExportForm
  model   = SheetExport
  extra   = 1
  formset = InvoiceOrderInlineFormset

class FieldExportInline(admin.TabularInline):
    compact = True
    model = FieldExport
    extra = 1
    exclude = ['style_field']
    def get_formset(self, request, obj=None, **kwargs):
      formset = admin.TabularInline.get_formset(self,request, obj=None, **kwargs)
      context = RequestContext(request)
      obj_id = int(re.sub("\D", "", request.META['PATH_INFO']) or 0)
      choices = [('','---------')]
      for sheet in SheetExport.objects.filter(export=obj_id).order_by('order'):
        choices.append((sheet.id, '%s. %s' % (sheet.order,sheet)))
      formset.form.base_fields['sheet'].choices = choices
      return formset

############################ MAINS ############################

class ExportTemplateAdmin(admin.ModelAdmin):
    list_display    = ('name',)
    search_fields   = ['name',]
admin.site.register( ExportTemplate,ExportTemplateAdmin )

class StyleExportAdmin(admin.ModelAdmin):
    list_display    = ('name',)
    search_fields   = ['name',]
    fieldsets = (
      (_('Details'), {
        'fields': (
          ('name'),
        )
      }),
      (_('Font'), {
        'fields': (
          ('font_family'),
          ('colour'),
        #  ('height'),
          ('italic'),
          ('bold'),
          ('shadow'),
          ('outline'),
         # ('struck_out'),
          ('underline'),
          ('charset'),
        )
      }),
      (_('Align'), {
        'fields': (
          ('horizontal'),
          ('vertical'),
          ('direction'),
          ('rotation'),
          ('indent'),
          ('shrink_to_fit'),
          ('wrap'),
        )
      }),
      (_('Borders'), {
        'fields': (
          ('left','left_colour'),
          ('right','right_colour'),
          ('top','top_colour'),
          ('bottom','bottom_colour'),
          ('diag','diag_colour'),
          ('need_diag_1','need_diag_2'),
        )
      }),
      (_('Pattern'), {
        'fields': (
          ('back_colour'),
          ('fore_colour'),
          ('pattern'),
        )
      }),
    )
admin.site.register( StyleExport,StyleExportAdmin )

class ExportAdmin(admin.ModelAdmin):
    form = ExportForm
    list_display      = ('action_name','file_type','model','active','_export_all','sheets_tot','fields_tot')
    list_filter       = ['file_type','model','active']
    search_fields     = ['description','action_name']
    #filter_horizontal = ('groups','exclude_models')
    raw_id_fields     = ('groups','exclude_models',)
    autocomplete_lookup_fields = {
        #'fk': ['related_fk'],
        'm2m': ['groups','exclude_models'],
    }

    def change_view(self, request, object_id, form_url='', extra_context=None):
      self.inlines=[SheetExportInline,FieldExportInline]
      return super(ExportAdmin, self).change_view(request, object_id, form_url, extra_context)
    def add_view(self, request, form_url='', extra_context=None):
      self.inlines=[SheetExportInline]
      return super(ExportAdmin, self).add_view(request,form_url, extra_context)

    fieldsets = (
      (_('Details'), {
        'fields': (
          ('file_type'),
          ('template'),
          ('action_name'),
          ('file_name'),
          ('description'),
        )
      }),
      (_('Related tables'), {
        'fields': (
          ('app'),
          ('model'),
          ('depth'),
          ('exclude_models'),
        )
      }),
      (_('Enabling'), {
        'fields': (
          ('active'),
          ('groups'),
        )
      }),
      (_('Default styles'), {
        'fields': (
          ('style_model'),
        #  ('style_field'),
          ('style_column'),
        )
      }),
    )  
    # link nella change_list per testare l'export di tutti i dati del modello impostato
    def _export_all(self,obj):
        return ('<a href="%s/extract/%d/">'+_('Export')+'</a>') % (settings.FORCE_SCRIPT_NAME_URL if settings.FORCE_SCRIPT_NAME_URL else '',obj.id)
    _export_all.allow_tags = True
    _export_all.verbose_name = _('Export')

admin.site.register( Export,ExportAdmin )
