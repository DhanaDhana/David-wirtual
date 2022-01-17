from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CategoryLabel, ClientInstrumentInfo, CategoryAndSubCategory,\
      ClientTask, StatusCollection, CategorySummary, Reminder, Staff,\
      InstrumentsRecomended,DraftReccomendation,DraftCheckList,ClientCheckList,ClientRecommendationNotification

from .checklist import update_or_create_checklist,delete_checklist
from .utils import add_activity_flow, pending_status_save, remove_ilustration_checklist
from data_collection.models import *
import re
import datetime
from .middleware.request_middleware import RequestUserMiddleware 

@receiver(post_save, sender=Client)
def create_client_status(sender, instance,created, **kwargs):
       
    if instance.is_deleted:
        print("instance deleted")
        
    else:
        client = Client.objects.get(id=instance.id)

        if created:
           
            try:
                client1=ClientData(client_id=instance.id,client_name=instance.user.first_name,client_email=instance.user.email)
                client_advisor=instance.created_by
                advisor=AdvisorData(advisor_id=client_advisor.id,advisor_name=client_advisor.first_name,advisor_email=client_advisor.email)

                categories=CategoryAndSubCategory.objects.filter(parent=None).order_by('category_order')
                for category in categories:
                    print(category.id,category.category_name)
                    categery=CategoryData(category_id=category.id,category_name=category.category_name,category_slug_name=category.category_slug_name)
                    child_categories=CategoryAndSubCategory.objects.filter(parent=category).order_by('category_order') 
                    form_data_list=[]
                    for childcategory in child_categories:
                        questions = CategoryLabel.objects.filter(category=childcategory,parent=None).order_by('order_number')
                      
                        label_data_list=[]
                        for question in questions:

                            child_questions=CategoryLabel.objects.filter(parent=question).order_by('order_number')
                            has_child_question = False
                            sub_label_index_list=[]
                            sub_label_data=[]
                            for child_question in child_questions:
                               
                                nested_child_questions = CategoryLabel.objects.filter(parent=child_question).order_by('order_number')
                                nested_sub_label_index_list=[]
                                has_nested_child_question=False
                                nested_sub_label_data = []
                                for nested_child_question in nested_child_questions:
                                   
                                    feeild_name = (str(childcategory.category_name) + '_' + nested_child_question.label+"_"+str(nested_child_question.id)).lower().replace(" ","_")
                                    feeild_name = re.sub('[^a-zA-Z0-9 \n\.]', '_', feeild_name)
                                    nested_label_slug=(re.sub('[^a-zA-Z0-9 \n\.]', '_', (nested_child_question.label_slug.lower().replace(" ","_"))))+"_"+str(nested_child_question.id)
                                    labaal_choice_list = []
                                    for choice in nested_child_question.label_choice:
                                        labaal_choice = LabelChoices(id=choice, option=choice)
                                        labaal_choice_list.append(labaal_choice.__dict__)
                                    
                                    if (nested_child_question.answer_parent is None):
                                        nested_child_question.answer_parent = []

                                    nested_map_field_to = []
                                    if (nested_child_question.mapfield_to):

                                        queryset = nested_child_question.mapfield_to.all()
                                        for item in queryset:

                                            nested_mapfield_to = str(item.category.category_name + '_' + item.label + '_'+str(item.id)).lower().replace(" ", "_")
                                            nested_map_field_to.append(re.sub('[^a-zA-Z0-9 \n\.]', '_', nested_mapfield_to))

                                    nested_sub_question = SubLabelData(label_id=nested_child_question.id,label=nested_child_question.label,label_slug=nested_label_slug, answer='',answer_parent=nested_child_question.answer_parent,

                                                                value_type=nested_child_question.get_value_type_display(),component_type=nested_child_question.get_component_type_display(),
                                                                search_api_url=nested_child_question.search_api_url, field_name=feeild_name,\
                                                                is_mandatory=nested_child_question.is_mandatory,label_choice=labaal_choice_list,
                                                                max_length=nested_child_question.max_len,min_length=nested_child_question.min_len,
                                                                has_local_data=nested_child_question.has_local_data,mapfield_to=nested_map_field_to)

                                    nested_sub_label_data.append(nested_sub_question.__dict__)
                                    has_nested_child_question = True
                                
                                if nested_sub_label_data:
                                    nested_sub_label_index = SubLabelIndexData(index=0, sub_label_data=nested_sub_label_data)
                                    nested_sub_label_index_list.append(nested_sub_label_index.__dict__)
                               
                                feild_name=(str(childcategory.category_name)+'_'+child_question.label+"_"+str(child_question.id)).lower().replace(" ", "_")
                                feild_name = re.sub('[^a-zA-Z0-9 \n\.]', '_', feild_name)
                                child_label_slug = (re.sub('[^a-zA-Z0-9 \n\.]', '_',(child_question.label_slug.lower().replace(" ","_")))) + "_" + str(child_question.id)
                                labal_choice_list = []
                                for choice in child_question.label_choice:
                                    labal_choice = LabelChoices(id=choice, option=choice)
                                    labal_choice_list.append(labal_choice.__dict__)
                               
                                if (child_question.answer_parent is None):
                                    child_question.answer_parent = []
                                child_map_field_to = []

                                if (child_question.mapfield_to):
                                    queryset = child_question.mapfield_to.all()
                                    for item in queryset:
                                        child_mapfield_to = str(item.category.category_name + '_' + item.label+ '_'+str(item.id)).lower().replace(" ", "_")
                                       
                                        child_map_field_to.append(re.sub('[^a-zA-Z0-9 \n\.]', '_', child_mapfield_to))



                                sub_question=SubLabelData(label_id=child_question.id,label=child_question.label,label_slug=child_label_slug, answer='',answer_parent=child_question.answer_parent,value_type=child_question.get_value_type_display(),

                                                          component_type=child_question.get_component_type_display(),search_api_url=child_question.search_api_url,response_required=child_question.response_required, \
                                                            field_name=feild_name,is_mandatory=child_question.is_mandatory,label_choice=labal_choice_list,has_sublabels=has_nested_child_question,is_repeat=child_question.is_repeat,\
                                                          max_length=child_question.max_len,min_length=child_question.min_len,has_local_data = child_question.has_local_data,mapfield_to=child_map_field_to,\
                                                        sub_labels=nested_sub_label_index_list)

                                sub_label_data.append(sub_question.__dict__)
                                has_child_question = True

                            if sub_label_data:
                                sub_label_index=SubLabelIndexData(index=0, sub_label_data=sub_label_data)
                                sub_label_index_list.append(sub_label_index.__dict__)#only 0###rest needs to be filled dynamically
                            
                            field_name=(str(childcategory.category_name+'_'+question.label+"_"+str(question.id))).lower().replace(" ", "_")
                            field_name=re.sub('[^a-zA-Z0-9 \n\.]', '_', field_name)
                            label_slug = (re.sub('[^a-zA-Z0-9 \n\.]', '_',(question.label_slug.lower().replace(" ","_")))) + "_" + str(question.id)
                            label_choice_list=[]
                            for choice in question.label_choice:
                                label_choice=LabelChoices(id=choice,option=choice)
                                label_choice_list.append(label_choice.__dict__)
                           
                            if(question.answer_parent is None):
                                question.answer_parent=[]
                            label_map_field_to =[]
                            if(question.mapfield_to):
                                queryset=question.mapfield_to.all()
                                for item in queryset:
                                    label_mapfield_to=str(item.category.category_name+'_'+item.label+ '_'+str(item.id)).lower().replace(" ", "_")
                                    label_map_field_to.append(re.sub('[^a-zA-Z0-9 \n\.]', '_', label_mapfield_to))
                            answer=''
                            if(question.label_slug=='Name'):
                                answer=client.user.first_name+" "+client.user.last_name
                            elif(question.label_slug=='Email'):
                                answer=client.user.email
                            elif(question.label_slug == 'Phone Number  1'):
                                answer = client.phone_number

                            label_data=LabelData(label_id=question.id,label_parent=question.parent, label=question.label, label_slug=label_slug,answer=answer,answer_parent=question.answer_parent,

                                                 value_type=question.get_value_type_display(),response_required=question.response_required,search_api_url=question.search_api_url,
                                    has_sublabels=has_child_question,is_mandatory=question.is_mandatory ,\
                                    component_type=question.get_component_type_display(),field_name=field_name,has_local_data = question.has_local_data,\
                                    max_length=question.max_len,min_length=question.min_len,label_choice=label_choice_list,mapfield_to=label_map_field_to ,\
                                    is_repeat=question.is_repeat, sub_labels=sub_label_index_list)

                            label_data_list.append(label_data.__dict__)
                           
                        form_data=SubcategoryData(subcategory_id=childcategory.id,subcategory_name=childcategory.category_name,subcategory_slug_name=childcategory.category_slug_name, subcategory_data=label_data_list)
                        form_data_list.append(form_data.__dict__)

                    SurveyFormData.objects.create(client_id=client.id,client=client1.__dict__,advisor_id=client_advisor.id,advisor=advisor.__dict__,category_id=category.id,category=categery.__dict__,form_data = form_data_list)
                    print("survey form created")
                    try:
                        print("category is",category.category_name)
                        pending_status=None
                        if(category.category_slug_name=='personal_information_7'):
                            print("inside personal")
                            pending_status = StatusCollection.objects.get(status='1.12')  #surveyform pending status
                        elif(category.category_slug_name=='occupation_info_11'):
                            print("inside occupatn")
                            pending_status = StatusCollection.objects.get(status='1.14')  #surveyform pending status
                        elif(category.category_slug_name=='income___expenditure_summary_14'):
                            print("inside income")
                            pending_status = StatusCollection.objects.get(status='1.16')  #surveyform pending status
                        elif (category.category_slug_name == 'net_worth_summary_21'):
                            print("inside ntwrth")
                            pending_status = StatusCollection.objects.get(status='1.61')  # surveyform pending status
                        elif (category.category_slug_name == 'plans___atr_27'):
                            print("inside pln&Atr")
                            pending_status = StatusCollection.objects.get(status='1.60')  # surveyform pending status
                        if pending_status:
                            pending_status_save( pending_status=pending_status,client_id=client.id)
                    except Exception as e:
                        print("survey form reminder errors")
                        print(str(e))


                    days_remaining=str(category.allowed_days)+" days remaining"
                    CategorySummary.objects.create(client=client, category=category,days_remaining=days_remaining)

            except Exception as e:
                print(str(e))


@receiver(post_save, sender=ClientInstrumentInfo)
def create_client_instrument_status(sender, instance,created, **kwargs):
    client_instrument = ClientInstrumentInfo.objects.get(id=instance.id)
    if instance.is_deleted:
        print("instance deleted")
        
    else:
       
        #TO DO any change related with data extraction ??
        if instance.is_recommended==False:
            ###clones deletion##
            ClientInstrumentInfo.objects.filter(client=instance.client, is_recommended=True,parent=instance, is_active=True).update(is_deleted=True)
            InstrumentsRecomended.objects.filter(client_instrumentinfo__client=instance.client,client_instrumentinfo__parent=instance).update(is_deleted=True)
            ClientCheckList.objects.filter(client=instance.client,client_instrument__parent=instance).update(is_deleted=True)
            #parent deletion
            instrument_recomended_obj = InstrumentsRecomended.objects.filter(client_instrumentinfo=instance.id,client_instrumentinfo__client=instance.client).first()
            if instrument_recomended_obj:
                #removing documents related to client instrument (except LOA response doc)
                ClientInstrumentInfo.objects.filter(id=instrument_recomended_obj.client_instrumentinfo.id).update(fund_research=None, critical_yield=None, illustration=None, app_summary=None, weighted_average_calculator=None)
                instrument_recomended_obj.is_deleted=True
                instrument_recomended_obj.save()
                remove_ilustration_checklist(instrument_recomended_obj)

                #Delete DraftReccomendation if no entry in InstrumentsRecomended
            instrument_obj = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=instance.client).first()
            if not instrument_obj:
                draft_recommendation_obj = DraftReccomendation.objects.filter(client=instance.client, is_active=True).first() 
                if draft_recommendation_obj:
                    draft_recommendation_obj.is_deleted=True  
                    draft_recommendation_obj.save()

        thread_local = RequestUserMiddleware.thread_local
        if hasattr(thread_local, 'current_user'):
            request_user = thread_local.current_user
            add_activity_flow(action_performed_by=request_user,client=client_instrument.client, status=client_instrument.instrument_status,client_instrument=client_instrument)
        else:
            add_activity_flow(action_performed_by=client_instrument.created_by,client=client_instrument.client, status=client_instrument.instrument_status,client_instrument=client_instrument)


@receiver(post_save, sender=Reminder)
def update_notification_count(sender, instance,created, **kwargs):
    try:

        if created:

            if(instance.reminder_date==datetime.date.today()):
                staff_obj = Staff.objects.filter(user__id=instance.owned_by.id).first()
                staff_obj.notification_update(1)
                print("count incremented")

        elif instance.is_deleted:
            if (instance.reminder_date== datetime.date.today()) and (instance.is_viewed is False):
                staff_obj = Staff.objects.filter(user__id=instance.owned_by.id).first()
                staff_obj.notification_update(-1)
                print("count decremented")
                

    except Exception as e:
        print(str(e))

@receiver(post_save, sender=CategoryAndSubCategory)
def create_category_slug_name(sender, instance,created, **kwargs):
    if created:
        instance.category_slug_name=(re.sub('[^a-zA-Z0-9 \n\.]', '_', instance.category_slug_name.lower().replace(" ", "_")))+ "_" + str(instance.id)
        instance.save()







# @receiver(post_save, sender=ClientTask)
# def client_task_signal(sender, instance, created, **kwargs):

#     if instance.task_status == '3':       
#         # archiving all the client checklists
#         archive = ClientCheckListArchive()
#         checklist_list = ClientCheckList.objects.filter(client=instance.client)

#         for checklist in checklist_list:
#             for field in checklist._meta.fields:
#                 if field.primary_key == True:
#                     continue  # don't want to clone the PK
#                 setattr(archive, field.name, getattr(checklist, field.name))
#             archive.task = instance.id
#             archive.save()
#         print('data copy done')


#     if instance.is_ops_verified:       
#         #updating status of current sub task in the timeline
#         # current_timeline_task_name = TaskCollection.objects.filter(task_name='Task Verified').first()
#         # current_timeline_task = ClientTaskTimeline.objects.filter(client_task=instance, task_collection=current_timeline_task_name, task_status='1').first()
#         # if current_timeline_task:
#         #     current_timeline_task.task_status = '3'
#         #     current_timeline_task.save()
#         client_task=ClientTask.objects.filter(id=instance.id).update(task_status='2')

@receiver(post_save, sender=ClientTask)
def client_task_signal(sender, instance, created, **kwargs):

    if created:
        print("inside created")
        recommended_producttypes = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=instance.client,is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
        draftchecklist = DraftCheckList.objects.filter(category_name__in=['10','6'])  # post recommended instruments
        for checklist in draftchecklist:
            # print(checklist.id,checklist)
            advisor = Staff.objects.filter(user=instance.client.created_by).first()
            all_products = True if not(list(checklist.product_type.all())) else False
            checklist_product_types = list(checklist.product_type.all().values_list('fund_type', flat=True))
            producttype_exist = any(item in checklist_product_types for item in list(recommended_producttypes))
            if producttype_exist or all_products:
                update_or_create_checklist(instance.client, checklist.id, advisor)
            else:
                delete_checklist(instance.client, checklist)


@receiver(post_save, sender=InstrumentsRecomended)
def checklist_post_instrumentrecommended(sender, instance, created, **kwargs):
    client=instance.client_instrumentinfo.client
    recommended_producttypes=InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
    draftchecklist=DraftCheckList.objects.filter(category_name='5')#post recommended instruments#draft update default creation

    for checklist in draftchecklist:
        print(checklist.id,checklist)
        advisor = Staff.objects.filter(user=instance.client_instrumentinfo.client.created_by).first()
        checklist_product_types=list(checklist.product_type.all().values_list('fund_type',flat=True))
        all_products = True if not (list(checklist.product_type.all())) else False
        producttype_exist = any(item in checklist_product_types for item in list(recommended_producttypes))
        if producttype_exist or all_products:
            update_or_create_checklist(client,checklist.id,advisor)
        else:
            delete_checklist(client,checklist)



@receiver(post_save, sender=ClientRecommendationNotification)
def client_recommendation_save(sender, instance, created, **kwargs):
    if instance.recommendation_status.is_question:
        if instance.recommendation_status.draft_checklist:
            checklist = instance.recommendation_status.draft_checklist
            all_products = True if not (list(checklist.product_type.all())) else False
            checklist_product_types = list(checklist.product_type.all().values_list('fund_type', flat=True))
            recommended_producttypes = ClientInstrumentInfo.objects.filter(client=instance.client,is_recommended=True, is_active=True).values_list('instrument__product_type__fund_type', flat=True)
            producttype_exist = any(item in checklist_product_types for item in list(recommended_producttypes))
            if producttype_exist or all_products:
                advisor = Staff.objects.filter(user=instance.client.created_by).first()
                update_or_create_checklist(instance.client, checklist.id, advisor, is_answer=instance.is_answer)
            else:
                delete_checklist(instance.client, checklist)







