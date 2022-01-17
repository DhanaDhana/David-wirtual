from django.contrib.auth.models import User
from djongo import models


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
    '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)'''
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
    component_type = models.CharField(max_length=250, blank=True)
    label_choice = models.ArrayField(model_container=LabelChoices, blank=True)
    max_length = models.PositiveIntegerField(blank=True)
    min_length = models.PositiveIntegerField(default=0)
    mapfield_to = models.JSONField(blank=True,null=True)  # to handle prefetching
    has_local_data = models.BooleanField(default=False)
   



class SubLabelIndexData(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.id

    index = models.PositiveIntegerField(blank=True)
    sub_label_data = models.ArrayField(model_container=SubLabelData, blank=True)


