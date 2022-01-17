from cap_outlook_service.outlook_services.models import OutlookSync, MailFolder, Email, Attachments, OutlookSyncErrorLog
from clients.models import ClientInstrumentInfo, Document, StatusCollection, Provider, Reminder, Staff,Instrument
from django.contrib.auth.models import User, Group
from clients.utils import pending_status_save
from datetime import datetime, timezone

def CalendarEventsUpdate():
    print('\n\n\n\n EVENT SYNC CRON INITIATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')
    advisors = User.objects.filter(is_staff=True, is_superuser=False)
    for advisor in advisors:
        print('\n')
        last_cron_status_check = OutlookSync.objects.filter(user=advisor, sync_category='1').last()
        if last_cron_status_check:
            if last_cron_status_check.status != '2':
                OutlookSync.objects.create(user=advisor, sync_category='1', status='1')
            else:
                #revert to state 1 if been status=2 for a long time
                duration_diff = datetime.now(timezone.utc) - last_cron_status_check.updated_time
                if duration_diff:
                    if divmod(duration_diff.total_seconds(), 3600)[0] > 2:  #Greater than 2 hour
                        updt = OutlookSync.objects.filter(id=last_cron_status_check.id).update(status='1')
                        continue

                error_msg ="Last Calendar cron job not yet finished for " + advisor.username + ". Skipping current cron execution"
                print("   ",error_msg)
                error_log = OutlookSyncErrorLog.objects.create(user=advisor, sync_category='1', cron_start_time=datetime.now(), error_category='1', error_message=error_msg)
        else:
            OutlookSync.objects.create(user=advisor, sync_category='1', status='1')
    print('\n EVENT SYNC CRON TERMINATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')

def MailsUpdate():
    print('\n\n\n\n MAIL SYNC CRON INITIATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')
    advisors = User.objects.filter(is_staff=True, is_superuser=False)
    for advisor in advisors:
        print('\n')
        last_cron_status_check = OutlookSync.objects.filter(user=advisor, sync_category='2').last()
        if last_cron_status_check:
            if last_cron_status_check.status != '2':
                OutlookSync.objects.create(user=advisor, sync_category='2', status='1')
            else:
                #revert to state 1 if been status=2 for a long time
                duration_diff = datetime.now(timezone.utc) - last_cron_status_check.updated_time
                if duration_diff:
                    if divmod(duration_diff.total_seconds(), 3600)[0] > 2:  #Greater than 2 hour
                        updt = OutlookSync.objects.filter(id=last_cron_status_check.id).update(status='1')
                        continue

                error_msg ="Last Mail cron job not yet finished for " + advisor.username + ". Skipping current cron execution"
                print("   ",error_msg)
                error_log = OutlookSyncErrorLog.objects.create(user=advisor, sync_category='2', cron_start_time=datetime.now(), error_category='1', error_message=error_msg)
        else:
            OutlookSync.objects.create(user=advisor, sync_category='2', status='1')
    print('\n MAIL SYNC CRON TERMINATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')

def MailFoldersUpdate():
    print('\n\n\n\n MAIL FOLDER SYNC CRON INITIATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')
    advisors = User.objects.filter(is_staff=True, is_superuser=False)
    for advisor in advisors:
        print('\n')
        last_cron_status_check = OutlookSync.objects.filter(user=advisor, sync_category='3').last()
        if last_cron_status_check:
            if last_cron_status_check.status != '2':
                OutlookSync.objects.create(user=advisor, sync_category='3', status='1')
            else:
                #revert to state 1 if been status=2 for a long time
                duration_diff = datetime.now(timezone.utc) - last_cron_status_check.updated_time
                if duration_diff:
                    if divmod(duration_diff.total_seconds(), 3600)[0] > 2:  #Greater than 2 hour
                        updt = OutlookSync.objects.filter(id=last_cron_status_check.id).update(status='1')
                        continue

                error_msg = "Last Mail Folder cron job not yet finished for " + advisor.username + ". Skipping current cron execution"
                print("   ", error_msg)
                error_log = OutlookSyncErrorLog.objects.create(user=advisor, sync_category='3', cron_start_time=datetime.now(), error_category='1', error_message=error_msg)
        else:
            OutlookSync.objects.create(user=advisor, sync_category='3', status='1')
    print('\n\n\n\n MAIL FOLDER SYNC CRON TERMINATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')
    


def ParseLOAMails():
    print('\n\n\n\n LOA RESPONSE PARSING CRON INITIATED AT TIME : ', datetime.now().strftime("%m/%d/%Y %H:%M:%S"), '\n\n')
    staffs = Staff.objects.filter(user__groups__name='Advisor')
    for staff in staffs:
        advisor = staff.user
        print("\n\n Parsing for Advisor :::::     ", advisor.email)
        client_instruments = ClientInstrumentInfo.objects.filter(loa_mail_sent=True, pdf_data=None, created_by=advisor, provider_type='1')
        for instrument in client_instruments:
            print('\n Client instrument   : ', instrument)
            # check_subject = 'Re: '+ instrument.instrument.mail_template.subject+' - CLT_' + str(instrument.client.id) + '_'+ str(instrument.id)33
            if instrument.signed_loa:
                check_subject = 'Re: '+ instrument.instrument.mail_template.subject+' - CLT_' + str(instrument.id) + '_' + str(instrument.signed_loa.id)
                print(check_subject, ' ----mail subject ')
                folder_to_filter = MailFolder.objects.filter(user=advisor, folder_name = 'Inbox').first()
                print(folder_to_filter, '  folder')
                if folder_to_filter:
                    print('enter folder to filter   ', folder_to_filter.folder_name)
                    response_mail = Email.objects.filter(message_subject=check_subject, user=instrument.created_by, folder=folder_to_filter).order_by('-message_recieved').first()
                    print('received mail  :  ', response_mail)
                    
                    #print('provider_emails  : ', instrument_emails)
                    instrument_emails = []
                    for instr in Instrument.objects.all():
                        if instr.mail_id:
                            for mail_id in instr.mail_id:
                                instrument_emails.append(mail_id)
                    if response_mail:
                        if response_mail.message_sender in instrument_emails:
                            print("enter ParseLOAMails")


                            # instrument.instrument_status = StatusCollection.objects.filter(status='1.26').first()
                            # instrument.save()
                            # # reminder removal
                            # try:
                            #     reminder_status = StatusCollection.objects.get(status='1.57')  # loa mail response pending status
                            #     # To update pending actions
                            #     pending_status = StatusCollection.objects.get(status='1.28')  # LoA Response Upload Pending
                            #     remove_reminder = Reminder.objects.filter(client_instrument=instrument,status=reminder_status).update( is_deleted=True)  # loa mail response pending status

                            #     pending_status_save(client_instrument=instrument, pending_status=pending_status)
                            # except Exception as e:
                            #     print(e)
                            # ends
                            # attached_response = Attachments.objects.filter(email_id=response_mail).first()
                            attached_response = Attachments.objects.filter(email_id=response_mail)
                            if attached_response.count() == 1:
                                print('Single Attachment Mail')

                                instrument.instrument_status = StatusCollection.objects.filter(status='1.26').first()
                                instrument.save()
                                # reminder removal
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

                                attached_response = attached_response.first()
                                created_doc = Document.objects.create(uploaded_by=advisor, owner=instrument.client, doc_type='5', doc=attached_response.attachments)
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
                            elif attached_response.count()>1:
                                print('Multiple Attachments found. Skipping the parsing')
                                if instrument.instrument_status.status != '1.26':
                                    instrument.instrument_status = StatusCollection.objects.filter(status='1.26').first()
                                    instrument.save()
                                    try:
                                        reminder_status = StatusCollection.objects.get(status='1.57')  # loa mail response pending status
                                        # To update pending actions
                                        pending_status = StatusCollection.objects.get(status='1.28')  # LoA Response Upload Pending
                                        
                                        for rem in Reminder.objects.filter(client_instrument=instrument,status=reminder_status):
                                            rem.is_deleted = True
                                            rem.save()
                                        pending_status_save(client_instrument=instrument, pending_status=pending_status)

                                    except Exception as e:
                                        print(e)
                            else:
                                print('No Attachments found. Skipping the parsing')

                else:
                    print('No INBOX found')

