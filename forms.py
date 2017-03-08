# -*- coding: utf-8 -*-

# standard library
from django.utils.translation import ugettext as _
from django import forms
from django.contrib.contenttypes.models import ContentType

# flexport packet
from models import Export,SheetExport
import xlwt

class ExportForm(forms.ModelForm):
  class Meta:
    model = Export    
    #fields = '__all__'
    widgets = { 'app':  forms.Select() }
    fields  = ['action_name', 'active', 'app', 'depth', 'description', 'exclude_models', 'file_name', 'file_type', 'groups', 'model', 'style_column', 'style_field', 'style_model', 'template']
 
  def clean(self):
    cl_data   = self.cleaned_data
    file_type = cl_data.get('file_type')
    template  = cl_data.get('template')
    if file_type in ['pdf','html'] and template == None:
      raise forms.ValidationError(_("You must set the template when you choose one of HTML or PDF export types"))
    return cl_data
  def __init__(self, *args, **kwargs):  
    super(ExportForm, self).__init__(*args, **kwargs)  
    self.fields["app"].widget.choices = [(i,i) for i in ContentType.objects.all().values_list('app_label',flat=True).order_by().distinct()]
    
        
        
class SheetExportForm(forms.ModelForm):
    class Meta:
      model  = SheetExport
      fields = ['export', 'order', 'sheet_name']
    def clean_sheet_name(self):
      data = self.cleaned_data['sheet_name']
      if not xlwt.Utils.valid_sheet_name(data):
        raise forms.ValidationError(_("Some characters are invalids. Ex.[]:\\?/*\x00 "))
      return data
