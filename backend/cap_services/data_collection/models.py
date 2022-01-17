
from django.contrib.auth.models import User
from djongo import models
from clients.models import Client
from .nested_label_models import SubLabelIndexData as nestedLabelIndex
from .nested_label_models import SubLabelData as nestedLabelData


class ClientData(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.client_id
    
    client_id = models.PositiveIntegerField(blank=True)
    client_name = models.CharField(max_length=250, blank=True)
    client_email = models.CharField(max_length=250, blank=True)



class AdvisorData(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.advisor_id
    
    advisor_id = models.PositiveIntegerField(blank=True)
    advisor_name = models.CharField(max_length=250, blank=True)
    advisor_email = models.CharField(max_length=250, blank=True)


class CategoryData(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.category_id

    category_id = models.PositiveIntegerField(blank=True)
    category_name = models.CharField(max_length=250, blank=True)
    category_slug_name = models.CharField(max_length=300, blank=True)


class LabelChoices(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.key

    id = models.CharField(max_length=100, blank=True)
    option = models.TextField(null=True, blank=True)


class SubLabelData(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.id

    label_id = models.PositiveIntegerField(blank=True)
    label = models.CharField(max_length=250, blank=True)
    label_slug = models.CharField(max_length=300, blank=True)
    field_name = models.CharField(max_length=250, blank=True)  # new
    is_mandatory = models.BooleanField(default=False)#new
    search_api_url = models.CharField(max_length=300, null=True,blank=True)
    answer = models.TextField(blank=True)
  
    answer_parent = models.JSONField(blank=True,null=True)
    value_type = models.CharField(max_length=100, blank=True, null=True)  # new
    response_required = models.BooleanField(default=True)
    component_type = models.CharField(max_length=250, blank=True)
    label_choice = models.ArrayField(model_container=LabelChoices, blank=True)
    max_length = models.PositiveIntegerField(null=True, blank=True)
    min_length = models.PositiveIntegerField(null=True, blank=True)
    
    mapfield_to =models.JSONField(blank=True,null=True)
    has_local_data = models.BooleanField(default=False)
    has_sublabels = models.BooleanField(default=False)
    is_repeat = models.BooleanField(default=False)
    sub_labels = models.ArrayField(model_container=nestedLabelIndex, blank=True)



class SubLabelIndexData(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.id

    index = models.PositiveIntegerField(blank=True)
    sub_label_data = models.ArrayField(model_container=SubLabelData, blank=True)


class LabelData(models.Model):
    class Meta:
        
        abstract = True

    def __str__(self):
        return self.label

    label_id = models.PositiveIntegerField(blank=True)
    label_parent = models.PositiveIntegerField(blank=True)
    label = models.CharField(max_length=250, blank=True)
    label_slug = models.CharField(max_length=300, blank=True)
    field_name = models.CharField(max_length=250, blank=True)#new
    is_mandatory = models.BooleanField(default=False)#new
    search_api_url = models.CharField(max_length=300, null=True, blank=True)

    answer = models.TextField(blank=True)

    answer_parent=models.JSONField(blank=True,null=True)
    response_required=models.BooleanField(default=True)
    value_type = models.CharField(max_length=100, blank=True, null=True)  # new
    has_sublabels = models.BooleanField(default=False)
    component_type = models.CharField(max_length=250, blank=True)
    label_choice = models.ArrayField(model_container=LabelChoices, blank=True)
    max_length = models.PositiveIntegerField(blank=True)
    min_length = models.PositiveIntegerField(default=0)
    is_repeat = models.BooleanField(default=False)

    mapfield_to = models.JSONField(blank=True, null=True)
    has_local_data = models.BooleanField(default=False)
    sub_labels = models.ArrayField(model_container=SubLabelIndexData, blank=True)


class SubcategoryData(models.Model):
    class Meta:
       
        abstract = True

    def __str__(self):
        
        return self.subcategory_name

    subcategory_id = models.PositiveIntegerField(blank=True)
    subcategory_name = models.CharField(max_length=150, blank=True)
    subcategory_slug_name=models.CharField(max_length=150, blank=True)
    subcategory_data = models.ArrayField(model_container=LabelData, blank=True)




class SurveyFormData(models.Model):
    class Meta:
        app_label = 'data_collection'

    client_id = models.PositiveIntegerField(blank=True)
    client = models.EmbeddedField(model_container=ClientData, blank=True)
    advisor_id = models.PositiveIntegerField(blank=True)
    advisor = models.EmbeddedField(model_container=AdvisorData, blank=True)
    category_id = models.PositiveIntegerField(blank=True)
    category = models.EmbeddedField(model_container=CategoryData, blank=True)
    form_data = models.ArrayField(model_container=SubcategoryData, blank=True)


    is_deleted = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='Created Time')
    updated_time = models.DateTimeField(auto_now=True, verbose_name='Updated Time')

    objects = models.DjongoManager()

    def atr_values_is_updated(self, new_list):
        is_updated = False
        for subcategory in self.form_data:
            if subcategory['subcategory_slug_name'] == 'attitude_to_risk_29':
                old_list=subcategory['subcategory_data']
        
        diff = [i for i in old_list + new_list if i not in old_list or i not in new_list]
        result = len(diff) == 0
        if not result:
            is_updated = True
        return is_updated


    def update_client_profile(self, profile_data):
        for subcategory in profile_data:
            label_list = subcategory['subcategory_data']
            
            if subcategory['subcategory_slug_name'] == "basic_info_8":
                for label in label_list:
                    if (label['label_slug'] == 'name_17'):
                        name = label['answer']
                        print("name",name)
                        if name is not None and name != "":
                            
                            name_list=name.split()
                            first_name = name_list[0]
                            last_name = ' '.join(string for string in name_list[1:])
                        else:
                            first_name=""
                            last_name=""
                       
            if subcategory['subcategory_slug_name'] =='contact_details_10':
                for label in label_list:
                    if (label['label_slug'] == 'phone_number__1_24'):
                        phone = label['answer']
                    
                    if (label['label_slug'] == 'email_26'):
                        email = label['answer']

        User.objects.filter(client__id =self.client_id).update(first_name=first_name,last_name=last_name,email=email,username=email)
        Client.objects.filter(id=self.client_id).update(phone_number=phone,is_survey_updated=True)


class ClientInstrumentDocument(models.Model):
    class Meta:
        app_label = 'data_collection'
    DOC_STATUS = [
            ('failed', 'failed'),
            ('initiated', 'initiated'),
            ('completed', 'completed'),
    ]
    _id = models.ObjectIdField()
    client_id = models.PositiveIntegerField(null=True,blank=True)
    instrument_id = models.PositiveIntegerField(null=True,blank=True) 
    client_instrument_id = models.PositiveIntegerField(null=True,blank=True) #refernces ClientInstrumentInfo id
    document_path = models.TextField(null=True,blank=True)
    status  = models.CharField(max_length=1, blank=False, default='0', choices=DOC_STATUS)

    is_deleted = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='Created Time')
    updated_time = models.DateTimeField(auto_now=True, verbose_name='Updated Time')
    objects = models.DjongoManager()


class InstrumentExtractedData(models.Model):
    class Meta:
        app_label = 'data_collection'
    _id = models.ObjectIdField()
    client_instrumentinfo_id = models.IntegerField(null=True,blank=True)
    instrumentdocument_id = models.CharField(blank=False, max_length=255, null=False)
    remarks = models.TextField(null=True,blank=True)
    extracted_doc_path = models.TextField(null=True,blank=True)
    extracted_data =  models.TextField(null=True,blank=True)
    extracted_table = models.TextField(null=True,blank=True)
   

    is_deleted = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='Created Time')
    updated_time = models.DateTimeField(auto_now=True, verbose_name='Updated Time')
    objects = models.DjongoManager()


    def __str__(self):
        return self.client_instrumentinfo_id


