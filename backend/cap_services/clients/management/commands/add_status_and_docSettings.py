from django.core.management.base import BaseCommand
from ...models import DocumentSetting, StatusCollection

# Sample command : python manage.py add_status_and_docSettings


class Command(BaseCommand):
    help = '--- Create StatusCollection and  DocumentSettings records ---'

    def handle(self, *args, **kwargs):
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.1',defaults={'status_name': '1'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.2', defaults={'status_name': '1'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.3', defaults={'status_name': '21'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.4', defaults={'status_name': '2'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.5', defaults={'status_name': '2'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.6', defaults={'status_name': '2'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.7', defaults={'status_name': '2'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.8', defaults={'status_name': '2'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.9', defaults={'status_name': '27'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.10', defaults={'status_name': '27'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.11', defaults={'status_name': '3'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.12', defaults={'status_name': '3'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.13', defaults={'status_name': '4'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.14', defaults={'status_name': '4'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.15', defaults={'status_name': '5'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.16', defaults={'status_name': '5'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.17', defaults={'status_name': '6'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.18', defaults={'status_name': '6'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.19', defaults={'status_name': '7'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.20', defaults={'status_name': '8'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.21', defaults={'status_name': '8'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.22', defaults={'status_name': '9'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.23', defaults={'status_name': '9'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.24', defaults={'status_name': '10'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.25', defaults={'status_name': '10'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.26', defaults={'status_name': '10'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.27', defaults={'status_name': '11'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.28', defaults={'status_name': '11'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.29', defaults={'status_name': '12'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.30', defaults={'status_name': '12'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.31',defaults={'status_name': '13'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.32', defaults={'status_name': '13'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.34', defaults={'status_name': '15'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.49', defaults={'status_name': '7'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.50', defaults={'status_name': '9'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.51', defaults={'status_name': '9'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.52', defaults={'status_name': '11'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.53', defaults={'status_name': '11'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.54', defaults={'status_name': '12'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.55', defaults={'status_name': '12'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.56', defaults={'status_name': '21'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.57', defaults={'status_name': '23'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.58', defaults={'status_name': '22'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.59',defaults={'status_name': '26'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.60',defaults={'status_name': '26'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.61',defaults={'status_name': '25'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.62',defaults={'status_name': '25'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.63',defaults={'status_name': '3'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.64',defaults={'status_name': '4'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.65',defaults={'status_name': '5'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.67',defaults={'status_name': '25'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.68',defaults={'status_name': '26'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.69',defaults={'status_name': '27'}, )
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.70', defaults={'status_name': '3'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.71', defaults={'status_name': '19'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.72', defaults={'status_name': '20'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.73', defaults={'status_name': '20'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='1.81',defaults={'status_name': '13'}, )
        
        status_obj, status_created = StatusCollection.objects.update_or_create(status='2.1', defaults={'status_name': '29'},)
        status_obj, status_created = StatusCollection.objects.update_or_create(status='2.2', defaults={'status_name': '29'},)


        docset_obj_1, obj_created_1 = DocumentSetting.objects.get_or_create(type='1')
        docset_obj_1.max_size_limit = '5242880'  # 5MB
        docset_obj_1.allowed_format = '["pdf","jpeg","jpg","png"]'
        docset_obj_1.save()

        docset_obj_2, obj_created_2 = DocumentSetting.objects.get_or_create(type='2')
        docset_obj_2.max_size_limit = '5242880'  # 5MB
        docset_obj_2.allowed_format = '["csv",]'
        docset_obj_2.save()

        docset_obj_3, obj_created_3 = DocumentSetting.objects.get_or_create(type='3')
        docset_obj_3.max_size_limit = '5242880'  # 5MB
        docset_obj_3.allowed_format = '["pdf","jpeg","jpg","png"]'
        docset_obj_3.save()

        docset_obj_4, obj_created_4 = DocumentSetting.objects.get_or_create(type='4')
        docset_obj_4.max_size_limit = '5242880'  # 5MB
        docset_obj_4.allowed_format = '["pdf",]'
        docset_obj_4.save()

        docset_obj_5, obj_created_5 = DocumentSetting.objects.get_or_create(type='5')
        docset_obj_5.max_size_limit = '5242880'  # 5MB
        docset_obj_5.allowed_format = '["pdf",]'
        docset_obj_5.save()

        self.stdout.write(self.style.SUCCESS('Successfully created status and document settings'))


