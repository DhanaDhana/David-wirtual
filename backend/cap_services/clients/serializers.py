from .models import Client
from rest_framework import serializers
from cap_services.settings import BASE_URL, USE_S3, IS_S3,AWS_STORAGE_BUCKET_NAME as bucket
from cap_services.settings import MEDIA_PATH as MEDIA_URL
from cap_services.s3connect import S3Media
from django.contrib.auth.models import User, Group
from .models import StatusCollection, Company, Document, DocumentSetting, ClientLabelData, CategoryAndSubCategory, \
    CategoryLabel, Provider, Instrument, ClientInstrumentInfo, Templates, TemplateCategory, ActivityFlow, Reminder, \
    ClientTask, TaskCollection, ClientTaskComments, Staff, Job_titles, Lender_names, pension_providers, ClientAudioExtraction, \
    TaskEvents, Countries, CategorySummary, ClientTaskTimeline,FundRisk,FeeRuleConfig,DraftReccomendation,\
    Reason,Function,InstrumentsRecomended,ExtractedData,ClientRecommendationNotification,ClientCheckList,\
    ProductType,DraftCheckList,Smartserach,Errorlog
from .checklist import  update_or_create_checklist
from .utils import pending_status_save, add_activity_flow,client_profile_completion
from django.template import Context, Template
from data_collection.models import SurveyFormData,ClientInstrumentDocument,InstrumentExtractedData
from django.contrib.auth.validators import UnicodeUsernameValidator
from datetime import datetime, timezone, timedelta
from pdf2image import convert_from_path, convert_from_bytes
from django.conf import settings
import os
import datetime as dt
from cap_outlook_service.outlook_services.models import Email, OutlookLog, MailFolder

from .common.page_urls import get_page_url
from .utils import add_task_activity, calculate_fee, reset_checklist_and_reccommendations, encrypt_and_send_mail,illustration_appsummary_checklists
from outlook_app.utils import templatemailsend

import time
import requests
import json
from random import random

from django.utils import timezone as tz
import pytz
import math

class UserSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    email = serializers.CharField(required=True)
    phone_number = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'phone_number', 'user_type')
        extra_kwargs = {
            'username': {
                'validators': [UnicodeUsernameValidator()],
            }
        }

    def get_phone_number(self, obj):
        if hasattr(obj, 'client'):
            return obj.client.phone_number
        else:
            return ""

    def get_user_type(self, obj):
        group = Group.objects.filter(user=obj).first()
        if group:
           return group.name
        else:
           return None



class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ('id', 'name','logo','url')


class DocumentSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentSetting
        fields = ('type', 'max_size_limit', 'allowed_format')


class DocumentSerializer(serializers.ModelSerializer):
    doc_label = serializers.SerializerMethodField()
    client_instrument_id = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    document_name = serializers.SerializerMethodField()


    class Meta:
        model = Document
        fields = ( 'id','owner', 'doc', 'doc_type','doc_label','create_time','client_instrument_id','draft_doc','is_active','task','document_name')
    
    def get_document_name(self,obj):
        return obj.doc.name
    
    def get_is_active(self,obj):
        return obj.is_active
    
    def get_doc_label(self, obj):
        if obj.doc_type:
           return obj.get_doc_type_display()
        else:
           return None
    def get_client_instrument_id(self, obj):
        clientinstrument=None
        if obj.doc_type == '3':
            clientinstrument=ClientInstrumentInfo.objects.filter(client=obj.owner,signed_loa=obj.id).first()
        if obj.doc_type == '5':
            clientinstrument=ClientInstrumentInfo.objects.filter(client=obj.owner,pdf_data=obj.id).first()
        if obj.doc_type == '7':
            clientinstrument=ClientInstrumentInfo.objects.filter(client=obj.owner,pdf_data=obj.id).first()
        if obj.doc_type == '13':
            clientinstrument=ClientInstrumentInfo.objects.filter(client=obj.owner,app_summary=obj.id).first()
        if obj.doc_type == '14':
            clientinstrument=ClientInstrumentInfo.objects.filter(client=obj.owner,fund_research=obj.id).first()
        if obj.doc_type == '15':
            clientinstrument=ClientInstrumentInfo.objects.filter(client=obj.owner,critical_yield=obj.id).first()
        if obj.doc_type == '16':
            clientinstrument=ClientInstrumentInfo.objects.filter(client=obj.owner,illustration=obj.id).first()
        if obj.doc_type == '17':
            clientinstrument=ClientInstrumentInfo.objects.filter(client=obj.owner,weighted_average_calculator=obj.id).first()
        if clientinstrument:
            return clientinstrument.id

        return clientinstrument

    '''get the original representation'''
    def to_representation(self, obj):
       
        data = super(DocumentSerializer, self).to_representation(obj)
        request=self.context.get('request', None)
        fetch_recent_docs = request.query_params.get('fetch_recent_docs', None)
        if fetch_recent_docs=='true':
            client_instrument_id=self.get_client_instrument_id(obj)
            if client_instrument_id:
                clientinstrumentlist = InstrumentsRecomended.objects.filter(client_instrumentinfo__client__id=obj.owner.id).values_list('client_instrumentinfo', flat=True)
                if client_instrument_id not in clientinstrumentlist:
                    return None
            elif obj.doc_type in ['3','5','7','13','14','15','16','17']:
                return None
        return data


    def create(self,validated_data):
        user = None
        pending_status=None
        current_doc_version = 0
        request = self.context.get("request")
        client_instrument_id = request.query_params.get('client_instrument_id', None)
        draft_doc = request.query_params.get('draft_doc', None)
        task_doc = request.query_params.get('task_doc', None)
        
        task_obj = ClientTask.objects.filter(client=validated_data['owner']).exclude(task_status='3')
        if not task_obj and task_doc =='true':
            raise serializers.ValidationError({"file": ["Task file already closed, cannot upload document"]})
        
        comments=None
        if client_instrument_id=='null':
            client_instrument_id=None
        if client_instrument_id is not None :
            client_instrument = ClientInstrumentInfo.objects.filter(id=client_instrument_id, is_active=True).last()

            if validated_data['doc_type'] == '3' and client_instrument.signed_loa:
                # if client_instrument.signed_loa:
                current_doc_version = client_instrument.signed_loa.version
                    
            if validated_data['doc_type'] == '5' and client_instrument.pdf_data:
                current_doc_version = client_instrument.pdf_data.version
                    
            if validated_data['doc_type'] == '7' and client_instrument.pdf_data:
                current_doc_version = client_instrument.pdf_data.version

            if validated_data['doc_type'] == '13' and client_instrument.app_summary:
                current_doc_version = client_instrument.app_summary.version

            if validated_data['doc_type'] == '14' and client_instrument.fund_research:
                current_doc_version = client_instrument.fund_research.version

            if validated_data['doc_type'] == '15' and client_instrument.critical_yield:
                current_doc_version = client_instrument.critical_yield.version

            if validated_data['doc_type'] == '16' and client_instrument.illustration:
                current_doc_version = client_instrument.illustration.version

            if validated_data['doc_type'] == '17' and client_instrument.weighted_average_calculator:
                current_doc_version = client_instrument.weighted_average_calculator.version         

        if request and hasattr(request, "user"):
            user = request.user
        user_obj = User.objects.get(id=user.id)
        document_obj = None
        
        try:
            document_obj = Document.objects.create(uploaded_by=user_obj, **validated_data, version=current_doc_version+1)
            current_task = ClientTask.objects.filter(client=validated_data['owner']).exclude(task_status='3').first()
            
            status_dict = {'3':'LoA Response','5':'Product information doc','7':'LOA Response','8':'Suitability Report',
            '9':'AML','10':'Authority to Proceed','11':'ATR','12':'Platform Costs','13':'Application Summary',
            '14':'Fund Research','15':'Critical Yield','16':'Illustration','17':'Weighted Average Calculator'}
            
            atp_status_dict = {'12':'2.3','8':'2.4','10':'2.5','9':'2.6','11':'2.7','13':'2.8','14':'2.9',
            '15':'2.10','16':'2.11','17':'2.12','3':'2.13','5':'2.13','7':'2.13'}
           
  
            if document_obj is not None and  draft_doc=='false': 
                if document_obj.doc_type in status_dict and status_dict[document_obj.doc_type]:
                    
                    if client_instrument_id is not None:
                        instrument_name=client_instrument.instrument.instrument_name
                    else:
                        instrument_name = ""
                    comments = instrument_name+" "+status_dict[document_obj.doc_type]
            if draft_doc=='true' and draft_doc is not None and document_obj is not None:
                if document_obj.doc_type in status_dict and status_dict[document_obj.doc_type]:
                    if document_obj.doc_type != "7":
                        status_value = atp_status_dict[document_obj.doc_type]
                        if client_instrument_id is not None:
                            instrument_name=client_instrument.instrument.instrument_name
                        else:
                            instrument_name = ""
                        current_doc_version_new = str(document_obj).split("_v")
                        current_doc_version= current_doc_version_new[1].split(".")
                        comment = instrument_name+" "+'v'+str(current_doc_version[0])
                        activity_flow_update_status = StatusCollection.objects.get(status=status_value)
                        add_activity_flow(action_performed_by=document_obj.uploaded_by, client=document_obj.owner, status=activity_flow_update_status,comment=comment)
                
            
            if current_task and draft_doc!='true':
                group = user_obj.groups.first()
                if group.name == 'Ops':
                    task_collection = TaskCollection.objects.filter(task_slug='ops_updated_client_file').first()
                    add_task_activity(client_task=current_task, task_collection=task_collection, created_by=current_task.ops, task_status='3',comments=comments,req_user=request.user)
                elif group.name == 'Administrator':
                    task_collection = TaskCollection.objects.filter(task_slug='admin_updated_client_file').first()
                    add_task_activity(client_task=current_task, task_collection=task_collection, created_by=current_task.administrator, task_status='3',comments=comments,req_user=request.user)
                elif group.name == 'Compliance':
                    task_collection = TaskCollection.objects.filter(task_slug='compliance_updated_client_file').first()
                    add_task_activity(client_task=current_task, task_collection=task_collection, created_by=current_task.compliance, task_status='3',comments=comments,req_user=request.user)
                elif group.name =='Advisor':
                    task_collection = TaskCollection.objects.filter(task_slug='advisor_updated_client_file').first()
                    add_task_activity(client_task=current_task, task_collection=task_collection, created_by=current_task.advisor, task_status='3',comments=comments,req_user=request.user)

        except Exception as e:
            print(str(e))
            print("Exception in doc create")
    
        if document_obj is not None :
            if document_obj.doc_type =="11":
                checklist = DraftCheckList.objects.filter(id=11).first()  # Is there sufficient information to justify the advice ?
                staffuser = Staff.objects.filter(user=document_obj.owner.created_by).first()
                update_or_create_checklist(document_obj.owner, checklist.id, staffuser,result='passed')
            
            if client_instrument_id is not None:
                if document_obj.doc_type =="3":######for loa doc
                    if document_obj.doc.name.split('.')[1] == 'pdf':
                        if IS_S3:
                            pages = convert_from_bytes(document_obj.doc.read(), 500)
                            preview_path = os.path.join(bucket,'media', document_obj.doc.name)
                           
                            result_path = preview_path.split('.')[0] + '_preview' + '.jpg'
                            
                            for page in pages:
                                s3_upload = S3Media()
                                s3_upload.to_s3(page, result_path)
                            print(result_path)
                            print(preview_path)
                        else:
                            preview_path = document_obj.doc.path
                            pages = convert_from_path(preview_path, 500)
                            result_path =  preview_path.split('.')[0]+ '_preview' + '.jpg'
                            for page in pages:
                                page.save(result_path, 'JPEG')
                    client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id, is_active=True)
                    client_instrument.instrument_status = StatusCollection.objects.get(status='1.22')
                    client_instrument.signed_loa = document_obj
                    client_instrument.save()

                    pending_status = StatusCollection.objects.get(status='1.25')  # loa mail senting pending status


                elif document_obj.doc_type =="5":#######for data extraction doc
                    client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id, is_active=True)
                    client_instrument.instrument_status = StatusCollection.objects.get(status='1.27')
                    client_instrument.pdf_data = document_obj
                    client_instrument.save()
                    if draft_doc=='false' and  task_doc!='true':
                        extraction_obj = client_instrument.data_extarction()
                        print("extraction status -extraction_obj ",extraction_obj)

                    pending_status = StatusCollection.objects.get(status='1.32')  # data extraction pending status'''
                elif document_obj.doc_type == "7":
                    try:
                        client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id, is_active=True)
                        if draft_doc!='true':
                            client_instrument.instrument_status = StatusCollection.objects.get(status='1.29')
                        else:
                            client_instrument.instrument_status = StatusCollection.objects.get(status='2.13')
                        client_instrument.pdf_data = document_obj
                        client_instrument.save()
                        pending_status = StatusCollection.objects.get(status='1.32')  # data extraction pending status'''
                        print("document saved")
                    except Exception as e:
                        print(str(e))
                elif document_obj.doc_type == "13":
                    try:

                        ClientInstrumentInfo.objects.filter(id=client_instrument_id, is_active=True).update(app_summary=document_obj)
                        client_instrument = ClientInstrumentInfo.objects.filter(id=client_instrument_id,is_active=True).first()
                        if draft_doc == 'true' and task_doc != 'true':
                            if client_instrument:
                                if client_instrument.provider.id in [10, 12]:
                                    checklist = DraftCheckList.objects.filter(id=30).first()  # Is there sufficient information to justify the advice ?
                                    staffuser = Staff.objects.filter(user=document_obj.owner.created_by).first()
                                    update_or_create_checklist(document_obj.owner, checklist.id,staffuser)
                                illustration_appsummary_checklists(client_instrument,document_obj.doc_type)
                        print("document saved")
                    except Exception as e:
                        print(str(e))
                elif document_obj.doc_type == "14":
                    try:

                        ClientInstrumentInfo.objects.filter(id=client_instrument_id, is_active=True).update(fund_research=document_obj)
                    except Exception as e:
                        print(str(e))
                elif document_obj.doc_type == "15":
                    try:
                       
                        ClientInstrumentInfo.objects.filter(id=client_instrument_id, is_active=True).update(critical_yield=document_obj)
                    except Exception as e:
                        print(str(e))
                elif document_obj.doc_type == "16":
                    try:

                        ClientInstrumentInfo.objects.filter(id=client_instrument_id, is_active=True).update(illustration=document_obj)
                        client_instrument = ClientInstrumentInfo.objects.filter(id=client_instrument_id,is_active=True).first()
                        if draft_doc=='true' and  task_doc!='true':
                            if client_instrument:
                                if client_instrument.provider.id in [10,12]:
                                    checklist = DraftCheckList.objects.filter(id=30).first()  # Is there sufficient information to justify the advice ?
                                    staffuser=Staff.objects.filter(user=document_obj.owner.created_by).first()
                                    update_or_create_checklist(document_obj.owner, checklist.id,staffuser )
                                illustration_appsummary_checklists(client_instrument, document_obj.doc_type)
                                print("illustration doc data extraction starts")
                                


                    except Exception as e:
                        print(str(e))
                elif document_obj.doc_type == "17":
                    try:
 
                        ClientInstrumentInfo.objects.filter(id=client_instrument_id, is_active=True).update(weighted_average_calculator=document_obj)
                    except Exception as e:
                        print(str(e))
        
        try:
            
            
            if client_instrument_id is not None:
                remove_reminder = Reminder.objects.filter(client_instrument=client_instrument).first()
                if remove_reminder:
                    remove_reminder.is_deleted = True
                    remove_reminder.save()
                if pending_status:
                    pending_status_save(client_instrument=client_instrument, pending_status=pending_status)
                    print("status saved")
        except Exception as e:
            print(e)
        return document_obj

    def update(self, instance, validated_data):
        user = None
        request = self.context.get("request")
        client_instrument_id = request.query_params.get('client_instrument_id', None)
        if request and hasattr(request, "user"):
            userobj = request.user
            print(instance.id)
            if client_instrument_id is not None:

                # to check mismatch bw clientinstrument loa id and doc id.
                
                    Document.objects.filter(id=instance.id).update(is_deleted=True)
                   
                    docobj=Document.objects.create(uploaded_by=userobj, **validated_data)
                    if docobj is not None:
                        if docobj.doc_type == "3":  ######for loa doc
                            if docobj.doc.name.split('.')[1] == 'pdf':
                                if IS_S3:
                                    pages = convert_from_bytes(docobj.doc.read(), 500)
                                    preview_path = os.path.join('media', docobj.doc.name)
                                    result_path = preview_path.split('.')[0] + '_preview' + '.jpg'
                                    for page in pages:
                                        s3_upload = S3Media()
                                        s3_upload.to_s3(page, result_path)
                                else:
                                    preview_path = docobj.doc.path
                                    pages = convert_from_path(preview_path, 500)
                                    result_path = preview_path.split('.')[0] + '_preview' + '.jpg'
                                    for page in pages:
                                        page.save(result_path, 'JPEG')
                            client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                            client_instrument.instrument_status = StatusCollection.objects.get(status='1.50')
                            client_instrument.signed_loa=docobj
                            client_instrument.save()
                        elif docobj.doc_type == "5":
                            client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                            client_instrument.instrument_status = StatusCollection.objects.get(status='1.52')
                            client_instrument.pdf_data=docobj
                            client_instrument.save()
                        elif docobj.doc_type == "7":
                            client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                            client_instrument.instrument_status = StatusCollection.objects.get(status='1.54')
                            client_instrument.pdf_data=docobj
                            client_instrument.save()
                        elif docobj.doc_type == "13":
                            client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                            
                            client_instrument.app_summary=docobj
                            client_instrument.save()
                        elif docobj.doc_type == "14":
                            client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                           
                            client_instrument.fund_research=docobj
                            client_instrument.save()
                        elif docobj.doc_type == "15":
                            client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                           
                            client_instrument.critical_yield=docobj
                            client_instrument.save()
                        elif docobj.doc_type == "16":
                            client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                           
                            client_instrument.illustration=docobj
                            client_instrument.save()
                        elif docobj.doc_type == "17":
                            client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                            
                            client_instrument.weighted_average_calculator=docobj
                            client_instrument.save()




                    return docobj



class ClientSerializer(serializers.ModelSerializer):
    """
        A client serializer to return the client details
    """
    user = UserSerializer(required=True)
    referred_by_id = serializers.IntegerField(required=False, allow_null=True)
    company = serializers.CharField(required=True)
    referred_user_first_name = serializers.SerializerMethodField()
    referred_user_last_name = serializers.SerializerMethodField()
    referred_user_email = serializers.SerializerMethodField()
    referred_user_phone_number = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()
    advisor = serializers.SerializerMethodField()

    #added for fee management
    ni_number = serializers.CharField(required = False, allow_null = True)

    class Meta:
        model = Client
        fields = ('id', 'user', 'phone_number', 'referred_by_id', 'referred_date', 'company', 'enable_cold_calling',
                  'referred_user_first_name', 'referred_user_last_name', 'referred_user_email',
                  'referred_user_phone_number', 'company_id','net_worth','pre_contract_percent','atp_percent','post_contract_percent','is_confirmed_client','created_by','current_task_id','is_survey_updated','advisor', 'ni_number')
        read_only_fields = ('pre_contract_percent','atp_percent','post_contract_percent','created_by',)
    
    def get_advisor(self, obj):
        return obj.created_by.first_name.title() + ' ' +  obj.created_by.last_name.title()

    def get_company_id(self, obj):
        return obj.company.id

    def get_referred_user_first_name(self, obj):
        if obj.referred_by: 
            return obj.referred_by.first_name
        else:
            return None    

    def get_referred_user_last_name(self, obj):
        if obj.referred_by: 
            return obj.referred_by.last_name
        else:
            return None      

    def get_referred_user_email(self, obj):
        if obj.referred_by: 
            return obj.referred_by.email
        else:
            return None      

    def get_referred_user_phone_number(self, obj):
        if hasattr(obj.referred_by, 'client'):
            return obj.referred_by.client.phone_number
        else:
            return ""

    def run_checklist(self,user,client):
        try:
            staffinstance=Staff.objects.filter(user=user).first()
            draftchecklist1 = DraftCheckList.objects.filter(id=5).first()#5
            draftchecklist3 = DraftCheckList.objects.filter(id=4).first()#4
            draftchecklist4 = DraftCheckList.objects.filter(id=1).first()#1
            draftchecklist5 = DraftCheckList.objects.filter(id=2).first()#2
            draftchecklist6 = DraftCheckList.objects.filter(id=3).first()#3
            draftchecklist7 = DraftCheckList.objects.filter(id=6).first()#6
            ClientCheckList.objects.create(draft_checklist=draftchecklist1, owner_group='Advisor',user=staffinstance, client=client, colour_code='Red')
            ClientCheckList.objects.create(draft_checklist=draftchecklist3, owner_group='Advisor',user=staffinstance, client=client,colour_code='Red')
            ClientCheckList.objects.create(draft_checklist=draftchecklist4, owner_group='Advisor',user=staffinstance, client=client,colour_code='Red')
            ClientCheckList.objects.create(draft_checklist=draftchecklist5, owner_group='Advisor',user=staffinstance, client=client,colour_code='Red')
            ClientCheckList.objects.create(draft_checklist=draftchecklist6, owner_group='Advisor',user=staffinstance, client=client,colour_code='Red')
            ClientCheckList.objects.create(draft_checklist=draftchecklist7, owner_group='Advisor',user=staffinstance, client=client, colour_code='Red')
        except Exception as e:
            print(str(e))

    def get_ni_number(self, obj):
        if obj.ni_number:
            return obj.ni_number
        else:
            return ""

    def create(self, validated_data):
        """
        Overriding the default create method of the Model serializer.
        :param validated_data: data containing all the details of client
        :return: returns a successfully created client record
        """

        #TO DO - ADD A 'TASK ADDED' ENTRY INTO DB WHEN THE CONFIRMATION FROM ADVISOR SIDE IS DONE AND PASSED TO OPS

        user_data = validated_data.pop('user')
        print("||| | |  |  | This is the validated data |  |  | | | |||",validated_data)
        user = UserSerializer.create(UserSerializer(), validated_data=user_data)
        company_obj, created = Company.objects.get_or_create(name=validated_data.pop('company'))
        status = StatusCollection.objects.get(status='1.1')
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            created_user = request.user
            client = Client.objects.create(created_by=created_user, user=user, status=status, company=company_obj,
                                           **validated_data)

        else:
            client = Client.objects.create(user=user, status=status, company=company_obj, **validated_data)
           
        add_activity_flow(action_performed_by=client.created_by,client=client,status=status)
        '''add profile completion''' 
        
        
        client_profile_completion(client=client,percentage=10,phase='pre-contract',sign='positive')

        '''Adding user group'''
        group = Group.objects.filter(name='Client').first()
        if group:
            group.user_set.add(client.user)

        '''create advisor checklist'''
        self.run_checklist(request.user,client)

        if client.referred_by:
            try:     #To send thanks mail to the corresponding referrer
                request_info = {}
                
                advisor_name = client.created_by.first_name.title()
                advisor_full_name = client.created_by.first_name.title() + ' ' + client.created_by.last_name.title()
               
                thanks_template = Templates.objects.filter(template_name='Thanks mail').first()
                template_instance = Template(thanks_template.template_header + thanks_template.content + thanks_template.template_footer)
                try:
                    staff = Staff.objects.filter(user=request.user).first()
                    if staff:
                        company_url = staff.company.url
                        company_logo = staff.company.logo.url
                        phone_number = staff.phone_number
                        phone_number2 = staff.phone_number2
                        designation = staff.designation

                    else:
                        company_logo = Document.objects.get(doc='advisors/company/Lathe-logo.png').doc.url
                except:
                    company_logo = " "
                    company_url = " "
                    phone_number = None
                    phone_number2 = None
                    designation = None
                referrer_name=client.referred_by.first_name
                context = Context({"referrer_name":referrer_name,"advisor_name": advisor_name,"company_logo":company_logo,
                                   'company_website':company_url,'static_image_path':os.path.join(MEDIA_URL, 'advisors/company'),"advisor_full_name":advisor_full_name, \
                                   "phone_number":phone_number,"phone_number2":phone_number2,"designation":designation})
                html = template_instance.render(context)

                request_info['user'] = client.created_by
                request_info['message_sender'] = client.created_by.email
                request_info['message_subject'] = thanks_template.subject
                request_info['message_body'] = html
                request_info['message_body_type'] = 'html'
                request_info['message_to']=[]
                if client.referred_by.email:
                    request_info['message_to'] = [client.referred_by.email]
                request_info['has_attachments'] = False

                folder_id = MailFolder.objects.filter(folder_name='Sent Items', user=client.created_by).first()
                message_created = dt.datetime.utcnow()
                message_modified = dt.datetime.utcnow()
                message_recieved = dt.datetime.utcnow()
                message_sent = dt.datetime.utcnow()


                rand = str(random()).split('.')[-1]
                stamp = str(time.time()).replace(".","")
                

                email = Email.objects.create(user=client.created_by, message_sender=request_info['message_sender'], folder=folder_id,
                                             message_subject=request_info['message_subject'],conversation_id=str(client.created_by.id)+str(stamp)+str(rand),
                                             message_body=request_info['message_body'],
                                             message_to=request_info['message_to'],
                                             has_attachments=request_info['has_attachments'],message_created=message_created,message_modified=message_modified,\
                                             message_sent=message_sent,message_recieved=message_recieved)
                OutlookLog.objects.create(user=client.created_by, email=email, request_info=request_info, log_type=2, status=1)
                
                if client.referred_by and client.referred_by is not None:
                    referred_client_obj = Client.objects.filter(user=client.referred_by).first()
                    status = StatusCollection.objects.get(status='1.4')
                    add_activity_flow(action_performed_by=client.created_by, client=referred_client_obj, status=status)
            except Exception as e:

                print("thanks mail not sent",e)
        return client



    def update(self, instance, validated_data):
        print(validated_data, ' *****************************')
        request = self.context.get("request")
        user_data = validated_data.pop('user')
        user = instance.user
        user_serializer = UserSerializer(user, data=user_data)
        if user_serializer.is_valid(raise_exception=True):
            user_serializer.save()
        company_obj, created = Company.objects.get_or_create(name=validated_data.pop('company'))
        status = StatusCollection.objects.get(status='1.2')#to do
        if request and hasattr(request, "user"):
            created_user = request.user
            Client.objects.filter(id=instance.id).update(created_by=created_user, status=status, company=company_obj, **validated_data)

        else:
            Client.objects.filter(id=instance.id).update(status=status, company=company_obj, **validated_data)

        client = Client.objects.get(id=instance.id)
        client.save()
        add_activity_flow(action_performed_by=client.created_by, client=client, status=status)

        return client


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ('id', 'name','provider_logo')


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = ('id', 'instrument_name','instrument_description','provider_id')

class ClientInstrumentInfoSerializer(serializers.ModelSerializer):
    client_id = serializers.IntegerField(required=True)
    instrument_id = serializers.IntegerField(required=True)
    provider_id = serializers.IntegerField(required=True)
    provider_type = serializers.IntegerField(required=True)
    instrument_name = serializers.SerializerMethodField()
    product_type = serializers.SerializerMethodField()
    loa_template_id = serializers.SerializerMethodField()
    email_template_id=serializers.SerializerMethodField()
    reminder_count = serializers.SerializerMethodField()
    signed_loa    = serializers.SerializerMethodField()
    pdf_data = serializers.SerializerMethodField()
    data_extracted = serializers.SerializerMethodField()
    is_mail_available=serializers.SerializerMethodField()
    extracted_doc_id= serializers.SerializerMethodField()
    is_remainder_mail_active= serializers.SerializerMethodField()


    class Meta:
        model = ClientInstrumentInfo
        fields = ('id','client_id','instrument_id','provider_id','provider_type','is_mail_available','instrument_name','product_type','loa_template_id', \
                  'email_template_id','reminder_count','signed_loa','pdf_data','data_extracted','loa_mail_sent','data_extraction_status',
                  'extracted_doc_id','is_remainder_mail_active','is_recommended')

    def get_signed_loa(self, obj):
        if obj.signed_loa is not None:
            return obj.signed_loa.id
        else:
            return None

    def get_pdf_data(self, obj):
        if obj.pdf_data is not None:
            return obj.pdf_data.id
        else:
            return None
    def get_data_extracted(self, obj):
        if obj.data_extracted is not None:
            return obj.data_extracted.id
        else:
            return None

    def get_reminder_count(self, obj):
        return obj.reminder_count

    def get_email_template_id(self, obj):
        template_id=obj.instrument.mail_template.id
        return template_id


    def get_loa_template_id(self, obj):
        return obj.instrument.loa_template.id

    def get_instrument_name(self, obj):
        return obj.instrument.instrument_name
    
    def get_product_type(self, obj):
        if obj.instrument.product_type:
            return obj.instrument.product_type.fund_type
        else:
            return None
    def get_is_mail_available(self, obj):
        if obj.instrument.mail_id:
            return True
        else:
            return False
        
    def get_extracted_doc_id(self,obj):
        data = ClientInstrumentDocument.objects.filter(instrument_id=obj.id).last()
        if data and data.status=='completed':
            instrumentdocument_id = str(data._id)
            return instrumentdocument_id    
        else:
            return None    
    
    def get_is_remainder_mail_active(self,obj):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
        sent_items = MailFolder.objects.filter(user=user, folder_name='Sent Items').first()
        template_subject = obj.instrument.mail_template.subject

        if obj.signed_loa:
            message_subject=template_subject + ' - CLT_' + str(obj.id) + '_' + str(obj.signed_loa.id)

            if sent_items:
                mail = Email.objects.filter(message_subject=message_subject, folder=sent_items, user=user).exclude(object_id='').order_by('-message_recieved').last()
                if mail:
                    return True
        return False
           


    def create(self, validated_data):
        """
        Overriding the default create method of the Model serializer.
        :param validated_data: data containing all the details of clientinstruments
        :return: returns a successfully created clientinstrument record
        """
        print("||| | | |  |  |   |",validated_data,len(validated_data))
        client_obj = Client.objects.get(id=validated_data.pop('client_id'))
        instrument_obj = Instrument.objects.get(id=validated_data.pop('instrument_id'))
        provider_obj = Provider.objects.get(id=validated_data.pop('provider_id'))
        status = StatusCollection.objects.get(status='1.19')#instrument created status
        user = None
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user = request.user
        user_obj = User.objects.get(id=user.id)
        try:
            client_instrument = ClientInstrumentInfo.objects.create(client=client_obj,instrument=instrument_obj,provider=provider_obj,created_by=user_obj,\
                                                               instrument_status=status,**validated_data)
            print("-------------- |||||||| YES CREATED |||||||| -------------------")
            try:

                if(client_instrument.provider_type==1):
                    pending_status = StatusCollection.objects.get(status='1.21')  # loa download pending status
                    pending_status_save(client_instrument=client_instrument,pending_status=pending_status)
               
            except Exception as e:
                print(e)

        except Exception as e:
            print(e)
        return client_instrument


class TemplateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Templates
        fields = ('id','template_name','subject','content','template_header','template_footer','template_attachment_url',)
        
class TemplateCategorySerializer(serializers.ModelSerializer):
    temp_category_name = serializers.SerializerMethodField()
    class Meta:
        model = TemplateCategory
        fields = ('id','temp_category','temp_category_name')

    def get_temp_category_name(self, obj):
        return obj.get_temp_category_display()



class ActivityFlowSerializer(serializers.ModelSerializer):
    activity_status = serializers.SerializerMethodField()
    stage = serializers.SerializerMethodField()
    page_url = serializers.SerializerMethodField()

    class Meta:
        model = ActivityFlow
        
        fields = ('activity_status','create_time','stage','page_url')
    
    def get_activity_status(self, obj):
        by=""
        request = self.context.get("request")    

        if obj.client_task:
            if obj.task_status.created_by:
                if request and hasattr(request, "user"):
                    if obj.task_status.created_by.user != request.user:
                        
                        by = " - " + obj.task_status.created_by.user.first_name.title()
          
            if obj.task_status.meeting_info:

                return obj.task_status.task_collection.task_name + " - " + obj.task_status.meeting_info.subject + by

            if obj.task_status.assigned_to and obj.task_status.assigned_to.user:
               
                return obj.task_status.task_collection.task_name +" - "+obj.task_status.assigned_to.user.first_name+" "+obj.task_status.assigned_to.user.last_name + by
            else:
                if obj.task_status.comments is not None:
                    
                    return obj.task_status.task_collection.task_name +" - "+obj.task_status.comments + by
                else:
                    
                    return obj.task_status.task_collection.task_name + by

        else:
            if obj.action_performed_by:
                if request and hasattr(request, "user"):
                    if obj.action_performed_by != request.user:
                        
                        by = " - " + obj.action_performed_by.first_name.title()
            result=obj.status.get_status_display()
            if obj.comment:
                result=result+" - "+obj.comment
            if obj.status.get_status_name_display().startswith("Instrument_") or  obj.status.get_status_name_display().startswith("Draft"):
                if obj.client_instrument is not None:
                    result=result+" - "+obj.client_instrument.instrument.instrument_name
        
            
            result = result+by
        return result

    def get_stage(self, obj):
        if obj.client_task:
            result="POST"
            return result
        if obj.status.status.startswith("1"):
            result="PRE"
        if obj.status.status.startswith("2") :
            result="ATP"
        if obj.status.status.startswith("3"):
            result="POST"
        return result

    def get_page_url(self, obj):
        #to return the url of the corresponding activity
        request = self.context.get("request")
        data = get_page_url(client=obj.client, status=obj.status, instrument=obj.client_instrument, user=request.user, voice_category=obj.comment, client_task=obj.client_task, task_collection=obj.task_status)
        return data



class ReminderSerializer(serializers.ModelSerializer):
    pending_actions = serializers.SerializerMethodField()
    snooze_status = serializers.SerializerMethodField()
    client= serializers.SerializerMethodField()
    client_instrument_id = serializers.SerializerMethodField()
    is_remainder_mail_active= serializers.SerializerMethodField()
    page_url = serializers.SerializerMethodField()
    

    class Meta:
        model = Reminder
        fields = ('id','pending_actions','pending_with','due_date','reminder_date','client','client_id','snooze_status','snooze_duration','snooze_duration_unit','mail_needed',\
                  'mail_count','client_instrument_id','is_remainder_mail_active', 'page_url')

   
    def get_client_instrument_id(self,obj):
        if obj.client_instrument:
            client_instrument_id = obj.client_instrument.id
        else:
            client_instrument_id = None 

        return client_instrument_id


    def get_pending_actions(self, obj):
        result=obj.status.get_status_display()
        if obj.comment:
            result=result+"-"+obj.comment
       

        return result

    def get_snooze_status(self, obj):
        result=obj.get_snooze_status_display()
        return result

    def get_client(self,obj):
        return obj.client.user.first_name+" "+obj.client.user.last_name

    def get_is_remainder_mail_active(self,obj):
        print(obj.client_instrument, ' asd=========================================\n\n')
        if obj.client_instrument:
            
            sent_items = MailFolder.objects.filter(user=obj.client_instrument.client.created_by, folder_name='Sent Items').first()
            template_subject = obj.client_instrument.instrument.mail_template.subject

            if obj.client_instrument.signed_loa:
                message_subject=template_subject + ' - CLT_' + str(obj.client_instrument.id) + '_' + str(obj.client_instrument.signed_loa.id)

                if sent_items:
                    mail = Email.objects.filter(message_subject=message_subject, folder=sent_items, user=obj.client_instrument.client.created_by).exclude(object_id='').order_by('-message_recieved').last()

                    if mail:
                        return True
        return False


    def get_page_url(self, obj):
        #to return the url of the corresponding activity
        request = self.context.get("request")
        data = get_page_url(client=obj.client, status=obj.status, instrument=obj.client_instrument, user=request.user, voice_category=obj.comment)
        return data
        

    def update(self, instance, validated_data):
        request = self.context.get("request")
        try:
            snooze_duration = validated_data.pop('snooze_duration')
            snooze_duration_unit = validated_data.pop('snooze_duration_unit')
            reminder_instance=Reminder.objects.get(id=instance.id)
            snooze_enable = self.context['request'].query_params.get('snooze_enable', None)
            if snooze_enable is not None:

                pre_reminder_date = instance.reminder_date


                if(snooze_enable=='true'):
                    reminder_instance.snooze_status="1"   #enabling snooze status
                    reminder_instance.snooze_duration = snooze_duration
                    reminder_instance.snooze_duration_unit = snooze_duration_unit
                    if (snooze_duration_unit == 'week'):
                        snooze_duration = snooze_duration * 7
                    reminder_instance.reminder_date = pre_reminder_date + timedelta(int(snooze_duration))
                else:
                    
                    reminder_instance.snooze_status = "2" #disabling snooze status
                    if (reminder_instance.snooze_duration_unit == 'week'):
                        reminder_instance.snooze_duration=reminder_instance.snooze_duration*7
                    reminder_instance.reminder_date = pre_reminder_date - timedelta(int(reminder_instance.snooze_duration))
                    reminder_instance.snooze_duration = snooze_duration




    

                reminder_instance.save()
        except Exception as e:
            print(e)

        return reminder_instance
        


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryAndSubCategory
        fields = ('id', 'category_name','category_order')

class CategorySummarySerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    days_remaining= serializers.SerializerMethodField()
    category_order =  serializers.SerializerMethodField()
    class Meta:
        model = CategorySummary
        fields = ('id', 'category_id','category_name','days_remaining','percentage_of_completion','total_mandatory_labels','answered_mandatory_labels',\
                  'total_labels','total_answered_labels','category_order')
    def get_category_order(self,obj):
        return obj.category.category_order
    def get_category_name(self,obj):
        return obj.category.category_name

    def get_days_remaining(self,obj):

        total_allowed_days = obj.category.allowed_days
        client_created_time = obj.client.create_time
        current_date_time = datetime.now(timezone.utc)
        date_diff = (current_date_time - client_created_time).days
        remaining_days = int(total_allowed_days) - date_diff
        if remaining_days > 1:
            days_remain=("{0} days remaining".format(remaining_days))
        elif remaining_days == 1:
            days_remain=("1 day remaining")
        elif remaining_days == 0:
            days_remain=("Few hours remaining")
        else:
            days_remain=("{0} days exceeded".format(str(remaining_days)[1:]))
        obj.days_remaining=days_remain
        obj.save()
        return days_remain



class CountrySerializer(serializers.ModelSerializer):

    class Meta:
        model = Countries
        fields = ('id','name')


class JobtitleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Job_titles
        fields = ('id','name')



class LenderSerializer(serializers.ModelSerializer):

    class Meta:
        model = Lender_names
        fields = ('id','name')


class PensionproviderSerializer(serializers.ModelSerializer):

    class Meta:
        model = pension_providers
        fields = ('id','name')



class ClientAudioExtractionSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ClientAudioExtraction
        fields =  ('id','advisor_id','client_id','recording_name','recording_text','recording_blob','audio_data','category_id')    
        read_only_fields = ('recording_text','recording_name','audio_data')
  


class ClientTaskSerializer(serializers.ModelSerializer):
    
    client_name = serializers.SerializerMethodField(read_only=True)
    assigned_to_staff_name = serializers.SerializerMethodField(read_only=True)
    current_task_name = serializers.SerializerMethodField(read_only=True)
    advisor_name = serializers.SerializerMethodField(read_only=True)
    assigned_staff_team = serializers.SerializerMethodField(read_only=True)
    kyc_status = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = ClientTask
        fields = ('id', 'client', 'assigned_to', 'task_status', 'advisor', 'administrator', 'compliance', \
            'is_ops_verified', 'is_admin_verified','is_compliance_verified',\
            'ops_verified_on', 'admin_verified_on', 'compliance_verified_on',\
            'is_admin_checklist_verified', 'is_compliance_checklist_verified', 'is_advisor_checklist_verified',\
            'client_name', 'assigned_to_staff_name', 'current_task_name', 'advisor_name', 'create_time', 'assigned_staff_team',\
            'advisor_approved', 'advisor_approved_on','kyc_status','is_kyc_confirmed')


    def get_client_name(self,obj):
        if obj.client:
            return obj.client.user.first_name.title() + ' ' + obj.client.user.last_name.title()

    def get_assigned_to_staff_name(self,obj):
        if obj.assigned_to:
            return obj.assigned_to.user.first_name.title() + ' ' + obj.assigned_to.user.last_name.title()

    def get_current_task_name(self,obj):
       
        if obj.current_sub_task:
            return obj.current_sub_task.task_name

        
   

    def get_advisor_name(self, obj):
        if obj.advisor:
            return obj.advisor.user.first_name.title() + ' ' + obj.advisor.user.last_name.title()

    def get_assigned_staff_team(self,obj):
        if obj.assigned_to:
          
            return Group.objects.filter(user=obj.assigned_to.user).first().name
    
    def get_kyc_status(self,obj):
        if obj.client:
            smartsearch_obj = Smartserach.objects.filter(client=obj.client,task=obj).last()
            if smartsearch_obj:
                status = smartsearch_obj.status
            else:
               status=None
            return status

    def create(self, validated_data):
        client = validated_data.pop('client')
        request = self.context.get("request")
        advisor = Staff.objects.filter(user=client.created_by).first()
        active_task = ClientTask.objects.filter(client=client).exclude(task_status='3')
        if 'assigned_to' in validated_data:
            assigned_to = validated_data.pop('assigned_to')   
        else:    
            assigned_to = Staff.objects.filter(user__groups__name='Ops', company=advisor.company).first()  

        if not assigned_to or not advisor:
            return False,False
        if active_task:
            return False,True

        task_obj = ClientTask.objects.create(assigned_to=assigned_to, client=client, advisor=advisor, ops=assigned_to, is_advisor_checklist_verified=True, advisor_checklist_verified_on=tz.now())
        client.current_task_id=task_obj

        status_collection = StatusCollection.objects.get(status='2.1')   #Task created
        add_activity_flow(action_performed_by=request.user, client=client, status=status_collection)

        status_collection = StatusCollection.objects.get(status='2.2')   #Task assigned
        add_activity_flow(action_performed_by=request.user, client=client, status=status_collection)

        result = templatemailsend("task_creation-notification_mail", advisor.user,client.id)
        if(result):
            print("task_creation-notification_mail has been sent ....")
        #updating the Client models as confirmed client
        client.is_confirmed_client = True
        client.confirm_client_date = dt.datetime.now()
        client.save()
        client_profile_completion(client=client,phase='atp',percentage=100,sign='positive')
        
        
        client.client_stage='3' 
        client.save()

        return task_obj,False


    def update(self, instance, validated_data):
        request = self.context.get("request")
        staff = Staff.objects.filter(user=request.user).first()
        
        is_ops_verified = instance.is_ops_verified
        ops_verified_on = instance.ops_verified_on
        
        is_admin_verified = instance.is_admin_verified
        admin_verified_on = instance.admin_verified_on

        is_compliance_verified = instance.is_compliance_verified
        compliance_verified_on = instance.compliance_verified_on

        is_advisor_checklist_verified = instance.is_advisor_checklist_verified
        advisor_checklist_verified_on = instance.advisor_checklist_verified_on
        
        is_admin_checklist_verified = instance.is_admin_checklist_verified
        admin_checklist_verified_on = instance.admin_checklist_verified_on
        
        is_compliance_checklist_verified = instance.is_compliance_checklist_verified
        compliance_checklist_verified_on = instance.compliance_checklist_verified_on

        advisor_approved = instance.advisor_approved
        advisor_approved_on = instance.advisor_approved_on

        is_kyc_confirmed = instance.is_kyc_confirmed
        kyc_confirmed_on = instance.kyc_confirmed_on
        task_collection = instance.current_sub_task

        if 'is_ops_verified' in validated_data and not instance.is_ops_verified:
            if instance.ops != staff:
                raise serializers.ValidationError("User not authorized")
            is_ops_verified = True
            ops_verified_on = tz.now()
            instance.task_status = '2'  #changing task status to Ongoing when ops verifies the task

           
            client_profile_completion(client=instance.client,phase='post-contract',percentage=25,sign='positive') 

            task_collection = TaskCollection.objects.filter(task_slug='task_verified').first()
            add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.ops, assigned_to=instance.administrator, task_status='3')

        if 'is_admin_verified' in validated_data and not instance.is_admin_verified:
            compliance_user = Staff.objects.filter(user__groups__name='Compliance', company=instance.administrator.company).first()
            if instance.administrator != staff:
                raise serializers.ValidationError("User not authorized")
            if not compliance_user:
                raise serializers.ValidationError("Client task could not be verified as Compliance user not found")

            is_admin_verified = True
            admin_verified_on = tz.now()
            instance.assigned_to = compliance_user
            instance.compliance = compliance_user
            client_profile_completion(client=instance.client,phase='post-contract',percentage=15,sign='positive') 
            
            
            task_collection = TaskCollection.objects.filter(task_slug='assign_to_compliance').first()
            add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.administrator, assigned_to=instance.compliance, task_status='3')
            result = templatemailsend("compliance_task_assignment", request.user, instance.client.id, assigned_to=instance.assigned_to, task=instance)
            if result:
                print("================== task assignment to compliance mail has been sent ================================ ")

        if 'is_compliance_verified' in validated_data and not instance.is_compliance_verified:
            if instance.compliance != staff:
                raise serializers.ValidationError("User not authorized")

            is_compliance_verified = True
            compliance_verified_on = tz.now()
            # instance.assigned_to = instance.advisor
            instance.assigned_to = instance.administrator
            instance.is_in_final = True
            
            client_profile_completion(client=instance.client,phase='post-contract',percentage=25,sign='positive')             

            task_collection = TaskCollection.objects.filter(task_slug='final_assign_to_administrator').first()
            add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.compliance, assigned_to=instance.administrator, task_status='3')
            result = templatemailsend("compliance_task_approval", request.user, instance.client.id, assigned_to=instance.assigned_to, task=instance)
            if result:
                print("================== task approval by compliance mail has been sent ================================ ")

        if 'is_advisor_checklist_verified' in validated_data and not instance.is_advisor_checklist_verified:
            is_advisor_checklist_verified = True
            advisor_checklist_verified_on = tz.now()
            task_collection = TaskCollection.objects.filter(task_slug='advisor_checklist_verified').first()
            add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.advisor, task_status='3')

        if 'is_admin_checklist_verified' in validated_data and not instance.is_admin_checklist_verified:
            is_admin_checklist_verified = True
            admin_checklist_verified_on = tz.now()
            task_collection = TaskCollection.objects.filter(task_slug='administrator_checklist_verified').first()
            add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.administrator, task_status='3')
        
        if 'is_compliance_checklist_verified' in validated_data and not instance.is_compliance_checklist_verified:
            is_compliance_checklist_verified = True
            compliance_checklist_verified_on = tz.now()
            task_collection = TaskCollection.objects.filter(task_slug='compliance_checklist_verified').first()
            add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.compliance, task_status='3')
        
        if 'is_kyc_confirmed' in validated_data and not instance.is_kyc_confirmed:
            is_kyc_confirmed = True
            kyc_confirmed_on = tz.now()
            task_collection = TaskCollection.objects.filter(task_slug='confirm_kyc').first()
            if not instance.kyc_ever_confirmed:
                add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.administrator, task_status='3')
                instance.kyc_ever_confirmed=True
            else:
                task_collection = TaskCollection.objects.filter(task_slug='kyc_reconfirmed').first()
                add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.administrator, task_status='3')
                

            update_or_create_checklist(instance.client,47,instance.advisor,result='passed')
            client_profile_completion(client=instance.client,phase='post-contract',percentage=10,sign='positive')

        
        if 'advisor_approved' in validated_data and not instance.advisor_approved:
            if instance.is_advisor_checklist_verified and instance.is_admin_checklist_verified and instance.is_compliance_checklist_verified:
                print('here')
                advisor_approved = True
                advisor_approved_on = tz.now()
                print(advisor_approved_on, '   ----------------------------- ')
                client_profile_completion(client=instance.client,phase='post-contract',percentage=25,sign='positive') 
               

                instance.task_status = '3'
                reset_checklist_and_reccommendations(task=instance)
                # task_collection = TaskCollection.objects.filter(task_slug='advisor_approval').first()
                task_collection = TaskCollection.objects.filter(task_slug='administrator_approval').first()
                add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.advisor, task_status='3')
                category = CategoryAndSubCategory.objects.filter(category_slug_name='personal_information_7').first()
                pdf_password = None
                if category:
                    try:
                        surveyform = SurveyFormData.objects.filter(client_id=instance.client.id, category_id=category.id).first()
                        if surveyform is not None:
                            for subcategory in surveyform.form_data:
                                label_list = subcategory['subcategory_data']
                                if subcategory['subcategory_slug_name'] == "basic_info_8":
                                    for label in label_list:
                                        if (label['label_slug'] == 'dob_84'):
                                            dob = label['answer']
                                            if dob:
                                                dob = datetime.strptime(dob,"%Y-%m-%dT%H:%M:%S.%fZ").strftime('%m%y')
                    except Exception as e:
                        print("exception ",e)
                        dob = '0000'
                if len(str(instance.client.user.first_name)) >= 4:
                    pdf_password = str(instance.client.user.first_name).upper()[:4:] + str(dob)
                else:
                    pdf_password = str(instance.client.user.first_name).upper() + str(dob)
                print(pdf_password)
                #sendng the final SR doc to the client after encrypting it#temporarily commented it
                #encrypt_and_send_mail(client=instance.client, advisor=instance.advisor, pdf_password=pdf_password, task=instance)

                task_collection = TaskCollection.objects.filter(task_slug='final_draft_mail_send').first()
                add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.advisor, task_status='3')
                task_collection = TaskCollection.objects.filter(task_slug='task_file_closed').first()
                add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.advisor, task_status='3')

                client = Client.objects.filter(id=instance.client.id).first()
                client.current_task_id = None
                client.save()
                
            else:
                raise serializers.ValidationError("Client task could not be approved as checklist verification pending")
        
        instance.current_sub_task = task_collection
        instance.is_ops_verified = is_ops_verified
        instance.ops_verified_on = ops_verified_on
        instance.is_admin_verified = is_admin_verified
        instance.admin_verified_on = admin_verified_on
        instance.is_compliance_verified = is_compliance_verified
        instance.compliance_verified_on = compliance_verified_on
        instance.is_advisor_checklist_verified = is_advisor_checklist_verified
        instance.advisor_checklist_verified_on = advisor_checklist_verified_on
        instance.is_admin_checklist_verified = is_admin_checklist_verified
        instance.admin_checklist_verified_on = admin_checklist_verified_on
        instance.is_compliance_checklist_verified = is_compliance_checklist_verified
        instance.compliance_checklist_verified_on = compliance_checklist_verified_on
        instance.advisor_approved = advisor_approved
        instance.advisor_approved_on = advisor_approved_on
        instance.is_kyc_confirmed = is_kyc_confirmed
        instance.kyc_confirmed_on = kyc_confirmed_on
        instance.save()

        return instance


class ClientTaskCommentSerializer(serializers.ModelSerializer):
    
    commented_by_user =  serializers.SerializerMethodField()
    commented_user_type =  serializers.SerializerMethodField()

    class Meta:
        model = ClientTaskComments
        
        fields = ('id', 'comment', 'task', 'commented_by', 'commented_by_user', 'create_time', 'commented_user_type')
        

    def get_commented_by_user(self, obj):
        if obj.commented_by:
            return obj.commented_by.user.first_name +' '+ obj.commented_by.user.last_name

    def get_commented_user_type(self, obj):
        if obj.commented_by:
            group = Group.objects.filter(user=obj.commented_by.user).first() 
            if group:
                return group.name

    def create(self, validated_data):
        user_id = validated_data.pop('commented_by')
        staff = Staff.objects.filter(user__id=user_id)
        if staff:
            created = ClientTaskComments.objects.create(comment=validated_data['comment'], task__id=validated_data['task_id'], commented_by=staff)
        return created




class StaffSerializer(serializers.ModelSerializer):

    user = UserSerializer(required=True)
    company = serializers.CharField(required=True)
    
    user_type = serializers.CharField(read_only=True)

    class Meta:
        model = Staff
        fields = ('id', 'user', 'company', 'user_type')

    def create(self, validated_data):
        """
        Overriding the default create method of the Model serializer.
        :param validated_data: data containing all the details of staff
        :return: returns a successfully created staff record
        """
        user_data = validated_data.pop('user')        
        user = UserSerializer.create(UserSerializer(), validated_data=user_data)
        company_obj, created = Company.objects.get_or_create(name=validated_data.pop('company'))
        request = self.context.get("request") 
        if request and hasattr(request, "user"):
            created_user = request.user
            staff = Staff.objects.create(created_by=created_user, user=user, company=company_obj)
        return staff



    def get_user_type(self,obj):
        return Group.objects.filter(user=obj.user).first().name


class InstrumentExtractedDataSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = InstrumentExtractedData
        fields =('instrumentdocument_id','extracted_data','extracted_table')


class TaskEventSerializer(serializers.ModelSerializer):
    
    event_start = serializers.SerializerMethodField()
    event_end = serializers.SerializerMethodField()
    event_is_all_day = serializers.SerializerMethodField()
    event_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskEvents
        fields = ("event","client","advisor","task","scheduled_by","event_start","event_name", "event_end", "event_is_all_day" )

    def get_event_start(self,obj):
        return obj.event.event_start
    
    def get_event_end(self,obj):
        return obj.event.event_end
    
    def get_event_is_all_day(self,obj):
        return obj.event.is_all_day

    def get_event_name(self,obj):
        return obj.event.subject



class ClientTaskTimelineSerializer(serializers.ModelSerializer):

    task_collection =  serializers.SerializerMethodField()
    
    class Meta:
        model = ClientTaskTimeline
        fields = ('id', 'task_collection', 'create_time', 'assigned_to')

    def get_task_collection(self,obj):
        print('here')
        if obj.meeting_info:
            return obj.task_collection.task_name +" - "+obj.meeting_info.subject

        elif obj.assigned_to and obj.assigned_to.user:
            return obj.task_collection.task_name +" - "+obj.assigned_to.user.first_name+" "+obj.assigned_to.user.last_name
        elif obj.comments is not None:
            return obj.task_collection.task_name+" - "+obj.comments
        else:
            return obj.task_collection.task_name 



class FeeRuleConfigSerializer(serializers.ModelSerializer):

    class Meta:
        model = FeeRuleConfig
        fields = ('id','charge_name','start','end','interval','interval_type','default_value')


class ReasonSerializer(serializers.ModelSerializer):
    function_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Reason
        fields = ('id','reason', 'function', 'function_name') 

    def get_function_name(self, obj):
        return obj.function.get_function_type_display()       


class DraftReccomendationSerializer(serializers.ModelSerializer):

    
    class Meta:
        model = DraftReccomendation
        fields = ('id','instrument_recommended', 'advisor_comments','client')    


class InstrumentsRecomendedSerializer(serializers.ModelSerializer):
    

    product_type =  serializers.SerializerMethodField()
    provider_type = serializers.SerializerMethodField()
    recomended_instrument = serializers.SerializerMethodField()
    annual_amount = serializers.SerializerMethodField()

    class Meta:
       
        model = InstrumentsRecomended
        fields = ('id','advisor','client_instrumentinfo','recomended_instrument', 'initial_fee','ongoing_fee','dfm_fee','amount','map_transfer_from',\
        'provider_type','product_type','reason','function_list','fund_risk','is_clone', 'annual_amount', 'is_active')    




    def get_provider_type(self,obj):
        extracted_data_obj = ClientInstrumentInfo.objects.filter(id=obj.client_instrumentinfo.id).first()
        if extracted_data_obj:
            provider_type = extracted_data_obj.get_provider_type_display()
            return provider_type
        else:
            return None

    def get_product_type(self,obj):
        client_instrument = ClientInstrumentInfo.objects.filter(id=obj.client_instrumentinfo.id).first()
        if client_instrument and client_instrument is not None:
            instrument = Instrument.objects.filter(id=client_instrument.instrument.id).first()
            if instrument:
                product_type_obj = instrument.product_type
            else:
                product_type_obj = None
            if product_type_obj:
                product_type = ProductType.objects.filter(id=product_type_obj.id).first()
                product_type = product_type.fund_type
            else :
                product_type = None
        else:
            product_type = None
        
        return product_type

    def get_recomended_instrument(self,obj):
        recomended_instrument =None
        if obj.client_instrumentinfo:
            recomended_instrument = obj.client_instrumentinfo.instrument.instrument_name
        return recomended_instrument

    def get_annual_amount(self, obj):
       
        total_amount = 0
        instr_rec = InstrumentsRecomended.objects.filter(client_instrumentinfo__client_id=obj.client_instrumentinfo.client_id)
        charge_valid_instrs = instr_rec.filter(function_list__in=['1'], map_transfer_from__isnull=False)
        charge_valid_instrs = charge_valid_instrs | instr_rec.exclude(function_list__in=['1'])
        charge_valid_instrs = charge_valid_instrs.distinct()
        
        for ins in charge_valid_instrs:
            if ins.amount:
                total_amount = total_amount + ins.amount

        total_initial_fee_percent, total_dfm_fee_percent, total_ongoing_fee_percent = calculate_fee(amount=total_amount, inst_rec=charge_valid_instrs)
        total_fee_percent = round(total_dfm_fee_percent + total_ongoing_fee_percent,2)
        # comment above line and uncomment below to fix the rounding issue when total fee percent is close to zero 
        # total_fee_percent = total_dfm_fee_percent + total_ongoing_fee_percent
        # print(total_dfm_fee_percent + total_ongoing_fee_percent, ' ------------------------------------- ')
        if obj.amount:
            annual_fee_amount = round(obj.amount * total_fee_percent / 100, 2)
        else:
            annual_fee_amount = 0

        return annual_fee_amount



class ClientRecommendationNotificationSerializer(serializers.ModelSerializer):
    notification = serializers.SerializerMethodField()
    is_question = serializers.SerializerMethodField()
    class Meta:
        model = ClientRecommendationNotification
        fields = ('id','notification','is_question','is_answer')

    def get_notification(self,obj):
        if obj.recommendation_status:
            notification = obj.recommendation_status.status_name
            return notification
        else:
            return None

    def get_is_question(self,obj):
        if obj.recommendation_status:
            is_question = obj.recommendation_status.is_question
            return is_question
        else:
            return None
    
   
class ExtractedDataSerializer(serializers.ModelSerializer):
    master_keywords =  serializers.SerializerMethodField()
    extraction_keyword =  serializers.SerializerMethodField()
   
    class Meta:
        model = ExtractedData
        fields = ('client_instrumentinfo','master_keywords','extraction_keyword','extracted_value')

    def get_master_keywords(self, obj):
        return obj.master_keywords.keyword

    def get_extraction_keyword(self, obj):
        return obj.extraction_keyword.mapped_keywords



class ClientCheckListSerializer(serializers.ModelSerializer):

        checklist_name = serializers.SerializerMethodField()
        class Meta:
            model = ClientCheckList
            fields = ('id','checklist_name','colour_code','client','owner_group','user','administrator','compliance')

        def get_checklist_name(self, obj):
            if obj.draft_checklist:
                if obj.instrument_recommended:
                    function_type=(list(obj.instrument_recommended.function_list.all())[0]).get_function_type_display()
                    return str(obj.instrument_recommended.client_instrumentinfo.instrument.instrument_name)+'('+str(function_type)+')'\
                            +' : '+(obj.draft_checklist.checklist_names)
                elif obj.client_instrument:
                    return str(obj.client_instrument.instrument.instrument_name)+' : '+(obj.draft_checklist.checklist_names)
                    
                else:
                    return obj.draft_checklist.checklist_names
            else:
                return None


class AdvisorProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    company_name =serializers.SerializerMethodField()
    company_logo = serializers.SerializerMethodField()
    company_website = serializers.SerializerMethodField()
    signature_name = serializers.SerializerMethodField()
    company_logo_name = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = ('id','first_name','last_name','company_id','company_name','company_logo','company_website','phone_number','email','advisor_terms_and_agreement', 'signature','designation','phone_number2','signature_name','company_logo_name')

    def get_first_name(self, obj):
        return obj.user.first_name
    def get_last_name(self, obj):
        return obj.user.last_name
    def get_email(self, obj):
        return obj.user.email
    def get_company_name(self, obj):
        return obj.company.name
    def get_company_logo(self, obj):
        if obj.company.logo:
           return obj.company.logo.url
        else:
            return None
    def get_company_website(self, obj):
        return obj.company.url
    def get_company_logo_name(self,obj):
        if obj.company.logo:
           return obj.company.logo.name
        else:
            return None
    

    def get_signature_name(self,obj):
        if obj.signature:
           return obj.signature.name
        else:
            return None
        

class ErrorlogSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Errorlog
        fields = ('logs',)