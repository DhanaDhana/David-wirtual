from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from ...models import Staff
from django.contrib.contenttypes.models import ContentType


permissions = (
        ("dashboard_view", "DASHBOARD-VIEW"),
        ("filter_chart_with_advisor", "FILTER-CHART-WITH-ADVISOR"),
        ("client_management_view", "CLIENT-MANAGEMENT-VIEW"),
        ("client_add", "ADD-CLIENT"),
        ("client_edit", "EDIT-CLIENT"),
        ("clients_list_view", "LIST-CLIENT"),
        ("non_prospect_client_list_view", "LIST-NON-PROSPECT-LIST"),
        ("recently_added_client_list_view", "LIST-RECENTLY-ADDED-CLIENTS"),
        ("clients_added_by_me_list_view", "LIST-CLIENTS-ADDED-BY-ME"),
        
        ("client_profile_view", "CLIENT-PROFILE-VIEW"),
        ("product_add", "ADD-PRODUCT"),
        ("survey_form_status_view", "LIST-SURVEY-FORM-STATUSES"),
        ("pre_contracting_timeline_view", "LIST-PRE-CONTRACTING-TIMELINE"),
        ("atp_timeline_view", "LIST-ATP-TIMELINE"),
        ("post_contracting_timeline_view", "LIST-POST-CONTRACTING-TIMELINE"),
        
        ("survey_form_view", "SURVEY-FORM-VIEW"),
        ("survey_audio_record", "RECORD-SURVEY-DATA"),
        ("survey_audio_list", "LIST-SURVEY-RECORDINGS"),
        ("survey_audio_delete", "DELETE-SURVEY-RECORDINGS"),
        
        ("product_list_view", "PRODUCT-LIST-VIEW"),
        ("product_add", "ADD-PRODUCT"),
        ("loa_download", "DOWNLOAD-LOA"),
        ("signed_loa_upload", "UPLOAD-SIGNED-LOA"),
        ("email_bulk_send", "SEND-BULK-EMAIL"),
        ("reminder_email_send", "SEND-REMINDER-EMAIL"),
        ("provider_type_change", "CHANGE-PROVIDER-TYPE"),
        ("signed_loa_preview_view", "VIEW-SIGNED-LOA-PREVIEW"),
        ("data_extraction_file_upload", "UPLOAD-DATA-EXTRACTION-FILE"),
        
        ("calendar_view", "CALENDAR-VIEW"),
        ("event_create", "CREATE-EVENT"),
        ("event_cancel", "CANCEL-EVENT"),
        ("event_edit", "EDIT-EVENT"),
        ("event_respond", "RESPOND-TO-EVENT"),

        ("email_view", "MAIL-VIEW"),
        ("email_compose", "COMPOSE-MAIL"),
        ("email_delete", "DELETE-MAIL"),

        ("profile_settings_view", "PROFILE-SETTINGS-VIEW"),
        ("profile_settings_edit", "UPDATE-PROFILE-SETTINGS"),

        ("reset_password", "RESET-PASSWORD"),
        
        ("reminder_view", "REMINDERS-VIEW"),
        ("reminder_snooze", "SNOOZE-REMINDER"),
        ("reminder_remove_snooze", "REMOVE-REMINDER-SNOOZE-DATE"),
        
        ("list_task","LIST-TASKS"),
        ("task_details","TASK-DETAILS"),

        ("assign_task", "ASSIGN-TASK"),
        ("schedule_task_meeting","SCHEDULE-TASK-MEETING"),
        ("survey_form_edit", "SURVEY-FORM-EDIT"),

        ("add_advisor_comment", "ADD-ADVISOR-COMMENT"),
        ("update_dr_notes", "UPDATE-DR-NOTES"),
        ("generate_sr", "GENERATE-SR"),
        ("upload_sr", "UPLOAD-SR"),
        ("update_draft_recommendation_doc", "UPDATE-DRAFT-RECOMMENDATION-DOC"),
        ("create_task", "CREATE-TASK"),
        ("add_task_comments","ADD-TASK-COMMENTS"),
        ("draft_reccommendation_list_view","DRAFT-RECOMMENDATION-LIST-VIEW"),

        ( "click_pre_contracting_timeline", "CLICK-PRE-CONTRACTING-TIMELINE"),
        ( "click_atp_timeline", "CLICK-ATP-TIMELINE"),
        ( "click_post_contracting_timeline", "CLICK-POST-CONTRACTING-TIMELINE"),
        ( "delete_product", "DELETE-PRODUCT"),
        ( "checkbox_fca_guidelines", "CHECKBOX-FCA-GUIDELINES"),
        ( "checkbox_product_list", "CHECKBOX-PRODUCT-LIST"),
        ( "redirect_to_task_from_profile", "REDIRECT-TO-TASK-FROM-PROFILE"),
        ( "close_case_file", "CLOSE-CASE-FILE"),
        ( "edit_advisor_checklist", "EDIT-ADVISOR-CHECKLIST"),

        ( "is_advisor", "IS-ADVISOR"),
        ( "is_ops", "IS-OPS"),
        ( "is_administrator", "IS-ADMINISTRATOR"),
        ( "is_compliance", "IS-COMPLIANCE"),
        ( "is_superadmin", "IS-SUPERADMIN")

    )



class Command(BaseCommand):
    help = '''create user group   ----    ./manage.py initial_setup '''

    def handle(self, *args, **kw):
        ct = ContentType.objects.get_for_model(Staff)
        
        #Adding Custom Permissions
        for permission in permissions:
            perm, created = Permission.objects.get_or_create(
                name=permission[1], codename=permission[0], content_type=ct
            )
            if created:
                print('Permission {} added'.format(permission[1]))

        print('\n')

        #Adding user groups and assigining related permissions
        user_group_list = ['Admin', 'Advisor', 'Client', 'Administrator', 'Ops', 'Compliance', 'SuperAdmin']
        permission = Permission.objects.filter(content_type=ct)
        for group in user_group_list:
            new_group, created = Group.objects.get_or_create(name=group)

            assigned_permission_list=[]
            assigned_permissions = new_group.permissions.filter(content_type=ct)
            if assigned_permissions:
                assigned_permission_list = [p.codename for p in assigned_permissions]

            # if created:
            if group == 'Advisor':
                
                excluded_permissions = [ "filter_chart_with_advisor", "is_administrator", "is_compliance", "is_ops", "is_superadmin", "redirect_to_task_from_profile", "schedule_task_meeting", "close_case_file"]
                for perms in permission:
                    if perms.codename not in assigned_permission_list and perms.codename not in excluded_permissions:
                        new_group.permissions.add(perms)
                print("Permissions added for Advisor User Group")
            
            elif group == 'Ops':
              
                excluded_permissions = [ "checkbox_fca_guidelines", "client_add", "close_case_file", "is_administrator", "is_compliance", "is_advisor", "is_superadmin"]
                for perms in permission:
                    if perms.codename not in assigned_permission_list and perms.codename not in excluded_permissions:
                        new_group.permissions.add(perms)
                print("Permissions added for Ops User Group")
            
            elif group == 'Administrator':
               
                excluded_permissions = [ "client_add", "checkbox_fca_guidelines", "is_advisor", "is_compliance", "is_ops", "is_superadmin", "redirect_to_task_from_profile", "schedule_task_meeting" ]
                for perms in permission:
                    if perms.codename not in assigned_permission_list and perms.codename not in excluded_permissions:
                        new_group.permissions.add(perms)
                print("Permissions added for Administrator User Group")
            
            elif group == 'Compliance':
               
                excluded_permissions = [ "checkbox_fca_guidelines", "client_add", "close_case_file", "is_administrator", "is_ops", "is_advisor", "is_superadmin", "redirect_to_task_from_profile", "schedule_task_meeting"]
                for perms in permission:
                    if perms.codename not in assigned_permission_list and perms.codename not in excluded_permissions:
                        new_group.permissions.add(perms)
                print("Permissions added for Compliance User Group")
            
            elif group == 'SuperAdmin':
                excluded_permissions = [ "assign_task", "checkbox_fca_guidelines", "client_add", "close_case_file", "is_administrator", "is_ops", "is_advisor", "is_compliance", "redirect_to_task_from_profile", "schedule_task_meeting" ]
                for perms in permission:
                    if perms.codename not in assigned_permission_list and perms.codename not in excluded_permissions:
                        new_group.permissions.add(perms)
                print("Permissions added for SuperAdmin User Group")


        self.stdout.write(self.style.SUCCESS('Successfully created User Groups with permissions'))