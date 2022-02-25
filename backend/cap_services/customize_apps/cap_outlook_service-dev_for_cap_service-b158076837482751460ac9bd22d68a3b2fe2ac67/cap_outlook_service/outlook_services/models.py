from django.db import models
# from clients.models import CapBaseModel
from django.contrib.auth.models import User, Group
from django.contrib.postgres.fields import ArrayField
from django.core.files.storage import FileSystemStorage as server_storage
from django.conf import settings
import os
import pathlib


# Create your models here.


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


class MailFolder(CapBaseModel):
    class Meta:
        db_table = 'cap_outlook_service_mailfolder'

    folder_id = models.CharField(max_length=250, unique=True)
    parent_id = models.CharField(max_length=250, null=True, blank=True)
    folder_name = models.CharField(max_length=50, null=True, blank=True)
    user = models.ForeignKey(User, related_name='user_mail_folder', on_delete=models.CASCADE)


class Email(CapBaseModel):
    class Meta:
        db_table = 'cap_outlook_service_email'

    IMPORTANCE_LEVEL = [
        (1, 'low'),
        (2, 'normal'),
        (3, 'high')
    ]

    ACTIONS = [
        ('1', 'send'),
        ('2', 'reply'),
        ('3', 'reply_all'),
        ('4', 'forward')
    ]

    user = models.ForeignKey(User, related_name='user_email', on_delete=models.CASCADE)
    folder = models.ForeignKey(MailFolder, related_name='email_folder_id', on_delete=models.CASCADE, null=True,
                               blank=True)
    object_id = models.CharField(max_length=220, blank=True, null=True)
    message_created = models.DateTimeField(blank=True, null=True)
    message_modified = models.DateTimeField(blank=True, null=True)
    message_recieved = models.DateTimeField(blank=True, null=True)
    message_sent = models.DateTimeField(blank=True, null=True)
    message_subject = models.TextField(null=True, blank=True)
    message_body_preview = models.TextField(null=True, blank=True)
    message_body = models.TextField(null=True, blank=True)
    message_body_type = models.CharField(max_length=150, null=True, blank=True)

    message_sender = models.EmailField(max_length=120, null=True)
    message_to = ArrayField(models.EmailField(max_length=120), null=True, blank=True)
    message_cc = ArrayField(models.EmailField(max_length=120), blank=True, null=True)
    message_bcc = ArrayField(models.EmailField(max_length=120), blank=True, null=True)
    message_reply_to = ArrayField(models.EmailField(max_length=120), blank=True, null=True)

    message_categories = ArrayField(models.CharField(max_length=100), blank=True, null=True)
    message_importance = models.IntegerField(choices=IMPORTANCE_LEVEL, default=1)
    message_is_read = models.BooleanField(default=False)
    message_is_deleted = models.BooleanField(default=False)
    message_is_read_receipt_requested = models.BooleanField(default=False)
    message_is_delivery_receipt_requested = models.BooleanField(default=False)
    meeting_message_type = models.CharField(max_length=50, null=True)
    message_is_draft = models.BooleanField(default=False)
    conversation_id = models.CharField(max_length=220, null=True, blank=True)
    message_flag = models.BooleanField(default=False)
    internet_message_id = models.CharField(max_length=220, null=True, blank=True)
    has_attachments = models.BooleanField(default=False)

    reply_id = models.CharField(max_length=220, blank=True, null=True)
    mail_action = models.CharField(choices=ACTIONS, max_length=1, default='1')
    message_deleted_from = models.ForeignKey(MailFolder, related_name='deleted_from_folder', on_delete=models.CASCADE,
                                             null=True, blank=True)

    # @property
    # def attachment_list(self):
    #   """ setting as a read only field to avoid while POST request in DRF Serializer """
    #   attachments = Attachments.objects.filter(email_id=self.id)
    #   attachment_list = [attached_file.attachments.name for attached_file in attachments]
    #   return attachment_list


class Event(CapBaseModel):
    class Meta:
        db_table = 'cap_outlook_service_event'

    IMPORTANCE_LEVEL = [
        ('1', 'low'),
        ('2', 'normal'),
        ('3', 'high')
    ]

    SENSITIVITY_CHOICES = [
        ('1', 'normal'),
        ('2', 'personal'),
        ('3', 'private'),
        ('4', 'confidential')
    ]

    SHOW_AS_CHOICES = [
        ('1', 'free'),
        ('2', 'tentative'),
        ('3', 'busy'),
        ('4', 'oof'),
        ('5', 'workingElsewhere'),
        ('6', 'unknown')
    ]

    EVENT_TYPE_CHOICES = [
        ('1', 'singleInstance'),
        ('2', 'occurrence'),
        ('3', 'exception'),
        ('4', 'seriesMaster'),
    ]

    EVENT_STATUS_CHOICES = [
        ('1', 'organizer'),
        ('2', 'accepted'),
        ('3', 'declined'),
        ('4', 'tentative'),
        ('5', 'not_responded'),
    ]

    user = models.ForeignKey(User, related_name='user_event', on_delete=models.CASCADE)
    object_id = models.CharField(max_length=250, blank=True, null=True)
    # created_on = models.DateTimeField(auto_now_add=True)
    # modified_on = models.DateTimeField(auto_now=True)
    description = models.TextField(null=True, blank=True)
    subject = models.CharField(max_length=250, null=True, blank=True)
    event_start = models.DateTimeField(null=True, blank=True)
    event_end = models.DateTimeField(null=True, blank=True)
    importance = models.CharField(choices=IMPORTANCE_LEVEL, max_length=1, default='1')
    is_all_day = models.BooleanField(default=False)
    location = models.CharField(max_length=250, null=True, blank=True)
    is_remainder_on = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)
    remind_before_minutes = models.IntegerField(null=True)
    response_requested = models.BooleanField(default=False)
    organizer = models.CharField(max_length=250, null=True)
    show_as = models.CharField(choices=SHOW_AS_CHOICES, max_length=1, default='1')
    sensitivity = models.CharField(choices=SENSITIVITY_CHOICES, max_length=1, default='1')
    # attendees = ArrayField(models.EmailField(max_length=254))
    categories = ArrayField(models.CharField(max_length=70), null=True, blank=True)
    event_type = models.CharField(choices=EVENT_TYPE_CHOICES, max_length=1, default='1')
    ical_uid = models.CharField(max_length=250, null=True, blank=True)
    response_status = models.CharField(choices=EVENT_STATUS_CHOICES, max_length=1, default='1')
    response_time = models.DateTimeField(null=True, blank=True)
    is_recurring = models.BooleanField(default=False)
    recurrence_interval = models.CharField(max_length=10, null=True, blank=True)
    recurrence_days_of_week = ArrayField(models.CharField(max_length=10), null=True, blank=True)
    recurrence_end_date = models.DateTimeField(null=True, blank=True)


class Attendees(CapBaseModel):
    class Meta:
        db_table = 'cap_outlook_service_attendees'

    RESPONSES = [
        ('1', 'organizer'),
        ('2', 'accepted'),
        ('3', 'declined'),
        ('4', 'tentative'),
        ('5', 'not_responded'),
    ]

    event = models.ForeignKey(Event, related_name='attendees_event', on_delete=models.CASCADE)
    attendee = models.EmailField(max_length=254, null=True)
    response_status = models.CharField(choices=RESPONSES, max_length=1, default='5')
    # user =


class OutlookLog(CapBaseModel):
    class Meta:
        db_table = 'cap_outlook_service_outlooklog'

    LOG_TYPE = [
        ('1', 'calendar_instance'),
        ('2', 'mail_instance'),
        ('3', 'event_attach_remove')
    ]

    LOG_STATUS = [
        ('1', 'db_updated'),
        ('2', 'outlook_request_sent'),
        ('3', 'outlook_resposne_received')
    ]

    REQUEST_TYPE = [
        ('1', 'post'),
        ('2', 'put'),
        ('3', 'delete'),
        ('4', 'rsvp'),
        ('5', 'mark_read')
    ]

    user = models.ForeignKey(User, related_name='log_user', on_delete=models.CASCADE)
    email = models.ForeignKey(Email, related_name='log_email', on_delete=models.CASCADE, null=True, blank=True)
    event = models.ForeignKey(Event, related_name='log_event', on_delete=models.CASCADE, null=True, blank=True)
    request_info = models.TextField(null=True, blank=True)
    request_type = models.CharField(choices=REQUEST_TYPE, max_length=1, default='1')
    response_info = models.TextField(null=True, blank=True)
    log_type = models.CharField(choices=LOG_TYPE, max_length=1, default='2')
    status = models.CharField(choices=LOG_STATUS, max_length=1, default='1')
    # is_sync_request = models.BooleanField(default=False)


def get_upload_path(instance, filename):
    """ MUST FIGURE OUT HOW TO ADD USER ID INSTEAD OF EMAIL ID"""
    if instance.email_id:
        return 'attachments/mail/' + str(instance.email_id) + '/' + filename
    elif instance.event_id:
        return 'attachments/event/' + str(instance.event_id) + '/' + filename


class Attachments(CapBaseModel):
    class Meta:
        db_table = 'cap_outlook_service_attachments'

    email = models.ForeignKey(Email, related_name='attachment_email', on_delete=models.CASCADE, null=True, blank=True)
    event = models.ForeignKey(Event, related_name='attachment_event', on_delete=models.CASCADE, null=True, blank=True)
    attachments = models.FileField(max_length=250, upload_to=get_upload_path, null=True, blank=True)
    is_outlook_synced = models.BooleanField(default=False)
    object_id = models.CharField(max_length=250, blank=True, null=True)

    def update(self, *args, **kwargs):
        try:
            if settings.IS_S3:
                df = server_storage()
                full_path = os.path.join(df.base_location, self.attachments.name)
                pathlib.Path(os.path.split(full_path)[0]).mkdir(parents=True, exist_ok=True)
                df.save(self.attachments.name, self.attachments.open())
        except:
            print("No local save")
        super(Attachments, self).save(*args, **kwargs)


def get_token_upload_path(instance, filename):
    return 'tokens/' + str(instance.user.id) + '/' + filename


class OutlookCredentials(CapBaseModel):
    class Meta:
        db_table = 'cap_outlook_service_outlookcredentials'

    def __str__(self):
        return self.user.email

    user = models.ForeignKey(User, related_name='outlook_user', on_delete=models.CASCADE)
    client_id = models.CharField(max_length=256, null=True, blank=True)
    client_secret = models.CharField(max_length=256, null=True, blank=True)
    tenant_id = models.CharField(max_length=256, null=True, blank=True)
    token_path = models.FileField(upload_to=get_token_upload_path, null=True, blank=True)
    token_expiry = models.CharField(max_length=256, null=True, blank=True)


class OutlookSync(CapBaseModel):
    SYNC_TYPE = [
        ('1', 'events'),
        ('2', 'mails'),
        ('3', 'mail folder')
    ]

    LOG_STATUS = [
        ('1', 'db_updated'),
        ('2', 'sync_initiated'),
        ('3', 'sync_completed')
    ]

    user = models.ForeignKey(User, related_name='sync_user', on_delete=models.CASCADE)
    sync_category = models.CharField(choices=SYNC_TYPE, max_length=1, default='1')
    status = models.CharField(choices=LOG_STATUS, max_length=1, default='1')


class OutlookSyncErrorLog(CapBaseModel):
    SYNC_TYPE = [
        ('1', 'events'),
        ('2', 'mails'),
        ('3', 'mail folder')
    ]

    ERROR_CAT = [
        ('1', 'skipping cron'),
        ('2', 'error'),
        ('3', 'mail folder missing')
    ]
    user = models.ForeignKey(User, related_name='sync_log_user', on_delete=models.CASCADE)
    sync_category = models.CharField(choices=SYNC_TYPE, max_length=1, default='1')
    cron_start_time = models.DateTimeField(auto_now_add=True, verbose_name='Cron Start Time')
    error_category = models.CharField(choices=ERROR_CAT, max_length=1, default='1')
    error_message = models.TextField(null=True, blank=True)
    traceback = models.TextField(null=True, blank=True)
