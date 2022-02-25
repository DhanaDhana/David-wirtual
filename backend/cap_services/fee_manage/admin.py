from django.contrib import admin
from .models import Provider_StatementInfo,Suggested_Reasons,Income_Issued
# Register your models here.

admin.site.register(Provider_StatementInfo)
admin.site.register(Suggested_Reasons)
admin.site.register(Income_Issued)
