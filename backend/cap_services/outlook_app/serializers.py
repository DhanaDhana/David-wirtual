from cap_outlook_service.outlook_services.models import MailFolder, Email, OutlookLog, Attachments, Event, Attendees, OutlookCredentials
from clients.models import MailTemplateMapping, Templates,Document,Staff
from rest_framework import serializers
from django.contrib.auth.models import User
import datetime as dt
import time
import os
from django.conf import settings
from django.template import Context, Template
from cap_services.settings import BASE_URL
from cap_services.settings import MEDIA_PATH as MEDIA_URL
from django.db.models import Q
from random import random

class MailFolderSerializer(serializers.ModelSerializer):
    
    unread_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MailFolder
        fields = ('id', 'folder_name', 'folder_id', 'parent_id', 'user', 'unread_count')

    def get_unread_count(self, obj):
        unread_count = Email.objects.filter(folder = obj, message_is_read=False, meeting_message_type=None).count()
        return unread_count


class AttachmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Attachments
        fields = "__all__"


class AttendeesSerializer(serializers.ModelSerializer):

    class Meta:
        model = Attendees
        fields = "__all__"


class MailSerializer(serializers.ModelSerializer):
    
    attachments = AttachmentSerializer(required=False, many=True, read_only=True)
    attachment_list = serializers.SerializerMethodField(read_only=True)
    message_sender_details = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField(read_only=True)
    template = serializers.SerializerMethodField(read_only=True)
    template_header = serializers.SerializerMethodField(read_only=True)
    template_footer = serializers.SerializerMethodField(read_only=True)
    template_content = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Email
        fields = ('id', 'user', 'folder', 'object_id', 'message_recieved', 'message_modified', 'message_sent','message_created', 'message_subject', 'message_body_preview', 
            'message_body', 'message_sender', 'message_sender_details', 'message_to', 'message_cc', 'message_bcc', 'message_reply_to', 'message_importance', 
            'message_is_read', 'message_is_draft', 'conversation_id', 'message_flag', 'attachments', 'has_attachments', 'attachment_list', 'message_is_deleted','message_deleted_from',
            'unread_count', 'reply_id', 'mail_action', 'category', 'template','template_header', 'template_footer', 'template_content','meeting_message_type')
    
    def get_message_sender_details(self, obj):
        sender_mail = obj.message_sender
        
        try:
            user_details =  User.objects.get(email=obj.message_sender)
            sender_name  = user_details.first_name+' '+user_details.last_name
        except Exception as e:
            print("exception ",e)
            sender_name = sender_mail

        sender = {'sender_mail': sender_mail, 'sender_name': sender_name} 
        return sender

    def get_attachment_list(self, obj):
        attachments = Attachments.objects.filter(email_id=obj.id)
        try:
            if attachments:
              
                attachment_list = [{'fileId':attached_file.id, 'name':attached_file.attachments.name.split('/')[-1], 'item_url':attached_file.attachments.url,\
                'item_path':attached_file.attachments.url, 'item_size':attached_file.attachments.size} for attached_file in attachments]
                return attachment_list
        except Exception as e:
            print("Exception occured as ", e)

        return []

    def get_unread_count(self, obj):
        unread_count = Email.objects.filter(folder_id=obj.folder_id, conversation_id=obj.conversation_id, message_is_read=False).count()
        return unread_count

    def get_template(self, obj):
        mapping_obj = MailTemplateMapping.objects.filter(email_id=obj.id).first()
        if mapping_obj:
            if mapping_obj.template:
                return mapping_obj.template.id 
            else:
                return None
        else:
            return None

    def get_category(self, obj):
        mapping_obj = MailTemplateMapping.objects.filter(email_id=obj.id).first()
        if mapping_obj:
            if mapping_obj.category:
                return mapping_obj.category.id
            else:
                return None
        else:
            return None

    def get_template_header(self, obj):
        mapping_obj = MailTemplateMapping.objects.filter(email_id=obj.id).first()
        if mapping_obj:
            if mapping_obj.template:
                template_header=mapping_obj.template.template_header
                try:
                    template_header=Template(template_header)
                    try:
                        request = self.context.get("request")
                        staff = Staff.objects.filter(user=request.user).first()
                        if staff:
                            company_url = staff.company.url
                            company_logo = staff.company.logo.url
                       
                        else:
                            company_logo = Document.objects.get(doc='advisors/company/Lathe-logo.png').doc.url
                    except:
                        company_logo = " "
                        company_url = " "
                    context = Context({"company_logo": company_logo,"company_url":company_url})
                    template_header = template_header.render(context)
                except Exception as e:
                    print("Exception occured as ", e)
                return template_header
            else:
                return None
        else:
            return None

    def get_template_footer(self, obj):
        mapping_obj = MailTemplateMapping.objects.filter(email_id=obj.id).first()        
        if mapping_obj:
            if mapping_obj.template:
                template_footer= mapping_obj.template.template_footer

                try:
                    template_footer = Template(template_footer)
                    context = Context({"static_image_path":os.path.join(MEDIA_URL,'advisors/company')})
                    template_footer = template_footer.render(context)
                except Exception as e:
                    print("Exception occured as ", e)

                return template_footer
            else:
                return None
        else:
            return None

    def get_template_content(self, obj):
        mapping_obj = MailTemplateMapping.objects.filter(email_id=obj.id).first()        
        if mapping_obj:
            if mapping_obj.template:
                
                return mapping_obj.content
            else:
                return None
        else:
            return None


    def create(self, validated_data):
        if 'conversation_id' not in validated_data.keys() or validated_data['conversation_id'] is None or validated_data['conversation_id']=="":
            rand = str(random()).split('.')[-1]
            stamp = str(time.time()).replace(".","")
            validated_data['conversation_id'] = str(validated_data['user'].id)+str(stamp)+str(rand)
        
        if 'folder' not in validated_data.keys() or validated_data['folder'] is None:
            if 'message_is_draft' in validated_data and validated_data['message_is_draft'] is True:
                folder_id = MailFolder.objects.get(folder_name='Drafts', user_id=validated_data['user'])
            else:    
                folder_id = MailFolder.objects.get(folder_name='Sent Items', user_id=validated_data['user'])
        else:    
            folder_id = MailFolder.objects.get(folder_name='Sent Items', user_id=validated_data['user'])
        
        validated_data['folder'] = folder_id
        
        if 'object_id' in validated_data.keys() and validated_data['object_id'] is not None and validated_data['object_id'] != "":
            user_id = validated_data.pop('user')
            object_id = validated_data.pop('object_id')
            new_mail = Email.objects.get(object_id=object_id)
            new_mail.message_modified = dt.datetime.utcnow()
            new_mail.message_recieved = dt.datetime.utcnow()
            if 'message_to' in validated_data.keys():
                new_mail.message_to = validated_data['message_to']
            else:
                new_mail.message_to = []
            if 'message_cc' in validated_data.keys():
                new_mail.message_cc = validated_data['message_cc']
            else:
                new_mail.message_cc = []
            if 'message_bcc' in validated_data.keys():
                new_mail.message_bcc = validated_data['message_bcc']
            else:
                new_mail.message_bcc = []
            if 'message_subject' in validated_data.keys():
                new_mail.message_subject = validated_data['message_subject']
            else:
                new_mail.message_subject = ""
            if 'message_body' in validated_data.keys():
                new_mail.message_body = validated_data['message_body']
            else:
                new_mail.message_body = ""
            if 'message_sender' in validated_data.keys():
                new_mail.message_sender = validated_data['message_sender']
            else:
                new_mail.message_sender = []
            if 'message_reply_to' in validated_data.keys():
                new_mail.message_reply_to = validated_data['message_reply_to']
            else:
                new_mail.message_reply_to = []
            new_mail.folder = validated_data['folder']
            new_mail.message_is_read = validated_data['message_is_read']
            new_mail.message_is_draft = validated_data['message_is_draft']
            new_mail.message_flag = validated_data['message_flag']
            new_mail.has_attachments = validated_data['has_attachments']
            new_mail.message_is_deleted = validated_data['message_is_deleted']
            
            new_mail.save()
        else:
            validated_data['message_created'] = dt.datetime.utcnow()
            validated_data['message_modified'] = dt.datetime.utcnow()
            validated_data['message_recieved'] = dt.datetime.utcnow()
            validated_data['message_sent'] = dt.datetime.utcnow()   
            new_mail = Email.objects.create(**validated_data)

        return new_mail




class EventSerializer(serializers.ModelSerializer):
    
    attachments = AttachmentSerializer(required=False, many=True)
    attachment_list = serializers.SerializerMethodField(read_only=True)
    attendees = serializers.SerializerMethodField(read_only=True)
    
    colour_scheme = serializers.SerializerMethodField(read_only=True)
    event_start_date = serializers.SerializerMethodField(read_only=True)
    event_start_time = serializers.SerializerMethodField(read_only=True)
    event_end_time = serializers.SerializerMethodField(read_only=True)
    event_end_date = serializers.SerializerMethodField(read_only=True)
    is_event_by_me = serializers.SerializerMethodField(read_only=True)


    class Meta:
        model = Event
       
        fields = ('id', 'user', 'object_id', 'description', 'subject', 'event_start', 'event_end', 'importance', 
            'is_all_day', 'location', 'is_remainder_on', 'remind_before_minutes', 'response_requested', 'organizer', 'show_as', 'sensitivity', 
            'attendees', 'categories', 'event_type', 'ical_uid', 'response_status', 'response_time', 'is_recurring', 'recurrence_interval', 
            
            'recurrence_days_of_week', 'recurrence_end_date', 'attachments', 'attachment_list', 'colour_scheme', 'is_event_by_me', 'is_cancelled',
           
            'event_start_date', 'event_start_time', 'event_end_time', 'event_end_date' )



    def get_attachment_list(self, obj):
        attachments = Attachments.objects.filter(event_id=obj.id)        
        if attachments:
            
            try:
                attachment_list = [{'fileId':attached_file.id, 'name':attached_file.attachments.name.split('/')[-1],\
                                    'item_path':attached_file.attachments.url, 'item_size':attached_file.attachments.size} for attached_file in attachments]
            # 'item_path':os.path.join(MEDIA_URL,attached_file.attachments.name)
            except Exception as e:
                print('err : ', e)
                attachment_list = []
            return attachment_list
        return []

    def get_attendees(self, obj):
        attendees = Attendees.objects.filter(event_id=obj.id)

        response_dict = {}
        if attendees:
            for attendee in attendees:
                if attendee.response_status not in response_dict.keys():
                    response_dict[attendee.response_status] = []
                response_dict[attendee.response_status].append(attendee.attendee)

        return response_dict


    def get_colour_scheme(self, obj):
        event_count=0
        no_client_flag = True
        colour_scheme = {
                          'first': '#a0c4e2', #blue
                          'second': '#eba6a9', #pink
                          'next': '#9fcc2e', #green
                          'other': '#fffdf9' #white
                        }

        attendees = Attendees.objects.filter(event_id=obj.id)
        attendee_list = [att.attendee for att in attendees if att.response_status != '1']

        print(attendee_list, '\n')

        and_set = None

        for attendee in attendees:
            try:
                client = User.objects.get(email=attendee.attendee, is_staff=False)
            except Exception as e:
                print(e, '  ', attendee.attendee, 'for setting colour scheme for event')
            else:
                no_client_flag = False
                event_count += Attendees.objects.filter(attendee=client.email, event__event_start__lt=obj.event_start, event__organizer=obj.user.email).exclude(event__is_cancelled=True).count()
                # print(event_count, ' --------- scenario 1 ')

                event_count += Attendees.objects.filter(attendee=obj.user.email, event__event_start__lt=obj.event_start, event__organizer=client.email).exclude(event__is_cancelled=True).count()
                # print(event_count, ' --------- scenario 2 ')


                if attendee.attendee != obj.user.email and (obj.user.email in attendee_list or attendee.attendee in attendee_list) :
                    third_scen1 = Attendees.objects.filter(attendee=attendee.attendee, event__event_start__lt=obj.event_start).exclude(event__organizer=obj.user.email).values_list('event')
                    event_list1 = Event.objects.filter(id__in=third_scen1).exclude(is_cancelled=True)
                    third_scen2 = Attendees.objects.filter(attendee=obj.user.email, event__event_start__lt=obj.event_start).exclude(event__organizer=attendee.attendee).values_list('event')
                    event_list2 = Event.objects.filter(id__in=third_scen2).exclude(is_cancelled=True)

                    final_list = event_list1 & event_list2
                    event_count+=final_list.count()
                    # print(event_count, ' --------- scenario 3 ')


        if event_count==0:
            
            colour_code = settings.COLOR_SCHEME['first']
        elif event_count in [1,2]:
            
            colour_code = settings.COLOR_SCHEME['second']
        elif event_count>2:
           
            colour_code = settings.COLOR_SCHEME['fourth']

        if no_client_flag:
            return settings.COLOR_SCHEME['default']

        return colour_code


    def get_event_start_date(self, obj):
        return obj.event_start.date()

    def get_event_end_date(self, obj):
        return obj.event_end.date()

    def get_event_start_time(self, obj):
        return obj.event_start.time()

    def get_event_end_time(self, obj):
        return obj.event_end.time()
        
    def get_is_event_by_me(self,obj):
        if obj.organizer == obj.user.email:
            return True
        return False

        
# datetime.datetime(2020, 8, 26, 15, 46, 2, 513901, tzinfo=<UTC>)
    



class OutlookCredentialsSerializer(serializers.ModelSerializer):

    class Meta:
        model = OutlookCredentials
        fields = "__all__"

    def create(self, validated_data):
        outlook_cred = OutlookCredentials.objects.filter(user=validated_data['user']).first()
        if outlook_cred:
            outlook_cred.client_id=validated_data['client_id']
            outlook_cred.client_secret=validated_data['client_secret']
            outlook_cred.save()
        else:
            outlook_cred = OutlookCredentials.objects.create(user=validated_data['user'], client_id=validated_data['client_id'], client_secret=validated_data['client_secret'])

        return outlook_cred