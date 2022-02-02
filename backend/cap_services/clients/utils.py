from io import BytesIO
from django.http import HttpResponse
from django.template import Context, Template
from .models import ActivityFlow, Provider, CAP_settings, Reminder, Client, ClientRecommendationNotification, ClientInstrumentInfo, \
        InstrumentsRecomended, ClientTaskTimeline, ClientTask, ClientCheckList, ClientCheckListArchive, DraftReccomendation, Document,\
        IllustrationData,DraftCheckList,Staff
from datetime import timedelta
from cap_outlook_service.outlook_services.models import Email, MailFolder
from django.contrib.auth.models import User
import os
import subprocess
import io
from django.core.files import File
from xhtml2pdf import pisa
import datetime
from .checklist import update_or_create_checklist,delete_checklist
# from .common.libreoffice import run as update_doc
# from .common.libreoffice import run_S3 as update_S3doc
from cap_services.settings import IS_S3, MEDIA_ROOT
from outlook_app.utils import templatemailsend
import pikepdf
from pikepdf import Pdf
import pathlib
from django.core.files.storage import FileSystemStorage as server_storage
from django.core.files.storage import default_storage

def render_to_pdf(template_src, context_dict={}):#To convert html template into pdf
    template = Template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None

def add_activity_flow(**kwargs):
    ActivityFlow.objects.create(action_performed_by=kwargs.get('action_performed_by',None), client=kwargs.get('client',None), status=kwargs.get('status',None),\
                                client_instrument=kwargs.get('client_instrument',None),comment=kwargs.get('comment',None), client_task=kwargs.get('client_task',None), task_status=kwargs.get('task_status',None))

def add_task_activity(**kwargs):
    created_by = kwargs.get('created_by',None)
    if created_by is None:
        req_user = kwargs.get('req_user',None)
        if req_user is not None:
            created_by = Staff.objects.filter(user=req_user).first()
    obj = ClientTaskTimeline.objects.create( client_task=kwargs.get('client_task',None), task_collection=kwargs.get('task_collection',None), \
        created_by=created_by, assigned_to=kwargs.get('assigned_to',None), task_status=kwargs.get('task_status',None), meeting_info=kwargs.get('meeting_info',None),\
        comments=kwargs.get('comments',None))

    task = kwargs.get('client_task',None)
    created_by = kwargs.get('created_by',None)
    comments=kwargs.get('comments',None)
    if created_by is None:
        req_user = kwargs.get('req_user',None)
        add_activity_flow(action_performed_by=req_user, client=task.client, client_task=task, task_status=obj,comment=comments)
    else:  
        add_activity_flow(action_performed_by=created_by.user, client=task.client, client_task=task, task_status=obj,comment=comments)


def pending_status_save(**kwargs):
    print("im inside pending status save")
    pending_status=kwargs.get('pending_status',None)
    clientinstrument=kwargs.get('client_instrument',None)
    client_id=kwargs.get('client_id',None)
    mail_needed = kwargs.get('mail_needed', None)
    pending_with = kwargs.get('pending_with', None)
    mail_count = kwargs.get('mail_count', None)
 

    if mail_needed is None:
       mail_needed=False
       
    if pending_with is None:
       pending_with='Me'
       
    if mail_count is None:
       mail_count= 0
    capsettings=CAP_settings.objects.filter(label_name=pending_status.get_status_name_display()).first()
    print("im here in pending status")
    if clientinstrument:
        client=clientinstrument.client
       
        created_by=client.created_by
        comment=clientinstrument.instrument.instrument_name
    elif client_id:
        client=Client.objects.filter(id=client_id).first()
        created_by = client.created_by
        comment  = None

    due_date=client.create_time+timedelta(int(capsettings.due_date_duration))
    print("due_date ",due_date)
    print("im here in pending status")
    reminder_date=client.create_time+timedelta(int(capsettings.reminder_date_duration))
    reminder_date=reminder_date.date()
    today= datetime.date.today()
    if reminder_date < today :
        reminder_date = today

    ''''check if any reminder exists if not,then create a new reminder'''
    
    reminder_obj_check = Reminder.objects.filter(owned_by=created_by,client=client,status=pending_status,client_instrument=clientinstrument)
    if not reminder_obj_check:
        Reminder.objects.create(owned_by=created_by, client=client, status=pending_status, client_instrument=clientinstrument, due_date=due_date, reminder_date=reminder_date, \
            comment=comment, mail_needed=mail_needed, pending_with=pending_with, mail_count=mail_count)
        
        #check basic profile created then not add otherwise add 
        activity_count = ActivityFlow.objects.filter(client=client).count()
        if activity_count>1:
            survey_category_status=['1.14','1.12','1.16','1.60','1.61']
            if pending_status.status in survey_category_status:
                client = client_profile_completion(client=client,phase='pre-contract',percentage=10,sign='negative')
    return client


def get_mail_with_subject(subject, user):
    sent_items = MailFolder.objects.filter(user=user, folder_name='Sent Items').first()
    if sent_items:
        mail = Email.objects.filter(message_subject=subject, folder=sent_items, user=user).exclude(object_id='').order_by('-message_recieved').last()
        print(mail, ' mail mail mail')
        if mail:
            return mail
    return None

def recommendation_notification_save(**kwargs):
    print(" ******************* inside recommndation notification  save *****************")
    client=kwargs.get('client',None)
    advisor=kwargs.get('advisor',None)
    recommendation_status=kwargs.get('recommendation_status',None)
    is_deleted = kwargs.get('is_deleted',None)
    is_answer = kwargs.get('is_answer', None)
    try:
        client_obj =Client.objects.filter(id=client).first()
        advisor_obj = User.objects.filter(id=advisor).first()
        if is_deleted:
            recommendation_obj=ClientRecommendationNotification.objects.filter(advisor=advisor_obj,client=client_obj,recommendation_status=recommendation_status).update(is_deleted=True)
           
        else:
            print(advisor_obj)
            print(client_obj)
            print(recommendation_status)
            recommendation_obj_check = ClientRecommendationNotification.objects.filter(advisor=advisor_obj,client=client_obj,recommendation_status=recommendation_status)
            if recommendation_obj_check:
                print("already there")
            if not recommendation_obj_check:
                if is_answer is not None:
                    recommendation_obj = ClientRecommendationNotification.objects.create(advisor=advisor_obj,client=client_obj,recommendation_status=recommendation_status,is_answer=is_answer)
                    print("created",recommendation_obj)
                else:
                    recommendation_obj=ClientRecommendationNotification.objects.create(advisor=advisor_obj,client=client_obj,recommendation_status=recommendation_status)
  
    except Exception as e:
        print(str(e))  




def calculate_fee(**kwargs):
    total_amount = kwargs.get('amount',None)
    reccomended_instr = kwargs.get('inst_rec',None)

    total_initial_fee_percent = 0
    total_ongoing_fee_percent = 0
    total_dfm_fee_percent = 0

    for ins in reccomended_instr:
        if ins.amount:
            
            instrument_amt_ratio = ins.amount / total_amount 
            if ins.initial_fee:
                total_initial_fee_percent = total_initial_fee_percent + (ins.initial_fee * instrument_amt_ratio)
            if ins.dfm_fee:
                total_dfm_fee_percent = total_dfm_fee_percent + (ins.dfm_fee * instrument_amt_ratio)
            if ins.ongoing_fee:
                total_ongoing_fee_percent = total_ongoing_fee_percent + (ins.ongoing_fee * instrument_amt_ratio)
    return total_initial_fee_percent, total_dfm_fee_percent, total_ongoing_fee_percent




def reset_checklist_and_reccommendations(**kwargs):
    task = kwargs.get('task',None)
    checklist_list = ClientCheckList.objects.filter(client=task.client)
    for checklist in checklist_list:
        archive = ClientCheckListArchive()
        for field in checklist._meta.fields:
            if field.primary_key == True:
                continue  # don't want to clone the PK
            setattr(archive, field.name, getattr(checklist, field.name))
        archive.task = task
        archive.save()
    print('data copy done')

    #removing all checklists related to the client except the survey for related checklists. 
    except_survery_checklist = ClientCheckList.objects.filter(client=task.client).exclude(draft_checklist__category_name__in=['1','3','4'])
    except_survery_checklist.update(is_deleted=True)

    #resetting reccommended instruments and draft reccomendations and product list
    DraftReccomendation.objects.filter(client=task.client, is_active=True).update(is_active=False)
    InstrumentsRecomended.objects.filter(client_instrumentinfo__client=task.client, is_active=True).update(is_active=False, task=task)
    ClientInstrumentInfo.objects.filter(client=task.client, is_active=True).update(is_active=False)

    #updating is_active flag on documents
    # documents = Document.objects.filter(owner=task.client, is_active=True, doc_type__in=['3','5','7','14','15','16','17']).update(is_active=False)
    Document.objects.filter(owner=task.client, is_active=True).update(is_active=False, task=task)
    
    client = Client.objects.filter(id=task.client.id).first()
    print("current pre contract percentage ",client.pre_contract_percent)
    if client.pre_contract_percent >= 40:
        client.pre_contract_percent-= 40
    client.atp_percent=0
    client.post_contract_percent=0
    client.pre_contract_date=None
    client.confirm_client_date =None
    client.post_contract_date = None
    client.client_stage='0'
    client.save()


def encrypt_and_send_mail(**kwargs):

    client = kwargs.get('client',None)
    uploaded_by = kwargs.get('advisor', None)
    pdf_password = kwargs.get('pdf_password', None)
    task = kwargs.get('task', None)
    sr_doc = Document.objects.filter(owner=client, doc_type='8').order_by('-id').first()
    result = None
    administrator_obj = task.administrator.user
    try:
        if IS_S3:
            df = server_storage()
            full_path = os.path.join(df.base_location, sr_doc.doc.name)
            pathlib.Path(os.path.split(full_path)[0]).mkdir(parents=True, exist_ok=True)
            df.save(full_path, sr_doc.doc.open())
            
            subprocess.call(['libreoffice', '--headless', '--convert-to', 'pdf:writer_pdf_Export', '--outdir',
                             os.path.split(full_path)[0], full_path,
                             '-env:UserInstallation=file:///tmp/LibreOffice_Conversion_${USER}'])
            filepath, ext = os.path.splitext(full_path)
            fileurlpdf = os.path.realpath(filepath + ".pdf")
        else:
            update_doc(sr_doc.doc.path, True, True)
            filepath, ext = os.path.splitext(sr_doc.doc.path)
            fileurlpdf = os.path.realpath(filepath + ".pdf")

        no_extracting = pikepdf.Permissions(extract=False)
        pdf = Pdf.open(fileurlpdf, allow_overwriting_input=True)
        pdf.save(fileurlpdf, encryption=pikepdf.Encryption(user=pdf_password, owner="cap321", allow=no_extracting))
        _report_doc = File(open(fileurlpdf, mode='rb'), name='PDF')
        report_obj = Document.objects.create(owner=client, uploaded_by=uploaded_by.user, doc_type='18')
        doc_name, ext = os.path.splitext(sr_doc.doc.name)
        report_obj.doc.name = doc_name + ".pdf"
        path = default_storage.save(report_obj.doc.name, _report_doc)
        report_obj.save()
    except Exception as e:
        print("Final Report PDF Error", e)
        
    else:

        templatemailsend("final_report_mail",administrator_obj, client.id, report_doc=report_obj, task=task)
 
    return True


def client_profile_completion(**kwargs):
    client = kwargs.get('client',None)
    phase = kwargs.get('phase',None)
    percentage = kwargs.get('percentage',None)
    sign = kwargs.get('sign',None)
    model_object = kwargs.get('obj',None)
    obj_check = None
    advisor = kwargs.get('advisor',None)
    instr_count =  kwargs.get('instr_count',None)
    client_instr_count = kwargs.get('client_instr_count',None)
    instr_many_rec = "false"
    is_client_instr = "false"

    if model_object is not None:
        if model_object =='client-instrument-info':
            print("percentage calculation in client-instrument-info  ")
            obj_check = ClientInstrumentInfo.objects.filter(client=client,is_deleted=False,is_active=True).count()
            print("obj count ",obj_check)
            if obj_check==1:
                print("first entry.... ")
            elif obj_check==0:
                print("last entry....")
            else:
                print("not last")
                if client_instr_count==obj_check:
                    print("multiple client instrument creation ")
                    is_client_instr="true"
        
        if model_object=='instrument-recomended':
            print("percentage calculation ... instrument-recomended ")
            obj_check= InstrumentsRecomended.objects.filter(advisor=advisor,client_instrumentinfo__client=client,is_deleted=False,is_active=True).count()
            print("obj_check ",obj_check)
            if obj_check==1:
                print("first entry.... ")
            elif obj_check==0:
                print("last entry....")
            else:
                print("not last")
                if instr_count==obj_check:
                    print("multiple instrument creation ")
                    instr_many_rec="true"
    try:
        if client is not None :

            if phase=='pre-contract':
                if sign=='positive' and (obj_check==1 or obj_check==None or instr_many_rec=="true" or is_client_instr=="true"):
                    current_percentage = client.pre_contract_percent
                    print("inside positive condition........")
                    if current_percentage<100 and current_percentage+percentage<=100:
                        client.pre_contract_percent +=percentage
                        print("=====================profile percentage addition in pre_contract=====================",percentage)

                if sign=='negative' and (obj_check==0 or obj_check==None):
                    client.pre_contract_percent -=percentage 
                    print("===============profile percentage decremented in pre_contract=======================",percentage)
                client.save()
            if phase=='atp':
                if sign=='positive':
                    client.atp_percent +=percentage
                    client.save()
                    print("=====================profile percentage addition in atp_percent=====================",percentage)
                if sign=='negative':
                    client.atp_percent -=percentage
                    client.save()        
                    print("===============profile percentage decremented in atp phase=======================",percentage)
            if phase=='post-contract':
                if sign=='positive':
                    client.post_contract_percent +=percentage
                    client.save()
                    print("=====================profile percentage addition in post_contract=====================",percentage)
                if sign=='negative':
                    client.post_contract_percent -=percentage
                    client.save()   
                    print("===============profile percentage decremented in post_contract=======================",percentage)

    except Exception as e:
        print("Exception while calculating profile completion",e)
    return client


def illustration_appsummary_checklists(client_instrument,doc_type):
    instrument_recommended = InstrumentsRecomended.objects.filter(client_instrumentinfo=client_instrument, is_active=True).first()
    transferfrom_instruments = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client_instrument.client, is_active=True).exclude(map_transfer_from=None).values_list('map_transfer_from', flat=True).distinct()
    if instrument_recommended.id not in list(transferfrom_instruments):
        if doc_type == '13':
            checklists = DraftCheckList.objects.filter(category_name=14)
        elif doc_type == '16':
            checklists = DraftCheckList.objects.filter(category_name=9)
        user = Staff.objects.filter(user=client_instrument.client.created_by).first()
        for draftchecklist in checklists:
            all_products = True if not (list(draftchecklist.product_type.all())) else False
            checklist_product_types = list(draftchecklist.product_type.all())
            producttype_exist = True if client_instrument.instrument.product_type in checklist_product_types else False
            if producttype_exist or all_products:
                update_or_create_checklist(client_instrument.client, draftchecklist.id,user,client_instrument=client_instrument,result='amber', instrument_recommended=instrument_recommended)
            else:
                delete_checklist(client_instrument.client, draftchecklist,client_instrument=client_instrument)




def remove_ilustration_checklist(instr_recc_obj,**kwargs):
    client_instrument = instr_recc_obj.client_instrumentinfo
    checklists = ClientCheckList.objects.filter(client=client_instrument.client, client_instrument=client_instrument)
    for checklist in checklists:
        delete_checklist(client_instrument.client, checklist.draft_checklist, client_instrument=client_instrument)
    ###To handle remove illustrations if same illustration doc for multiple products##########
    ''''
    if client_instrument.illustration is None:
        #print("illustration is none")
        #remove illustration checklists
        for checklist in checklists:
            delete_checklist(client_instrument.client, checklist.draft_checklist, client_instrument=client_instrument)

    else:
        #transferfrom_instruments = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client_instrument.client, is_active=True).exclude(map_transfer_from=None).values_list('map_transfer_from', flat=True).distinct()
        same_provider_recc_ins = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client_instrument.client, is_active=True, \
                                    client_instrumentinfo__provider=client_instrument.provider, client_instrumentinfo__instrument__product_type=client_instrument.instrument.product_type).exclude(id=instr_recc_obj.id)
        print(same_provider_recc_ins)
        check_later_illustration_present = same_provider_recc_ins.filter(client_instrumentinfo__illustration__create_time__gt=client_instrument.illustration.create_time)
        if check_later_illustration_present or not same_provider_recc_ins:

            for checklist in checklists:
                print(client_instrument)
                delete_checklist(client_instrument.client, checklist.draft_checklist, client_instrument=client_instrument)
        else:
            print("2")
            #remove illustration checklists
            all_same_instr_checklists = ClientCheckList.objects.filter(client=client_instrument.client,draft_checklist__category_name='9' ,client_instrument__id__in=same_provider_recc_ins.values_list('client_instrumentinfo'))
            for checklist in checklists:
                
                delete_checklist(client_instrument.client, checklist.draft_checklist,client_instrument=checklist.client_instrument)

            latest_illus_doc_ins = None
            for illus_ins in same_provider_recc_ins:
                if illus_ins.client_instrumentinfo.illustration:
                    if latest_illus_doc_ins is None:
                        latest_illus_doc_ins = illus_ins

                    elif illus_ins.client_instrumentinfo.illustration.create_time > latest_illus_doc_ins.client_instrumentinfo.illustration.create_time:
                        latest_illus_doc_ins = illus_ins

            #create checklist based on illustration doc in this illus_ins
            if latest_illus_doc_ins:

                Illustration_checklist_run(latest_illus_doc_ins.client_instrumentinfo)
            else:
                if not check_later_illustration_present and same_provider_recc_ins:
                    for checklist in all_same_instr_checklists:
                        delete_checklist(client_instrument.client, checklist.draft_checklist,client_instrument=checklist.client_instrument)'''


def format_content_for_sr(content):
    formatted_content = content.replace('<li><span style="font-family: sans-serif; font-size: 10px; color: #00b050;">', '<li><span style=" font-family: sans-serif; font-size: 10px; color: rgb(0,176,80);">')
    formatted_content = formatted_content.replace('<span style="text-align: justify; font-family: sans-serif; font-size: 10px; color: #00b050;">', '<span style=" text-align: justify; font-family: sans-serif; font-size: 10px; color: rgb(0,176,80);">')
    return formatted_content
