from clients.models import Templates, Client, Document, User, Staff, DraftReccomendation, InstrumentsRecomended,TemplateAttachments
from django.template import Context, Template
from cap_outlook_service.outlook_services.models import Email, OutlookLog, MailFolder
from .serializers import AttachmentSerializer
from cap_services.settings import BASE_URL, EMAIL_SENDER
from cap_services.settings import MEDIA_PATH as MEDIA_URL
import os
import datetime as dt
from dateutil.relativedelta import *
from django.utils import timezone as tz
import time
from random import random


def templatemailsend(type, user, client_id, **kwargs):
    request_info = {}
    message_to = []
    administrator = ""
    ops_lead = None
    client_full_name = ""
    compliance_first_name = ""
    opslead_full_name=None
    advisor_full_name=None
    mortgage_broker_first_name = " "
    administrator_full_name=None,
    compliance_full_name =None
    mortgage_details = {}
    property_value = None
    amount_mortgage = None
    result = True
    month_year = None
    phone_number =None
    phone_number2=None
    designation=None
    company_website = None
    checklist_content = kwargs.get('checklist_content', None)
    reccommended_instrument_details = []
    reccommended_instrument_funtion_list = []
 
    try:
        client = Client.objects.filter(id=client_id).first()
        staff = Staff.objects.filter(user=user).first()
        advisor_name = user.first_name.title()
        advisor_full_name = user.first_name.title() + " " + user.last_name.title()
        if staff:
            phone_number = staff.phone_number
            phone_number2 = staff.phone_number2
            designation = staff.designation
            company_website = staff.company.url

        if client:
            if client.user.email:
                message_to.append(client.user.email)
        if type == 'will_referral':
            templateobj = Templates.objects.filter(template_name='Will Referral').first()
            request_info['has_attachments'] = False
        if type == 'BR19':
            templateobj = Templates.objects.filter(template_name='BR19 Form').first()
            request_info['has_attachments'] = True
            request_info['attachment_list'] = []
            try:
               
                templates_data=Document.objects.filter(doc='cap/brochures/BR19.pdf').first()
                attachment_file = templates_data.doc
                

            except Exception as e:
                attachment_file = " "
                print("br19 mail - file not found ",e)
        if type == 'HR_Insurance_Check':
            templateobj = Templates.objects.filter(template_name='HR -Insurance Check').first()
            request_info['has_attachments'] = False

        if type == 'mortgage_broker_mail':
            message_to = []
            request_info['has_attachments'] = False
            if staff is not None:
                if staff.company.mortgage_broker_mail:
                    message_to.append(staff.company.mortgage_broker_mail)
                mortgage_broker_first_name = staff.company.mortgage_broker_first_name.title()
            templateobj = Templates.objects.filter(template_name='Mortgage broker mail').first()

            mortgage_details = kwargs.get('mortgage_details_dict', None)
            property_value = mortgage_details.get('property_value', None)
            if property_value:
                property_value = '£' + " " + str(property_value)
            else:
                property_value = 'NA'
            amount_mortgage = mortgage_details.get('amount_mortgage_outstanding', None)
            if amount_mortgage:
                amount_mortgage = '£' + " " + str(amount_mortgage)
            else:
                amount_mortgage = 'NA'

        if type == 'task_creation-notification_mail':
            message_to = []

           
            recc_ins = DraftReccomendation.objects.filter(advisor=staff, client=client).first()
            recc_ins_list = recc_ins.instrument_recommended.all()
            for rec in recc_ins_list:
                prod_type = rec.client_instrumentinfo.instrument.product_type.fund_type
                amount_val = rec.amount
                for func in rec.function_list.all():
                    reccommended_instrument_details.append(
                        {'product_type': prod_type, 'amount': amount_val, 'function': func.get_function_type_display()})

            print("inside task creation 1")
            templateobj = Templates.objects.filter(template_name='Task creation- notification mail').first()
            request_info['has_attachments'] = False

            staff_obj = Staff.objects.filter(user=user).first()
            if staff_obj:
                print("inside task creation 2")
                ops_result = Staff.objects.filter(user__groups__name='Ops', company=staff_obj.company_id).first()
                print(ops_result)
                if ops_result.user.email:
                    message_to.append(ops_result.user.email)
                print("inside task creation 3")


        if type == 'task_assignment-notification_mail':
            message_to = []

            recc_ins = DraftReccomendation.objects.filter(client=client).first()
            recc_ins_list = recc_ins.instrument_recommended.all()
            for rec in recc_ins_list:
                for func in rec.function_list.all():
                    if func.get_function_type_display() not in reccommended_instrument_funtion_list:
                        reccommended_instrument_funtion_list.append(func.get_function_type_display())

            templateobj = Templates.objects.filter(template_name='Task assignment-notification mail').first()
            request_info['has_attachments'] = False

            assigned_to = kwargs.get('assigned_to', None)
            task = kwargs.get('task', None)
            administrator = task.administrator.user.first_name.title() + ' ' + task.administrator.user.last_name.title()
            ops_lead = task.ops.user.first_name.title()
            opslead_full_name = task.ops.user.first_name.title() + ' ' + task.ops.user.last_name.title()
            staff_obj = Staff.objects.filter(user=user).first()
            group_list = ['Administrator', 'Advisor']
            advisor_list = Staff.objects.filter(user__groups__name__in=group_list, company=staff_obj.company_id)
            if task.advisor.user.email:
                message_to.append(task.advisor.user.email)
            if task.administrator.user.email:
                message_to.append(task.administrator.user.email)
            
            advisor_name = task.advisor.user.first_name.title() 
            advisor_full_name = task.advisor.user.first_name.title() + ' ' + task.advisor.user.last_name.title()
            phone_number = task.ops.phone_number
            phone_number2 = task.ops.phone_number2
            designation = task.ops.designation
            company_website = task.ops.company.url
            print("mail sent tooooo",message_to)


        if type == 'compliance_task_assignment':
            message_to = []

            templateobj = Templates.objects.filter(template_name='Compliance task assignment').first()
            request_info['has_attachments'] = False
            assigned_to = kwargs.get('assigned_to', None)
            task = kwargs.get('task', None)
            if task.compliance.user.email:
                message_to.append(task.compliance.user.email)
            if task.advisor.user.email:
                message_to.append(task.advisor.user.email)
           
            
            administrator = task.administrator.user.first_name.title() 
            administrator_full_name = task.administrator.user.first_name.title() + ' ' + task.administrator.user.last_name.title()
            advisor_name = task.advisor.user.first_name.title() 
            advisor_full_name = task.advisor.user.first_name.title() + ' ' + task.advisor.user.last_name.title()
            phone_number = task.administrator.phone_number
            phone_number2 = task.administrator.phone_number2
            designation = task.administrator.designation
            company_website = task.administrator.company.url


            recc_ins = DraftReccomendation.objects.filter(client=client).first()
            recc_ins_list = recc_ins.instrument_recommended.all()
            for rec in recc_ins_list:
                for func in rec.function_list.all():
                    if func.get_function_type_display() not in reccommended_instrument_funtion_list:
                        reccommended_instrument_funtion_list.append(func.get_function_type_display())

        if type == 'compliance_task_approval':
            message_to = []
            templateobj = Templates.objects.filter(template_name='Compliance task approval').first()
            request_info['has_attachments'] = False
            assigned_to = kwargs.get('assigned_to', None)
            task = kwargs.get('task', None)
            administrator = task.administrator.user.first_name.title() + ' ' + task.administrator.user.last_name.title()
            if task.advisor.user.email:
                message_to.append(task.advisor.user.email)
            if task.administrator.user.email:
                message_to.append(task.administrator.user.email)
            advisor_full_name = task.advisor.user.first_name.title() + ' ' + task.advisor.user.last_name.title()
            compliance_first_name = task.compliance.user.first_name.title() 
            
            compliance_full_name = task.compliance.user.first_name.title() + ' ' + task.compliance.user.last_name.title()
            phone_number = task.compliance.phone_number
            phone_number2 = task.compliance.phone_number2
            designation = task.compliance.designation
            company_website = task.compliance.company.url

            recc_ins = DraftReccomendation.objects.filter(client=client).first()
            recc_ins_list = recc_ins.instrument_recommended.all()
            for rec in recc_ins_list:
                for func in rec.function_list.all():
                    if func.get_function_type_display() not in reccommended_instrument_funtion_list:
                        reccommended_instrument_funtion_list.append(func.get_function_type_display())
            
            
        if type == 'weekly_checklist_report':
            message_to = []
            request_info['has_attachments'] = False
            templateobj = Templates.objects.filter(template_name='Weekly Checklist Summary Report').first()
            compliance = Staff.objects.filter(user__groups__name='Compliance', company=staff.company_id).first()  # getting the compliance id
            compliance_first_name = compliance.user.first_name.title()
            
            compliance_full_name = compliance.user.first_name.title() + ' ' + compliance.user.last_name.title()
            phone_number = compliance.phone_number
            phone_number2 = compliance.phone_number2
            designation = compliance.designation
            company_website = compliance.company.url
            if compliance.user.email:
                message_to.append(compliance.user.email)

        if type == 'monthly_checklist_report':
            message_to = []
            request_info['has_attachments'] = False
            templateobj = Templates.objects.filter(template_name='Monthly Checklist Summary Report').first()
            compliance = staff  # getting the compliance id from the staff
            compliance_first_name = compliance.user.first_name.title()
            last_month = dt.datetime.now() - relativedelta(months=1)
            month_year = last_month.strftime("%B-%Y")
            if compliance.user.email:
                message_to.append(compliance.user.email)
        

        if type=='final_report_mail':
            message_to = []
            task = kwargs.get('task', None)
            administrator = task.administrator.user.first_name 
            advisor_name = task.advisor.user.first_name.title() + ' ' + task.advisor.user.last_name.title()
            templateobj = Templates.objects.filter(template_name='Final Report').first()

            administrator_full_name = task.administrator.user.first_name.title() + ' ' + task.administrator.user.last_name.title()
            phone_number = task.administrator.phone_number
            phone_number2 = task.administrator.phone_number2
            designation = task.administrator.designation
            company_website = task.administrator.company.url

            request_info['has_attachments'] = True
            request_info['attachment_list'] = []
            report_doc = kwargs.get('report_doc', None)
            try:
                attachment_file = report_doc.doc
            except Exception as e:

                attachment_file = " "
                print("file not found",e)
            if client.user.email:
                message_to.append(client.user.email)
           
        template_instance = Template(templateobj.template_header + templateobj.content + templateobj.template_footer)
        try:

            if staff:
                company_url = staff.company.url
                company_logo = None
                if staff.company.logo:
                    company_logo = staff.company.logo.url

          
            else:
             
                company_doc_obj = Document.objects.filter(doc='advisors/company/Lathe-logo.png').first()
                company_logo = None
                if company_logo:
                    company_logo = company_doc_obj.doc.url
        except Exception as e:
            print(e)
            company_logo = " "

        client_first_name = client.user.first_name.title()
        client_full_name = client.user.first_name.title() + " " + client.user.last_name.title()
        context = Context({"company_logo": company_logo, 'advisor_name': advisor_name,
                           'static_image_path': os.path.join(MEDIA_URL, 'advisors/company'),
                           "client_first_name": client_first_name, "client_full_name": client_full_name, \
                           'property_value': property_value, 'mortgage_amount': amount_mortgage,
                           'opslead_name': ops_lead, \
                           'tie_in_period': mortgage_details.get('tie_in_period', None),
                           'mortgage_broker_name': mortgage_broker_first_name, 'company_url': company_url, \
                           "administrator_name": administrator,
                           "reccommended_instrument_details": reccommended_instrument_details,
                           "reccommended_instrument_funtion_list": reccommended_instrument_funtion_list, \
                           "checklist_content": checklist_content, "compliance_first_name": compliance_first_name,
                           "month_year": month_year,"phone_number":phone_number,"phone_number2":phone_number2,"designation":designation, \
                           "company_website":company_website,"advisor_full_name":advisor_full_name,"administrator_full_name":administrator_full_name,\
                           "opslead_full_name":opslead_full_name,"compliance_full_name":compliance_full_name})

        template_instance = template_instance.render(context)
        print("inside task creation 5")
       

        request_info['user'] = user
        request_info['message_sender'] = user.email
        request_info['message_subject'] = templateobj.subject
        request_info['message_body'] = template_instance
        request_info['message_body_type'] = 'html'
        request_info['message_to'] = message_to

        print("debug 2")

        try:
            rand = str(random()).split('.')[-1]
            stamp = str(time.time()).replace(".", "")

            folder_id = MailFolder.objects.filter(folder_name='Sent Items', user=user).first()
            message_created = tz.now()
            message_modified = tz.now()
            message_recieved = tz.now()
            message_sent = tz.now()
            email = Email.objects.create(user=user, message_sender=request_info['message_sender'], folder=folder_id,
                                         message_subject=request_info['message_subject'],
                                         conversation_id=str(user.id) + str(stamp) + str(rand),
                                         message_body=request_info['message_body'],
                                         message_to=request_info['message_to'],
                                         has_attachments=request_info['has_attachments'],
                                         message_created=message_created, message_modified=message_modified, \
                                         message_sent=message_sent, message_recieved=message_recieved)
            print("EMAIL CREATED", email)
            #print(email.message_to)

        except Exception as e:

            print(str(e))

        
        if request_info['has_attachments']:
            file_serializer = AttachmentSerializer(data={'email': email.id, 'attachments': attachment_file})

            if file_serializer.is_valid():
              

                file_list = file_serializer.save()

                request_info['attachment_list'].append(
                    {'fileId': file_list.id, 'name': file_list.attachments.name.split('/')[-1],
                     'item_url': os.path.join(MEDIA_URL, file_list.attachments.name), \
                     'item_path': os.path.join(MEDIA_URL, file_list.attachments.name),
                     'item_size': file_list.attachments.size})

        OutlookLog.objects.create(user=user, email=email, request_info=request_info, log_type=2,
                                        status=1)
    except Exception as e:
        print("Inside exception", str(e))
        result = False

    return result
