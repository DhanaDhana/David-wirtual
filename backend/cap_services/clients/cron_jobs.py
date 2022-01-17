from .models import Reminder, Staff, ClientCheckList, Templates, Client, ClientTask,DraftCheckList
from django.contrib.auth.models import User, Group
from datetime import datetime,timedelta
from django.template import Context, Template
from cap_services.settings import CAP_SUPERUSER_EMAIL
from outlook_app.utils import templatemailsend
from dateutil.relativedelta import relativedelta
from drf_api_logger.models import APILogsModel
from auditlog.models import LogEntry

def UpdateNotificationCount():
    today = datetime.today().date()
    print('\n\n NOTIFICATION UPDATE CRON INITIATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')


    advisors = Staff.objects.filter(user__groups__name='Advisor')
    for advisor in advisors:
        print('Updating Notifications for : ',advisor.user)
        pending_tasks = Reminder.objects.filter(owned_by=advisor.user, reminder_date=today,is_viewed=False)
        updated_count = advisor.notification_count + pending_tasks.count()
        advisor.notification_count = updated_count
        advisor.save()



'''reset advisor's fca permission after one year'''
def ResetAdvisorDeclaration():
    print('\n\n ADVISOR DECLARATION RESET CRON INITIATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')
    
    advisors = Staff.objects.filter(user__groups__name='Advisor')
    for advisor in advisors:
        fca_renewal_date  = None
        if advisor.fca_renewal_date:
            fca_renewal_date = (advisor.fca_renewal_date).strftime("%m-%d-%Y")
        
        advisor_created_date = advisor.create_time
        new_date = advisor_created_date + relativedelta(years=1)
        new_date =new_date.strftime("%m-%d-%Y")
        advisor_created_date = advisor_created_date.strftime("%m-%d-%Y")
        current_date = (datetime.now()- timedelta(days=1)).strftime("%m-%d-%Y")

        if fca_renewal_date==current_date or  current_date==new_date:
            advisor.advisor_terms_and_agreement = False
            advisor.fca_renewal_date= (datetime.now()+ relativedelta(years=1)).strftime("%Y-%m-%d")
            print(advisor.user,"\t advisor created date ",advisor_created_date,"\t renewal date ",new_date,"\t current_date ",current_date,"\t fca_renewal_date ",advisor.fca_renewal_date)
            advisor.save()
            try:
                draftchecklist = DraftCheckList.objects.filter(id=7).first()
                if not advisor.advisor_terms_and_agreement:
                    ClientCheckList.objects.filter(draft_checklist=draftchecklist,client__is_confirmed_client=False,user=advisor).update(colour_code='Red')

            except Exception as e:
                print(str(e))

def SendWeeklyChecklistReport():
   
    amberlist_clients= ClientCheckList.objects.filter(colour_code='Amber').values_list('client', flat=True).distinct()
    for client in amberlist_clients:
        client_active_task = ClientTask.objects.filter(client__id=client).exclude(task_status='3').order_by('id').last()
        if client_active_task:
            clientinstance=Client.objects.filter(id=client).first()
            amber_checklists = ClientCheckList.objects.filter(client=client,colour_code='Amber').values_list('draft_checklist__checklist_names', flat=True)
            count=1
            checklist_content=""
            for checklist in amber_checklists:
                checklist_content =checklist_content+ "<p style=\"font-family: 'Roboto', sans-serif;color: rgb(34,34,34);font-size:14px; line-height: 24px;\"><span style=\"margin-right: 10px;0\">"+str(count)+".</span> "+checklist+"</p>"
                count=count+1
            if checklist_content:
                superuser_mail = CAP_SUPERUSER_EMAIL
                superuser = User.objects.filter(email=superuser_mail).first()
                templatemailsend("weekly_checklist_report",superuser,client,checklist_content=checklist_content)

def SendMonthlyChecklistReport():
   
    redlist_companies = ClientCheckList.objects.filter(colour_code='Red').values_list('user__company', flat=True).distinct()
    print(redlist_companies)
    for company in redlist_companies:
        count = 1
        checklist_content = ""
        compliance = Staff.objects.filter(user__groups__name='Compliance',company=company).first()  # getting the compliance id
        redlist_clients = ClientCheckList.objects.filter(colour_code='Red', user__company=company).values_list('client',flat=True).distinct()
        print(redlist_clients)
        for client in redlist_clients:
            client_active_task = ClientTask.objects.filter(client__id=client).exclude(task_status='3').order_by('id').last()
            if client_active_task:
                print(client)
                clientinstance=Client.objects.filter(id=client).first()
                print(clientinstance)
                client_name=clientinstance.user.first_name+" "+clientinstance.user.last_name
                advisor=clientinstance.created_by.first_name+" "+clientinstance.created_by.last_name
                checklist_content =checklist_content+ "<tr><td style=\"font-family: 'Roboto', sans-serif;color: rgb(34,34,34);font-size:14px; line-height: 24px;  padding:5px 10px;border-bottom: 1px solid #ccc;\">"+str(count)+"</td><td style=\"font-family: 'Roboto', sans-serif;color: rgb(34,34,34);font-size:14px; line-height: 24px;  padding:5px 10px;border-bottom: 1px solid #ccc;\">"+client_name+"</td><td style=\"font-family: 'Roboto', sans-serif;color: rgb(34,34,34);font-size:14px; line-height: 24px;  padding:5px 10px;border-bottom: 1px solid #ccc;\">"+advisor+"</td></tr>"
                count=count+1
        if checklist_content and compliance:
            print("COMPLIANCE USER IS",compliance.user)
            print("company",company)
            print("CLIENT",client)
            superuser_mail=CAP_SUPERUSER_EMAIL
            superuser=User.objects.filter(email=superuser_mail).first()
            templatemailsend("monthly_checklist_report",superuser,client,checklist_content=checklist_content)

def Resetlogs():
    try:
        current_date = (datetime.now()- timedelta(days=14)).replace(hour=0, minute=0)
        APILogsModel.objects.filter(added_on__lt=current_date).delete()
        LogEntry.objects.filter(timestamp__lt=current_date).delete()
        print("logs cleared  till ",current_date)
    except Exception as e:
        print("error in Resetlogs",e)