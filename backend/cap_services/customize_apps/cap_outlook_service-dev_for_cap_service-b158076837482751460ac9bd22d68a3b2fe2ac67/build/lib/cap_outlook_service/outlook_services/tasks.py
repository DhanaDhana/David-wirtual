from celery.decorators import task
from .models import Email, Event, OutlookLog, Attachments, MailFolder, OutlookCredentials, Attendees, OutlookSync
from O365 import Account, MSGraphProtocol, FileSystemTokenBackend, Connection, Protocol
from requests_oauthlib import OAuth2Session
from django.conf import settings  # or from my_project import settings
from .graph_helper import get_sign_in_url, get_token_from_code, get_token
import pytz
import os, sys
import pathlib
import time
from datetime import datetime, timedelta, date

utc = pytz.UTC
import json
from operator import itemgetter
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage as server_storage
from django.core.files.storage import default_storage
from django.core.files import File
import shutil
import traceback


def authenticate(userid, oauth_credentials):
    credentials = (oauth_credentials.client_id, oauth_credentials.client_secret)
    # scopes=['offline_access', 'https://graph.microsoft.com/Mail.ReadWrite', 'https://graph.microsoft.com/Mail.Send']
    protocol_graph = MSGraphProtocol()
    scopes = ["offline_access"]
    scopes_graph = protocol_graph.get_scopes_for('message_all')
    scopes.extend(scopes_graph)
    calendar_graph = protocol_graph.get_scopes_for('calendar_all')
    scopes.extend(calendar_graph)
    account = Account(credentials)

    token_path = "/".join(oauth_credentials.token_path.name.split('/')[:-1:]) + '/'
    token_path = settings.MEDIA_ROOT + '/' + token_path
    # token_path = os.getcwd()+oauth_credentials.token_path.name.split('/')[:-2:]

    token_name = oauth_credentials.token_path.name.split('/')[-1]

    token_backend = FileSystemTokenBackend(token_path=token_path, token_filename=token_name)
    account = Account(credentials, token_backend=token_backend)

    if not account.is_authenticated:  # will check if there is a token and has not expired
        # ask for a login
        print('Going to Authenticate ==================================================== ')
        if oauth_credentials.token_path:
            if settings.IS_S3:
                path = os.path.join(settings.MEDIA_ROOT, oauth_credentials.token_path.name)
                if not os.path.exists(path):
                    df = server_storage()
                    full_path = os.path.join(df.base_location, oauth_credentials.token_path.name)
                    pathlib.Path(os.path.split(full_path)[0]).mkdir(parents=True, exist_ok=True)
                    df.save(full_path, oauth_credentials.token_path.open())
            else:
                path = oauth_credentials.token_path.path
            with open(path, 'r') as content_file:
                token = content_file.read()
            token = json.loads(token)
            now = time.time()
            print('Re authenticating')
            # Subtract 5 minutes from expiration to account for clock skew
            expire_time = token['expires_at'] - 300
            if now >= expire_time:
                # Refresh the token
                aad_auth = OAuth2Session(oauth_credentials.client_id, token=token, scope=settings.SCOPES,
                                         redirect_uri=settings.REDIRECT)

                refresh_params = {
                    'client_id': oauth_credentials.client_id,
                    'client_secret': oauth_credentials.client_secret,
                }
                token_url = '{0}{1}'.format(settings.AUTHORITY, settings.TOKEN_ENDPOINT)
                new_token = aad_auth.refresh_token(token_url, **refresh_params)

                dir_path = os.path.join('tokens', str(oauth_credentials.user.id))

                if not settings.IS_S3:
                    with open(oauth_credentials.token_path.path, 'w', encoding='utf-8') as f:
                        json.dump(new_token, f, ensure_ascii=False, indent=4)
                else:
                    _path = os.path.join(settings.MEDIA_ROOT, oauth_credentials.token_path.name)
                    with open(_path, 'w', encoding='utf-8') as f:
                        json.dump(new_token, f, ensure_ascii=False, indent=4)

                oauth_credentials.token_path = dir_path + '/oauth_token.txt'
                oauth_credentials.save()
                # file_save = oauth_credentials.save(location=dir_path, custom_name=new_token)

                token_path = "/".join(oauth_credentials.token_path.name.split('/')[:-1:]) + '/'
                token_path = settings.MEDIA_ROOT + '/' + token_path

                token_name = oauth_credentials.token_path.name.split('/')[-1]
                token_backend = FileSystemTokenBackend(token_path=token_path, token_filename=token_name)
                account = Account(credentials, token_backend=token_backend)

                print(' Re-authentication status ===================  ', account.is_authenticated)
        else:
            print('Authenticate failed ==================================================== ')
    else:
        print('Authentication Success ==================================================== ')

        # RuntimeError: No auth token found. Authentication Flow needed   ------ needs to be handled
    return account



@task(name="send_mail_to_outlook_server")
def async_send_mail(userid, mailid, template_content, attachments=None):
    print('\n Trying to send mail: ', mailid, '   with template: ', template_content)
    oauth_credentials = OutlookCredentials.objects.get(user_id=userid)
    account = authenticate(userid, oauth_credentials)
    mailbox = account.mailbox()
    mail = Email.objects.filter(id=mailid).first()
    if mail.mail_action == '4':
        print('Mail Action : Forward           parent mail: ', mail.object_id)
        reply_mail = Email.objects.filter(object_id=mail.reply_id).first()
        reply_mail = mailbox.get_message(object_id=reply_mail.object_id)
        new_mail = reply_mail.forward()
    elif mail.mail_action == '3':
        print('Mail Action : Reply all           parent mail: ', mail.object_id)
        reply_mail = Email.objects.filter(object_id=mail.reply_id).first()
        reply_mail = mailbox.get_message(object_id=reply_mail.object_id)
        new_mail = reply_mail.reply(to_all=True)
    elif mail.mail_action == '2':
        print('Mail Action : Reply           parent mail: ', mail.object_id)
        reply_mail = Email.objects.filter(object_id=mail.reply_id).first()
        reply_mail = mailbox.get_message(object_id=reply_mail.object_id)
        new_mail = reply_mail.reply(to_all=False)
    else:
        new_mail = mailbox.new_message()

    # if mail.has_attachments == True:
    #     attachments = Attachments.objects.filter(email=mail, is_outlook_synced=False).values_list('attachments')

    print('\nMail obj set with data to send...')
    if mail.message_to:
        for to in mail.message_to:
            if to not in new_mail.to:
                new_mail.to.add(mail.message_to)

    # code to remove the sender email from reply to list
    if mail.mail_action == '2':
        print('Removing current user mail from TO list for reply case.')
        curr_user = User.objects.get(id=userid)
        for too in new_mail.to:
            if too.address == curr_user.email:
                new_mail.to.remove(too.address)

    new_mail.cc.add(mail.message_cc)
    new_mail.bcc.add(mail.message_bcc)
    new_mail.subject = mail.message_subject
    # if template_details:
    #     print('Setting template values to mail object.')
    #     final_content = template_details.template.template_header + '<div class="dontStyle" style="width:80%;margin:0 auto;">' + template_details.content + '</div>' + template_details.template.template_footer
    #     new_mail.body = final_content
    # else:
    #     if mail.message_body:
    #         new_mail.body = '<div>'+mail.message_body+'</div>'
    new_mail.body = template_content

    if attachments:
        print('Adding attachments to mail object.')
        for attach in attachments:
            new_mail.attachments.add(settings.MEDIA_ROOT + '/' + attach[0])

    if mail.message_is_draft:
        print('Saving message as Draft.')
        if mail.object_id:
            new_mail.object_id = mail.object_id
        status = new_mail.save_draft()
        mail.object_id = new_mail.object_id
        mail.save()

    else:
        print('Sending Mail to outlook server')

        if mail.object_id:
            new_mail.object_id = mail.object_id
            # new_mail.is_draft = True  #setting is_draft = True so that the package knows that this message was a draft
        status = new_mail.send()

        # running mail sync suddenly
        # log_entry = OutlookSync.objects.create(user_id=userid, sync_category='2', status='1')
    return status


def async_move_mail(userid, email, oauth_credentials):
    account = authenticate(userid, oauth_credentials)
    mailbox = account.mailbox()

    mail = mailbox.get_message(object_id=email.object_id)
    mail.move(email.folder.folder_id)
    # if email.message_is_deleted == True:
    #     #delete mail is the opreation
    #     mail = mailbox.get_message(object_id=email.object_id)
    #     mail.delete()

    # else:
    #     print('folder move operation to be done')


def get_mail_folders(account):
    mailbox = account.mailbox()
    try:
        folder_list = mailbox.get_folders()
    except Exception as e:
        print(e)
        return [], e
    else:
        return folder_list, None


@task(name="sync_mail_folders_from_outlook_server")
def async_get_mailfolders(instance, oauth_credentials):
    print('Syncing Mail Folders....')
    try:
        account = authenticate(instance.user, oauth_credentials)
        last_synced_obj = OutlookSync.objects.filter(user=instance.user, sync_category='3', status='3').exclude(id=instance.id).order_by('-id').first()
        folder_list, err = get_mail_folders(account)

        if folder_list:
            if last_synced_obj:
                for folder in folder_list:
                    if utc.localize(folder.updated_at) > last_synced_obj.updated_time:
                        mail_folder = MailFolder.objects.filter(folder_id=folder.folder_id, folder_name=folder.name, user=instance.user).first()
                        if mail_folder:
                            mail_folder.parent_id = folder.parent_id
                            mail_folder.folder_name = folder.name
                            mail_folder.user = instance.user
                            mail_folder.updated_time = utc.localize(folder.updated_at)
                            mail_folder.save()
                        else:
                            new_folder = MailFolder.objects.create(folder_id=folder.folder_id, parent_id=folder.parent_id, folder_name=folder.name, user=instance.user, updated_time=utc.localize(folder.updated_at))
            else:
                for folder in folder_list:
                    check_existing = MailFolder.objects.filter(folder_id=folder.folder_id).first()
                    if not check_existing:
                        mail_folder = MailFolder.objects.create(folder_id=folder.folder_id, parent_id=folder.parent_id, folder_name=folder.name, user=instance.user, updated_time=utc.localize(folder.updated_at))
        else:
            print("No Folders found to sync from Outlook Server..!!")
            print(err)
            if err:
                return False, str(err)
    except Exception as e:
        print(e)
        return False, str(e), traceback.format_exc()
    return True, None, None


def get_calendar_events(account, last_sync_date=None, event_start_date=None, rec_start=None, rec_end=None):
    schedule = account.schedule()
    calendar = schedule.get_default_calendar()
    query = None
    if rec_start and rec_end:
        query = calendar.new_query('start').greater_equal(rec_start)
        query.chain('and').on_attribute('end').less_equal(rec_end)
        event_list = calendar.get_events(limit=10000, include_recurring=True, batch=500, query=query)
    else:
        if last_sync_date:
            query = calendar.new_query('lastModifiedDateTime').greater_equal(last_sync_date)
        if event_start_date:
            query = calendar.new_query('start').greater_equal(event_start_date)

        if query:
            event_list = calendar.get_events(limit=10000, include_recurring=False, batch=500, query=query)
        else:
            event_list = calendar.get_events(limit=10000, include_recurring=False, batch=500)

    return event_list


def monthdelta(date, delta):
    m, y = (date.month + delta) % 12, date.year + ((date.month) + delta - 1) // 12
    if not m: m = 12
    d = min(date.day, [31,
                       29 if y % 4 == 0 and (not y % 100 == 0 or y % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date.replace(day=d, month=m, year=y)


def remove_outlook_deleted_events(user, event_list, start_date):
    events = Event.objects.filter(user=user, event_start__gte=start_date)
    event_db_set = set(event.object_id for event in events)
    event_server_set = set(event.object_id for event in event_list)

    difference_in_events = event_db_set - event_server_set

    print(len(event_db_set), '  db')
    print(len(event_server_set), '  server')
    print(len(difference_in_events), '   difference')

    print("removed events ", )
    for e in Event.objects.filter(object_id__in=difference_in_events):
        print('    ', e.subject, '   ', e.object_id)

    removed_events = Event.objects.filter(object_id__in=difference_in_events).update(is_deleted=True)


@task(name="sync_events_from_outlook_server")
def async_get_events(instance, oauth_credentials):
    print('Syncing Events....')
    try:
        account = authenticate(instance.user, oauth_credentials)
    
        last_synced_obj = OutlookSync.objects.filter(user=instance.user, sync_category='1', status='3').exclude(id=instance.id).order_by('-id').first()

        importance = {'low': '1', 'normal': '2', 'high': '3'}
        sensitivity = {'normal': '1', 'personal': '2', 'private': '3', 'confidential': '4'}
        show_as = {'free': '1', 'tentative': '2', 'busy': '3', 'oof': '4', 'working_elsewhere': '5', 'unknown': '6'}
        event_type = {'single_instance': '1', 'occurrence': '2', 'exception': '3', 'series_master': '4'}
        response_status = {'organizer': '1', 'accepted': '2', 'declined': '3', 'tentatively_accepted': '4', 'not_responded': '5'}

        event_list_start = None
        event_list_end = None
        # event_list_end = datetime(2200, 9, 1, 11, 51, 24)

        if last_synced_obj:
            print('Last sync done on', last_synced_obj.updated_time)
            event_list = get_calendar_events(account, last_sync_date=last_synced_obj.updated_time)

            for event in event_list:
                # to get the start and end dates for querying recurring events  ===>
                if event_list_start is None:
                    event_list_start = event.start
                    # event_list_end = event.end

                if event.start < event_list_start:
                    event_list_start = event.start
                # if event.end > event_list_end:
                #     event_list_end = event.end
                # <======

                try:
                    if event.modified > last_synced_obj.updated_time:
                        location = event.location['displayName'] if event.location else None
                        event_from_db = Event.objects.filter(object_id=event.object_id, user=instance.user).first()
                        importance_value = importance[event.importance.value] if event.importance else importance['low']
                        sensitivity_value = sensitivity[event.sensitivity.value] if sensitivity else sensitivity['normal']
                        event_type_value = event_type[event.event_type.value] if event.event_type else event_type['single_instance']
                        show_as_value = show_as[event.show_as.value] if event.show_as else show_as['free']
                        response_status_value = response_status[event.response_status.status.value] if event.response_status.status else response_status['organizer']

                        if event_from_db:
                            print("    ", event.subject, ' present in db   ', event.start)
                            if event.recurrence:
                                print('          with recurrence. so removing event from normal type and will be added later along with recurring events')
                                event_from_db.is_deleted = True
                                event_from_db.save()
                            else:
                                event_from_db.updated_time = event.modified
                                event_from_db.description = event.body
                                event_from_db.subject = event.subject
                                event_from_db.event_start = event.start
                                event_from_db.event_end = event.end
                                event_from_db.importance = importance_value
                                event_from_db.is_all_day = event.is_all_day
                                event_from_db.location = location
                                event_from_db.is_remainder_on = event.is_reminder_on
                                event_from_db.remind_before_minutes = event.remind_before_minutes
                                event_from_db.response_requested = event.response_requested
                                event_from_db.organizer = event.organizer.address
                                event_from_db.show_as = show_as_value
                                event_from_db.sensitivity = sensitivity_value
                                event_from_db.categories = event.categories
                                event_from_db.event_type = event_type_value
                                event_from_db.ical_uid = event.ical_uid
                                event_from_db.is_cancelled = event.is_cancelled
                                event_from_db.response_status = response_status_value
                                event_from_db.save()

                                new_attendees_list = set(attendee.address.strip() for attendee in event.attendees)
                                event_attendees = Attendees.objects.filter(event__object_id=event.object_id).values_list('attendee', flat=True)
                                event_attendees = set(attendee.strip() for attendee in event_attendees)
                                total_attendees = set(new_attendees_list) | event_attendees

                                for attendee in total_attendees:
                                    if attendee not in new_attendees_list:
                                        print(attendee, ' not in new_attendees_list')
                                        # Remove existing attendee from Model
                                        remove_attendee = Attendees.objects.filter(event__object_id=event.object_id,
                                                                                   attendee=attendee)
                                        remove_attendee.update(is_deleted=True)
                                    elif attendee not in event_attendees:
                                        print(attendee, ' not in event_attendees_list')
                                        # add new attendee to Model
                                        for att in event.attendees:
                                            if att.address == attendee:
                                                if att.response_status.status is None:
                                                    resp = response_status['not_responded']
                                                else:
                                                    resp = response_status[att.response_status.status.value]
                                                # add_attendee = Attendees.objects.create(event__object_id=event.object_id, attendee=attendee, response_status=resp)
                                                ev = Event.objects.filter(object_id=event.object_id).first()
                                                add_attendee = Attendees.objects.create(event=ev, attendee=attendee, response_status=resp)
                                    elif attendee in event_attendees:
                                        print(attendee, ' existing attendee')
                                        # update existing attendee
                                        for att in event.attendees:
                                            if att.address == attendee:
                                                # att.response_status.status
                                                if att.response_status.status is None:
                                                    resp = response_status['not_responded']
                                                else:
                                                    resp = response_status[att.response_status.status.value]
                                                ev = Event.objects.filter(object_id=event.object_id).first()
                                                # update_attendee = Attendees.objects.filter(event=ev, attendee=attendee).update(response_status=resp)
                                                update_attendee = Attendees.objects.filter(event=ev, attendee=attendee)
                                                for attendee in update_attendee:
                                                    attendee.response_status = resp
                                                    attendee.save()

                                remove_attachements = Attachments.objects.filter(event=event_from_db.id)
                                if event.attachments.download_attachments():
                                    try:
                                        att_obj = event.attachments._BaseAttachments__attachment_obj[0]
                                        att_obj_id = list(map(itemgetter('id'), att_obj))
                                        remove_attachements = Attachments.objects.filter(event=event_from_db.id).exclude(object_id__in=att_obj_id)
                                        remove_attachements.delete()

                                        dir_path = os.path.join(settings.MEDIA_ROOT, 'attachments', 'event', str(event_from_db.id))
                                        # # dir_path = os.path.join('attachments','event',str(created_event.id))
                                        if not os.path.isdir(dir_path):
                                            os.makedirs(dir_path)
                                        for _att in att_obj:
                                            att_obj_in_db = Attachments.objects.filter(object_id=_att['id'])
                                            if not att_obj_in_db:
                                                print("adding new event attcahment to db")
                                                new_file_name = _att['name'].name
                                                att_name = new_file_name.replace('/', '-').replace('\\', '')
                                                if len(att_name) > 210:
                                                    att_name = att_name[:210] + '.' + att_name.split('.')[-1]

                                                if settings.IS_S3:
                                                    file_save = _att['name'].save(location=dir_path, custom_name=att_name)
                                                    if file_save:
                                                        new_file_name = os.path.join('attachments', 'event', str(event_from_db.id), att_name)
                                                        _report_doc = File(open(os.path.join(settings.MEDIA_ROOT, new_file_name), mode='rb'))
                                                        path = default_storage.save(att_name, _report_doc)
                                                        created_att = Attachments.objects.create(event=event_from_db, attachments=path, object_id=_att['id'], is_outlook_synced=True)
                                                        os.remove(os.path.join(settings.MEDIA_ROOT, new_file_name))
                                                else:
                                                    file_save = _att['name'].save(location=dir_path, custom_name=att_name)
                                                    if file_save:
                                                        new_file_name = os.path.join('attachments', 'event', str(event_from_db.id), att_name)
                                                        created_att = Attachments.objects.create(event=event_from_db, attachments=new_file_name, object_id=_att['id'], is_outlook_synced=True)

                                        if settings.IS_S3:
                                            shutil.rmtree(dir_path)
                                            # os.rmdir(dir_path)
                                    except Exception as e:
                                        print("No attachmnet object id error", e)
                        else:
                            # recurring events added later
                            if not event.recurrence:
                                print("    ", event.subject, ' not in db')
                                importance_value = importance[event.importance.value] if event.importance else importance['low']
                                sensitivity_value = sensitivity[event.sensitivity.value] if sensitivity else sensitivity['normal']
                                event_type_value = event_type[event.event_type.value] if event.event_type else event_type['single_instance']
                                show_as_value = show_as[event.show_as.value] if event.show_as else show_as['free']
                                response_status_value = response_status[event.response_status.status.value] if event.response_status.status else response_status['organizer']

                                created_event = Event.objects.create(user=instance.user, object_id=event.object_id,
                                                                     create_time=event.created,
                                                                     updated_time=event.modified,
                                                                     description=event.body, subject=event.subject,
                                                                     event_start=event.start, event_end=event.end,
                                                                     importance=importance_value,
                                                                     is_all_day=event.is_all_day, location=location,
                                                                     is_remainder_on=event.is_reminder_on,
                                                                     remind_before_minutes=event.remind_before_minutes,
                                                                     response_requested=event.response_requested,
                                                                     organizer=event.organizer.address,
                                                                     show_as=show_as_value,
                                                                     sensitivity=sensitivity_value,
                                                                     categories=event.categories,
                                                                     event_type=event_type_value,
                                                                     ical_uid=event.ical_uid,
                                                                     response_status=response_status_value,
                                                                     is_cancelled=event.is_cancelled)

                                for attendee in event.attendees:
                                    if attendee.address == created_event.organizer:
                                        add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address, response_status=response_status['organizer'])
                                    elif attendee.response_status.status:
                                        add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address, response_status=response_status[ attendee.response_status.status.value])
                                    else:
                                        add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address)

                                if event.attachments.download_attachments():
                                    dir_path = os.path.join(settings.MEDIA_ROOT, 'attachments', 'event', str(created_event.id))
                                    if not os.path.isdir(dir_path):
                                        os.makedirs(dir_path)
                                    
                                    for att in event.attachments:
                                        att_name = att.name.replace('/', '-').replace('\\', '')
                                        if len(att_name) > 210:
                                            att_name = att_name[:210] + '.' + att_name.split('.')[-1]
                                        
                                        if settings.IS_S3:
                                            file_save = att.save(location=dir_path, custom_name=att_name)
                                            if file_save:
                                                new_file_name = os.path.join('attachments', 'event', str(created_event.id), att_name)
                                                _report_doc = File(open(os.path.join(settings.MEDIA_ROOT, new_file_name), mode='rb'))
                                                path = default_storage.save(att_name, _report_doc)
                                                created_att = Attachments.objects.create(event=created_event, attachments=path)
                                                os.remove(os.path.join(settings.MEDIA_ROOT, new_file_name))
                                        else:
                                            file_save = att.save(location=dir_path, custom_name=att_name)
                                            if file_save:
                                                new_file_name = os.path.join('attachments', 'event', str(created_event.id), att_name)
                                                created_att = Attachments.objects.create(event=created_event, attachments=new_file_name)

                                    if settings.IS_S3:
                                        # os.rmdir(dir_path)
                                        shutil.rmtree(dir_path)


                except Exception as e:
                    print("Exception in adding event from outlook to db during further sync for user : ", instance.user, "on date: ", datetime.now(), " with error : ", e)

        else:
            event_list = get_calendar_events(account)
            print('First time sync ::: ')
            for event in event_list:
                # to get the start and end dates for querying recurring events  ===>
                if event_list_start is None:
                    event_list_start = event.start
                    # event_list_end = event.end

                if event.start < event_list_start:
                    event_list_start = event.start
                # if event.end > event_list_end:
                #     event_list_end = event.end
                # <======
                # recurring events added later
                if not event.recurrence:
                    try:
                        print("    ", event.subject)
                        location = event.location['displayName'] if event.location else None

                        importance_value = importance[event.importance.value] if event.importance else importance['low']
                        sensitivity_value = sensitivity[event.sensitivity.value] if sensitivity else sensitivity['normal']
                        event_type_value = event_type[event.event_type.value] if event.event_type else event_type['single_instance']
                        show_as_value = show_as[event.show_as.value] if event.show_as else show_as['free']
                        response_status_value = response_status[event.response_status.status.value] if event.response_status.status else response_status['organizer']

                        created_event = Event.objects.create(user=instance.user, object_id=event.object_id,
                                                             create_time=event.created, updated_time=event.modified,
                                                             description=event.body, subject=event.subject,
                                                             event_start=event.start, event_end=event.end,
                                                             importance=importance_value, is_all_day=event.is_all_day,
                                                             location=location, is_remainder_on=event.is_reminder_on,
                                                             remind_before_minutes=event.remind_before_minutes,
                                                             response_requested=event.response_requested,
                                                             organizer=event.organizer.address, show_as=show_as_value,
                                                             sensitivity=sensitivity_value, categories=event.categories,
                                                             event_type=event_type_value, ical_uid=event.ical_uid,
                                                             response_status=response_status_value,
                                                             is_cancelled=event.is_cancelled)

                        for attendee in event.attendees:
                            if attendee.address == created_event.organizer:
                                add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address, response_status=response_status['organizer'])
                            elif attendee.response_status.status:
                                add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address, response_status=response_status[ attendee.response_status.status.value])
                            else:
                                add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address)

                        if event.attachments.download_attachments():
                            dir_path = os.path.join(settings.MEDIA_ROOT, 'attachments', 'event', str(created_event.id))
                            if not os.path.isdir(dir_path):
                                os.makedirs(dir_path)
                            
                            for att in event.attachments:
                                att_name = att.name.replace('/', '-').replace('\\', '')
                                if len(att_name) > 210:
                                    att_name = att_name[:210] + '.' + att_name.split('.')[-1]
                                
                                if settings.IS_S3:
                                    file_save = att.save(location=dir_path, custom_name=att_name)
                                    if file_save:
                                        new_file_name = os.path.join('attachments', 'event', str(created_event.id), att_name)
                                        _report_doc = File(open(os.path.join(settings.MEDIA_ROOT, new_file_name), mode='rb'))
                                        path = default_storage.save(att_name, _report_doc)
                                        created_att = Attachments.objects.create(event=created_event, attachments=path)
                                        os.remove(os.path.join(settings.MEDIA_ROOT, new_file_name))
                                else:
                                    file_save = att.save(location=dir_path, custom_name=att_name)
                                    if file_save:
                                        new_file_name = os.path.join('attachments', 'event', str(created_event.id), att_name)
                                        created_att = Attachments.objects.create(event=created_event, attachments=new_file_name)
                            
                            if settings.IS_S3:
                                # os.rmdir(dir_path)
                                shutil.rmtree(dir_path)

                    except Exception as e:
                        print("Exception in adding event from outlook to db during first time sync for user : ", instance.user, "on date: ", datetime.now(), " with error : ", e)

        rec_events = None
        if event_list_start:
            event_list_end = event_list_start + timedelta(days=1800)
            print(event_list_start, event_list_end)
            print(" \n getting recurring events")
            # rec_events = get_calendar_events(account, rec_start=event_list_start, rec_end=event_list_end+timedelta(days=1))
            rec_events = get_calendar_events(account, rec_start=event_list_start, rec_end=event_list_end)

            for event in rec_events:
                event_from_db = Event.objects.filter(object_id=event.object_id, user=instance.user).first()
                if not event_from_db:
                    try:
                        print(event.subject, '  ', event.object_id, '  ', event.start)
                        location = event.location['displayName'] if event.location else None

                        importance_value = importance[event.importance.value] if event.importance else importance['low']
                        sensitivity_value = sensitivity[event.sensitivity.value] if sensitivity else sensitivity[
                            'normal']
                        event_type_value = event_type[event.event_type.value] if event.event_type else event_type[
                            'single_instance']
                        show_as_value = show_as[event.show_as.value] if event.show_as else show_as['free']
                        response_status_value = response_status[
                            event.response_status.status.value] if event.response_status.status else response_status[
                            'organizer']

                        created_event = Event.objects.create(user=instance.user, object_id=event.object_id,
                                                             create_time=event.created, updated_time=event.modified,
                                                             description=event.body, subject=event.subject,
                                                             event_start=event.start, event_end=event.end,
                                                             importance=importance_value, is_all_day=event.is_all_day,
                                                             location=location, is_remainder_on=event.is_reminder_on,
                                                             remind_before_minutes=event.remind_before_minutes,
                                                             response_requested=event.response_requested,
                                                             organizer=event.organizer.address, show_as=show_as_value,
                                                             sensitivity=sensitivity_value, categories=event.categories,
                                                             event_type=event_type_value, ical_uid=event.ical_uid,
                                                             response_status=response_status_value,
                                                             is_cancelled=event.is_cancelled)
                        if created_event:
                            print('create success')

                        for attendee in event.attendees:
                            if attendee.address == created_event.organizer:
                                add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address,
                                                                        response_status=response_status['organizer'])
                            elif attendee.response_status.status:
                                add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address,
                                                                        response_status=response_status[
                                                                            attendee.response_status.status.value])
                            else:
                                add_attendee = Attendees.objects.create(event=created_event, attendee=attendee.address)

                        if event.attachments.download_attachments():
                            dir_path = os.path.join(settings.MEDIA_ROOT, 'attachments', 'event', str(created_event.id))
                            if not os.path.isdir(dir_path):
                                os.makedirs(dir_path)
                            for att in event.attachments:
                                att_name = att.name.replace('/', '-').replace('\\', '')
                                if len(att_name) > 210:
                                    att_name = att_name[:210] + '.' + att_name.split('.')[-1]

                                if settings.IS_S3:
                                    file_save = att.save(location=dir_path, custom_name=att_name)
                                    if file_save:
                                        new_file_name = os.path.join('attachments', 'event', str(created_event.id), att_name)
                                        _report_doc = File(open(os.path.join(settings.MEDIA_ROOT, new_file_name), mode='rb'))
                                        path = default_storage.save(att_name, _report_doc)
                                        created_att = Attachments.objects.create(event=created_event, attachments=path)
                                        os.remove(os.path.join(settings.MEDIA_ROOT, new_file_name))
                                else:
                                    file_save = att.save(location=dir_path, custom_name=att_name)
                                    if file_save:
                                        new_file_name = os.path.join('attachments', 'event', str(created_event.id), att_name)
                                        created_att = Attachments.objects.create(event=created_event, attachments=new_file_name)
                            if settings.IS_S3:
                                # os.rmdir(dir_path)
                                shutil.rmtree(dir_path)

                    except Exception as e:
                        print("Exception in adding recurring events from outlook to db for user : ", instance.user,
                              "on date: ", datetime.now(), " with error : ", e)

        if last_synced_obj:
            print("\nRemoving cap deleted events")
            one_month_delta_time = monthdelta(last_synced_obj.updated_time, -1)
            events = get_calendar_events(account, event_start_date=one_month_delta_time)
            rec_events = get_calendar_events(account, rec_start=one_month_delta_time,
                                             rec_end=one_month_delta_time + timedelta(days=1800))
            from itertools import chain
            event_list = chain(events, rec_events)
            remove_outlook_deleted_events(instance.user, event_list, start_date=one_month_delta_time)

    except Exception as e:
        print('Exception occured during Event Sync (user auth) with error : ', e)
        return False, str(e), traceback.format_exc()

    return True, None, None


def async_create_event(userid, event, oauth_credentials, attachments):
    account = authenticate(userid, oauth_credentials)
    schedule = account.schedule()
    calendar = schedule.get_default_calendar()
    new_event = calendar.new_event()  # creates a new unsaved event
    new_event.subject = event.subject
    new_event.is_all_day = event.is_all_day
    new_event.body = event.description
    new_event.location = event.location
    new_event.start = event.event_start
    new_event.end = event.event_end

    if event.location:
        new_event.location = event.location

    if event.remind_before_minutes:
        new_event.remind_before_minutes = event.remind_before_minutes

    attendees = Attendees.objects.filter(event=event.id)
    if attendees:
        for attendee in attendees:
            new_event.attendees.add(attendee.attendee)

    if attachments:
        for attachment in attachments:
            # new_event.attachments.add(settings.MEDIA_ROOT+'/'+attachment[0])
            new_event.attachments.add(
                {'attach_id': attachment['id'], 'attachment': settings.MEDIA_ROOT + '/' + attachment['attachments']})
    # try:
    status = new_event.save()
    if status:
        event.object_id = new_event.object_id
        event.ical_uid = new_event.ical_uid
        at_resposne = new_event._Event__attachment_response
        if at_resposne:
            for at in at_resposne:
                Attachments.objects.filter(id=at['id']).update(object_id=at['obj_id'], is_outlook_synced=True)
        # if new_event.is_all_day:
        #     event.event_end = new_event.end - timedelta(0,5)
        event.save()
    # except Exception as e:
    #     print('Error while creating event : ', event.subject, ' for user : ', userid.username, 'with error : ', e )
    #     data = e.response.json()

    # return data
    return event


def async_edit_event(userid, event, oauth_credentials, attachments):
    account = authenticate(userid, oauth_credentials)
    schedule = account.schedule()
    calendar = schedule.get_default_calendar()
    response_dict = {'2': 'accepted', '3': 'declined', '4': 'tentativelyAccepted', '5': 'notResponded'}

    try:
        exist_event = calendar.get_event(event.object_id)
    except Exception as e:
        print('Event not found...!!')
        return False

    exist_event.subject = event.subject
    exist_event.start = event.event_start
    exist_event.end = event.event_end
    exist_event.body = event.description
    exist_event.location = event.location
    exist_event.is_all_day = event.is_all_day

    if event.location:
        exist_event.location = event.location

    if event.remind_before_minutes:
        exist_event.remind_before_minutes = event.remind_before_minutes

    attendees = Attendees.objects.filter(event=event.id)

    for exs_att in exist_event.attendees:
        exist_event.attendees.remove(exs_att)
    if attendees:
        for attendee in attendees:
            exist_event.attendees.add(attendee.attendee)

    if attachments:
        for attachment in attachments:
            # exist_event.attachments.add(settings.MEDIA_ROOT+'/'+attachment[0])
            exist_event.attachments.add(
                {'attach_id': attachment['id'], 'attachment': settings.MEDIA_ROOT + '/' + attachment['attachments']})

    # print(dir(exist_event))
    status = exist_event.save()
    if status:
        at_resposne = exist_event._Event__attachment_response
        if at_resposne:
            for at in at_resposne:
                Attachments.objects.filter(id=at['id']).update(object_id=at['obj_id'], is_outlook_synced=True)
    return True


def async_mark_rsvp(userid, event, oauth_credentials):
    account = authenticate(userid, oauth_credentials)
    schedule = account.schedule()
    calendar = schedule.get_default_calendar()
    response_dict = {'2': 'accepted', '3': 'declined', '4': 'tentativelyAccepted', '5': 'notResponded'}

    try:
        exist_event = calendar.get_event(event.object_id)
    except Exception as e:
        print('Event not found...!!')
        return False
    else:
        print(event.response_status, ' ---------- \n\n\n')

        if response_dict[event.response_status] == 'accepted':
            print('going to accept event')
            status = exist_event.accept_event(send_response=True, tentatively=False)
            if status == True:
                print("Event Accepted")
                return True
            else:
                print("Event Response could not be updated")
                return False

        elif response_dict[event.response_status] == 'tentativelyAccepted':
            print('going to accept event tentatively')
            status = exist_event.accept_event(send_response=True, tentatively=True)
            if status == True:
                print("Event Accepted Tentatively")
                return True
            else:
                print("Event Response could not be updated")
                return False

        elif response_dict[event.response_status] == 'declined':
            print('going to decline event')
            status = exist_event.decline_event(send_response=True)
            if status is True:
                print("Event Declined")
                return True
            else:
                print("Event Response could not be updated")
                return False


def async_mark_mail_read(userid, email, oauth_credentials):
    account = authenticate(userid, oauth_credentials)
    mailbox = account.mailbox()

    mail = mailbox.get_message(object_id=email.object_id)
    status = mail.mark_as_read()
    if status is True:
        print("Mail marked read")
        return True
    else:
        print("Mail could not marked read")
        return False


def async_delete_event(userid, event, oauth_credentials):
    account = authenticate(userid, oauth_credentials)
    schedule = account.schedule()
    calendar = schedule.get_default_calendar()
    try:
        exist_event = calendar.get_event(event.object_id)
    except Exception as e:
        print('Event not found...!!')
        return False
    else:
        if exist_event.delete():
            print('Event deleted successfully...!!')
            print(' Going to delete the event from CAP system.....')
            event.is_deleted = True
            event.save()
            return True
        else:
            print('Event delete unsuccessfull')
            return False


def async_delete_attachment(userid, event, oauth_credentials, instance):
    account = authenticate(userid, oauth_credentials)
    schedule = account.schedule()
    calendar = schedule.get_default_calendar()
    try:
        exist_event = calendar.get_event(event.object_id)
    except Exception as e:
        print('Event not found...!!')
        return False
    else:
        log = OutlookLog.objects.get(id=instance.id)
        data = json.loads(log.request_info)
        exist_event.attachment_obj_id = data['attachment_id']
        if exist_event.deleteattachment():
            print('Event attachment deleted successfully...!!')
            print(' Going to delete the event from CAP system.....')
            Attachments.objects.filter(object_id=data['attachment_id'], event=event).delete()
            return True
        else:
            print('Event attachment delete unsuccessfull')
            return True


def remove_duplicate_mails(user, mail_folder, sync_end_date=None):
    # for folder in mail_folders:
    mail_to_remove = Email.objects.filter(user=user, object_id__isnull=True, folder=mail_folder, message_modified__lte=sync_end_date).update(is_deleted=True)
    print(mail_to_remove, ' mails deleted for user ', user.username, ' in folder ', mail_folder.folder_name)


def remove_outlook_deleted_mails(user, folder, mails, sync_start_date=None):
    print('\n')
    if sync_start_date:
        emails = Email.objects.filter(folder=folder, user=user, message_modified__gte=sync_start_date)
    else:
        emails = Email.objects.filter(folder=folder, user=user)
    # print('total emails in ',folder.folder_name, ' is ', emails.count())
    email_db_set = set(mail.object_id for mail in emails)
    email_server_set = set(mail.object_id for mail in mails)
    difference_in_mails = email_db_set - email_server_set

    print(len(email_db_set), '  db')
    print(len(email_server_set), '  server')
    print(len(difference_in_mails), '   difference')

    removed_mails = Email.objects.filter(object_id__in=difference_in_mails).update(is_deleted=True)
    print(removed_mails, 'mails deleted')


def get_mails_from_server(mailbox, mails, sync_start_date=None, sync_end_date=None):
    if sync_start_date:
        query = mailbox.new_query().on_attribute('lastModifiedDateTime').greater_equal(sync_start_date)
        if sync_end_date:
            query.chain('and').on_attribute('lastModifiedDateTime').less_equal(sync_end_date)
        mail_list = mails.get_messages(limit=10000, batch=500, query=query)
    else:
        mail_list = mails.get_messages(limit=10000, batch=500)

    return mail_list


@task(name="sync_mails_from_outlook_server")
def async_get_mails(instance, oauth_credentials, mail_folders):
    print('Syncing Mails....')
    account = authenticate(instance.user, oauth_credentials)
    mailbox = account.mailbox()
    query = None

    last_synced_obj = OutlookSync.objects.filter(user=instance.user, sync_category='2', status='3').exclude(
        id=instance.id).order_by('-id').first()
    sync_end_date = datetime.now()

    try:
        for folder in mail_folders:
            print("Syncing ", folder.folder_name)
            mails = mailbox.get_folder(folder_name=folder.folder_name)
        
            if mails.total_items_count != 0:
                if last_synced_obj:
                    last_sync_date = last_synced_obj.updated_time - timedelta(minutes=15)
                    mail_list = get_mails_from_server(mailbox, mails, sync_start_date=last_sync_date)
                else:
                    static_start = datetime(2021, 1, 1, 0, 0, 0, 0)  #Jan 1st 2021
                    mail_list = get_mails_from_server(mailbox, mails, sync_start_date=static_start)

                for mail in mail_list:
                    folder = MailFolder.objects.get(folder_id=mail.folder_id)
                    to = [rec.address for rec in mail._Message__to._recipients]
                    cc = [rec.address for rec in mail._Message__cc._recipients]
                    bcc = [rec.address for rec in mail._Message__bcc._recipients]
                    reply_to = [rec.address for rec in mail._Message__reply_to._recipients]
                    mail_delivery_requested = mail._Message__is_delivery_receipt_requested if mail._Message__is_delivery_receipt_requested else False

                    try:
                        mail_exist = Email.objects.get(object_id=mail.object_id)
                        print(mail._Message__subject, '   in db  ', mail._Message__created)
                    except Email.DoesNotExist:
                        print(mail._Message__subject, '       not in db  ', mail._Message__created)
                        created = Email.objects.create(user=instance.user, object_id=mail.object_id,
                                                       message_sender=mail._Message__sender.address,
                                                       message_subject=mail._Message__subject,
                                                       message_body=mail._Message__body, \
                                                       message_body_preview=mail._Message__body_preview, message_to=to,
                                                       message_is_read=mail._Message__is_read,
                                                       message_is_draft=mail._Message__is_draft, \
                                                       has_attachments=mail.has_attachments, message_cc=cc,
                                                       message_bcc=bcc, message_reply_to=reply_to, folder=folder,
                                                       conversation_id=mail.conversation_id, \
                                                       message_categories=mail._Message__categories,
                                                       message_is_read_receipt_requested=mail._Message__is_read_receipt_requested,
                                                       internet_message_id=mail.internet_message_id, \
                                                       message_is_delivery_receipt_requested=mail_delivery_requested,
                                                       meeting_message_type=mail._Message__meeting_message_type,
                                                       message_created=mail._Message__created, \
                                                       message_modified=mail._Message__modified,
                                                       message_recieved=mail._Message__received,
                                                       message_sent=mail._Message__sent)
                        
                        if folder.folder_name == 'Deleted Items':
                            created.message_is_deleted = True
                            created.save()
                        
                        if mail.has_attachments and mail.attachments.download_attachments():
                            dir_path = os.path.join(settings.MEDIA_ROOT, 'attachments', 'mail', str(created.id))
                            if not os.path.isdir(dir_path):
                                os.makedirs(dir_path)
                            for att in mail.attachments:
                                att_name = att.name.replace('/', '-').replace('\\', '')
                                if len(att_name) > 210:
                                    att_name = att_name[:210] + '.' + att_name.split('.')[-1]

                                if settings.IS_S3:
                                    file_save = att.save(location=dir_path, custom_name=att_name)
                                    if file_save:
                                        new_file_name = os.path.join('attachments', 'mail', str(created.id), att_name)
                                        _report_doc = File(open(os.path.join(settings.MEDIA_ROOT, new_file_name), mode='rb'))
                                        path = default_storage.save(att_name, _report_doc)
                                        created_att = Attachments.objects.create(email=created, attachments=path)
                                        os.remove(os.path.join(settings.MEDIA_ROOT, new_file_name))
                                else:
                                    file_save = att.save(location=dir_path, custom_name=att_name)
                                    if file_save:
                                        new_file_name = os.path.join('attachments', 'mail', str(created.id), att_name)
                                        print(new_file_name, ' ===')                                                                                
                                        created_att = Attachments.objects.create(email=created, attachments=new_file_name)
                            if settings.IS_S3:
                                # os.rmdir(dir_path)
                                shutil.rmtree(dir_path)
                    else:
                        mail_exist.message_is_read = mail._Message__is_read
                        mail_exist.message_is_draft = mail._Message__is_draft
                        mail_exist.folder = folder
                        mail_exist.message_modified = mail._Message__modified
                        mail_exist.message_created = mail._Message__created
                        mail_exist.message_sent = mail._Message__sent
                        mail_exist.message_recieved = mail._Message__received
                        mail_exist.conversation_id = mail.conversation_id
                        if folder.folder_name == 'Deleted Items':
                            mail_exist.message_is_deleted = True
                        mail_exist.save()

                        # TO DO -  Update attachments from outlook server to local in case of drafts here

                        if mail.has_attachments and mail.attachments.download_attachments():
                            exist_attach = Attachments.objects.filter(email=mail_exist).update(is_deleted=True)
                            dir_path = os.path.join(settings.MEDIA_ROOT, 'attachments', 'mail', str(mail_exist.id))
                            if not os.path.isdir(dir_path):
                                os.makedirs(dir_path)
                            for att in mail.attachments:
                                att_name = att.name.replace('/', '-').replace('\\', '')
                                if len(att_name) > 210:
                                    att_name = att_name[:210] + '.' + att_name.split('.')[-1]

                                if settings.IS_S3:
                                    file_save = att.save(location=dir_path, custom_name=att_name)
                                    if file_save:
                                        new_file_name = os.path.join('attachments', 'mail', str(mail_exist.id), att_name)
                                        _report_doc = File(open(os.path.join(settings.MEDIA_ROOT, new_file_name), mode='rb'))
                                        path = default_storage.save(att_name, _report_doc)
                                        created_att = Attachments.objects.create(email=mail_exist, attachments=path)
                                        os.remove(os.path.join(settings.MEDIA_ROOT, new_file_name))
                                else:
                                    file_save = att.save(location=dir_path, custom_name=att_name)
                                    if file_save:
                                        new_file_name = os.path.join('attachments', 'mail', str(mail_exist.id), att_name)
                                        created_att = Attachments.objects.create(email=mail_exist, attachments=new_file_name)

                            if settings.IS_S3:
                                # os.rmdir(dir_path)
                                shutil.rmtree(dir_path)
                                
            mails = mailbox.get_folder(folder_name=folder.folder_name)
            if last_synced_obj:
                last_sync_date = last_synced_obj.updated_time - timedelta(minutes=15)
                mail_list = get_mails_from_server(mailbox, mails, sync_start_date=last_sync_date)
                if mail_list:
                    remove_outlook_deleted_mails(instance.user, folder, mail_list, sync_start_date=last_sync_date)
            else:
                mail_list = get_mails_from_server(mailbox, mails)
                if mail_list:
                    remove_outlook_deleted_mails(instance.user, folder, mail_list)

            remove_duplicate_mails(instance.user, folder, sync_end_date=sync_end_date)
            print('\n\n')
        
    except Exception as e:
        print(e)
        return False, str(e), traceback.format_exc()
            
    return True, None, None

