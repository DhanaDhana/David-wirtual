from django.contrib import admin
from django import forms
from .models import CategoryAndSubCategory, CategoryLabel, ClientLabelData, Provider, Instrument, Templates, TemplateCategory, ClientInstrumentInfo,\
    Document, Client, StatusCollection, ActivityFlow, DocumentSetting, CAP_settings, Reminder, TaskCollection, ClientTask, ClientTaskComments, \
    Staff, Company, RecommendationNotificationStatus, ClientTaskTimeline,ClientRecommendationNotification,\
    FeeRuleConfig,Reason,FundRisk,DraftReccomendation,Function,InstrumentsRecomended,MasterKeywords,\
    ExtractionKeywordMapping,ExtractedData,TemplateAttachments, ATR, SRProviderContent, SRAdditionalCheckContent, \
    ProductType, DraftCheckList, ClientCheckList, CategorySummary, IllustrationKeywordMapping, ClientCheckListArchive, IllustrationData, \
    Smartserachlog,Smartserach,Errorlog

from cap_outlook_service.outlook_services.models import MailFolder, Email, OutlookLog, Event, Attachments, OutlookCredentials, Attendees, OutlookSync, OutlookSyncErrorLog

from django.contrib.auth.models import Group, Permission

from .forms import GroupMenuForm
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin import SimpleListFilter, FieldListFilter
from django.utils import timezone




import datetime

test_company_list = ['Maincorps']

admin.site.register(CategoryAndSubCategory)
admin.site.register(CategoryLabel)
admin.site.register(ClientLabelData)
admin.site.register(Provider)
admin.site.register(Instrument)
admin.site.register(Templates)
admin.site.register(TemplateCategory)
admin.site.register(ClientInstrumentInfo)
admin.site.register(Document)
admin.site.register(Client)
admin.site.register(StatusCollection)
admin.site.register(OutlookCredentials)
admin.site.register(ActivityFlow)
admin.site.register(DocumentSetting)
admin.site.register(CAP_settings)
admin.site.register(Reminder)
admin.site.register(TaskCollection)
admin.site.register(ClientTask)
admin.site.register(ClientTaskComments)
admin.site.register(Staff)
admin.site.register(Company)
admin.site.register(RecommendationNotificationStatus)
admin.site.register(ClientTaskTimeline)
admin.site.register(ClientRecommendationNotification)
admin.site.register(Permission)

admin.site.register(MailFolder)
admin.site.register(Email)
admin.site.register(Event)
admin.site.register(OutlookLog)
admin.site.register(Errorlog)


class InstrumentSortFilter(SimpleListFilter):
    title = 'Instrument' # or use _('product') for translated title
    parameter_name = 'instrument'

    def lookups(self, request, model_admin):
        return [(p.id, p.instrument_name) for p in Instrument.objects.all().order_by('instrument_name')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        ids = [inst.id for inst in Instrument.objects.filter(id=self.value())]
        return queryset.filter(instrument_id__in=ids)


class ExtractionKeywordMappingAdmin(admin.ModelAdmin):
    list_display = ('create_time', 'instrument','master_keywords', 'mapped_keywords', 'is_value_based', 'position','description_endswith')
    list_filter = (InstrumentSortFilter,)
    list_per_page = 20


admin.site.register(ExtractionKeywordMapping, ExtractionKeywordMappingAdmin)



class ProductFilter(SimpleListFilter):
    title = 'product'  # or use _('product') for translated title
    parameter_name = 'product'

    def lookups(self, request, model_admin):
        return [(p.id, p.name) for p in Provider.objects.all()]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        ids = [inst.id for inst in ClientInstrumentInfo.objects.filter(provider_id=self.value())]
        return queryset.filter(client_instrumentinfo_id__in=ids)

class InstrumentFilter(SimpleListFilter):
    title = 'Instrument'  
    parameter_name = 'instrument'

    def lookups(self, request, model_admin):
        return [(p.id, p.instrument_name) for p in Instrument.objects.all()]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        ids = [inst.id for inst in ClientInstrumentInfo.objects.filter(instrument_id=self.value())]
        return queryset.filter(client_instrumentinfo_id__in=ids)

class ExtractedDataAdmin(admin.ModelAdmin):
    list_display = ('create_time','instrument','master_keywords', 'map_keyword', 'position',
                    'extracted_value', 'extracted_description','description_endswith')
    list_filter = ('master_keywords', ProductFilter, InstrumentFilter)
    list_per_page = 20

    def instrument(self, obj):
        try:
            return str(obj.client_instrumentinfo.instrument.id)+"-"+ str(obj.client_instrumentinfo)
        except Exception as e:
            print("Exception in ExtractedDataAdmin - Instrument",e)
            return None
    instrument.short_description = 'Instrument'
    instrument.admin_order_field = 'instrument'

    def map_keyword(self, obj):
        try:
            return obj.extraction_keyword.mapped_keywords
        except Exception as e:
            print("Exception in ExtractedDataAdmin - map_keyword ",e)
            return None
    map_keyword.short_description = 'Map Keywords'
    map_keyword.admin_order_field = 'map_keywords'

    def description_endswith(self, obj):
        try:
            return obj.extraction_keyword.description_endswith
        except Exception as e:
            print("Exception in ExtractedDataAdmin - description_endswith",e)
            return None
    description_endswith.short_description = 'Description endswith'
    description_endswith.admin_order_field = 'description_endswith'

    def position(self, obj):
        try:
            if obj.extraction_keyword.position == 'SR':
                return 'SAME_ROW'
            elif obj.extraction_keyword.position == 'NR':
                return  'NEXT_ROW'
            return obj.extraction_keyword.position
        except Exception as e:
            print("Exception in ExtractedDataAdmin - position",e)
            return None
    position.short_description = 'Position'
    position.admin_order_field = 'position'

admin.site.register(ExtractedData, ExtractedDataAdmin)

admin.site.register(DraftCheckList)
admin.site.register(ClientCheckList)
admin.site.register(ClientCheckListArchive)
admin.site.register(CategorySummary)


from django.utils.safestring import mark_safe
class ATRAdmin(admin.ModelAdmin):
    fields = ('risk_type', 'loss_percentage', 'content', 'extra_content', 'risk_graph', 'risk_graph_preview', 'risk_portfolio', 'risk_portfolio_preview')
    readonly_fields = ('risk_portfolio_preview','risk_graph_preview')

    def risk_portfolio_preview(self, obj):
        if obj.risk_portfolio:
            return mark_safe('<a href="{0}" target="blank"> <img src="{0}" width="250" height="250" style="object-fit:contain" /> </a>'.format(obj.risk_portfolio.url))
        else:
            return '(No preview)'

    def risk_graph_preview(self, obj):
        if obj.risk_graph:
            return mark_safe('<a href="{0}" target="blank"> <img src="{0}" width="250" height="250" style="object-fit:contain" /> </a>'.format(obj.risk_graph.url))
        else:
            return '(No preview)'

class FeeRuleAdmin(admin.ModelAdmin):
    fields = ('charge_name', 'start', 'end', 'interval', 'interval_type', 'default_value')

admin.site.register(ATR, ATRAdmin)

admin.site.register(SRAdditionalCheckContent)
admin.site.register(ProductType)

admin.site.register(FeeRuleConfig, FeeRuleAdmin)
admin.site.register(Reason)
admin.site.register(FundRisk)
admin.site.register(DraftReccomendation)
admin.site.register(Function)
admin.site.register(InstrumentsRecomended)
admin.site.register(TemplateAttachments)
admin.site.register(Smartserachlog)
admin.site.register(Smartserach)


class SmartserachlogAdmin(admin.ModelAdmin):

    list_display = ('id','create_time','request_url','method')
    list_filter = ('method',)
    list_per_page = 20


admin.site.unregister(Smartserachlog)
admin.site.register(Smartserachlog, SmartserachlogAdmin)


admin.site.register(SRProviderContent)
from tinymce.widgets import TinyMCE


class SRPageForm(forms.ModelForm):
    content = forms.CharField(widget=TinyMCE(attrs={'cols': 120, 'rows': 20}))

    class Meta:
        model = SRProviderContent
        fields = ('provider', 'content')

class SRAdmin(admin.ModelAdmin):
    form = SRPageForm
    list_display = ('provider',)

admin.site.unregister(SRProviderContent)
admin.site.register(SRProviderContent, SRAdmin)


from django.contrib.auth.admin import UserAdmin, GroupAdmin

'''staff model changes for adding staff with user in same panel'''

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'first_name' , 'last_name', )

class UserAdmin(UserAdmin):
    add_form = UserCreateForm
   
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name','email','username', 'password1', 'password2','groups','is_staff'),
        }),
    )

    def get_queryset(self, request): 
        # For Django < 1.6, override queryset instead of get_queryset
        queryset = super(UserAdmin, self).get_queryset(request) 

        u_group = request.user.groups.values_list('name', flat=True)
        if 'Admin' in u_group:
            c_ids = [company_obj.id for company_obj in Company.objects.filter(name__in=test_company_list)]
            staff_user_ids = [s.user.id for s in Staff.objects.filter(company_id__in=c_ids)]
            client_by_staff = [c.user.id for c in Client.objects.filter(created_by__in=staff_user_ids)]
            exclude_list = set(staff_user_ids + client_by_staff)
            queryset= queryset.exclude(id__in=exclude_list)

        
        return queryset


    def get_changeform_initial_data(self, request):
        return {
            'is_staff': True
        }



admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class StaffCreateForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = '__all__'

    def __init__(self, *args, **kwargs):     
        super(StaffCreateForm, self).__init__(*args, **kwargs)
        self.fields['company'].queryset = Company.objects.filter(is_client_company=False)
        self.fields['user'].queryset = User.objects.filter(is_staff=True)
        self.fields['created_by'].queryset = User.objects.filter(is_staff=True,is_superuser=True)


class CompanySortFilter(SimpleListFilter):
    title = 'Company' 
    parameter_name = 'company'

    def lookups(self, request, model_admin):
       
        u_group = request.user.groups.values_list('name', flat=True)
        if 'Admin' in u_group:
            return [(p.id, p.name) for p in Company.objects.all().exclude(name__in=test_company_list).order_by('name') if not p.is_client_company]
        else:
            return [(p.id, p.name) for p in Company.objects.all().order_by('name') if not p.is_client_company]

    def queryset(self, request, queryset):
        u_group = request.user.groups.values_list('name', flat=True)
        if 'Admin' in u_group:
            c_ids = [company_obj.id for company_obj in Company.objects.filter(name__in=test_company_list)]
            queryset = queryset.exclude(company_id__in=c_ids) 
        if not self.value():
            return queryset
        ids = [company_obj.id for company_obj in Company.objects.filter(id=self.value())]
        return queryset.filter(company_id__in=ids)


class StaffAdmin(admin.ModelAdmin):

    form = StaffCreateForm
    list_display = ('user','company','created_by','designation',)
    list_filter = (CompanySortFilter,)
    list_per_page = 20


admin.site.unregister(Staff)
admin.site.register(Staff, StaffAdmin)

class GroupMenuAdmin(GroupAdmin):

    def get_form(self, request, obj=None, **kwargs):
        form = super(GroupMenuAdmin, self).get_form(request, obj, **kwargs)
        if 'permissions' in form.base_fields:
            permissions = form.base_fields['permissions']
            allowed_permissions = permissions.queryset.none()  #initializing an empty queryset
            for m in [Staff, ATR, FeeRuleConfig, SRProviderContent, User]:
                ct = ContentType.objects.get_for_model(m)
                queryset1 = permissions.queryset.filter(content_type=ct)
                allowed_permissions = allowed_permissions | queryset1
            permissions.queryset = allowed_permissions
        return form

admin.site.unregister(Group)
admin.site.register(Group, GroupMenuAdmin)


from auditlog.registry import auditlog
auditlog.register(Client)
auditlog.register(Document)
auditlog.register(ClientInstrumentInfo)
auditlog.register(ActivityFlow)
auditlog.register(Reminder)
auditlog.register(ClientTask)
auditlog.register(ClientTaskComments)
# auditlog.register(Staff)
auditlog.register(ClientTaskTimeline)
auditlog.register(ClientRecommendationNotification)
auditlog.register(ExtractionKeywordMapping)
auditlog.register(ExtractedData)
auditlog.register(DraftCheckList)
auditlog.register(ClientCheckList)
auditlog.register(DraftReccomendation)
auditlog.register(InstrumentsRecomended)




class MasterKeywordsAdminForm(forms.ModelForm):
    class Meta:
        model = MasterKeywords
       
        fields = '__all__' # required for Django 3.x
    
    PLANNING_CHOICES = (
    ('1','LOA_Response'),
    ('2','Illustration'),
    )

    keyword_type = forms.MultipleChoiceField(required=True, choices = PLANNING_CHOICES, widget=forms.CheckboxSelectMultiple,)
   

class MasterKeywordsAdmin(admin.ModelAdmin):
    form = MasterKeywordsAdminForm

admin.site.register(MasterKeywords, MasterKeywordsAdmin)


class IllustrationKeywordMappingAdmin(admin.ModelAdmin):
    list_display = ('create_time', 'provider', 'master_keywords', 'mapped_keywords', 'is_value_based', 'position', 'table_head')

    list_per_page = 20

    def render_change_form(self, request, context, *args, **kwargs):
         context['adminform'].form.fields['master_keywords'].queryset = MasterKeywords.objects.filter(keyword_type__contains=['2'])
         return super(IllustrationKeywordMappingAdmin, self).render_change_form(request, context, *args, **kwargs)

admin.site.register(IllustrationKeywordMapping, IllustrationKeywordMappingAdmin)

class IllustrationDataAdmin(admin.ModelAdmin):
    list_display = ('create_time','instrument','master_keywords', 'map_keyword', 'position',
                    'extracted_value','extracted_type','extracted_description','description_endswith')
    list_filter = ('master_keywords', ProductFilter, InstrumentFilter)
    list_per_page = 20

    def instrument(self, obj):
        try:
            return str(obj.client_instrumentinfo.instrument.id)+"-"+ str(obj.client_instrumentinfo)
        except Exception as e:
            print("Exception in IllustrationDataAdmin - instrument",e)
            return None
    instrument.short_description = 'Instrument'
    instrument.admin_order_field = 'instrument'

    def map_keyword(self, obj):
        try:
            return obj.extraction_keyword.mapped_keywords
        except Exception as e:
            print("Exception in IllustrationDataAdmin - mapped_keywords ",e)
            return None
    map_keyword.short_description = 'Map Keywords'
    map_keyword.admin_order_field = 'map_keywords'

    def description_endswith(self, obj):
        try:
            return obj.extraction_keyword.description_endswith
        except Exception as e:
            print("Exception in IllustrationDataAdmin - description_endswith ",e)
            return None
    description_endswith.short_description = 'Description endswith'
    description_endswith.admin_order_field = 'description_endswith'

    def position(self, obj):
        try:
            if obj.extraction_keyword.position == 'SR':
                return 'SAME_ROW'
            elif obj.extraction_keyword.position == 'NR':
                return  'NEXT_ROW'
            return obj.extraction_keyword.position
        except Exception as e:
            print("Exception in IllustrationDataAdmin - position ",e)
            return None
    position.short_description = 'Position'
    position.admin_order_field = 'position'
admin.site.register(IllustrationData, IllustrationDataAdmin)








class DateFieldListFilter(FieldListFilter):
    def __init__(self, field, request, params, model, model_admin, field_path):
        self.field_generic = '%s__' % field_path
        self.date_params = dict([(k, v) for k, v in params.items()
                                 if k.startswith(self.field_generic)])

        now = timezone.now()
        # When time zone support is enabled, convert "now" to the user's time
        # zone so Django's definition of "Today" matches what the user expects.
        if timezone.is_aware(now):
            now = timezone.localtime(now)

        # if isinstance(field, model.DateTimeField):
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # else:       # field is a models.DateField
        #     today = now.date()
        tomorrow = today + datetime.timedelta(days=1)

        self.lookup_kwarg_since = '%s__gte' % field_path
        self.lookup_kwarg_until = '%s__lt' % field_path
        self.links = (
            (('Any date'), {}),
            (('Today'), {
               self.lookup_kwarg_since: str(today),
                self.lookup_kwarg_until: str(tomorrow),
            }),
            (('Past 7 days'), {
                self.lookup_kwarg_since: str(today - datetime.timedelta(days=7)),
                self.lookup_kwarg_until: str(tomorrow),
            }),
            (('This month'), {
                self.lookup_kwarg_since: str(today.replace(day=1)),
                self.lookup_kwarg_until: str(tomorrow),
            }),
            (('This year'), {
                self.lookup_kwarg_since: str(today.replace(month=1, day=1)),
                self.lookup_kwarg_until: str(tomorrow),
            }),
        )
        super(DateFieldListFilter, self).__init__(
            field, request, params, model, model_admin, field_path)

    def expected_parameters(self):
        return [self.lookup_kwarg_since, self.lookup_kwarg_until]

    def choices(self, cl):
        for title, param_dict in self.links:
            yield {
                'selected': self.date_params == param_dict,
                'query_string': cl.get_query_string(
                                    param_dict, [self.field_generic]),
                'display': title,
            }

FieldListFilter.register( lambda f: isinstance(f, models.DateField), DateFieldListFilter)


#to show distinct dates in the filter section
# class CreateDateFilter(SimpleListFilter):
#     title = 'create date'  # or use _('product') for translated title
#     parameter_name = 'create date'

#     def lookups(self, request, model_admin):
#         return [(p.id, p.create_time.date) for p in ActivityFlow.objects.all().order_by('-create_time__date').distinct('create_time__date')]

#     def queryset(self, request, queryset):
#         if not self.value():
#             return queryset
#         queryset = queryset.filter(create_time=self.value())
#         return queryset


class ClientFilter(SimpleListFilter):
    title = 'client'  
    parameter_name = 'client'

    def lookups(self, request, model_admin):
        return [(p.client_id, p.client) for p in ActivityFlow.objects.all().order_by('client__user__username').distinct('client__user__username')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        queryset = queryset.filter(client__id=self.value())
        return queryset


class StaffFilter(SimpleListFilter):
    title = 'action performed by'  
    parameter_name = 'action performed by'

    def lookups(self, request, model_admin):
        return [(p.action_performed_by_id, p.action_performed_by) for p in ActivityFlow.objects.all().order_by('action_performed_by__username').distinct('action_performed_by__username')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        queryset = queryset.filter(action_performed_by__id=self.value())
        return queryset


class ActivityFlowAdmin(admin.ModelAdmin):
    date_hierarchy = 'create_time'
    list_display = [ 'client', 'action_performed_by', 'status', 'client_instrument','create_time']
   
    list_filter = [('create_time', DateFieldListFilter), ClientFilter, StaffFilter]
    list_per_page = 20

    def create_time(self, obj):
        try:
            return obj.create_time
        except ValueError as e:
            print("value error in ActivityFlowAdmin",e)
            return None


admin.site.unregister(ActivityFlow)
admin.site.register(ActivityFlow, ActivityFlowAdmin)




class ClientSortFilter(SimpleListFilter):
    title = 'Advisor' 
    parameter_name = 'clients'

    def lookups(self, request, model_admin):
        return [(p.id, p.email) for p in User.objects.filter(groups__name__in=['Advisor'])]

    def queryset(self, request, queryset):
        
        if not self.value():
            return queryset
        ids = [client_obj.created_by for client_obj in Client.objects.filter(created_by__id=self.value())]
        return queryset.filter(created_by__in=ids)


class ClientAdmin(admin.ModelAdmin):
    date_hierarchy = 'create_time'
    list_display = ('user','created_by','confirm_client_date', 'create_time')
    list_filter = (ClientSortFilter,)
    list_per_page = 20

admin.site.unregister(Client) 
admin.site.register(Client, ClientAdmin)




class SyncCategoryFilter(SimpleListFilter):
    title = 'Sync Category'
    parameter_name = 'sync_category'

    def lookups(self, request, model_admin):
        return [(p.sync_category, p.get_sync_category_display()) for p in OutlookSyncErrorLog.objects.all().order_by('sync_category').distinct('sync_category')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        queryset = queryset.filter(sync_category=self.value())
        return queryset

class ErrorCategoryFilter(SimpleListFilter):
    title = 'Error Category'
    parameter_name = 'error_category'

    def lookups(self, request, model_admin):
        return [(p.error_category, p.get_error_category_display()) for p in OutlookSyncErrorLog.objects.all().order_by('error_category').distinct('error_category')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        queryset = queryset.filter(error_category=self.value())
        return queryset

class UserFilter(SimpleListFilter):
    title = 'User'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        return [(p.user_id, p.user) for p in OutlookSyncErrorLog.objects.all().order_by('user__username').distinct('user__username')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        queryset = queryset.filter(user__id=self.value())
        return queryset

class OutlookSyncErrorLogAdmin(admin.ModelAdmin):
    date_hierarchy = 'cron_start_time'
    list_display = ('user', 'sync_category','cron_start_time', 'error_category', 'error_message')
    list_filter = (SyncCategoryFilter, ErrorCategoryFilter, UserFilter)
    list_per_page = 25

admin.site.register(OutlookSyncErrorLog, OutlookSyncErrorLogAdmin)




class SyncUserFilter(SimpleListFilter):
    title = 'User'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        return [(p.user_id, p.user) for p in OutlookSync.objects.all().order_by('user__username').distinct('user__username')]

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        queryset = queryset.filter(user__id=self.value())
        return queryset

class OutlookSyncAdmin(admin.ModelAdmin):
    date_hierarchy = 'create_time'
    list_display = ('user', 'sync_category', 'status', 'create_time')
    list_filter = ('sync_category', 'status', SyncUserFilter)
    list_per_page = 25
admin.site.register(OutlookSync, OutlookSyncAdmin)