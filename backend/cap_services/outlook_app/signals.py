from cap_outlook_service.outlook_services.models import Email, Event, OutlookLog, Attachments, MailFolder, OutlookCredentials,\
                                                        OutlookSync, Attendees , OutlookSyncErrorLog

from clients.models import Client,StatusCollection,Staff,Templates
from clients.utils import add_activity_flow
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from cap_outlook_service.outlook_services.tasks import async_send_mail, async_get_mailfolders, async_get_events, async_create_event, async_edit_event,\
        async_get_mails, async_delete_event, async_mark_rsvp, async_move_mail, async_mark_mail_read, async_delete_attachment
from clients.models import MailTemplateMapping,Document
from django.template import Context, Template
import json
import os, sys
from datetime import datetime
from cap_services.settings import BASE_URL
from cap_services.settings import MEDIA_PATH as MEDIA_URL


def send_mail(instance):
    try:
        mail = Email.objects.get(id=instance.email.id)
        credentials = OutlookCredentials.objects.get(user=instance.user)
    except Email.DoesNotExist: 
        print("Email not Found for user : ", instance.user, " for email : ", instance.email.id)
        return False
    except OutlookCredentials.DoesNotExist: 
        print("OutlookCredentials for the User missing for user : ", instance.user, " when sending email : ", instance.email.id)
        return False
    else:
        attachments = None
        attach = None
        if mail.has_attachments == True:
            print('has attachments')
            attach = Attachments.objects.filter(email=mail, is_outlook_synced=False)
            attachments = attach.values_list('attachments')
        try:
            template_details = MailTemplateMapping.objects.filter(email=instance.email).first()            
            if (template_details is not None) and (template_details.template is not None):
                print('Setting template values to mail object.')
                template_header=Template(template_details.template.template_header)
                template_footer=Template(template_details.template.template_footer)
                try:

                    staff = Staff.objects.filter(user=instance.user).first()
                    if staff:
                        company_url = staff.company.url
                        company_logo = staff.company.logo.url

                    else:
                        company_logo = Document.objects.get(doc='advisors/company/Lathe-logo.png').doc.url
                except:
                    company_logo = " "
                    company_url = " "

                context = Context({"company_logo": company_logo,"company_url":company_url,
                                   'static_image_path': os.path.join(MEDIA_URL, 'advisors/company')})
                template_header=template_header.render(context)
                template_footer = template_footer.render(context)
                print("template header---",template_header)
                print("template fiooter---", template_footer)
                print("templt content",template_details.content)
                print("setting the company logo and static file paths")
                final_content = template_header + '<div class="dontStyle" style="width:80%;margin:0 auto;">' + template_details.content + '</div>' + template_footer
                content = final_content
            else:
                if mail.message_body:
                    content = '<div>'+mail.message_body+'</div>'
                else:
                    content = '<div></div>'

            print('JUST BEFORE outlook app 9999999999999999999999999999999999999                           email id', instance.email.id)
            status = async_send_mail(instance.user.id, instance.email.id, content, attachments)
            print("status  =   ", status)
            response = json.dumps({"message": "Mail sent successfully"})
            instance.response_info = response
            instance.status = 3
            instance.save()
        except Exception as e:
            print("Could not send mail due to the error : ", e)
            try:
                response = json.dumps(e.response.json())
            except:
                print("error dict**************",e.__dict__)
                
                try:
                    if e.description:
                        error_msg = e.description.split('\r')[0]
                        error_msg = (error_msg.split(':',1)[-1]).strip()
                        response=json.dumps({'error':{'message':error_msg}})
                    else:
                        response=json.dumps({'error':{'message':"Error in mail sending"}})
                except Exception as err:
                    print("exception ",err)
                    response=json.dumps({'error':{'message':"Error in mail sending"}})
                    
            instance.response_info = response
            instance.status = 3
            instance.save()
            outbox = MailFolder.objects.filter(folder_name='Outbox', user=instance.user).first()
            mail.folder = outbox
            mail.save()
            return False
        else:
            if status:
                if attach:
                    attach.update(is_outlook_synced=True)
                print("Email send status : ", status)
                response = json.dumps({"message": "Mail sent successfully"})
                print('Mail send to server..!! ')

            else:
                print("Email send status : ", status)
                response = json.dumps({"error": {"message" : "Mail sending failed"}})
                print('Mail sending failed to server..!! ')

            instance.response_info = response
            instance.status = 3
            instance.save()
           
            return status
        


def set_event(instance):
    try:
        event = Event.objects.get(id=instance.event.id)
        credentials = OutlookCredentials.objects.get(user=instance.user)
    except Event.DoesNotExist: 
        print("Event not Found for user : ", instance.user, " for event : ", instance.event.id)
        return False
    except OutlookCredentials.DoesNotExist: 
        print("OutlookCredentials for the User missing for user : ", instance.user, " when creating event : ", instance.event.id)
        return False
    else:
        attachments = None    
        attachment_list = Attachments.objects.filter(event=event, is_outlook_synced=False)
        if attachment_list:
            attachments = attachment_list.values('id', 'attachments')
        if event.object_id:
           
            try:
                status = async_edit_event(instance.user, instance.event, credentials, attachments)
                response = json.dumps({"message": "Event created successfully"})
                instance.response_info = response
                instance.status = 3
                instance.save()
                if attachments:
                    attachment_list.update(is_outlook_synced=True)
            except Exception as e:
                print("Could not edit event due to the error : ", e)
                response = json.dumps(e.response.json())
                instance.response_info = response
                instance.status = 3
                instance.save()
                status = False
        else:
            try:
                new_event = async_create_event(instance.user, instance.event, credentials, attachments)
                response = json.dumps({"message": "Event created successfully"})
                instance.response_info = response
                instance.status = 3
                instance.save()
                if attachments:
                    attachment_list.update(is_outlook_synced=True)

            except Exception as e:
                print("Could not create event due to the error :   >>>> ", e)
                try:
                    response = json.dumps(e.response.json())
                except Exception as err:
                    print("exception ",err)
                    response = '{"error":{"message":"Event could not be added"}}'
               

                instance.response_info = response
                instance.status = 3
                instance.save()
                status = False
            else:
                if new_event:
                    event.object_id = new_event.object_id
                    event.save()
                    status = True

                
        return status


def delete_event(instance):
    try:
        event = Event.objects.get(id=instance.event.id)
    except Event.DoesNotExist: 
        print('Event not found to delete for user : ', instance.user, ' for event : ', instance.event.id)
    else:
        credentials = OutlookCredentials.objects.get(user=instance.user)
        try:
            status = async_delete_event(instance.user, event, credentials)
            subject=event.subject
            status_obj  = StatusCollection.objects.get(status='1.77')
            attendee_obj = Attendees.objects.filter(event=event).first()
            client=Client.objects.filter(user__email__exact=attendee_obj.attendee).first()
            if client:
                add_activity_flow(action_performed_by=instance.user,client=client, status=status_obj,comment= subject)
            return status
        except Exception as e:
            print("Could not delete event due to the error : ", e)
            return False


def delete_attachment(instance):
    try:
        event = Event.objects.get(id=instance.event.id)
    except Event.DoesNotExist:
        print('Event not found to delete for user : ', instance.user, ' for event : ', instance.event.id)
    else:
        credentials = OutlookCredentials.objects.get(user=instance.user)
        try:
            status = async_delete_attachment(instance.user, event, credentials, instance)
            return status
        except Exception as e:
            print("Could not delete event due to the error : ", e)
            return False


def delete_mail(instance):
    pass

def move_mail(instance):
    try:
        print(1111)
        email = Email.objects.get(id=instance.email.id)
        credentials = OutlookCredentials.objects.get(user=instance.user)
        status = async_move_mail(instance.user, email, credentials)
        return status
    except Email.DoesNotExist:
        print('Email not found to move for user : ', instance.user, ' for email : ', instance.email.id)
        return False
    except OutlookCredentials.DoesNotExist:
        print('Outlook Credentials not found for user : ', instance.user, ' for email : ', instance.email.id)   
        return False
    except Exception as e:
        print("Could not move mail due to the error : ", e)
        return False


def mark_rsvp(instance):
    try:
        event = Event.objects.get(id=instance.event.id)
    except Event.DoesNotExist:
        print('Event not found to mark rsvp for user : ', instance.user, ' for event : ', instance.event.id)
    else:
        credentials = OutlookCredentials.objects.get(user=instance.user)
        try:
            status = async_mark_rsvp(instance.user, event, credentials)
            return status
        except Exception as e:
            print("Could not mark rsvp due to the error : ", e)
            return False


def mark_mail_read(instance):
    try:
        mail = Email.objects.get(id=instance.email.id)
    except Email.DoesNotExist:
        print('Email not found to mark read for user : ', instance.user, ' for email : ', instance.email.subject)
    else:
        credentials = OutlookCredentials.objects.get(user=instance.user)
        try:
            status = async_mark_mail_read(instance.user, mail, credentials)
            return status
        except Exception as e:
            print("Could not mark mail read due to the error : ", e)
            return False

@receiver(post_save, sender=Attendees)
def postsave_Attendees(sender, instance, created, **kwargs):
    subject = instance.event.subject
    if subject is None:
        subject = " "
    if instance.is_deleted:
        print("Attendees instance has is_deleted")
        
    if created is True:
       
        print("created is True")
        
    else:
        try:
            client = Client.objects.get(user__email__exact=instance.attendee)
        except Client.DoesNotExist:
            client = None
        if client:

            if instance.response_status== '2':
                status = StatusCollection.objects.get(status='1.8')
            if (instance.response_status == '3'):
                status = StatusCollection.objects.get(status='1.6')
            if (instance.response_status == '4'):
                status = StatusCollection.objects.get(status='1.7')
            if(instance.response_status == '5'):
                print("response status not_responded")
            else:
                user = User.objects.filter(email=instance.event.organizer).first()
                if user:
                    add_activity_flow(action_performed_by=user, client=client, status=status, comment= subject)



@receiver(post_save, sender=Email)
def postsave_email(sender, instance, created, **kwargs):
    if (created is True) and (instance.object_id) and (instance.folder.folder_name=="Sent Items"):
        # need to test  
        #user = User.objects.filter(email=instance.user).first()
        subject=instance.message_subject
        if subject is None:
            subject=" "
        recipient_list = instance.message_to
        if recipient_list:
            for recipient in recipient_list:
                try:
                    client = Client.objects.filter(user__email__exact=recipient).first()
                except Client.DoesNotExist:
                    client = None
                if (client):
                    if ('welcome mail' in subject.lower()):
                        
                        status = StatusCollection.objects.get(status='1.3')
                        add_activity_flow(action_performed_by=instance.user, client=client, status=status)
                       
                    else:
                        if not instance.meeting_message_type:
                            status = StatusCollection.objects.get(status='1.56')           
                            thanks_template = Templates.objects.filter(template_name='Thanks mail').first()
                            
                          
                            if subject !=thanks_template.subject:
                                add_activity_flow(action_performed_by=instance.user, client=client, status=status, comment=subject)





@receiver(post_save, sender=OutlookLog)
def postsave_outlooklog(sender, instance, created, **kwargs):
    if instance.id:
        if instance.request_type == '1' or instance.request_type == 1:       # POST
            if instance.log_type == 1:
                # calendar instance
                OutlookLog.objects.filter(id=instance.id).update(status='2')
                if created is True:
                    
                    signal_status = set_event(instance)

            elif instance.log_type == 2:
                # mail instance
                if created is True:
                    print('\nSending Mail to Outlook server for user: ', instance.user.email)
                    OutlookLog.objects.filter(id=instance.id).update(status='2')
                    signal_status = send_mail(instance)
                    if signal_status is True:
                        print('Mail send successfully to outlook server.\n\n')
                        OutlookLog.objects.filter(id=instance.id).update(status='3')
                    else:
                        print('Mail send to outlook server failed.\n\n')
                        OutlookLog.objects.filter(id=instance.id).update(status='1')

        elif instance.request_type == '2' or instance.request_type == 2:     # PUT
            if instance.log_type == 1:
                # calendar instance
                OutlookLog.objects.filter(id=instance.id).update(status='2')
                if created is True:
                    signal_status = set_event(instance)

            elif instance.log_type == 2:
                # mail instance
                OutlookLog.objects.filter(id=instance.id).update(status='2')
                signal_status = send_mail(instance)
                if signal_status is True:
                    OutlookLog.objects.filter(id=instance.id).update(status='3')
                    try:
                        folder = MailFolder.objects.get(folder_name='Sent Items', user=instance.user)
                    except MailFolder.DoesNotExist: 
                        print("Mail folder not found after send mail edit in user: ", instance.user, " for email : ", instance.email.id)
                    else:
                        Email.objects.filter(id=instance.email.id).update(folder=folder)
                else:
                    OutlookLog.objects.filter(id=instance.id).update(status='1')

        elif instance.request_type == '3' or instance.request_type == 3:     # DELETE
            if instance.log_type == 1:
                # calendar instance
                OutlookLog.objects.filter(id=instance.id).update(status='2')
                signal_status = delete_event(instance)
            if instance.log_type == 2:
                #mail instance 
                OutlookLog.objects.filter(id=instance.id).update(status='2')
                signal_status = move_mail(instance)
                if signal_status == True:
                    OutlookLog.objects.filter(id=instance.id).update(status='3')
                else:
                    OutlookLog.objects.filter(id=instance.id).update(status='1')

            if instance.log_type == 3 or instance.log_type == '3':  # Delete Attachment
                OutlookLog.objects.filter(id=instance.id).update(status='2')
                signal_status = delete_attachment(instance)

        elif instance.request_type == '4' or instance.request_type == 4:     # RSVP
            if instance.log_type == 1:
                OutlookLog.objects.filter(id=instance.id).update(status='2')
                signal_status = mark_rsvp(instance)
                if signal_status == True:
                    OutlookLog.objects.filter(id=instance.id).update(status='3')
                else:
                    OutlookLog.objects.filter(id=instance.id).update(status='1')

        elif instance.request_type == '5' or instance.request_type == 5:     # RSVP
            if instance.log_type == 2:
                OutlookLog.objects.filter(id=instance.id).update(status='2')
                signal_status = mark_mail_read(instance)
                if signal_status == True:
                    OutlookLog.objects.filter(id=instance.id).update(status='3')
                else:
                    OutlookLog.objects.filter(id=instance.id).update(status='1')


@receiver(post_save, sender=OutlookSync)
def postsave_outlooksync(sender, instance, **kwargs):
    if instance.id:
        try:
            credentials = OutlookCredentials.objects.get(user=instance.user)
        except OutlookCredentials.DoesNotExist: 
            print("OutlookCredentials for the User missing for user : ", instance.user, " when syncing")
            
        else:
            print("OutlookCredentials found for the User : ", instance.user, " for syncing")    
            upd = OutlookSync.objects.filter(id=instance.id).update(status='2')
            traceback = None
            if instance.sync_category == '1':     # calendar event sync
                try:
                    status, error, traceback = async_get_events(instance, credentials)
                    if status:
                        upd = OutlookSync.objects.filter(id=instance.id).update(status='3')
                    else:
                        raise Exception(error)
                except Exception as e:
                    error=str(e)
                    upd = OutlookSync.objects.filter(id=instance.id).update(status='1')
                    error_msg = "Error in calendar sync for user : " + instance.user.username + " with error as : " + error
                    print("   ", error_msg)                    
                    error_log = OutlookSyncErrorLog.objects.create(user=instance.user, sync_category='1', cron_start_time=instance.create_time, error_category='2', error_message=error, traceback=traceback)
            
            elif instance.sync_category == '2':   # mail sync
                # no need to sync outbox folder
                mail_folders = MailFolder.objects.filter(user=instance.user).exclude(folder_name='Outbox')
                if mail_folders:                   
                    try:
                        status, error, traceback = async_get_mails(instance, credentials, mail_folders)
                        if status:
                            upd = OutlookSync.objects.filter(id=instance.id).update(status='3')
                        else:
                            raise Exception(error)
                    except Exception as e:
                        error = str(e)
                        upd = OutlookSync.objects.filter(id=instance.id).update(status='1')
                        error_msg = "Error in mail sync for user : " + instance.user.username + " with error as : " + error
                        print("   ", error_msg)
                        error_log = OutlookSyncErrorLog.objects.create(user=instance.user, sync_category='2', cron_start_time=instance.create_time, error_category='2', error_message=error, traceback=traceback)
                else:
                    print("Mail folders missing for user.....!!! Sync not performed.")
                    upd = OutlookSync.objects.filter(id=instance.id).update(status='1')
                    error_log = OutlookSyncErrorLog.objects.create(user=instance.user, sync_category='2', cron_start_time=instance.create_time, error_category='3', error_message='Mail Folder missing')

            elif instance.sync_category == '3':   # mail folder sync
                try:
                    status, error, traceback = async_get_mailfolders(instance, credentials)
                    if status:
                        upd = OutlookSync.objects.filter(id=instance.id).update(status='3')
                    else:
                       raise Exception(error)
                except Exception as e:
                    error = str(e)
                    OutlookSync.objects.filter(id=instance.id).update(status='1')
                    print(" Error in mail folder sync for user : ",instance.user.username," with error as : ", error)
                    error_log = OutlookSyncErrorLog.objects.create(user=instance.user, sync_category='3', cron_start_time=instance.create_time, error_category='2', error_message=error, traceback=traceback)

