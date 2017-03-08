# -*- coding: utf-8 -*-

# standard library
try:
  from django.contrib.gis.db import models
except:
  from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group
from django.template import Context, Template
# flexport packet
from utils_extractor import extractor
from admintools import models_AT
from django.utils.translation import ugettext_lazy as _

try:
  from localsettings import localsettings as settings
except:
  from django.conf import settings

if not hasattr(settings, 'PDF_TEMPLATES_PATH') or not settings.PDF_TEMPLATES_PATH:
  raise Exception(_('PDF_TEMPLATES_PATH is not set in your settings.py'))
if not hasattr(settings, 'TEMP_PATH') or not settings.TEMP_PATH:
  raise Exception(_(' TEMP_PATH is not set in your settings.py'))


def autocomplete_search_fields():
  return ("app_label__icontains", "model__icontains",)

ContentType.autocomplete_search_fields = staticmethod(autocomplete_search_fields)

####################################### EXPORT #######################################
class ExportTemplate(models.Model):
    '''
    Model for manage PDF templates
    '''
    template = models.FileField(_("Template description"),upload_to=settings.PDF_TEMPLATES_PATH)
    name = models.CharField(_(u"Name"),max_length=50)
    class Meta:
        db_table            = u'flexport_templates'
        verbose_name        = _(u'Export template')
        verbose_name_plural = _(u'Esport templates')
    def __unicode__(self):
      return u"%s" % (self.name)

def get_apps_labels():
  return [(i,i) for i in ContentType.objects.values_list('app_label',flat=True).distinct()]

class Export(models.Model):
    '''
    Main model for export data
    '''
    # settings
    # da errore se content type non esiste, per esempio manage.py syncdb iniziale
#    if not hasattr(settings, 'MANAGEMENT_UTILITY') or not settings.MANAGEMENT_UTILITY:
#        APPS           = [(app['app_label'],app['app_label']) for app in ContentType.objects.all().values('app_label').order_by().distinct()]
#    else:
#        APPS = ((None,None),)
    EXPORT_TYPES   = (('xlsx','Excel XLSX'),('xls','Excel XLS'),('pdf','PDF'),('html','HTML'))
    # fields
    description    = models.TextField(_(u"Export description"),blank=True,null=True)
    action_name    = models.CharField(_(u"Action name"),max_length=50)
    file_name      = models.CharField(_(u'File name'),max_length=50,help_text=_(u"It's possibile set model info. Example:")+'"{{NOME}}_{% now "Y-m-d_H-i" %}"')
    file_type      = models.CharField(_(u'File type'),max_length=10,choices=EXPORT_TYPES,default='xlsx')
    template       = models.ForeignKey('ExportTemplate',verbose_name=_('Template'),blank=True,null=True,help_text=_('To set only if you want to export in PDF or HTML'))
    app            = models.CharField(_(u'Reference application'),max_length=100,choices=[])
    model          = models.ForeignKey(ContentType,verbose_name=_(u'Reference model'),help_text = _(u"Main model for data export"))
    depth          = models.IntegerField(_(u'Search depth between models'),choices=[(i,i) for i in range(1,11)],default=3)
    active         = models.BooleanField('Active',default=True,blank=True)
    groups         = models.ManyToManyField(Group,verbose_name=_(u"Enabled groups for this export"),blank=True)
    exclude_models = models.ManyToManyField(ContentType,verbose_name=_(u'Exclude models'),blank=True,related_name='exclude_models')

    style_model    = models.ForeignKey('StyleExport',verbose_name=_(u'Model header style'),blank=True,null=True,related_name='style_model_main',help_text=_(u"Main style, you can overload it in each cell"))
    style_field    = models.ForeignKey('StyleExport',verbose_name=_(u'Field header style'),blank=True,null=True,related_name='style_field_main',help_text=_(u"Main style, you can overload it in each cell"))
    style_column   = models.ForeignKey('StyleExport',verbose_name=_(u'Column header style'),blank=True,null=True,related_name='style_column_main',help_text=_(u"Main style, you can overload it in each cell"))

    class Meta:
        db_table            = u'flexport_exports'
        verbose_name        = _(u'Export model')
        verbose_name_plural = _(u'Export models')
    def __unicode__(self):
      return u"%s" % (self.action_name)
    def extractor(self,filepath=None,qs=None):
        return extractor(self,filepath,qs)
    def get_filename(self):
        t = Template(self.file_name)
        c = Context({"self": self})
        return t.render(c) + '.' + self.file_type
    def get_filepath(self):
        return settings.TEMP_PATH + self.get_filename()
    def is_enabled(self,request):
        if self.active and request: # ONLY BY REQUEST
            if hasattr(request,'user'):
                if request.user:
                    if request.user.is_superuser or len(frozenset(request.user.groups.all()).intersection(self.groups.all())) > 0:
                        return True
        return True
    @property
    def sheets_tot(self):
      return self.sheetexport_set.count()
    @property
    def fields_tot(self):
      return self.fieldexport_set.count()
     
#from adminsortable.models import Sortable
#class SheetExport(Sortable):
class SheetExport(models.Model):
    '''
    Model for set export sheets
    '''
    order      = models.IntegerField(_(u'Sheet order'))
    export     = models.ForeignKey('Export',verbose_name=_(u'Export'))
    sheet_name = models.CharField(max_length=30,verbose_name=_(u'Sheet name'))
#    class Meta(Sortable.Meta):
    class Meta:
        db_table            = u'flexport_sheets'
        verbose_name        = _(u'Export sheet')
        verbose_name_plural = _(u'Export sheets')
        #ordering            = ['order']
    def __unicode__(self):
      return u"%s" % (self.sheet_name)

class FieldExport(models.Model):
    '''
    Fields that are included in sheets with style features
    NOTE: possibility of recursion / duplication of lines per data 1TM
    '''
    order        = models.PositiveIntegerField(_(u'Column order'))
    export       = models.ForeignKey('Export',verbose_name=_(u'Export'))
    sheet        = models.ForeignKey('SheetExport',verbose_name=_('Sheet'))
    model        = models.CharField(_('Model'),max_length=2000)
    field        = models.CharField(_("Field"),max_length=2000,blank=True,null=True)
    field_header = models.CharField(_("Field header"),max_length=255,blank=True,null=True)
    style_model  = models.ForeignKey('StyleExport',verbose_name=_('Model header style'),blank=True,null=True,related_name='style_model')
    style_field  = models.ForeignKey('StyleExport',verbose_name=_('Field header style'),blank=True,null=True,related_name='style_field')
    style_column = models.ForeignKey('StyleExport',verbose_name=_('Column header style'),blank=True,null=True,related_name='style_column')
    class Meta:
        db_table            = u'flexport_fields'
        verbose_name        = _(u'Export field')
        verbose_name_plural = _(u'Export fields')
        ordering            = ['sheet','order']
    def __unicode__(self):
      return u"%s %s" % (self.model,(self.field or ''))
    def get_style_model(self):
      if self.style_model:
        return self.style_model
      if self.export.style_model:
        return self.export.style_model
      return None
    def get_style_field(self):
      if self.style_field:
        return self.style_field
      if self.export.style_field:
        return self.export.style_field
      return None
    def get_style_column(self):
      if self.style_column:
        return self.style_column
      if self.export.style_column:
        return self.export.style_column
      return None

####################################### STYLES #######################################

CHARSET = ('ansi_latin', 'sys_default', 'symbol', 'apple_roman', 'ansi_jap_shift_jis', 'ansi_kor_hangul', 'ansi_kor_johab,ansi_chinese_gbk',
           'ansi_chinese_big5', 'ansi_greek,ansi_turkish', 'ansi_vietnamese', 'ansi_hebrew,ansi_arabic', 'ansi_baltic', 'ansi_cyrillic',
           'ansi_thai', 'ansi_latin_ii', 'oem_latin_i')
CHARSET = [(i,i) for i in CHARSET]
COLOURS_DECOD = (
    ('00FFFF','aqua'),
    ('000000','black'),
    ('0000FF','blue'),
    ('666699','blue_gray'),
    ('00FF00','bright_green'),
    ('993300','brown'),
    ('FF8080','coral'),
#    ('','cyan_ega'),
    ('000080','dark_blue'),
#    ('','dark_blue_ega'),
    ('003300','dark_green'),
#    ('','dark_green_ega'),
    ('660066','dark_purple'),
    ('800000','dark_red'),
#    ('','dark_red_ega'),
#    ('','dark_teal'),
    ('808000','dark_yellow'),
#    ('','gold'),
#    ('','gray_ega'),
    ('C0C0C0','gray25'),
    ('969696','gray40'),
    ('808080','gray50'),
    ('333333','gray80'),
#    ('','grey_ega'),
    ('008000','green'),
    ('CCCCFF','ice_blue'),
    ('333399','indigo'),
    ('FFFFCC','ivory'),
    ('CC99FF','lavender'),
    ('3366FF','light_blue'),
    ('CCFFCC','light_green'),
    ('FF9900','light_orange'),
    ('CCFFFF','light_turquoise'),
    ('FFFF99','light_yellow'),
    ('99CC00','lime'),
#    ('','magenta_ega'),
    ('0066CC','ocean_blue'),
#    ('','olive_ega'),
    ('333300','olive_green'),
    ('FF6600','orange'),
#    ('','pale_blue'),
    ('9999FF','periwinkle'),
    ('FF00FF','pink'),
    ('993366','plum'),
#    ('','purple_ega'),
    ('FF0000','red'),
    ('FF99CC','rose'),
    ('339966','sea_green'),
#    ('','silver_ega'),
    ('00CCFF','sky_blue'),
    ('FFCC99','tan'),
    ('008080','teal'),
#    ('','teal_ega'),
    ('00FFFF','turquoise'),
    ('800080','violet'),
    ('FFFFFF','white'),
    ('FFFF00','yellow')
)

COLOURS = [(i[0],i[0]) for i in COLOURS_DECOD]
FONT_FAMILIES = ('Antiqua','Arial','Avqest','Blackletter','Calibri','Comic Sans','Courier','Decorative','Fraktur',
                 'Frosty','Garamond','Georgia','Helvetica','Impact','Minion','Modern','Monospace','Palatino','Roman',
                 'Script','Swiss','Times New Roman','Verdana','cursive','fantasy','monospace','sans-serif','serif')
FONT_FAMILIES = [(i,i) for i in FONT_FAMILIES]
UNDERLINE  = ('none','single','single_acc','double','double_acc')
UNDERLINE  = [(i,i) for i in UNDERLINE]
HORIZONTAL = ( 'general', 'left', 'center|centre', 'right', 'filled', 'justified', 'center|centre_across_selection', 'distributed')
HORIZONTAL = [(i,i) for i in HORIZONTAL]
VERTICAL   = ( 'top', 'center|centre', 'bottom', 'justified', 'distributed')
VERTICAL   = [(i,i) for i in VERTICAL]
BORDER_BASE     = ('no_line','thin','medium','dashed','dotted','thick','double','hair','mediumDashed','dashDot','mediumDashDot','dashDotDot','mediumDashDotDot','slantDashDot')
BORDER     = [(i,i) for i in BORDER_BASE]
PATTERN    = ('no_fill', 'none', 'solid', 'solid_fill', 'solid_pattern', 'fine_dots', 'alt_bars', 'sparse_dots', 'thick_horz_bands', 'thick_vert_bands', 'thick_backward_diag', 'thick_forward_diag', 'big_spots', 'bricks', 'thin_horz_bands', 'thin_vert_bands', 'thin_backward_diag', 'thin_forward_diag', 'squares', 'diamonds')
PATTERN    = [(i,i) for i in PATTERN]

class StyleExport(models.Model):
    '''
    Model to manage cells styles
    '''
    name = models.CharField(_("Style title"),max_length=255)
    css  = models.TextField(verbose_name="CSS")
    
    # FONT
    bold        = models.BooleanField(_('Font weight'),blank=True,default=False)
    charset     = models.CharField(_('Chars group'),max_length=50,choices=CHARSET,default = 'sys_default')
    colour      = models_AT.ColorLiteField(_('Colour'),max_length=50,choices=COLOURS,default = '000000')
    font_family = models.CharField(_('Font name'),max_length=50,choices=FONT_FAMILIES,default ='Arial')
    #height      = models.IntegerField(_('Font height'),choices=[(i,str(i)) for i in range(20,801,20)],help_text=_('Expressed as multiples of 20 (200 = 10pt)'), default = 200)
    italic      = models.BooleanField(_('Italics'),blank=True,default=False)
    outline     = models.BooleanField(_('Profile'),blank=True,default=False)
    shadow      = models.BooleanField(_('Shadow'),blank=True,default=False)
   # struck_out  = models.BooleanField(_('Struck out'),blank=True,default=False)
    underline   = models.CharField(_('Underline'),max_length=50,choices=UNDERLINE,default ='none')

    # ALIGNMENT
    direction     = models.CharField(_('Direction'),max_length=50,choices=(('general','general'),('lr','lr'),('rl','rl')),default ='general')
    horizontal    = models.CharField(_('Horizontal align'),max_length=50,choices=HORIZONTAL, default ='general')
    indent        = models.IntegerField(_('Indent'),choices=[(i,str(i)) for i in range(0,16)],default = 0)
    rotation      = models.IntegerField(_('Rotation'),choices=[(i,str(i)) for i in range(-90,91)],default = 0)
    shrink_to_fit = models.BooleanField(_('Shrink and fit'),blank=True,default=False)
    vertical      = models.CharField(_('Vertical align'),max_length=50,choices=VERTICAL,default ='bottom')
    wrap          = models.BooleanField(_('Wrap'),blank=True,default=False)
    
    # BORDERS
    left      = models.CharField(_('Left'),max_length=50,choices=BORDER,default ='none')
    right     = models.CharField(_('Right'),max_length=50,choices=BORDER,default ='none')
    top       = models.CharField(_('Top'),max_length=50,choices=BORDER,default ='none')
    bottom    = models.CharField(_('Bottom'),max_length=50,choices=BORDER,default ='none')
    diag      = models.CharField(_('Diagonal'),max_length=50,choices=BORDER,default ='none')
    left_colour   = models_AT.ColorLiteField(_('Left colour'),max_length=50,choices=COLOURS, default ='000000')
    right_colour  = models_AT.ColorLiteField(_('Right colour'),max_length=50,choices=COLOURS,default ='000000')
    top_colour    = models_AT.ColorLiteField(_('Top colour'),max_length=50,choices=COLOURS,default ='000000')
    bottom_colour = models_AT.ColorLiteField(_('Bottom colour'),max_length=50,choices=COLOURS,default ='000000')
    diag_colour   = models_AT.ColorLiteField(_('Diagonal colour'),max_length=50,choices=COLOURS,default ='000000')
    need_diag_1   = models.BooleanField(_('Enable diagonal 1'),blank=True,default=False)
    need_diag_2   = models.BooleanField(_('Enable diagonal 2'),blank=True,default=False)

    # PATTERN
    back_colour = models_AT.ColorLiteField(_('Background colour'),max_length=50,choices=COLOURS,default ='ffffff')
    fore_colour = models_AT.ColorLiteField(_('Foreground colour'),max_length=50,choices=COLOURS,default ='ffffff')
    pattern     = models.CharField(_('Pattern'),max_length=50,choices=PATTERN,default ='none')

    class Meta:
        db_table            = u'flexport_styles'
        verbose_name        = _(u'Export cell style')
        verbose_name_plural = _(u'Export cell styles')
    def __unicode__(self):
      return u"%s" % (self.name)
    
    @property
    def css(self):
      return {
          'font_charset': self.charset,
          'font_color':   dict(COLOURS_DECOD)[self.colour],
          'font_name':    self.font_family,
          'bold':         self.bold,
          'italic':       self.italic,
          'font_outline': self.outline,
          'font_shadow':  self.shadow,
          'underline':    self.underline,
          'align':        self.horizontal,
          'valign':       self.vertical,
          'indent':       self.indent,
          'rotation':     self.rotation,
          'shrink':       self.shrink_to_fit,
          'left':    BORDER_BASE.index(self.left),
          'right':   BORDER_BASE.index(self.right),
          'top':     BORDER_BASE.index(self.top),
          'bottom':  BORDER_BASE.index(self.bottom),
          'left_color':   dict(COLOURS_DECOD)[self.left_colour],
          'right_color':  dict(COLOURS_DECOD)[self.right_colour],
          'top_color':    dict(COLOURS_DECOD)[self.top_colour],
          'bottom_color': dict(COLOURS_DECOD)[self.bottom_colour],
          'bg_color': dict(COLOURS_DECOD)[ self.back_colour],
          'fg_color': dict(COLOURS_DECOD)[self.fore_colour],
          #'parrern': None,
        }
    
try:
    from mpaauth.utils import add_read_permissions
    add_read_permissions(globals())
except:
    pass
