from django.contrib.auth import models
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Provider_StatementInfo,Income_Issued
from clients.models import Staff

class ChoiceField(serializers.ChoiceField):

    def to_representation(self, obj):
        if obj == '' and self.allow_blank:
            return obj
        return self._choices[obj]

    def to_internal_value(self, data):
        # To support inserts with the value
        if data == '' and self.allow_blank:
            return ''

        for key, val in self._choices.items():
            if val == data:
                return key
        self.fail('invalid_choice', input=data)
        
class userSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('id','first_name','last_name','email','is_staff','date_joined','is_superuser','is_active')
        
class SpStatementInfoSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Provider_StatementInfo
        fields = ('product','provider','client','advisor','initial_fee','ongoing_fee','total_monthly_fee','month_year')
        
        # depth=2
        
class Income_IssuedSerializer(serializers.ModelSerializer):
    
    income_type = ChoiceField(choices=Income_Issued.INCOME_TYPES)
    
    class Meta:
        model = Income_Issued
        fields = ('statement','instrument_recommended','issued_type','account_type','manually_matched','income_type','amount','suggested_reason','advisor_remarks')
        
        # def get_suggested_reason(self,obj):
        #     return obj.get_suggested_reason_display()
        
        # depth=2