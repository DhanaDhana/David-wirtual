from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from ...models import TaskCollection

class Command(BaseCommand):
    help = '''create task collection   ----    ./manage.py initial_setup '''

    def handle(self, *args, **kw):    

        TASK_GROUPS =  {1:'Ops Lead', 3:'Compliance', 2:'Administrator', 4:'Final'}  
        TASK_LIST = { 
                        'Ops Lead': ['Task Verified', 'Meeting scheduled', 'Task Assigned', 'Task Reassigned', 'Meeting Cancelled', 'Meeting Re-scheduled'],
                        'Administrator': ['Update Client File', 'Generate FFR', 'Trigger KYC', 'Confirm KYC', 'Admin & Pre-compliance Checklist', 'Suitability Report Generation', 'Assign to Compliance Team'],
                        'Compliance': ['Case File Review', 'Compliance Checklist Review', 'Advisor & Admin Checklist Summary', 'Suitability Report Comparison', 'Approve Client File & Report'],
                        'Final': ['Compliance Team Review','Administrator Review', 'Advisor Review'] 
                    }
            
        for order, group in TASK_GROUPS.items():
            for task in TASK_LIST[group]:
                print(task , 'added')
                status_obj, task_created = TaskCollection.objects.update_or_create(task_name=task, task_group=group, group_order=order)

        self.stdout.write(self.style.SUCCESS('Successfully created Task Collections'))