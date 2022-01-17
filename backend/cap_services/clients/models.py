from django.db import models
from django.contrib.auth.models import User, Group, AbstractUser
import os
from cap_outlook_service.outlook_services.models import Email, Event
from django.contrib.postgres.fields import ArrayField,JSONField
from datetime import datetime
import re
from django.core.exceptions import ValidationError
from django.conf import settings
from cap_services.settings import IS_S3
import requests
import json
from django.core.validators import MaxLengthValidator



def monkey_patch_userfields():
    username = User._meta.get_field("username")
    firstname = User._meta.get_field("first_name")
    last_name=User._meta.get_field("last_name")
    field_list=[username,firstname,last_name]
    for field in field_list:
        field.max_length=255
        for v in field.validators:
            if isinstance(v, MaxLengthValidator):
                v.limit_value = 255


monkey_patch_userfields()

class ObjManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)



class CapBaseModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='Created Time')
    updated_time = models.DateTimeField(auto_now=True, verbose_name='Updated Time')
    objects = ObjManager()
    original_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self):
        self.is_deleted = True
        self.save()
        
class TemplateCategory(CapBaseModel):
    TEMPLATE_CATEGORY = [
        ('1', 'Document template'),
        ('2', 'Welcome'),
        ('3', 'Meeting'),
        ('4', 'System'),
        ('5', 'HR'),
        ('6', 'General')
    ]
    TEMPLATE_TYPE = [
        ('1', 'Email template'),
        ('2', 'Document template'),
    ]
    temp_type = models.CharField(max_length=1, choices=TEMPLATE_TYPE)
    temp_category = models.CharField(max_length=1, choices=TEMPLATE_CATEGORY)

    def __str__(self):
        return self.get_temp_category_display()

def get_template_path(instance, filename):
    return  'templates/'+filename   

class TemplateAttachments(CapBaseModel):
    template_name = models.CharField(max_length=100)
    category = models.ForeignKey(TemplateCategory, on_delete=models.CASCADE)
    attachment_url = models.FileField(upload_to=get_template_path,null=True, blank=True)
    watchable_attachment =models.BooleanField(default=True)

    def __str__(self):
        return self.template_name



class Templates(CapBaseModel):
    template_name = models.CharField(max_length=100)
    subject = models.CharField(max_length=255,blank=True)
    category = models.ForeignKey(TemplateCategory, on_delete=models.CASCADE)
    content = models.TextField()
    template_header = models.TextField(null=True,blank=True)
    template_footer = models.TextField(null=True,blank=True)
    template_attachment_url = models.ManyToManyField(TemplateAttachments, blank=True)
    def __str__(self):
        return self.template_name


class Provider(CapBaseModel):
    name = models.CharField(max_length=30)
    provider_logo = models.ImageField(blank=True,null=True)
    
    def __str__(self):
        return self.name


class ProductType(CapBaseModel):
    
    FUND_TYPES = [
        ('Pension', 'Pension'),
        ('ISA','ISA'),
        ('GIA','GIA')
    ]
    fund_type = models.CharField(max_length=20, choices=FUND_TYPES, default=1)
    

    def __str__(self):
        return self.fund_type


class Instrument(CapBaseModel):


     instrument_name = models.CharField(max_length=200)
     instrument_description = models.CharField(max_length=255,blank=True,null=True)
     product_type = models.ForeignKey(ProductType, related_name='instrument_product_type', on_delete=models.CASCADE,null=True)
     loa_template = models.ForeignKey(Templates,related_name='loa_template', on_delete=models.CASCADE)
     mail_template = models.ForeignKey(Templates,related_name='mail_template',on_delete=models.CASCADE)
     provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
     mail_id = ArrayField(models.EmailField(max_length=70), null=True, blank=True)
     row_tol = models.IntegerField(null=True,blank=True,default=5)
     remove_background = models.IntegerField(null=True,blank=True,default=0)


     class Meta:
         unique_together = (('instrument_name', 'provider'),)
         ordering = ('instrument_name', )
     def __str__(self):
         return self.instrument_name


class ClientDraft(CapBaseModel):
    pass


class StatusCollection(CapBaseModel):

    CLIENT_STATUSES = [
        ('1.1', 'Basic profile created'),('1.2','Profile details updated'),
        ('1.3', 'Welcome email sent'),('1.4', 'Thanks email received'),
        ('1.5', 'Meeting request sent'),('1.6', 'Meeting request declined'),('1.7', 'Meeting request tentatively accepted'),('1.8', 'Meeting request accepted'),
        ('1.9', 'Voice recorded'),('1.10', 'Voice record summary generated'),

        ('1.11', 'Personal Information survey form updated'),('1.12', 'Personal Information mandatory fields are missing'),
        ('1.13', 'Occupation Information survey form updated'),('1.14', 'Occupation Information mandatory fields are missing'),
        ('1.15', 'Income & Expenditure Summary updated'),
        ('1.16', 'Income & Expenditure Summary mandatory fields are missing'),
        ('1.17', 'Expenditure Data updated'),('1.18', 'Expenditure Data mandatory fields are missing'),
        ('1.62', 'Net Worth Summary updated'), ('1.61', 'Net Worth Summary mandatory fields are missing'),
        ('1.59', 'Plans & ATR updated'), ('1.60', 'Plans & ATR mandatory fields are missing'),
        ('1.63', 'Personal Information survey form completed'),('1.64', 'Occupation Information survey form completed'),
        ('1.65', 'Income & Expenditure Summary completed'),
        #('1.66', 'Expenditure Data completed'),
        ('1.67', 'Net Worth Summary completed'),('1.68', 'Plans & ATR completed'),
        ('1.69','Voice record deleted'),('1.70','Send email for Will Referral Recommendation'),
        ('1.75','Send email for BR19'),('1.76','Send email for HR Insurance Check'),

        ('1.19', 'Product added'),('1.49', 'Product details updated'), ('1.74', 'Product deleted'),
        ('1.20', 'LOA downloaded'),('1.21', 'LOA download pending'),
        ('1.22', 'Signed LOA uploaded'),('1.23', 'Signed LOA upload pending'),('1.50', 'Signed LOA document replaced'),('1.51', 'Signed LOA document deleted'),
        ('1.24', 'LOA mail sent to the providers'), ('1.25', 'LOA mail sending pending'),
        ('1.58', 'Reminder mail sent to the providers'),
        ('1.26', 'Provider responded'),('1.57', 'Provider response pending'),
        ('1.27', 'LOA Response upload completed'), ('1.28', 'LOA Response upload Pending'),('1.52', 'LOA Response doc replaced'),('1.53', 'LOA Response doc deleted'),
        ('1.29', 'Product information doc upload completed'), ('1.30', 'Product information doc upload pending'),('1.54', 'Product information doc replaced'),('1.55', 'Product information doc deleted'),
        ('1.31', 'Data extraction completed'),('1.81', 'Data extraction initiated'), ('1.32', 'Data extraction pending'),
        ('1.33', 'Instrument comparison done'), ('1.34', 'Instrument comparison pending'),
        ('1.35', 'Instrument summary list created'), ('1.36', 'Instrument list selected'), ('1.37', 'Lathe fee edited'), ('1.71', 'Instruments added to recomended list'),
        ('1.38', 'Advisor comments added'),('1.39', 'Run checklist initiated'),('1.40', 'Run checklist in progress'),
        ('1.41', 'Checklist summary generated'), ('1.42', 'Recommendation summary generated'), ('1.72','Draft recommendation summary updated' ),
        ('1.43', 'Draft recommendation template selected'), ('1.44', 'Digital signature added'),('1.45', 'Digital signature to be added'),
        ('1.46', 'Draft recommendation preview enabled'),('1.47', 'Draft recommendation published'), ('1.73','Suitability Report generated'),
        ('1.48', 'Draft report generated'), ('1.56', 'Email sent'),('1.77','Meeting deleted'),('1.78','Checklist status updated amber to green'),('1.79','Checklist status updated amber to red'),('1.80','Product cloned to recomended list'),
        ('2','ATP'),
        ('2.1', 'Client task created'), ('2.2', 'Client task assigned to Ops lead'),('2.3', 'Platform cost doc uploaded'),('2.4','Suitability Report uploaded'),('2.5','Authority to proceed doc uploaded'),
        ('2.6','AML doc uploaded'),('2.7','ATR doc uploaded'),('2.8','Application summary doc uploaded'),('2.9','Fund research doc uploaded'),
        ('2.10','Critical yield doc uploaded'),('2.11','Illustration doc uploaded'),('2.12','Weighted average calculator doc uploaded'),
        ('2.13','LOA doc uploaded'),('2.14','Final meeting request sent'),
        ('3','Post contracting phase'),

    ]


    CLIENT_STATUS_NAMES = [
        ('1', 'Client add'),
        ('2', 'Meeting request'),
        ('3', 'surveyform_Personal information'),
        ('4', 'surveyform_Occupation Info'),
        ('5', 'surveyform_Income & Expenditure Summary'),
        #('6', 'surveyform_Expenditure Data'),
        ('25', 'surveyform_Networth Summary'),
        ('26', 'surveyform_Plans&ATR'),

        ('7', 'Instrument_add'),
        ('29', 'Instrument_remove'),
        ('8', 'Instrument_loa download'),
        ('9', 'Instrument_signed loa upload'),
        ('10', 'Instrument_loa mail sent'),
        ('11', 'Instrument_loa response upload'),
        ('12', 'Instrument_third party doc'),
        ('13', 'Instrument_data extraction'),
        ('14', 'Instrument comparison'),
        ('15', 'Instrument list'),
        ('16', 'Lathe fee'),
        ('17', 'Advisor comments'),
        ('18', 'checklist'),
        ('19', 'Recommendation summary'),
        ('20', 'Draft recommendation'),
        ('21',  'Mail sent'),
        ('22', 'Instrument_loa reminder sent'),
        ('23', 'Instrument_loa mail response'),
        #('24', 'survey_form updates') 
        ('27','Voice record'),
        #('28', 'Will Referral'),
        ('30', 'Client Task'),
        ('31','Meeting Deleted'),
        ('32','Draft recommendation report'),

    ]

    status_name = models.CharField(max_length=5, choices=CLIENT_STATUS_NAMES,null=True)
    status = models.CharField(max_length=5, choices=CLIENT_STATUSES)
    is_percentage_contributing=models.BooleanField(default=False)
    percentage_weightage=models.PositiveIntegerField(default=0)
    remark = models.CharField(max_length=12, null=True, blank=True)

    def __str__(self):
        return self.get_status_display()


class Company(CapBaseModel):
    name = models.CharField(max_length=250)
    url = models.TextField(null=True, blank=True)
    logo = models.FileField(null=True, blank=True)
    mortgage_broker_mail=models.EmailField(null=True,blank=True)
    mortgage_broker_first_name = models.CharField(max_length=200,null=True, blank=True)
    mortgage_broker_last_name = models.CharField(max_length=200, null=True, blank=True)
    is_client_company = models.BooleanField(default=True)
    default_advisor_fee = models.IntegerField(null=True,blank=True,default=0)

    def __str__(self):
        return self.name


class Client(CapBaseModel):
    CLIENT_STAGE_NAMES = [
        ('0', 'Task completed'),
        ('1', 'Pre contract'),
        ('2', 'Atp'),
        ('3', 'Post contract')
    ]
    User._meta.get_field("username").max_length = 255
    User._meta.get_field("username").help_text = ""
    User._meta.get_field("first_name").max_length = 255
    User._meta.get_field("last_name").max_length = 255
    user = models.OneToOneField(User, related_name='client', on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, unique=True)
    referred_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='referred_user')
    referred_date = models.DateField(verbose_name='Client Referred Time', null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='client_working_company')
    enable_cold_calling = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, related_name='created_by', on_delete=models.CASCADE)
    status = models.ForeignKey(StatusCollection, on_delete=models.CASCADE)
    pre_contract_percent=models.PositiveIntegerField(default=0)
    atp_percent=models.PositiveIntegerField(default=0)
    post_contract_percent=models.PositiveIntegerField(default=0)
    net_worth = models.DecimalField(decimal_places=2, default=0, max_digits=19, null=True,blank=True)
    is_confirmed_client=models.BooleanField(default=False)
    current_task_id = models.ForeignKey('ClientTask', blank=True,null=True,on_delete=models.CASCADE,related_name='clienttaskid')
    pre_contract_date = models.DateField(null=True,blank=True)
    confirm_client_date = models.DateField(verbose_name='Client Confirm Date',null=True,blank=True)
    post_contract_date = models.DateField(null=True,blank=True)
    is_survey_updated = models.BooleanField(default=False) # details updated using survey form
    client_stage = models.CharField(max_length=5,choices=CLIENT_STAGE_NAMES,null=True,blank=True,default='1')
    age=models.PositiveIntegerField(null=True)
    retire_age=models.PositiveIntegerField(null=True)

    def __str__(self):
        return self.user.username


class DocumentSetting(CapBaseModel):
    DOC_TYPES = [
        ('1', 'Brochure'),
        ('2', 'Bulk_csv'),
        ('3', 'LOA'),
        ('4', 'Illustration_response'),
        ('5', 'LOA_Response'),
        ('7', 'LOA_Response'),
        ('8', 'Suitability_Report'),
        ('9', 'AML'),
        ('10', 'Authority to Proceed'),
        ('11', 'ATR'),
        ('12', 'Platform Costs'),
        ('13', 'Application Summary'),
        ('14', 'Fund Research'),
        ('15', 'Critical Yield'),
        ('16', 'Illustration'),
        ('17', 'Weighted Average Calculator')
    ]
    
    type = models.CharField(max_length=3, choices=DOC_TYPES)
    max_size_limit = models.CharField(max_length=50)  # in bytes
    allowed_format = models.CharField(max_length=50)

    def __str__(self):
        return self.get_type_display()

def get_doc_count(client,type):
    count = Document.objects.filter(owner=client, doc_type=type).exclude(doc__isnull=True).exclude(doc='').count()
    return count+1

def get_image_path(instance, filename):
    file_name, file_extension = os.path.splitext(filename)
    if instance.doc_type == '1':
        return 'cap/brochures/'+filename
        
    elif instance.doc_type == '2':
        return 'cap/client_csv/'+filename
       
    if instance.doc_type == '3':
        return 'client_'+str(instance.owner.id)+'/loa/'+file_name+'_v'+str(instance.version)+file_extension
        
    if instance.doc_type == '4':
        return 'client_'+str(instance.owner.id)+'/illustrations/'+file_name+'_v'+str(instance.version)+file_extension
        
    if instance.doc_type == '5':
        return 'client_'+str(instance.owner.id)+'/loa_response/'+file_name+'_v'+str(instance.version)+file_extension
       
    if instance.doc_type == '6':
        return 'advisors'+'/company/'+filename
       
    if instance.doc_type == '7':
        return 'client_'+str(instance.owner.id)+'/third_party_doc/'+file_name+'_v'+str(instance.version)+file_extension

    if instance.doc_type == '8':
        count = get_doc_count(instance.owner,'8')
        
        return 'client_'+str(instance.owner.id)+'/sr/SR_c'+str(instance.owner.id)+'_'+str(datetime.now().date())+'_v'+str(count)+'.'+str(filename.split('.')[-1])
    if instance.doc_type =='9':
        count = get_doc_count(instance.owner,'9')
        return 'client_'+str(instance.owner.id)+'/draft_docs/AML/'+file_name+'_v'+str(count)+file_extension
    if instance.doc_type =='10':
        count = get_doc_count(instance.owner, '10')
        return 'client_' + str(instance.owner.id) + '/draft_docs/ATP/' + file_name+'_v'+str(count)+file_extension
    if instance.doc_type =='11':
        count = get_doc_count(instance.owner, '11')
        return 'client_' + str(instance.owner.id) + '/draft_docs/ATR/' + file_name+'_v'+str(count)+file_extension
    if instance.doc_type =='12':
        count = get_doc_count(instance.owner, '12')
        return 'client_' + str(instance.owner.id) + '/draft_docs/Platform_Cost/' + file_name+'_v'+str(count)+file_extension
    if instance.doc_type =='13':
        return 'client_' + str(instance.owner.id) + '/draft_docs/App_Summary/' + file_name+'_v'+str(instance.version)+file_extension
    if instance.doc_type =='14':
        return 'client_'+str(instance.owner.id)+'/draft_docs/fund_research/'+file_name+'_v'+str(instance.version)+file_extension
       
    if instance.doc_type =='15':
        return 'client_'+str(instance.owner.id)+'/draft_docs/critical_yield/'+file_name+'_v'+str(instance.version)+file_extension
       
    if instance.doc_type =='16':
        return 'client_'+str(instance.owner.id)+'/draft_docs/illustration/'+file_name+'_v'+str(instance.version)+file_extension
       
    if instance.doc_type =='17':
        return 'client_'+str(instance.owner.id)+'/draft_docs/weighted_avg_calculator/'+file_name+'_v'+str(instance.version)+file_extension        
       



class Document(CapBaseModel):
    def __str__(self):
        return self.doc.name

    DOC_TYPES = [
        ('1', 'Brochure'),
        ('2', 'Bulk_csv'),
        ('3', 'LOA'),
        ('4', 'Illustration_response'),
        ('5', 'LOA_Response'),
        ('6', 'Advisor_company'),
        ('7', 'LOA_Response'),
        ('8', 'Suitability_Report'),
        ('9', 'AML'),
        ('10', 'Authority to Proceed'),
        ('11', 'ATR'),
        ('12', 'Platform Costs'),
        ('13', 'Application Summary'),
        ('14', 'Fund Research'),
        ('15', 'Critical Yield'),
        ('16', 'Illustration'),
        ('17', 'Weighted average calculator'),
        ('18', 'Final_Report'),
        ('19', 'Master'),
    ]

    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    owner = models.ForeignKey(Client, null=True, blank=True, on_delete=models.CASCADE) # null means it's cap doc
    doc_type = models.CharField(max_length=3, choices=DOC_TYPES)
    doc = models.FileField(upload_to=get_image_path, blank=False, null=False, max_length=250)
    version = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    draft_doc = models.BooleanField(default=False)
    task = models.ForeignKey('ClientTask', blank=True,null=True,on_delete=models.CASCADE,related_name='taskdocument')




class CategoryAndSubCategory(CapBaseModel):
    category_name = models.CharField(max_length=30)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    allowed_days = models.CharField(max_length=2, default=20)
    category_slug_name = models.CharField(max_length=100,blank=True)
    category_order=models.IntegerField(default=0)


    def __str__(self):
        return self.category_name


class CategoryLabel(CapBaseModel):
    COMPONENT_TYPES = [
        ('1', 'Input'),
        ('2', 'SingleSelect'),
        ('3', 'SearchableSelect'),
        ('5', 'Month/Year'),
        ('7', 'CheckBox'),
        ('8', 'MultiSelect'),
        ('9', 'Text&Checkbox'),
        ('10', 'TextArea'),
        ('11', 'Date'),
        ('12', 'Select&Checkbox'),
        ('13', 'Searchable&Checkbox'),
        ('14', 'MultiSelect&Checkbox'),
        ('15','SearchableButton'),
        ('16', 'currencyField'),
        ('17', 'currencyField&Checkbox')


    ]
    VALUE_TYPES = [
        ('1', 'Alphabet'),
        ('2', 'Number'),
        ('3', 'Alpha numeric'),
        ('4', 'Email'),
        ('5', 'Decimal'),
        ('6', 'No validation'),
        ('7', 'Phone number'),
        ('8', 'DOB'),
        ('9', 'percentage'),
        ('10', 'Readonly-dropdown'),
        ('11', 'DOB-legal'),
        ('12', 'Past date'),
        ('13', 'Country list'),
        ('14', 'Price'),
        ('15', 'Postcode')

    ]
    category = models.ForeignKey(CategoryAndSubCategory, on_delete=models.CASCADE)
    label = models.CharField(max_length=150)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,related_name="parent_category")

    response_required=models.BooleanField(default=True)#new
    value_type=models.CharField(max_length=2,choices=VALUE_TYPES,default='6',null=True)#new

    answer_parent = ArrayField(models.CharField(max_length=200), blank=True, null=True,default=list)

    is_mandatory = models.BooleanField(default=False)
    is_hard = models.BooleanField(default=False)

    search_api_url= models.CharField(max_length=250, null=True,blank=True)
    component_type = models.CharField(max_length=2, null=True,choices=COMPONENT_TYPES,default='1')
    max_len=models.PositiveIntegerField(null=True, blank=True)
    min_len = models.PositiveIntegerField(null=True, blank=True)
    label_choice = ArrayField(models.CharField(max_length=50), blank=True, null=True)

    mapfield_to = models.ManyToManyField('CategoryLabel',blank=True)
    has_local_data = models.BooleanField(default=False)
    is_repeat = models.BooleanField(default=False)
    label_slug=models.CharField(max_length=300,blank=True)
    order_number = models.PositiveIntegerField(null=True,blank=True,default=1)

    def __str__(self):
        return self.label


class ClientLabelData(CapBaseModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    label = models.ForeignKey(CategoryLabel, on_delete=models.CASCADE)
    category = models.ForeignKey(CategoryAndSubCategory, on_delete=models.CASCADE)
    data = models.CharField(max_length=30)


class ClientInstrumentInfo(CapBaseModel):
    PROVIDER_TYPES = [
        ('1', 'Existing'),
        ('2', 'New'),
    ]
    EXTRACTION_STATUS = [
            ('0', 'Not Initiated'),
            ('1', 'Initiated'),
            ('2', 'Completed'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    instrument = models.ForeignKey(Instrument,on_delete=models.CASCADE)
    provider =models.ForeignKey(Provider,on_delete=models.CASCADE)
    provider_type = models.CharField(max_length=1, choices=PROVIDER_TYPES)
    loa_mail_sent = models.BooleanField(default=False)
    reminder_count = models.IntegerField(default=0)
    ##instrumentdocuments
    signed_loa = models.ForeignKey(Document, related_name='signed_loa',on_delete=models.CASCADE,null=True, blank=True)
    pdf_data = models.ForeignKey(Document, related_name='pdf_data',on_delete=models.CASCADE,null=True, blank=True)
    fund_research = models.ForeignKey(Document, related_name='fund_research', on_delete=models.CASCADE, null=True, blank=True)
    critical_yield = models.ForeignKey(Document, related_name='critical_yield', on_delete=models.CASCADE, null=True, blank=True)
    illustration = models.ForeignKey(Document, related_name='illustration', on_delete=models.CASCADE, null=True, blank=True)
    weighted_average_calculator = models.ForeignKey(Document, related_name='weighted_average_calculator', on_delete=models.CASCADE, null=True,blank=True)
    app_summary = models.ForeignKey(Document, related_name='app_summary', on_delete=models.CASCADE, null=True, blank=True)

    data_extracted =models.ForeignKey(ClientDraft, on_delete=models.CASCADE,null=True,blank=True)
    created_by =models.ForeignKey(User,on_delete=models.CASCADE,null=True)
    instrument_status = models.ForeignKey(StatusCollection,on_delete=models.CASCADE,null=True,blank=True)
    data_extraction_status = models.CharField(max_length=1, blank=False, default='0', choices=EXTRACTION_STATUS)
    is_recommended=models.BooleanField(default=False)
    instrumentdocument_id =  models.CharField(max_length=25, blank=True,null=True)
    parent = models.ForeignKey('ClientInstrumentInfo', on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return self.instrument.instrument_name

    def data_extarction(self):
        print("here inside model")
        document = self.pdf_data
       
        doc_url = os.path.join(settings.MEDIA_PATH,document.doc.name)
        row_tol = self.instrument.row_tol
        remove_background = self.instrument.remove_background
        client   = document.owner
        if IS_S3:
            doc_path = doc_url
        else:
            doc_path = document.doc.path
        print("settings.DATA_EXTRACTION_URL ",settings.DATA_EXTRACTION_URL)       
        response = requests.post(settings.DATA_EXTRACTION_URL,
                                json= {'client_id':client.id,
                                        'instrumentdocument_id':self.instrument.id,
                                        'client_instrumentinfo_id':self.id,
                                        'document_path':doc_path,
                                        'row_tol':row_tol,
                                        'remove_background':remove_background,
                                        's3_value':IS_S3
                                }
                            )

        
        response_content =  json.loads(response.content.decode('utf-8'))
        if response.ok:
            response = response.json()
            response_status = response['status'] 
            mongo_object_id = response['mongo_object_id']
            
            #TO DO client_instrument_status value check true/false/success
            if response_status and self.data_extraction_status=='0': 
                self.instrumentdocument_id=mongo_object_id
                self.data_extraction_status= '1'
                self.instrument_status = StatusCollection.objects.filter(status='1.81').first()
                self.save()
                
                print("extraction status updated ..................")

        return True


class CAP_settings(CapBaseModel):
    UNITS = [
        ('day', 'day'),
        ('week', 'week')
    ]

    label_name=models.CharField(max_length=200)##change to choice field##status name
    due_date_duration = models.CharField(max_length=10,default=0)
    reminder_date_duration = models.CharField(max_length=10,default=0)
    unit=models.CharField(max_length=10,choices=UNITS,default="day")

    def __str__(self):
        return self.label_name


class Reminder(CapBaseModel):
    SNOOZE_STATES=[
        ('1', 'Enabled'),
        ('2', 'Disabled')#Initially reminder will be disabled(active state)
    ]
    SNOOZE_UNIT = [
        ('day', 'day'),
        ('week', 'week')  # Initially reminder will be disabled(active state)
    ]
    pending_with = models.CharField(max_length=255,default='Me')
    owned_by = models.ForeignKey(User, on_delete=models.CASCADE)#staff
    sent_to_group = models.CharField(max_length=255,null=True,blank=True)##when owner is a team
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    status = models.ForeignKey(StatusCollection, on_delete=models.CASCADE)
    client_instrument = models.ForeignKey(ClientInstrumentInfo, on_delete=models.CASCADE,null=True,blank=True)
    due_date = models.DateField()
    reminder_date = models.DateField()
    snooze_status = models.CharField(max_length=1, choices=SNOOZE_STATES,default='2')
    snooze_duration = models.IntegerField(null=True,default=0)
    snooze_duration_unit=models.CharField(max_length=10,choices=SNOOZE_UNIT,default="day")
    mail_needed = models.BooleanField(default=False)
    mail_count = models.PositiveIntegerField(default=0)
    comment = models.TextField(null=True,blank=True)
    is_viewed = models.BooleanField(default=False)



class MailTemplateMapping(CapBaseModel):
    email = models.ForeignKey(Email, on_delete=models.CASCADE)
    template = models.ForeignKey(Templates, on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey(TemplateCategory, on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField(null=True, blank=True)


class Job_titles(CapBaseModel):
    name=models.CharField(max_length=255,null=True,blank=True)


class Lender_names(CapBaseModel):
    name=models.CharField(max_length=255,null=True,blank=True)

class pension_providers(CapBaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)


class CategorySummary(CapBaseModel):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    category = models.ForeignKey(CategoryAndSubCategory, on_delete=models.CASCADE)
    days_remaining = models.CharField(max_length=100,default='0')
    answered_mandatory_labels = models.PositiveIntegerField(default=0)
    unknown_mandatory_labels=models.PositiveIntegerField(default=0)
    total_mandatory_labels = models.PositiveIntegerField(default=0)
    total_answered_labels = models.PositiveIntegerField(default=0)
    total_labels = models.PositiveIntegerField(default=0)
    percentage_of_completion = models.PositiveIntegerField(default=0)
    is_sub_category=models.BooleanField(default=False)


def get_audio_path(instance, filename):
    return  'survey/'+filename

def get_blob_path(instance, filename):
    return 'survey/blob/ '+str(instance.id)+'_'+filename

class ClientAudioExtraction(CapBaseModel):
    category_id = models.ForeignKey(CategoryAndSubCategory, on_delete=models.CASCADE,null=True, blank=True)
    advisor_id = models.PositiveIntegerField(blank=True,null=True)
    client_id = models.ForeignKey(Client, on_delete=models.CASCADE)
    audio_data= models.FileField(upload_to=get_audio_path,blank=True, null=True)
    recording_name = models.CharField(blank=False, max_length=255, null=False,default='Record-')
    recording_text = models.TextField(null=True,blank=True)
    recording_blob = models.FileField(upload_to=get_blob_path,blank=True, null=True)
    
   

class TaskCollection(CapBaseModel):

    def __str__(self):
        return self.task_name

    TASK_GROUPS = [ 
            ('Advisor', 'Advisor'),
            ('Ops Lead', 'Ops Lead'),
            ('Compliance', 'Compliance'),
            ('Administrator', 'Administrator'),
            ('Final', 'Final')
        ] 

    task_name = models.CharField(max_length=200, null=True, blank=True)
    task_group = models.CharField(null=True, blank=True, choices=TASK_GROUPS, default='Advisor', max_length=20)
    task_slug = models.CharField(max_length=200, null=True, blank=True)
    task_description = models.TextField(null=True, blank=True)
    group_order = models.PositiveIntegerField(blank=True,null=True,default=0)


def get_signature_path(instance, filename):
    return 'advisors/signatures/'+filename

def validate_image(image):
    pass


class Staff(CapBaseModel):
    User._meta.get_field("username").max_length = 255
    User._meta.get_field("first_name").max_length = 255
    User._meta.get_field("last_name").max_length = 255
    user = models.OneToOneField(User, related_name='staff', on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=22, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='user_company')
    created_by = models.ForeignKey(User, related_name='staff_created_by', on_delete=models.CASCADE,null=True,blank=True)
    notification_count = models.PositiveIntegerField(null=True,blank=True,default=0)
    advisor_terms_and_agreement = models.BooleanField(default=False)
    designation = models.CharField(max_length=200, null=True, blank=True)
    phone_number2 = models.CharField(max_length=22, null=True, blank=True)
    signature = models.ImageField(upload_to=get_signature_path, blank=True, null=True,max_length=255, validators=[validate_image])
    fca_renewal_date = models.DateField(null=True,blank=True)
    def __str__(self):
        return self.user.username

    def notification_update(self, value):
        ''' Update notification count,
        value  is remove or add new notification (integer can be +1 or -1)
         '''
        self.notification_count = self.notification_count + int(value)
        self.save()
        return self


class ClientTask(CapBaseModel):
    TASK_STATUS_LIST = [
        ('1', 'Pending'),
        ('2', 'Inprogress'),
        ('3', 'Completed'),
    ]
    
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE, related_name='assigned_to')
    task_status = models.CharField(max_length=1, choices=TASK_STATUS_LIST, default='1')
    
    advisor = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE, related_name='task_advisor')
    ops = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE, related_name='task_ops')
    administrator = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE, related_name='task_administrator')
    compliance = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE, related_name='task_compliance')
    is_in_final = models.BooleanField(default=False)
    
    is_ops_verified = models.BooleanField(default=False)
    is_admin_verified = models.BooleanField(default=False)
    is_compliance_verified = models.BooleanField(default=False)
    
    ops_verified_on = models.DateTimeField(null=True, blank=True)
    admin_verified_on = models.DateTimeField(null=True, blank=True)
    compliance_verified_on = models.DateTimeField(null=True, blank=True)

    is_advisor_checklist_verified = models.BooleanField(default=True)
    is_admin_checklist_verified= models.BooleanField(default=False)
    is_compliance_checklist_verified = models.BooleanField(default=False)
    
    advisor_checklist_verified_on = models.DateTimeField(null=True, blank=True)
    admin_checklist_verified_on = models.DateTimeField(null=True, blank=True)
    compliance_checklist_verified_on = models.DateTimeField(null=True, blank=True)

    advisor_approved = models.BooleanField(default=False)
    advisor_approved_on = models.DateTimeField(null=True, blank=True)

    current_sub_task = models.ForeignKey(TaskCollection, null=True, blank=True, on_delete=models.CASCADE, related_name='current_sub_task_name')
    
    is_kyc_confirmed = models.BooleanField(default=False)
    kyc_confirmed_on = models.DateTimeField(null=True, blank=True)
    kyc_ever_confirmed =  models.BooleanField(default=False)

    def __str__(self):
        return str(self.client)


class ClientTaskTimeline(CapBaseModel):
    TASK_STATUS_LIST = [ 
            ('1', 'Pending'),
            ('2', 'Inprogress'),
            ('3', 'Completed'),
        ]    
    client_task = models.ForeignKey(ClientTask, null=True, blank=True, on_delete=models.CASCADE)
    task_collection = models.ForeignKey(TaskCollection, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE, related_name='task_assigned_to')
    task_status = models.CharField(max_length=1, choices=TASK_STATUS_LIST, default='1') 
    meeting_info = models.ForeignKey(Event, null=True, blank=True, on_delete=models.CASCADE)
    comments = models.CharField(max_length=255,null=True,blank=True)


class ClientTaskComments(CapBaseModel):
    comment = models.TextField(null=True, blank=True)
    task = models.ForeignKey(ClientTask, null=True, blank=True, on_delete=models.CASCADE)
    commented_by = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.comment



class ActivityFlow(CapBaseModel):
    action_performed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    status = models.ForeignKey(StatusCollection, on_delete=models.CASCADE, null=True, blank=True)
    client_instrument = models.ForeignKey(ClientInstrumentInfo, on_delete=models.CASCADE,null=True,blank=True)
    comment = models.TextField(null=True,blank=True)
    client_task = models.ForeignKey(ClientTask, on_delete=models.CASCADE,null=True,blank=True)
    task_status = models.ForeignKey(ClientTaskTimeline, on_delete=models.CASCADE,null=True,blank=True)


class Countries(models.Model):
    name = models.CharField(verbose_name='Name', max_length=64)
    code2 = models.CharField(verbose_name='Alpha-2 Code', max_length=2)
    code3 = models.CharField(verbose_name='Alpha-3 Code', max_length=3)


class TaskEvents(CapBaseModel):
    event = models.ForeignKey(Event, related_name='task_event', on_delete=models.CASCADE, null=True, blank=True)
    client = models.ForeignKey(Client, related_name='task_client', on_delete=models.CASCADE, null=True, blank=True)
    advisor = models.ForeignKey(User, related_name='task_advisor', on_delete=models.CASCADE, null=True, blank=True)
    task = models.ForeignKey(ClientTask, related_name='client_task', on_delete=models.CASCADE, null=True, blank=True)
    scheduled_by = models.ForeignKey(User, related_name='task_scheduled_by', on_delete=models.CASCADE, null=True, blank=True)


class RecommendationNotificationStatus(CapBaseModel):
    status_name = models.CharField(max_length=255,null=True,blank=True)
    status_value = models.PositiveIntegerField(null=True,blank=True)
    comments = models.CharField(max_length=255,null=True,blank=True)
    is_question =  models.BooleanField(default=False)
    draft_checklist = models.ForeignKey('DraftCheckList', on_delete=models.CASCADE, related_name='checklistid', null=True, blank=True)
    
    def __str__(self):
        return self.status_name

class ClientRecommendationNotification(CapBaseModel):  
    client =  models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    advisor = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    recommendation_status = models.ForeignKey(RecommendationNotificationStatus, on_delete=models.CASCADE, null=True, blank=True)
    is_answer = models.BooleanField(default=False)

class AutotriggerMail(CapBaseModel):
    insurance_check_mail_sent=models.BooleanField(default=False)
    br19_mail_sent = models.BooleanField(default=False)
    will_referral_mail_sent = models.BooleanField(default=False)
    mortgagebroker_mail_sent = models.BooleanField(default=False)
    client=models.ForeignKey(Client, related_name='mail_trigger_client', on_delete=models.CASCADE, null=True, blank=True)
    advisor = models.ForeignKey(User, related_name='mail_trigger_advisor', on_delete=models.CASCADE, null=True, blank=True)


class AdvisorFeeConfig(CapBaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE,null=True, blank=True)
    advisor = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='advisor',null=True, blank=True)
    fee_percentage = models.FloatField(default=0.0,null=True, blank=True)

class MasterKeywords(CapBaseModel):

    VALUE_TYPES = [('Date','Date'),('Amount','Amount'),('Text','Text'),('Number','Number'),('Percentage','Percentage'),('Boolean','Boolean'),('Radio','Radio')]
    DOC_TYPES = [
        ('1', 'LOA_Response'),
        ('2', 'Illustration'),
        ('3','Application_Summary')
    ]
    

    keyword= models.CharField(max_length=255,null=True,blank=True)
    keyword_slug = models.CharField(max_length=255,null=True,blank=True)
    label_description=models.CharField(max_length=255,null=True,blank=True)
   
    value_type = models.CharField(null=True,blank=True,max_length=255, choices=VALUE_TYPES, default='Text')
    masterlabel_order=models.IntegerField(default=0)
    keyword_type = ArrayField(models.CharField(max_length=30, choices=DOC_TYPES), blank=True, null=True,default=list) 
    

    class Meta:
        unique_together = (('keyword_slug', 'keyword_type'),)
    
    def __str__(self):
        return self.keyword

class IllustrationKeywordMapping(CapBaseModel):    
    def __str__(self):
        if  self.provider:
            return self.provider.name+' - '+self.master_keywords.keyword
        else:
            return self.master_keywords.keyword

    POSITIONS = [
        ('SR', 'SAME_ROW'),
        ('NR', 'NEXT_ROW'),
        ('TXT','TEXT_ROW'),
    ]
    KEYWORDS_STATUS  = [
        ('0','KEY_WORD_HIDE'),
        ('1','KEY_WORD_SHOW')

    ]
    MULTI_STATUS = [
        (0, 'SINGLE'),
        (1, 'MULTI')
    ]

    AMOUNT_TYPES=[
        ("HIGH","HIGH"),
        ("LOW","LOW")
    ]
    master_keywords = models.ForeignKey(MasterKeywords, on_delete=models.CASCADE,related_name='illus_master_keywords',null=True,blank=True)
    
    mapped_keywords = ArrayField(models.CharField(max_length=200), blank=True, null=True,default=list)
    is_value_based = models.BooleanField(default=True)
    position = models.CharField(null=True, blank=True, choices=POSITIONS, default='SR', max_length=20)
    description_endswith = ArrayField(models.CharField(max_length=300), blank=True, null=True,default=list)
    keyword_status = models.CharField(null=True, blank=True, choices=KEYWORDS_STATUS, default='0', max_length=20)
    provider = models.ForeignKey(Provider,related_name='illus_provider', on_delete=models.CASCADE,null=True,blank=True)
    table_head=models.CharField(null=True, blank=True, max_length=255)
    is_multi=models.IntegerField(null=True, blank=True, choices=MULTI_STATUS, default=0)
    amount_type=models.CharField(null=True, blank=True, choices=AMOUNT_TYPES, default=None, max_length=20)


class ExtractionKeywordMapping(CapBaseModel):
    
    def __str__(self):
        return self.instrument.instrument_name+' - '+self.master_keywords.keyword

    POSITIONS = [
        ('SR', 'SAME_ROW'),
        ('NR', 'NEXT_ROW'),
        ('TXT','TEXT_ROW'),
    ]
    KEYWORDS_STATUS  = [
        ('0','KEY_WORD_HIDE'),
        ('1','KEY_WORD_SHOW')

    ]
    master_keywords = models.ForeignKey(MasterKeywords, on_delete=models.CASCADE,related_name='master_keywords',null=True,blank=True)
    instrument = models.ForeignKey(Instrument,related_name='instrument', on_delete=models.CASCADE,null=True,blank=True)
    mapped_keywords = ArrayField(models.CharField(max_length=200), blank=True, null=True,default=list)
    is_value_based = models.BooleanField(default=True)
    position = models.CharField(null=True, blank=True, choices=POSITIONS, default='SR', max_length=20)
    description_endswith = ArrayField(models.CharField(max_length=300), blank=True, null=True,default=list)
    keyword_status = models.CharField(null=True, blank=True, choices=KEYWORDS_STATUS, default='0', max_length=20)


class ExtractedData(CapBaseModel):
    VALUES = [('Yes', 'Yes'),('No', 'No')]
    
    client_instrumentinfo = models.ForeignKey(ClientInstrumentInfo,on_delete=models.CASCADE,null=True,blank=True)
    master_keywords = models.ForeignKey(MasterKeywords, on_delete=models.CASCADE,related_name='master_keyword_data',null=True,blank=True)
    extraction_keyword = models.ForeignKey(ExtractionKeywordMapping, on_delete=models.CASCADE,related_name='extraction_keyword',null=True,blank=True)
    extracted_value = models.CharField(null=True, blank=True, max_length=255)
    extracted_description = models.TextField(null=True, blank=True)
    select_value = models.CharField(choices=VALUES, null=True, blank=True, max_length=255)



class FundRisk(CapBaseModel):
    FUND_TYPES = [
        ('1','Conservative'), ('2','Balanced'), ('3','Moderate'), 
        ('4','Dynamic'),('5','Adventurous'),('6','Conservative ESG'),
        ('7','Balanced ESG'),('8','Moderate ESG'),('9','Dynamic ESG'),
        ('10','Adventurous ESG'), ('11','Other')
    ]
  
    
    fund_name = models.CharField(null=True, blank=True, choices=FUND_TYPES, max_length=50)
    
    fund_percentage = models.CharField(max_length=10,default='0',blank=True,null=True)

    def __str__(self):
        return self.get_fund_name_display()


class ClientFeeManagement(CapBaseModel):
    client_instrumentinfo= models.ForeignKey(ClientInstrumentInfo, on_delete=models.CASCADE,null=True,blank=True)
    extracted_data = models.ForeignKey(ExtractedData, on_delete=models.CASCADE,related_name='extracted_data',null=True,blank=True)
    advisor_fee = models.FloatField(default=0.0,null=True, blank=True)
    adjusted_fee = models.FloatField(default=0.0,null=True, blank=True) #negotiated value 
    final_fee = models.FloatField(default=0.0,null=True, blank=True)


class Function(CapBaseModel):
    FUNCTION_CHOICE = [
        ('1','Transfer'),('2','Lump sum'),('3','Regular contribution'),
        ('4','Withdrawal'),('5','Fund switch'),('6','Review')
    ]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='client_company_name',null=True, blank=True)
    function_type = models.CharField(max_length=30,choices=FUNCTION_CHOICE,null=True,blank=True)

    def __str__(self):
        return self.get_function_type_display()

    
class Reason(CapBaseModel):
    product_type = models.ForeignKey(ProductType, on_delete=models.CASCADE, null=True, blank=True)
    function = models.ForeignKey(Function, related_name='function_list',on_delete=models.CASCADE,null=True,blank=True) 
    reason = models.CharField(max_length=250, null=True, blank=True)
    description = models.TextField(null=True,blank=True)
   
    
    def __str__(self):
        if self.product_type:
            return self.product_type.get_fund_type_display() + ' '+ self.function.get_function_type_display() + ' - ' +self.reason
        elif self.function:
            return self.function.get_function_type_display() + ' - ' +self.reason
        else:
            return self.reason


class InstrumentsRecomended(CapBaseModel): 
    advisor = models.ForeignKey(Staff,related_name='advisor_name',on_delete=models.CASCADE,null=True,blank=True) 
    client_instrumentinfo = models.ForeignKey(ClientInstrumentInfo,on_delete=models.CASCADE,null=True,blank=True)
    function_list =  models.ManyToManyField(Function, blank=True)
    reason =  models.ManyToManyField(Reason, blank=True)
    fund_risk = models.ForeignKey(FundRisk, on_delete=models.CASCADE,related_name='fund_risk',max_length=30,null=True,blank=True)
    initial_fee = models.FloatField(default=3.0,blank=True,null=True)
    ongoing_fee = models.FloatField(default=0.75,blank=True,null=True)
    dfm_fee = models.FloatField(default=0.12,blank=True,null=True)
    amount = models.FloatField(default=0.0,blank=True,null=True)    
    is_clone = models.BooleanField(default=False)
    map_transfer_from = models.ManyToManyField('self', null=True, blank=True, symmetrical=False)
    is_active = models.BooleanField(default=True)
    task = models.ForeignKey(ClientTask, blank=True, null=True, on_delete=models.CASCADE, related_name='taskinstruments')



class DraftReccomendation(CapBaseModel):
    instrument_recommended = models.ManyToManyField(InstrumentsRecomended)
    advisor = models.ForeignKey(Staff, on_delete=models.CASCADE,null=True,blank=True) 
    advisor_comments = models.TextField(null=True,blank=True)
    client = models.ForeignKey(Client,related_name='client', on_delete=models.CASCADE,null=True,blank=True)
    is_active = models.BooleanField(default=True)


class FeeRuleConfig(CapBaseModel):
    INTERVAL_CHOICE = [ ('1','Percentage'), ('2','Numeric') ]
    
    charge_name = models.CharField(max_length=30,blank=True,null=True)
    start = models.FloatField(default=0.0,blank=True,null=True)
    end = models.FloatField(default=0.0,blank=True,null=True)
    interval = models.FloatField(default=0.0,blank=True,null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='client_company',null=True, blank=True)
    interval_type = models.CharField(max_length=30,choices=INTERVAL_CHOICE, default='1',null=True, blank=True)
    default_value = models.FloatField(default=0.0,blank=True,null=True)
    
    def __str__(self):
        return self.charge_name

    
class DraftCheckList(CapBaseModel):

     CATEGORY_NAMES=[
         ('1', 'Surveyform'), ('2', 'Product Summary'),
         ('3', 'CAP Mail'), ('4', 'Advisor profile'),
         ('5', 'Post_Instrument_recommended'),('6','Smart Search'),
         ('7', 'Draft-update'),('8', 'bulk-recommend'),
         ('9', 'Illustration-extraction'),('10','task-creation'),
         ('11', 'recommendation-notification'),
         ('12', 'SR-generation'),('13','transfer-draftupdate'),
         ('14', 'ApplicationSummary-extraction')



     ]
     CHECKLIST_GROUPS=[
        ('Advisor', 'Advisor'),
        ('Compliance', 'Compliance'),
    ]

     
     checklist_names = models.CharField(max_length=200)
     category_name= models.CharField(max_length=5, choices=CATEGORY_NAMES)
     product_type = models.ManyToManyField(ProductType,related_name='product_type',blank=True)
     checklist_group = models.CharField(null=True, blank=True, choices=CHECKLIST_GROUPS, default='Advisor', max_length=20)
    

     def __str__(self):
        return self.checklist_names


class ClientCheckList(CapBaseModel):
    GROUP_NAMES = [
        ('Advisor', 'Advisor'),
        ('Ops Lead', 'Ops Lead'),
        ('Compliance', 'Compliance'),
        ('Administrator', 'Administrator'),
        ('Final', 'Final')
    ]
    COLOUR_CODES = [
        ('Green', 'Green'),
        ('Red', 'Red'),
        ('Amber', 'Amber'),
    ]
    
    draft_checklist = models.ForeignKey(DraftCheckList, on_delete=models.CASCADE, related_name='checklist', null=True, blank=True)
    colour_code= models.CharField(null=True, blank=True, choices=COLOUR_CODES, default='Green', max_length=20)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='checklist_client', null=True, blank=True)
    owner_group = models.CharField(null=True, blank=True, choices=GROUP_NAMES, default='Advisor', max_length=20)
    user = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE,related_name='advisor_staff')
    compliance = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE,related_name='compliance_staff')
    administrator = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE,related_name='administrator_staff')
    client_instrument = models.ForeignKey(ClientInstrumentInfo, on_delete=models.CASCADE, related_name='client_instrument',null=True, blank=True)
    instrument_recommended=models.ForeignKey(InstrumentsRecomended, on_delete=models.CASCADE, related_name='instrument_recommended',null=True, blank=True)
    draft_recommendation = models.ForeignKey(DraftReccomendation, on_delete=models.CASCADE, related_name='draft_recommendation',null=True, blank=True)
   
    def __str__(self):
        if self.draft_checklist and self.draft_checklist is not None:
            return self.draft_checklist.checklist_names +" - "+str(self.client)
        else:
            return str(self.client) 

class ClientCheckListArchive(CapBaseModel):
    GROUP_NAMES = [
        ('Advisor', 'Advisor'),
        ('Ops Lead', 'Ops Lead'),
        ('Compliance', 'Compliance'),
        ('Administrator', 'Administrator'),
        ('Final', 'Final')
    ]
    COLOUR_CODES = [
        ('Green', 'Green'),
        ('Red', 'Red'),
        ('Amber', 'Amber'),
    ]
    
    draft_checklist = models.ForeignKey(DraftCheckList, on_delete=models.CASCADE, related_name='checklist_archive', null=True, blank=True)
    colour_code= models.CharField(null=True, blank=True, choices=COLOUR_CODES, default='Green', max_length=20)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='checklist_client_archive', null=True, blank=True)
    owner_group = models.CharField(null=True, blank=True, choices=GROUP_NAMES, default='Advisor', max_length=20)
    user = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE,related_name='advisor_staff_archive')
    compliance = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE,related_name='compliance_staff_archive')
    administrator = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.CASCADE,related_name='administrator_staff_archive')
    client_instrument = models.ForeignKey(ClientInstrumentInfo, on_delete=models.CASCADE, related_name='client_instrument_archive',null=True, blank=True)
    instrument_recommended = models.ForeignKey(InstrumentsRecomended, on_delete=models.CASCADE,related_name='instruments_recommended', null=True, blank=True)
    draft_recommendation = models.ForeignKey(DraftReccomendation, null=True, blank=True, on_delete=models.CASCADE, related_name='draft_recommendation_archive')
    task =  models.ForeignKey(ClientTask, null=True, blank=True, on_delete=models.CASCADE,related_name='client_task_archive')
   
    def __str__(self):
        return self.draft_checklist.checklist_names





def get_sr_image_path(instance, filename):
    return 'master/sr_images/'+filename

class ATR(CapBaseModel):

    def __str__(self):
        return self.get_risk_type_display()

    RISK_CHOICES = [
                    ('Conservative','Conservative'),
                    ('Balanced','Balanced'),
                    ('Moderate','Moderate'),
                    ('Dynamic','Dynamic'),
                    ('Adventurous','Adventurous')
                ]
    LOSS_CHOICES = [
                    ('5','5'),
                    ('10','10'),
                    ('15','15'),
                    ('20','20'),
                    ('25','25')
                ]
    risk_type = models.CharField(max_length=30,blank=True,null=True, choices=RISK_CHOICES)
    content = models.TextField(blank=True,null=True)
    extra_content = models.TextField(null=True, blank=True)
    risk_graph = models.ImageField(upload_to=get_sr_image_path, null=True, blank=True)
    risk_portfolio = models.ImageField(upload_to=get_sr_image_path, blank=False, null=False)
    loss_percentage = models.CharField(max_length=5,blank=True,null=True, choices=LOSS_CHOICES)


class SRProviderContent(CapBaseModel):
    def __str__(self):
        return self.provider.name

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    content = models.TextField(blank=True,null=True)


class SRAdditionalCheckContent(CapBaseModel):
    def __str__(self):
        return self.condition_check

    product_type = models.ForeignKey(ProductType, on_delete=models.CASCADE, null=True, blank=True)
    condition_check = models.CharField(max_length=250,blank=True,null=True)
    condition_description = models.TextField(blank=True,null=True)
    content = models.TextField(blank=True,null=True)


'''model for illustration checklist'''
class IllustrationData(CapBaseModel):
    TYPE_CHOICES=[
        ('1','Amount'),
        ('2','Percentage')

    ]
    client_instrumentinfo = models.ForeignKey(ClientInstrumentInfo,on_delete=models.CASCADE,null=True,blank=True)
    master_keywords = models.ForeignKey(MasterKeywords, on_delete=models.CASCADE,related_name='illustration_master_keyword',null=True,blank=True)
    extraction_keyword = models.ForeignKey(IllustrationKeywordMapping, on_delete=models.CASCADE,related_name='illustration_keyword',null=True,blank=True)
    extracted_value = models.CharField(null=True, blank=True, max_length=255)
    extracted_description = models.TextField(null=True, blank=True)
    extracted_type =models.CharField(null=True, blank=True, max_length=5,choices=TYPE_CHOICES)
    frequency  =models.CharField(max_length=255,blank=True,null=True)


class Smartserachlog(CapBaseModel):
    request_url= models.URLField(max_length = 200,null=True,blank=True)
    method = models.CharField(null=True, blank=True, max_length=25)
    request_msg = JSONField()
    response_msg = JSONField()


def get_smart_search_doc_path(instance, filename):
    return  'KYC/'+filename
    
class Smartserach(CapBaseModel):
    client = models.ForeignKey(Client,on_delete=models.CASCADE,null=True,blank=True)
    created_by = models.ForeignKey(Staff,on_delete=models.CASCADE,null=True,blank=True)
    smartserachlog = models.ForeignKey(Smartserachlog,on_delete=models.CASCADE,null=True,blank=True)
    document_path = models.FileField(upload_to=get_smart_search_doc_path,blank=True, null=True)
    status = models.CharField(null=True, blank=True, max_length=255)
    ssid = models.CharField(null=True, blank=True, max_length=255)
    task = models.ForeignKey(ClientTask,on_delete=models.CASCADE,null=True,blank=True)
    def __str__(self):
        return str(self.client.user.email)+" - "+str(self.ssid)


class Errorlog(CapBaseModel):
    # request_url= models.URLField(max_length = 200,null=True,blank=True)
    logs = JSONField()












