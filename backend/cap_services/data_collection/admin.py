from django.contrib import admin
from .models import SurveyFormData, ClientInstrumentDocument

admin.site.register(SurveyFormData)

from auditlog.registry import auditlog

auditlog.register(SurveyFormData)
auditlog.register(ClientInstrumentDocument)
