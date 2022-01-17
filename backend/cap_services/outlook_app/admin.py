from django.contrib import admin
from cap_outlook_service.outlook_services.models import MailFolder, Email, OutlookLog, Event, Attachments, OutlookCredentials, Attendees, OutlookSync




from auditlog.registry import auditlog

auditlog.register(MailFolder)
# auditlog.register(Email)
auditlog.register(OutlookLog)
auditlog.register(Attachments)
auditlog.register(Attendees)
# auditlog.register(OutlookSync)


class EmailAdmin(admin.ModelAdmin):
    date_hierarchy = 'create_time'
    list_display = ('create_time','message_sender','message_to', 'message_subject')
    list_per_page = 20

admin.site.unregister(Email) 
admin.site.register(Email, EmailAdmin)


class EventAdmin(admin.ModelAdmin):
    date_hierarchy = 'create_time'
    list_display = ('create_time','organizer','user', 'subject')
    list_per_page = 20

admin.site.unregister(Event) 
admin.site.register(Event, EventAdmin)