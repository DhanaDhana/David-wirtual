import pathlib
from cap_services.settings import IS_S3
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.decorators import action
from django.template import Context, Template
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from rest_framework import viewsets, status, filters, serializers
from .serializers import MailFolderSerializer, MailSerializer, AttachmentSerializer, EventSerializer, AttendeesSerializer, OutlookCredentialsSerializer
from .utils import templatemailsend
from clients.utils import add_activity_flow
import datetime as dt
from cap_services.settings import BASE_URL
from cap_services.settings import MEDIA_PATH as MEDIA_URL
import time
from dateutil.relativedelta import relativedelta
from rest_framework.views import APIView
from django.db.models import Q

from cap_outlook_service.outlook_services.models import MailFolder, Email, OutlookLog, Event, Attachments, OutlookCredentials, Attendees, OutlookSync, get_token_upload_path
from cap_outlook_service.outlook_services.graph_helper import get_sign_in_url, get_token_from_code
from clients.models import ClientInstrumentInfo, Document, MailTemplateMapping, Templates, TemplateCategory, StatusCollection, Provider, Client, Reminder, TaskEvents,\
                            AutotriggerMail, Staff, DraftCheckList, ClientCheckList, TaskCollection, ClientTask,TemplateAttachments,Instrument
from clients.utils import get_mail_with_subject, pending_status_save, add_task_activity
from rest_framework.authtoken.models import Token

from django.http import HttpResponseRedirect
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from cap_outlook_service.outlook_services.tasks import async_get_mailfolders
from django.conf import settings
import os
from django.db.models import Subquery
import json
from django.core.files.storage import FileSystemStorage as server_storage


import logging    
logger = logging.getLogger('django.request')


class MailFolderViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)
    queryset = MailFolder.objects.all()
    serializer_class = MailFolderSerializer

    def get_queryset(self):
        folder = self.request.query_params.get('folder', None)
        queryset = MailFolder.objects.all()
        queryset = queryset.filter(user_id=self.request.user.id)        
        if folder:
            try:
                folder_id = MailFolder.objects.get(id=folder)
                queryset = queryset.exclude(id=folder_id.id)

                if folder_id.folder_name == 'Inbox':
                    queryset = queryset.exclude(folder_name__in=['Sent Items', 'Outbox', 'Drafts', 'Conversation History'])
                elif folder_id.folder_name in ['Sent Items', 'Outbox', 'Drafts', 'Conversation History']:
                    queryset = queryset.exclude(folder_name__in=['Inbox', 'Outbox', 'Drafts'])
                else:
                    queryset = queryset.exclude(folder_name__in=['Inbox', 'Outbox', 'Drafts', 'Sent Items', 'Conversation History'])

            except Exception as e:
                print(e)
                raise serializers.ValidationError({"folder": ["Invalid folder specified"]})
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Mail Folder List',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

def set_response_data(response_data):
    response_data['status_code'] = '200'
    response_data['status'] = True
    response_data['message'] = 'Mail Already sent'
    return response_data

class EmailViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = MailSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)


    def get_queryset(self):        
        folder = self.request.query_params.get('folder', None)
        mail_id = self.request.query_params.get('mail', None)

        queryset = Email.objects.all()
        
        queryset = queryset.filter(user_id=self.request.user.id, meeting_message_type__isnull=True).order_by('-message_recieved')

        if folder:
            try:
                folder_id = MailFolder.objects.get(id=folder).id
                subquery = Email.objects.filter(user_id=self.request.user.id, folder_id=folder_id).order_by('conversation_id', '-message_recieved').distinct('conversation_id').values('pk')
                
                queryset = queryset.filter(pk__in = Subquery(subquery)).order_by('-message_recieved')
            except Exception as e:
                print("exception ",e)
                raise serializers.ValidationError({"folder": ["Invalid folder specified"]})
        elif mail_id:
            try:
                conversation_id = Email.objects.get(id=mail_id).conversation_id
                
                subquery = Email.objects.filter(user_id=self.request.user.id, conversation_id=conversation_id).values('pk')
                queryset = queryset.filter(pk__in = Subquery(subquery)).order_by('message_recieved')




            except:
                raise serializers.ValidationError({"mail": ["Invalid mail object"]})
        else:
            return []

        return queryset


    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        count = offset = limit = None
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            count = self.paginator.count
            offset = self.paginator.offset
            limit = self.paginator.limit
        folder = self.request.query_params.get('folder', None)
        if folder is None:
            for mail_data in serializer.data:
                mail_data.pop('unread_count')

        data = serializer.data
        
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Email List',
            "count": count,
            "offset": offset,
            "limit": limit,
            "folder":folder,
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    
    def create(self, request, *args, **kwargs):
        response_data = {}
        print("**************START****************")
        if 'template_id' in request.data.keys() and request.data['template_id']:
            try:
                template = Templates.objects.get(id=request.data['template_id'])
               



            except Exception as e:
                print(e)
                raise serializers.ValidationError({"template_id": ["Invalid template specified"]})

        if 'message_reply_to' in request.data.keys():
            if not request.data['message_reply_to']:
                request.data._mutable = True
                request.data.pop('message_reply_to')
                request.data._mutable = False
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = super().create(request)
        response.data.pop('unread_count')

       

        #chceking if mail template mapping exists
        mapping_exist = MailTemplateMapping.objects.filter(email_id=response.data['id']).first()
        if 'category_id' in request.data.keys() and request.data['category_id']:
            category = TemplateCategory.objects.get(id=request.data['category_id'])
            if 'template_id' in request.data.keys() and request.data['template_id']:
                template = Templates.objects.get(id=request.data['template_id'])
            else:
                template=None
                
            if mapping_exist:
                mapping_exist.template = template
                mapping_exist.category = category
                mapping_exist.content = response.data['message_body']
                mapping_exist.save()
            else:    
                MailTemplateMapping.objects.create(email_id=response.data['id'], template=template, category=category, content=response.data['message_body'])
        else:
            if mapping_exist:
                mapping_exist.is_deleted = True
                mapping_exist.save()

    

        if 'attachments' in request.data.keys():
            attachment_list = request.FILES.getlist('attachments')
           
            
            for file in attachment_list:
                file_serializer = AttachmentSerializer(data={'email':response.data['id'], 'attachments':file})

                if file_serializer.is_valid():
                   
                    file_list = file_serializer.save()
                    file_list.update()
                    response.data['attachment_list'].append({'fileId':file_list.id, 'name':file_list.attachments.name.split('/')[-1], 'item_url':os.path.join(MEDIA_URL,file_list.attachments.name),\
                                    'item_path':os.path.join(MEDIA_URL,file_list.attachments.name), 'item_size':file_list.attachments.size})
        
                
        if 'bulk_attachments' in request.data.keys():
            attachment_obj = TemplateAttachments.objects.filter(template_name='Welcome Letter').first().attachment_url.open() 

                
            file_serializer = AttachmentSerializer(data={'email':response.data['id'], 'attachments':attachment_obj})
            if file_serializer.is_valid():
                file_list = file_serializer.save()
                file_list.save()
                
                response.data['attachment_list'].append({'fileId':file_list.id, 'name':file_list.attachments.name.split('/')[-1], 'item_url':os.path.join(MEDIA_URL,file_list.attachments.name),\
                                'item_path':os.path.join(MEDIA_URL,file_list.attachments.name), 'item_size':file_list.attachments.size})

       
        if 'cap_drive_attachments' in request.data.keys():
            if request.data.get('loa_mail'):
                cap_attachment_list=request.data.get('cap_drive_attachments')
            else:
                cap_attachment_list = request.data.getlist('cap_drive_attachments')
                
            for doc_id in cap_attachment_list:
                print("before fetching doc")
                file=Document.objects.get(id=doc_id).doc
                print("after fetching doc")
                if IS_S3:
                    file = file.open()
                file_serializer = AttachmentSerializer(data={'email':response.data['id'], 'attachments':file})
                print("no error in serilaxzeer")
                if file_serializer.is_valid():
                    print("before file_list save")
                    file_list = file_serializer.save()
                    file_list.save()
                    print("afterfile_list save")
                    response.data['attachment_list'].append({'fileId':file_list.id, 'name':file_list.attachments.name.split('/')[-1], 'item_url':os.path.join(MEDIA_URL,file_list.attachments.name),\
                                                             'item_path':os.path.join(MEDIA_URL,file_list.attachments.name), 'item_size':file_list.attachments.size})

        # print('\n\n CAP Attachments Done -------------------------------------------------- ')


        if response.status_code == 201:
            response_data['status_code'] = '201'
            response_data['status'] = True
            if response.data['message_is_draft'] is True:
                response_data['message'] = 'Mail saved to drafts'
            else:
                response_data['message'] = 'Mail sent successfully'
            response_data['data'] = response.data
            user=User.objects.get(id=response.data["user"])
            email=Email.objects.get(id=response.data["id"])


           
            print("response data... ",response.data, '\n\n')

            log = OutlookLog.objects.create(user=user, email=email, request_info=response.data, log_type=2, status=1)

           

            while True:
                if log.status != 3:
                    continue
                else:
                    data = json.loads(log.response_info)
                    print("dataa", data)
                    if 'error' in data:
                        response_data['status_code'] = '400'
                        response_data['status'] = False
                        response_data['message'] = data['error']['message']
                        email.is_deleted = True
                        email.save()
                        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                    else:
                       
                        try:
                            
                            if 'template_id' in request.data.keys() and request.data['template_id']:
                                template_id=request.data['template_id']
                                watchable_attachment=False
                                if template_id == '23':  ##Terms of business template########

                                    if 'watchable_attachment' in request.data.keys() and request.data['watchable_attachment']:
                                        watchable_attachment = request.data['watchable_attachment']
                                    has_attachment = response.data["has_attachments"]
                                    draftchecklist1 = DraftCheckList.objects.filter(id=5).first()
                                    draftchecklist2 = DraftCheckList.objects.filter(id=6).first()
                                    recipient_list = response.data["message_to"]
                                    print("RECIPIENT LIST", recipient_list)
                                    if recipient_list:
                                        for recipient in recipient_list:
                                            try:
                                               
                                                client = Client.objects.filter(user__email__iexact=recipient).first()
                                            except Client.DoesNotExist:
                                                client = None

                                            if (client):
                                                print("CLIENT", client)
                                                print("client id", client.id)
                                              
                                                staff_user = Staff.objects.filter(user=client.created_by).first()
                                                if watchable_attachment and has_attachment:
                                                    client_checklist, created = ClientCheckList.objects.update_or_create(
                                                        draft_checklist=draftchecklist1,
                                                        client=client, owner_group='Advisor', user=staff_user,
                                                        defaults={'colour_code': 'Green'}, )
                                                    client_checklist2, created = ClientCheckList.objects.update_or_create(draft_checklist=draftchecklist2,client=client, owner_group='Advisor', user=staff_user,defaults={'colour_code': 'Green'}, )

                                                else:
                                                    client_checklist, created = ClientCheckList.objects.update_or_create(
                                                        draft_checklist=draftchecklist1,
                                                        client=client, owner_group='Advisor',
                                                        user=staff_user, defaults={
                                                            'colour_code': 'Red'}, )
                                                    client_checklist2, created = ClientCheckList.objects.update_or_create(draft_checklist=draftchecklist2,client=client, owner_group='Advisor', user=staff_user,defaults={'colour_code': 'Green'}, )
                                                
                        except Exception as e:
                            print(str(e))

                    break

        return Response(response_data, status=status.HTTP_201_CREATED )


    @action(methods=['post'], detail=True,parser_classes=[JSONParser])
    def Bulk_email(self, request, pk):
        response_data = {}
        error_list = []
        error_msg='Failed to send mail'
        message_to = []
        type = self.request.query_params.get('type', None)
        if type is not None:
            if (type == 'welcome_mail'):
                welcome_template = Templates.objects.filter(subject='Welcome Mail').first()
                template_instance = Template(welcome_template.template_header + welcome_template.content + welcome_template.template_footer)
                message_subject=welcome_template.subject
                
                request.data['has_attachments'] = True
                
            else:
                request.data['has_attachments'] = False
            client_list = request.data.pop('client_list')
            if client_list is not None:
                try:
                    for client_id in client_list:
                        print(client_id)
                        client = Client.objects.filter(id=client_id).first()
                        print(client)
                        client_first_name = client.user.first_name
                        message_to=[]
                        if client.user.email:
                            message_to=[client.user.email]
                        
                        staff = Staff.objects.filter(user=request.user).first()
                        if staff:
                            phone_number = staff.phone_number
                            phone_number2 = staff.phone_number2
                            designation = staff.designation
                            if staff.company:
                                company_url = staff.company.url
                                try:
                                    company_logo = staff.company.logo.url
                                except:
                                    company_logo = Document.objects.get(doc='advisors/company/Lathe-logo.png').doc.url
                            else:
                                company_logo = " "
                                company_url = " "
                        else:
                            company_logo = " "
                            company_url = " "
                            phone_number = None
                            phone_number2 = None
                            designation = None


                        advisor_name = request.user.first_name.title()
                        advisor_full_name = request.user.first_name.title() + ' ' + request.user.last_name.title()
                        context = Context({"advisor_name": advisor_name,"advisor_full_name":advisor_full_name,"client_first_name":client_first_name,"company_website": company_url,
                                           "company_logo":company_logo,'static_image_path':os.path.join(MEDIA_URL, 'advisors/company'),"phone_number2":phone_number2,"designation":designation,"phone_number":phone_number})
                        message_body = template_instance.render(context)
                        request.data['user'] = request.user.id
                        request.data['object_id'] = ''
                        request.data['message_sender'] = request.user.email
                        request.data['message_received'] = ''
                        request.data['message_subject'] = message_subject
                        request.data['message_body_preview'] = ''
                        request.data['message_body'] = message_body
                        request.data['message_to'] = message_to
                        request.data['message_importance'] = '1'
                        request.data['message_is_read'] = False
                        request.data['message_is_draft'] = False
                        request.data['message_flag'] = False
                        
                        
                        request.data['bulk_attachments'] = True
                        
                        try:
                            
                            result = self.create(request)
                            
                            if not result.data['status']:
                                error_list.append(client_id)

                        except Exception as e:
                            print("exception ",str(e))
                            error_list.append(client_id)
                except Exception as e:
                    print(str(e))
                    error_list.append(client_id)


        else:
            sent_reminder = self.request.query_params.get('sent_reminder', None)
            client_instrument_list=request.data.pop('instrument_list')
            print(sent_reminder, ' ----')
            if client_instrument_list is not None:
                error_msg = 'For the below Provider(s), email sending failed.'
                print("\n\nclient instrument list   :::  ", client_instrument_list)
                for instrument_id in client_instrument_list:
                    try:
                        print(instrument_id)
                        client_instr_obj=ClientInstrumentInfo.objects.get(id=instrument_id)
                        print(client_instr_obj.__dict__)

                        template_subject = client_instr_obj.instrument.mail_template.subject
                        message_to = client_instr_obj.instrument.mail_id
                        mail_template = client_instr_obj.instrument.mail_template
                        message_subject = template_subject + ' - CLT_' + str(instrument_id) + '_' +str(client_instr_obj.signed_loa.id)
                        print('sub ', message_subject)
                        if sent_reminder:
                            user=client_instr_obj.client.created_by
                            mail_instance=get_mail_with_subject(message_subject, user)
                            print("mail instance",mail_instance)
                            if mail_instance:
                                request.data['conversation_id'] = mail_instance.conversation_id
                                request.data['reply_id'] = mail_instance.object_id
                                request.data['mail_action']='2'
                                message_body="<p>This is a gentle reminder!!</p>"
                            else:
                                error_list.append(client_instr_obj.instrument.instrument_name)
                                continue

                        else:
                            template = Template(mail_template.template_header + mail_template.content + mail_template.template_footer)
                            
                            client_first_name=client_instr_obj.client.user.first_name
                            client_last_name = client_instr_obj.client.user.last_name
                            client_name = client_first_name+" "+client_last_name
                            staff = Staff.objects.filter(user=client_instr_obj.client.created_by).first()
                            if staff:
                                phone_number = staff.phone_number
                                phone_number2 = staff.phone_number2
                                designation = staff.designation
                                if staff.company:
                                    company_url = staff.company.url
                                    try:
                                        company_logo = staff.company.logo.url
                                    except Exception as e:
                                        print(e)
                                        company_logo = Document.objects.get(doc='advisors/company/Lathe-logo.png').doc.url
                                else:
                                    company_logo = " "
                                    company_url = " "
                            else:
                                company_logo = " "
                                company_url = " "
                                phone_number = None
                                phone_number2 = None
                                designation = None
                            print(client_name)
                            context = Context({"advisor_name": client_instr_obj.client.created_by.first_name + ' ' + client_instr_obj.client.created_by.last_name,"client_name":client_name,"company_url":company_url,
                                               "company_logo":company_logo,'static_image_path':os.path.join(MEDIA_URL, 'advisors/company')})
                            message_body = template.render(context)
                            if client_instr_obj.signed_loa:
                                loa_doc = str(client_instr_obj.signed_loa.id)
                                request.data['cap_drive_attachments'] = [loa_doc]

                        request.data['user']=client_instr_obj.client.created_by.id
                        request.data['object_id']=''
                        request.data['message_sender']=client_instr_obj.client.created_by.email
                        request.data['message_received'] = ''
                        request.data['message_subject'] = message_subject
                        request.data['message_body_preview'] = ''
                        request.data['message_body'] = message_body
                        request.data['message_to'] = message_to
                        request.data['message_importance'] = '1'
                        request.data['message_is_read'] = False
                        request.data['message_is_draft'] = False
                        request.data['message_flag'] = False
                        request.data['has_attachments'] = True
                        request.data['loa_mail']=True


                        try:
                            #request.data.update(qdict)
                            print('\n\n Inside TRY \n')
                            result=self.create(request)
                            print("after create")
                            if not result.data['status']:
                                print("problem in status")
                                error_list.append(client_instr_obj.instrument.instrument_name)
                            else:
                                if sent_reminder:
                                    client_instr_obj.reminder_count = client_instr_obj.reminder_count+1
                                    provider_status = StatusCollection.objects.get(status='1.57')  # loa mail response pending status
                                    Reminder.objects.filter(client_instrument=client_instr_obj,status=provider_status).update(mail_count=client_instr_obj.reminder_count)
                                    client_instr_obj.instrument_status = StatusCollection.objects.get(status='1.58')
                                    client_instr_obj.loa_mail_sent = True
                                    client_instr_obj.save()
                                else:
                                    client_instr_obj.instrument_status = StatusCollection.objects.get(status='1.24')
                                    client_instr_obj.loa_mail_sent=True
                                    client_instr_obj.save()

                                    try:
                                        # pending action update
                                        #statas = StatusCollection.objects.get(status='1.25')  # loa mail sending pending status
                                        # To update pending actions
                                        pending_with = client_instr_obj.instrument.provider.name
                                        mail_count =  client_instr_obj.reminder_count
                                        pending_status = StatusCollection.objects.get(status='1.57')  # loa mail response pending status
                                       
                                        remove_reminder = Reminder.objects.filter(client_instrument=client_instr_obj).first()
                                        if remove_reminder:
                                            remove_reminder.is_deleted = True
                                            remove_reminder.save()
                                        pending_status_save(client_instrument=client_instr_obj, pending_status=pending_status,mail_needed=True,pending_with=pending_with,mail_count=mail_count)
                                    except Exception as e:
                                        print(str(e))

                        except Exception as e:
                            print(str(e))
                            error_list.append(client_instr_obj.instrument.instrument_name)
                    except Exception as e:
                        print(str(e))
                        error_list.append(client_instr_obj.instrument.instrument_name)
        if error_list:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = error_msg
            response_data['data'] = error_list
            resp_status = status.HTTP_400_BAD_REQUEST
        else:
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'Mail sent successfully'
            resp_status=status.HTTP_201_CREATED

        return Response(response_data, status=resp_status )

    @action(methods=['get'], detail=False, name='Template-mail')
    def templatemail(self, request, *args, **kwargs):
        response_data = {}
        user = self.request.user
        type = self.request.query_params.get('type', None)
        will_referral_flag=br_19_flag=HR_Insurance_Check_flag=False
        client_id = self.request.query_params.get('client_id', None)
        user_list = Staff.objects.filter(user=user,user__groups__name__in=['Ops', 'Compliance','Administrator']).first()

        if user_list:
            client_obj=Client.objects.filter(id=client_id).first()
            user = client_obj.created_by
        if type is not None:
            try:
                trigger_mail_obj = AutotriggerMail.objects.filter(client=client_id).first()
                if not trigger_mail_obj:
                    trigger_mail_obj = AutotriggerMail.objects.create(client_id=client_id, advisor=user)
                if type=='will_referral':
                    if trigger_mail_obj.will_referral_mail_sent:
                        response_res = set_response_data(response_data)
                    else:
                        will_referral_flag=True
                if type=='BR19':
                    if trigger_mail_obj.br19_mail_sent:
                        response_res = set_response_data(response_data)
                    else:
                        br_19_flag=True
                if type=='HR_Insurance_Check':
                    if trigger_mail_obj.insurance_check_mail_sent:
                        response_res = set_response_data(response_data)
                    else:
                       HR_Insurance_Check_flag =True
                # if trigger_mail_obj.will_referral_mail_sent or trigger_mail_obj.insurance_check_mail_sent or trigger_mail_obj.br19_mail_sent:
                    # response_data['status_code'] = '200'
                    # response_data['status'] = True
                    # response_data['message'] = 'Mail Already sent'
                   
                if ((type =='will_referral'and will_referral_flag==True ) or (type =='BR19'and br_19_flag==True ) or (type =='HR_Insurance_Check'and HR_Insurance_Check_flag==True)):
  
                   
                    response=templatemailsend(type,user,client_id)
                    if response:
                        response_data['status_code'] = '200'
                        response_data['status'] = True
                        response_data['message'] = 'Mail sent succesfully'
                        if type=='will_referral':
                            trigger_mail_obj.will_referral_mail_sent=True
                        elif type=='BR19':
                            trigger_mail_obj.br19_mail_sent=True
                        else:
                            trigger_mail_obj.insurance_check_mail_sent=True
                        trigger_mail_obj.save()
                        if  type=='will_referral':
                            reminder_status=StatusCollection.objects.filter(status='1.70').first()
                        if type=='BR19':
                            reminder_status=StatusCollection.objects.filter(status='1.75').first()
                        if type=='HR_Insurance_Check':
                            reminder_status=StatusCollection.objects.filter(status='1.76').first()

                        remove_reminder = Reminder.objects.filter(status=reminder_status,client__id=client_id).first()
                        if remove_reminder:
                            remove_reminder.is_deleted = True
                            remove_reminder.save()
                    else:
                        response_data['status_code'] = '400'
                        response_data['status'] = False
                        response_data['message'] = 'Failed to send mail'

            except Exception as e:
                print(e)
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'Failed to send mail'


        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class EventViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)
    
    serializer_class = EventSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):        
        start_date = self.request.query_params.get('start', None)
        end_date = self.request.query_params.get('end', None)

        queryset = Event.objects.all()
        queryset = queryset.filter(user_id=self.request.user.id)
        
        if start_date:
            start_date = dt.datetime.strptime(start_date, '%d-%m-%Y')
           
        else:
            start_date = dt.datetime.today() + relativedelta(day=1, hour=0, minute=0, second=1)   

        """
            if relative data arguments are plural (days, months, hours, minutes etc.) that is realtive to current date and time. The values specifed will be added/subtracted to current date and time
                25-08-2020 + relativedelta(days=2) = 27-08-2020
                25-08-2020 + relativedelta(days=2, months=3) = 27-11-2020

            if arguments are singular (day, month, second, hour etc.) that is absolute. ie, the value will be set to the exact day,month,hour,minute and second in the argument.
                25-08-2020 + relativedelta(day=2) = 02-08-2020
                25-08-2020 + relativedelta(day=2, month=3) = 02-03-2020
        """
        
        if end_date:
            end_date = dt.datetime.strptime(end_date, '%d-%m-%Y') + relativedelta(days=+1)
        else:
            end_date = start_date + relativedelta(day=1, months=+1, hour=0, minute=0, second=1)

        queryset1 = queryset.filter(event_start__lte=start_date, event_end__gte=end_date)
        queryset2 = queryset.filter(event_start__gte=start_date, event_end__lte=end_date)
        queryset3 = queryset.filter(event_start__lte=end_date, event_end__gte=end_date,)
        queryset4 = queryset.filter(event_start__lte=start_date, event_end__gte=start_date)
        final_list = queryset1 | queryset2 | queryset3 | queryset4

        print(queryset1, ' \n')
        print(queryset2, ' \n')
        print(queryset3, ' \n')
        print(queryset4, ' \n')
    
        return final_list.order_by('event_start')
       


    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Event List',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)


    def create(self, request, *args, **kwargs):
        response_data = {}
       
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # for scheduling events from task page
        client=None
        advisor=None
        task=None
        if 'client_id' in request.data.keys() and 'advisor_id' in request.data.keys() and 'task_id' in request.data.keys():
            
            if request.data['client_id']:
                client = Client.objects.filter(id=request.data['client_id']).first()
                if not client:
                    raise serializers.ValidationError({"client": ["Invalid Client specified"]})
            if request.data['advisor_id']:
                advisor = User.objects.filter(id=request.data['advisor_id'], is_staff=True).first()
                if not advisor:
                    raise serializers.ValidationError({"advisor": ["Invalid Advisor specified"]})
            if request.data['task_id']:
                task = ClientTask.objects.filter(id=request.data['task_id']).first()
                if not task:
                    raise serializers.ValidationError({"advisor": ["Invalid Task specified"]})




        response = super().create(request)

        attendees_list = request.data.getlist('attendees')
        

        for attendee in attendees_list:
            attendee_serializer = AttendeesSerializer(data={'event':response.data['id'], 'attendee':attendee})
            if attendee_serializer.is_valid():
                attendees = attendee_serializer.save()
                # response.data['attendees'].append({'attendee':attendees.attendee, 'status':attendees.response_status})

                if attendees.response_status not in response.data['attendees'].keys():
                    response.data['attendees'][attendees.response_status] = []  
                response.data['attendees'][attendees.response_status].append(attendees.attendee)

        if 'attachments' in request.data.keys():
            attachment_list = request.FILES.getlist('attachments')
            for file in attachment_list:
                file_serializer = AttachmentSerializer(data={'event':response.data['id'], 'attachments':file})
                if file_serializer.is_valid():
                    file_list = file_serializer.save()
                    file_list.save()
                    # response.data['attachment_list'].append({'fileId':file_list.id, 'name':file_list.attachments.path.split('/')[-1], 'item_url':os.path.join(settings.BASE_URL,'media',file_list.attachments.name),\
                    response.data['attachment_list'].append({'fileId':file_list.id, 'name':file_list.attachments.name.split('/')[-1],\
                                    'item_path':os.path.join(MEDIA_URL,file_list.attachments.name), 'item_size':file_list.attachments.size})


        if 'cap_drive_attachments' in request.data.keys():
            
            attachment_list = request.data.getlist('cap_drive_attachments')
            for doc_id in attachment_list:
                file=Document.objects.get(id=doc_id).doc
                file_serializer = AttachmentSerializer(data={'event':response.data['id'], 'attachments':file})
                if file_serializer.is_valid():
                    file_list = file_serializer.save()
                    file_list.save()
                   
                    response.data['attachment_list'].append({'fileId':file_list.id, 'name':file_list.attachments.name.split('/')[-1],\
                                                           'item_path':os.path.join(MEDIA_URL,file_list.attachments.name), 'item_size':file_list.attachments.size})

        created_event = Event.objects.get(id=response.data['id'])
        if 'is_draft_meeting' in request.data.keys():
            if request.data['client_id']:
                client = Client.objects.filter(id=request.data['client_id']).first()
            if request.data['advisor_id']:
                advisor = User.objects.filter(id=request.data['advisor_id'], is_staff=True).first()
            if client and advisor and request.data['is_draft_meeting']:
               
                try:
                    status_obj  = StatusCollection.objects.get(status='2.14')
                    print("status ",status_obj)
                    
                    user=User.objects.filter(email=created_event.organizer).first()
                   
                  
                except Exception as e:
                    print("error in adding to activity flow",e)   

       
        # Adding the task mapping to scheduled events with client and advisor
        elif client and advisor and task:
            
            TaskEvents.objects.create(client=client, advisor=advisor, event=created_event, scheduled_by=self.request.user, task=task)
            task_collection = TaskCollection.objects.filter(task_slug='meeting_scheduled').first()
            staff=Staff.objects.filter(user=request.user).first()
            if not task.administrator:
                # task.update(current_sub_task = task_collection)
                task.current_sub_task = task_collection
                task.save()
            add_task_activity(client_task=task, task_collection=task_collection, created_by=staff, task_status='3', meeting_info=created_event)
        
        else:
            try:
                if 'client_id' in request.data.keys() and 'advisor_id' in request.data.keys():
                    if request.data['client_id']:
                        client = Client.objects.filter(id=request.data['client_id']).first()
                    if request.data['advisor_id']:
                        advisor = User.objects.filter(id=request.data['advisor_id'], is_staff=True).first()
                    status_obj  = StatusCollection.objects.get(status='1.5')
                    
                    user=User.objects.filter(email=created_event.organizer).first()
                    add_activity_flow(action_performed_by=request.user, client=client, status=status_obj,comment='subject:' + created_event.subject)
                   

                
            except Exception as e:
                print("error in adding to activity flow",e)



        if response.status_code == 201:
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'Event added successfully'
            response_data['data'] = response.data

            user=User.objects.get(id=response.data["user"])
            event=Event.objects.get(id=response.data["id"])
            log = OutlookLog.objects.create(user=user, event=event, request_info=response.data, log_type=1, status=1, request_type=1)

            while True:
               
               
                if log.status != 3:
                    continue
                else:
                    data = json.loads(log.response_info)
                    print("dataa", data)

                    if 'error' in data:
                        response_data['status_code'] = '400'
                        response_data['status'] = False
                        response_data['message'] = data['error']['message']
                        event.is_deleted = True
                        event.save()
                        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        if client:
                            status_obj  = StatusCollection.objects.get(status='1.5')
                            add_activity_flow(action_performed_by=request.user, client=client, status=status_obj,comment=created_event.subject)
                       
                    break
        return Response(response_data, status=status.HTTP_201_CREATED)


    def update(self, request,pk,*args, **kwargs):
        response_data = {}
        try:
           
            instance = Event.objects.get(id=pk)
        except Exception as e:
            print(e)
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            
            response = self.perform_update(serializer)
        except Exception as e:
            print(e)


        response_data['data'] = serializer.data
        response_data['data']['attachment_list'] = []
        
        attachment_list = request.FILES.getlist('attachments')
        cap_attachment_list = request.data.getlist('cap_drive_attachments')
        file_id_list = request.data.getlist('file_id_list')

        new_attendees_list = request.data.getlist('attendees')
        event_attendees = Attendees.objects.filter(event=instance.id).values_list('attendee', flat=True)
        event_attendees = set(attendee.strip() for attendee in event_attendees)
        total_attendees = set(new_attendees_list) | event_attendees
       
        for attendee in total_attendees:
            if attendee not in new_attendees_list:
                # Remove existing attendee from Model
                remove_attendee = Attendees.objects.filter(event=instance.id, attendee=attendee)
                remove_attendee.update(is_deleted=True)
            elif attendee not in event_attendees:
                # add new attendee to Model
                Attendees.objects.create(event=instance, attendee=attendee)
        response_data['data']['attendees'] = Attendees.objects.filter(event=instance.id).values('attendee', 'response_status')

        user = User.objects.get(id=instance.user_id)
        event = Event.objects.get(id=instance.id)
        ''' TO DO MOVE DELETE ATTACHMENT TO TASK'''
        remove_attachements = Attachments.objects.filter(event=instance.id).exclude(id__in=file_id_list)
        try:
            for rm in remove_attachements:
                if rm.object_id:
                    _data = json.dumps({'id': rm.id, 'attachment_id': rm.object_id})
                    OutlookLog.objects.create(user=user, event=event, request_info=_data, log_type=3, status=1,
                                                    request_type=3)
        except Exception as e:
            print("Error in removing attachment", e)
        for file in attachment_list:
            file_serializer = AttachmentSerializer(data={'event':instance.id, 'attachments':file})
            if file_serializer.is_valid():
                file_list = file_serializer.save()
                file_list.save()
               
                response_data['data']['attachment_list'].append({'fileId':file_list.id, 'name':file_list.attachments.name.split('/')[-1],\
                                                                 'item_path':os.path.join(MEDIA_URL,file_list.attachments.name), 'item_size':file_list.attachments.size})


        for doc_id in cap_attachment_list:
            file = Document.objects.get(id=doc_id).doc
            file_serializer = AttachmentSerializer(data={'event': instance.id, 'attachments': file})
            if file_serializer.is_valid():
                file_list = file_serializer.save()
                file_list.save()
               
                response_data['data']['attachment_list'].append({'fileId':file_list.id, 'name':file_list.attachments.name.split('/')[-1],\
                                                                 'item_path':os.path.join(MEDIA_URL,file_list.attachments.name), 'item_size':file_list.attachments.size})
        for file_id in file_id_list:
            attachment=Attachments.objects.get(id=file_id)
            
            response_data['data']['attachment_list'].append({'fileId': file_id, 'name': attachment.attachments.name.split('/')[-1],\
                                                             'item_path': os.path.join(MEDIA_URL,attachment.attachments.name), 'item_size': attachment.attachments.size})

        response_data['status_code'] = '200'
        response_data['status'] = True
        response_data['message'] = 'Event Edited Successfully'
        log = OutlookLog.objects.create(user=user, event=event, request_info=request.data, log_type=1, status=1, request_type=2)
        if log:
            while True:
                
                if log.status != 3:
                    continue
                else:
                    data = json.loads(log.response_info)
                    if 'error' in data:
                        response_data['status_code'] = '400'
                        response_data['status'] = False
                        response_data['message'] = data['error']['message']
                        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                    break

            # adding Task Timeline entry for Event Rescheduling
            event = Event.objects.get(id=instance.id)
            mapped_task = TaskEvents.objects.filter(event=event).first()
            task_collection = TaskCollection.objects.filter(task_slug='meeting_rescheduled').first()
            staff = Staff.objects.filter(user=request.user).first()
            if mapped_task and mapped_task.task and not mapped_task.task.administrator:
                task = mapped_task.task
               
                task.current_sub_task = task_collection
                task.save()
                add_task_activity(client_task=mapped_task.task, task_collection=task_collection, created_by=staff, task_status='3', meeting_info=event)


        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = "Something went wrong !!!"
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        return Response(response_data, status=status.HTTP_200_OK)


    def retrieve(self, request, pk):

        queryset = Event.objects.all()
        event = get_object_or_404(queryset, pk=pk)
        serializer = EventSerializer(event)
        response_data = {
                "status_code": "200",
                "status": True,
                "message": 'Event Details',
                "data": serializer.data
            }
        return Response(response_data, status=status.HTTP_200_OK)



    def destroy(self, request, pk=None):
        response_data = {}
        event_to_delete = Event.objects.filter(id=pk, user=request.user).first()
        if event_to_delete:
           
            event_to_delete.is_cancelled = True
            event_to_delete.save()
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'Event Deleted Successfully'
            OutlookLog.objects.create(user=request.user, event=event_to_delete, request_info=request.data, log_type=1, status=1, request_type=3)

            #adding a entry into Task Timeline if the cancelled event was created from Tasks page

            task_mapping = TaskEvents.objects.filter(event=event_to_delete).first()
            if task_mapping:
                task_collection = TaskCollection.objects.filter(task_slug='meeting_cancelled').first()
                staff_user=Staff.objects.filter(user=request.user).first()
                if not task_mapping.task.administrator:
                    task = task_mapping.task
                   
                    task.current_sub_task = task_collection
                    task.save()
                add_task_activity(client_task=task_mapping.task, task_collection=task_collection, created_by=staff_user, task_status='3', meeting_info=event_to_delete)
    
        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Event not found'

        if response_data['status_code']  == '200':
            resp_status = status.HTTP_200_OK  
        elif response_data['status_code']  == '400':
            resp_status = status.HTTP_400_BAD_REQUEST

        return Response(response_data, status=resp_status)



class MarkMailAsRead(APIView):
    permission_classes = (IsAuthenticated, )

    def post(self, request):
        response_data = {}
        conversation_id = request.data["conversation_id"]

        mail_list = Email.objects.filter(conversation_id=conversation_id, user=request.user)
        if mail_list:
            mails = mail_list.filter(message_is_read=False)
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'Conversation marked read successfully'
            for mail_to_mark_read in mails:
                OutlookLog.objects.create(user=request.user, email=mail_to_mark_read, request_info=request.data, log_type=2, status=1, request_type=5)
            mails.update(message_is_read=True)

        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Invalid conversation id'

        if response_data['status_code']  == '200':
            resp_status = status.HTTP_200_OK  
        elif response_data['status_code']  == '400':
            resp_status = status.HTTP_400_BAD_REQUEST

        # returinng un-read count
        folders = MailFolder.objects.filter(user=request.user)
        unread_count_list = []
        for folder in folders:
            unread_count = Email.objects.filter(folder=folder, user=request.user, message_is_read=False, meeting_message_type=None).count()
            folder_dict = {'id':folder.id, 'folder_id':folder.folder_id, 'folder_name':folder.folder_name, 'unread_count':unread_count}
            unread_count_list.append(folder_dict)
        response_data['data'] = unread_count_list
        return Response(response_data, status=resp_status)



class GetMailRecipients(APIView):
    permission_classes = (IsAuthenticated, )

    def get(self, request):
        response_data = {}
        staff_user_list=[]
        client_user_list=[]
        mail_keyword = self.request.query_params.get('key', None)
        
        staff=Staff.objects.filter(user=request.user).first()
        if staff:
            try:
                company=staff.company
                staff_user_list=Staff.objects.filter(company=company).values_list('user', flat=True)
                client_user_list=Client.objects.filter(created_by__in=staff_user_list).values_list('user', flat=True)
            except:
                staff_user_list = []
                client_user_list = []

        queryset = User.objects.filter(Q(email__startswith=mail_keyword,is_staff=True,id__in=staff_user_list)| Q(id__in=client_user_list,is_staff=False,email__startswith=mail_keyword))
        print(queryset)
        email_list = [email.email for email in queryset]
        response_data['status_code'] = '200'
        response_data['status'] = True
        response_data['message'] = 'Emails fetched successfully'
        response_data['data'] = email_list
        return Response(response_data, status=status.HTTP_200_OK)



class MoveToFolder(APIView):
    permission_classes = (IsAuthenticated, )

    def post(self, request):
        response_data = {}
       
        conv_list = request.data.get('conversation_list', '')
        email_id = request.data.get('mail_id', '')

        target_folder_id = request.data['target_folder_id']
        source_folder_id = request.data['source_folder_id']
        
        if not conv_list and not email_id:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'No selections made'

        if target_folder_id and source_folder_id:
            try:
                source_folder = MailFolder.objects.get(id=source_folder_id)
                target_folder = MailFolder.objects.get(id=target_folder_id)

                print('source : ',source_folder.folder_name,  'target : ', target_folder.folder_name)
                    
                if (target_folder.folder_name == 'Sent Items' and source_folder.folder_name in [ 'Inbox', 'Drafts']) or \
                    (source_folder == target_folder) or \
                    (target_folder.folder_name == 'Sent Items' and source_folder.folder_name == 'Inbox') or \
                    (target_folder.folder_name == 'Inbox' and source_folder.folder_name in [ 'Sent Items', 'Drafts']):
                    response_data['status_code'] = '400'
                    response_data['status'] = False
                    response_data['message'] = 'Forbidden operation'    
                else:
                    if conv_list:
                        conv_objs = Email.objects.filter(conversation_id__in=conv_list)
                        if conv_objs:
                            if target_folder.folder_name == 'Deleted Items':
                                conv_objs.update(folder=target_folder, message_is_deleted=True, message_deleted_from=source_folder,message_is_draft=False)
                            elif source_folder.folder_name == 'Deleted Items':
                                conv_objs.update(folder=target_folder,message_deleted_from=None, message_is_deleted=False)
                            else:
                                conv_objs.update(folder=target_folder)
                            response_data['status_code'] = '200'
                            response_data['status'] = True
                            response_data['message'] = 'Mails moved successfully'
                            for conv_mail in conv_objs:
                                OutlookLog.objects.create(user=request.user, email=conv_mail, request_info=request.data, log_type=2, status=1, request_type=2)
                            
                    elif email_id:
                        print("in mail id case")
                        mail_obj = Email.objects.filter(id=email_id).first()
                        if mail_obj:
                            mail_obj.folder = target_folder
                            if target_folder.folder_name == 'Deleted Items':
                                 mail_obj.message_is_deleted=True
                                 mail_obj.message_deleted_from=source_folder
                                 Email.objects.filter(conversation_id=mail_obj.conversation_id, message_body=mail_obj.message_body).update(message_deleted_from=source_folder.id,message_is_deleted=True)
                            if source_folder.folder_name == 'Deleted Items':
                                 mail_obj.message_is_deleted=False
                                 mail_obj.message_deleted_from = None
                                 Email.objects.filter(conversation_id=mail_obj.conversation_id, message_body=mail_obj.message_body).update(message_deleted_from=None,message_is_deleted=False)

                            mail_obj.save()
                            print(mail_obj.folder.id, ' ppppppppppppppp  ', target_folder_id, '   lllllllllll    ',mail_obj.id)
                            response_data['status_code'] = '200'
                            response_data['status'] = True
                            response_data['message'] = 'Mails moved successfully'
                            OutlookLog.objects.create(user=request.user, email=mail_obj, request_info=request.data, log_type=2, status=1, request_type=3)

            except MailFolder.DoesNotExist:
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'Folder does not exist'
            except Email.DoesNotExist:
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'Email does not exist'

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK

        return Response(response_data, status=resp_status)



class MarkRSVP(APIView):
    permission_classes = (IsAuthenticated, )

    def post(self, request):
        response_data = {}
        event_id = request.data['event']
        response_status = request.data['response_marked']
        
        response_dict = { 'accepted':'2',  'declined': '3', 'tentative':'4', 'not_responded':'5' }
        event = Event.objects.filter(id=event_id).first()
        if event:
            if event.organizer == request.user.email:
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = {"response_marked" : "Can't mark RSVP. You are the organizer."}
            else:
                if response_status not in response_dict.keys():
                    response_data['status_code'] = '400'
                    response_data['status'] = False
                    response_data['message'] = {"response_marked" : "Invalid Response "}
                else:
                    event.response_status = response_dict[response_status]
                    event.save()
                    response_data['status_code'] = '200'
                    response_data['status'] = True
                    response_data['message'] = 'RSVP Marked Successfully'
                    OutlookLog.objects.create(user=request.user, event=event, request_info=request.data, log_type=1, status=1, request_type=4)

        resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)



class OutlookCredViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)
    
    serializer_class = OutlookCredentialsSerializer

    def get_queryset(self):        
        queryset = OutlookCredentials.objects.all()
        queryset = queryset.filter(user_id=self.request.user.id)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Outlook Credentials',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)


    def create(self, request, *args, **kwargs):
        response_data = {}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = super().create(request)

        if response.status_code == 201:
            if request.data['outlook_email']:
                user = request.user
                user.email=request.data['outlook_email']
                user.save()
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'Credentials added successfully'
            response_data['data'] = response.data
        return Response(response_data, status=status.HTTP_201_CREATED)

    def update(self, request, pk, *args, **kwargs):
        instance = OutlookCredentials.objects.get(id=pk)
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            response = self.perform_update(serializer)
        except:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Error in updating Outlook credentials'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'Updated Outlook credentials successfully'
        
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK

        return Response(response_data, status=resp_status)


    def retrieve(self, request, *args, **kwargs):
        data = super().retrieve(request, *args, **kwargs).data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Outlook Credentials',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)





class OauthSignIn(APIView):
   
    
    def get(self, request):
        # Get the sign-in URL
        # sign_in_url, state = get_sign_in_url()
        token = self.request.query_params.get('token', None)
        try:
            user = Token.objects.get(key=token).user
        except Exception as e:
            print("exception",e)
            response_data = {
                "status_code": "400",
                "status": False,
                "message": "Invalid User credentials passed"
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        else:
           
            sign_in_url, state = get_sign_in_url(user)
            if not sign_in_url:
                response_data = {
                    "status_code": "400",
                    "status": False,
                    "message": state
                }
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # Save the expected state so we can validate in the callback
            request.session['auth_state'] = state
            request.session['outh_user'] = user.id

            # request.set_cookie('last_connection', datetime.datetime.now())
            # Redirect to the Azure sign-in page
            return HttpResponseRedirect(sign_in_url)


class OauthCallback(APIView):

    def get(self, request):
        # Get the state saved in session
        expected_state = request.session.pop('auth_state', '')   
        logged_user = request.session.pop('outh_user', '')

        log_user = User.objects.get(id=logged_user)

        # # Make the token request
        token = get_token_from_code(request.get_full_path(), expected_state, log_user)
        user = User.objects.get(username=log_user)
        cred = OutlookCredentials.objects.get(user=user)
        dt_object = dt.datetime.fromtimestamp(token['expires_at'])
        print(token, ' -------------------- \n')
        print(token['expires_at'], ' =============')
        print(dt_object, ' ------------------------------- ')
        cred.token_expiry = int(token['expires_at'])
        token = str(token).replace("\'", "\"")

        
        if IS_S3:
            path = get_token_upload_path(cred,'oauth_token.txt')
            df = server_storage()
            full_path = os.path.join(df.base_location, path)
            pathlib.Path(os.path.split(full_path)[0]).mkdir(parents=True, exist_ok=True)
            token_path = df.save(full_path, ContentFile(token.encode()))
            cred.token_path.save(token_path.split('/')[-1], ContentFile(token.encode()))
            cred.save()
        else:
            cred.token_path.save('oauth_token.txt', ContentFile(token.encode()))
            cred.save()
        
        return HttpResponseRedirect(settings.CALLBACK_OUTLOOK_URL)


class SyncOutlook(APIView):
    permission_classes = (IsAuthenticated, )

    def get(self, request):
        response_data = {}
        log_entry=None
        sync_keyword = self.request.query_params.get('sync', None)
        if not sync_keyword:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Please provide the sync keyword'
        
        if sync_keyword == 'events':
            
            log_entry = OutlookSync.objects.create(user=self.request.user, sync_category='1', status='1') 
        elif sync_keyword == 'mails':
            log_entry = OutlookSync.objects.create(user=self.request.user, sync_category='2', status='1') 
        elif sync_keyword == 'mail_folder':
            log_entry = OutlookSync.objects.create(user=self.request.user, sync_category='3', status='1')
        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Please provide a valid sync keyword'

        if log_entry:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'Sync initiated'
        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Sync request failed'

        if response_data['status_code'] == '200':
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)


class GetNextMeeting(APIView):
    permission_classes = (IsAuthenticated, )

    def get(self, request):
        response_data = {}
        client_id = self.request.query_params.get('client', None)
        if not client_id or client_id is None or client_id=='':
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Please provide the Client ID'

        user = self.request.user
        try:
            client = Client.objects.get(id=client_id)
            
        except User.DoesNotExist:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Please provide a valid client id'
        else:
            today = dt.datetime.utcnow()
            user_events1 = Event.objects.filter(user=user, event_start__gt=today, organizer=user.email, is_cancelled=False).order_by('-id').values_list('id')

            attendees_event_list = Attendees.objects.filter(attendee=client.user.email, event_id__in=user_events1).exclude(response_status__in=['1','3']).order_by('event__event_start').values_list('event_id')      # client as event organizer
            common_events = Attendees.objects.filter(event__user=user, attendee=client.user.email, event__event_start__gt=today).exclude(response_status__in=['3']).order_by('event__event_start').values_list('event_id')   # 3rd person event organizer with client and advisor as participants 
            
            events_as_attendee = Attendees.objects.filter(attendee=user.email, event__event_start__gt=today).exclude(response_status__in=['3']).order_by('event__event_start').values_list('event_id')
            event_as_client_attendee = Attendees.objects.filter(attendee=client.user.email, event__event_start__gt=today).exclude(response_status__in=['3']).order_by('event__event_start').values_list('event_id')
            intersection = events_as_attendee.intersection(event_as_client_attendee)

            event_id_list = attendees_event_list.union(common_events,intersection)
            next_event = Event.objects.filter(Q(user=user, event_start__gt=today, organizer=client.user.email, is_cancelled=False) | Q(id__in=event_id_list)).order_by('event_start').first()        
            response_data['status_code'] = '200'
            response_data['status'] = True

            if next_event:
                response_data['data'] = {'event_id':next_event.id, 'event_date':next_event.event_start, 'title':next_event.subject, 'event_end': next_event.event_end, 'event_is_all_day': next_event.is_all_day }
            else:
                response_data['data'] = {}

        if response_data['status_code'] == '200':
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)



class ParseLOAMails(APIView):
    permission_classes = (IsAuthenticated, )

    def get(self, request):
        response_data = {}
        
        client_instruments = ClientInstrumentInfo.objects.filter(loa_mail_sent=True, pdf_data=None, created_by=request.user)
        for instrument in client_instruments:            
            check_subject = 'Re: '+ instrument.instrument.mail_template.subject+' - CLT_' + str(instrument.id) + '_' + str(instrument.signed_loa.id)
            folder_to_filter = MailFolder.objects.filter(user=request.user, folder_name = 'Inbox').first()
            response_mail = Email.objects.filter(message_subject=check_subject, user=instrument.client.created_by, folder=folder_to_filter).order_by('-message_recieved').first()
            
            instrument_emails=[]
            for instr in Instrument.objects.all():
                if instr.mail_id:
                    for mail_id in instr.mail_id:
                        instrument_emails.append(mail_id)
            if response_mail:
                print(response_mail, response_mail.message_sender, instrument_emails)
                if response_mail.message_sender in instrument_emails:
                    print("enter ParseLOAMails")

                   
                    instrument.instrument_status = StatusCollection.objects.filter(status='1.26').first()
                    instrument.save()
                    #reminder removal
                    try:
                        reminder_status = StatusCollection.objects.get(status='1.57')  # loa mail response pending status
                        # To update pending actions
                        pending_status = StatusCollection.objects.get(status='1.28')  # LoA Response Upload Pending
                       
                        remove_reminder = Reminder.objects.filter(client_instrument=instrument,status=reminder_status).first()
                        if remove_reminder:
                            remove_reminder.is_deleted = True
                            remove_reminder.save()

                        pending_status_save(client_instrument=instrument, pending_status=pending_status)
                    except Exception as e:
                        print(e)
                    #ends
                    attached_response = Attachments.objects.filter(email_id=response_mail).first()
                    if attached_response:
                        current_doc_version = 0
                        if instrument.pdf_data:
                            current_doc_version = instrument.pdf_data.version
                        created_doc = Document.objects.create(uploaded_by=request.user, owner=instrument.client, doc_type='5', doc=attached_response.attachments, version=current_doc_version+1)
                        if created_doc:
                            instrument.pdf_data= created_doc
                            instrument.instrument_status = StatusCollection.objects.filter(status='1.27').first()
                            #reminder update
                            try:

                                reminder_status = StatusCollection.objects.get(status='1.28')  # LoA Response Upload Pending
                                # To update pending actions
                                pending_status = StatusCollection.objects.get(status='1.32')  # Data extraction pending
                               
                                remove_reminder = Reminder.objects.filter(client_instrument=instrument,status=reminder_status).first()
                                if remove_reminder:
                                    remove_reminder.is_deleted = True
                                    remove_reminder.save()
                                pending_status_save(client_instrument=instrument, pending_status=pending_status)
                            except Exception as e:
                                print(e)
                            #reminder updation ends

                            instrument.save()

        response_data = {"message":"Document Parsed Successfully", "status_code":"200", "status":True}
        return Response(response_data, status=status.HTTP_200_OK)



