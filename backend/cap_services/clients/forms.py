from django.forms import ModelForm
from .models import Staff
from django.contrib.admin.widgets import FilteredSelectMultiple, RelatedFieldWidgetWrapper
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group, Permission


class GroupMenuForm(ModelForm):

    class Meta:
        model = Group
        fields = '__all__'

    def __init__(self, group_id=None, *args, **kwargs):
        super(GroupMenuForm, self).__init__(*args, **kwargs)
        ct = ContentType.objects.get_for_model(Staff)
        
        self.fields['permissions'].widget = RelatedFieldWidgetWrapper(
            FilteredSelectMultiple(('permissions'), False,),
            Group._meta.get_field('permissions').remote_field,
            self.admin_site, can_add_related=False)
        if group_id:
            group = Group.objects.get(name=group_id['name'])
            perms_list = group.permissions.all()
            perms_list = [perms.id for perms in perms_list]
            self.fields['permissions'].choices = Permission.objects.filter(id__in=perms_list).values_list('id', 'name')
        else:
            perms_list = []
            self.fields['permissions'].choices = Permission.objects.filter(content_type=ct).values_list('id', 'name')
