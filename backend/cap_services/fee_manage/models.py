from django.db import models
from datetime import datetime
from clients.models import Instrument
from clients.models import Provider,InstrumentsRecomended
from clients.models import Client
from clients.models import Staff
from clients.models import CapBaseModel



class Provider_StatementInfo(CapBaseModel):
    """
    Provider_StatementInfo description
    """  
    
    policy_number=models.CharField(max_length=15, null=True, blank=True)
    product = models.ForeignKey(Instrument, related_name='instrument_product_type', on_delete=models.CASCADE)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    advisor = models.ForeignKey(Staff, on_delete=models.CASCADE)
    initial_fee = models.FloatField(default=0,blank=True,null=True)
    ongoing_fee = models.FloatField(default=0,blank=True,null=True)
    total_monthly_fee = models.FloatField(default=0,blank=True,null=True)
    month_year = models.DateField( null=True, blank=True)


    def _str_(self):
        return self.product.instrument_name
    
class Suggested_Reasons(CapBaseModel):
    REASON_NAMES=[
        ('1', 'Dummy Reason 1'),
        ('2', 'Dummy Reason 2'),
        ('3', 'Dummy Reason 3'),
        ('4', 'Dummy Reason 4'),
        ('5', 'Others')
    ]
    reason_name = models.CharField(max_length=5, choices=REASON_NAMES, null=True)
    reason_description = models.CharField(max_length=12, null=True, blank=True)

    def __str__(self):
        return self.get_reason_name_display()


class Income_Issued(CapBaseModel):
    ISSUED_TYPES = [
        ('1', 'Monthly_Issued'),
        ('2', 'Pending_Issued')
    ]
    ACCOUNT_TYPES=[
        ('1', 'Suspence_Account'),
        ('2', 'Writtenoff_Account')
    ]
    INCOME_TYPES=[
        ('1', 'Initial_income'),
        ('2', 'Ongoing_income')
    ]

    statement=models.ForeignKey(Provider_StatementInfo,on_delete=models.CASCADE)
    instrument_recommended=models.ForeignKey(InstrumentsRecomended,on_delete=models.CASCADE)
    issued_type=models.CharField(max_length=3, choices=ISSUED_TYPES)
    account_type=models.CharField(max_length=3, choices=ACCOUNT_TYPES)
    manually_matched =models.BooleanField(default=False)
    income_type=models.CharField(max_length=3, choices=INCOME_TYPES)
    amount =models.FloatField(default=0,blank=True,null=True)
    suggested_reason=models.ForeignKey(Suggested_Reasons,on_delete=models.CASCADE)
    advisor_remarks=models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.issued_type
