from clients.models import Client,CategoryAndSubCategory,CategoryLabel,CategorySummary,Reminder,StatusCollection,Staff
from datetime import datetime, timezone,timedelta
from clients.utils import pending_status_save,add_activity_flow,client_profile_completion
from .models import SurveyFormData


def parse_surveyform_summary(surveyform,updated_category_id_list, user):
    try:
        client_id=surveyform.client_id
        client=Client.objects.filter(id=client_id).first()
        category_id=surveyform.category['category_id']
        category=CategoryAndSubCategory.objects.filter(id=category_id).first()
        
        answered_mandatory_labels=get_answered_mandatory_labels(surveyform,client)
        total_mandatory_labels=get_total_mandatory_labels(category_id,surveyform,client)
        total_answered_labels=get_total_answered_labels(surveyform,client)
        total_labels=get_total_labels(category_id,surveyform,client)
        percentage_of_completion=get_percentage_of_completion(total_answered_labels,total_labels)
        if(not(total_mandatory_labels==0)):
            mandatory_percentage_of_completion=get_percentage_of_completion(answered_mandatory_labels,total_mandatory_labels)
        else:
            mandatory_percentage_of_completion =100
        #print("percentage of completion is ",mandatory_percentage_of_completion)
        category_summary,created=CategorySummary.objects.get_or_create(client=client,category=category)
        if category_summary is not None:
            #'days_remaining':days_remaining,
            summary_list={'answered_mandatory_labels':answered_mandatory_labels,'total_mandatory_labels':total_mandatory_labels,\
                                    'total_answered_labels':total_answered_labels,'total_labels':total_labels,'percentage_of_completion':percentage_of_completion}

            for key, value in summary_list.items():
                setattr(category_summary, key, value)
            category_summary.save()

        pending_status = None
        if (surveyform.category['category_slug_name'] == 'personal_information_7'):
            print("inside personal")
            activity_flow_update_status=StatusCollection.objects.get(status='1.11')
            activity_flow_complete_status =StatusCollection.objects.get(status='1.63')
            pending_status = StatusCollection.objects.get(status='1.12')  # surveyform pending status
        elif (surveyform.category['category_slug_name'] == 'occupation_info_11'):
            print("inside occupatn")
            activity_flow_update_status =StatusCollection.objects.get(status='1.13')
            activity_flow_complete_status =StatusCollection.objects.get(status='1.64')
            pending_status = StatusCollection.objects.get(status='1.14')  # surveyform pending status
        elif (surveyform.category['category_slug_name'] == 'income___expenditure_summary_14'):
            print("inside income")
            activity_flow_update_status =StatusCollection.objects.get(status='1.15')
            activity_flow_complete_status =StatusCollection.objects.get(status='1.65')
            pending_status = StatusCollection.objects.get(status='1.16')  # surveyform pending status
            
        
        # elif (surveyform.category['category_name'] == 'Expenditure Data'):
        #     print("inside expndtr")
        #     activity_flow_update_status =StatusCollection.objects.get(status='1.17')
        #     activity_flow_complete_status =StatusCollection.objects.get(status='1.66')
        #     pending_status = StatusCollection.objects.get(status='1.18')  # surveyform pending status
        elif (surveyform.category['category_slug_name'] == 'net_worth_summary_21'):
            print("inside NTWRTH SUMMARY")
            activity_flow_update_status=StatusCollection.objects.get(status='1.62')
            activity_flow_complete_status =StatusCollection.objects.get(status='1.67')
            pending_status = StatusCollection.objects.get(status='1.61')  # surveyform pending status
        elif (surveyform.category['category_slug_name'] == 'plans___atr_27'):
            print("inside pln&Atr")
            activity_flow_update_status=StatusCollection.objects.get(status='1.59')
            activity_flow_complete_status =StatusCollection.objects.get(status='1.68')
            pending_status = StatusCollection.objects.get(status='1.60')

        if(updated_category_id_list) and str(category_id) in updated_category_id_list:

            # if(updated_category_id==str(category_id)):
            # if(str(category_id) in updated_category_id_list):

                #print("im here in updtd ctgry id")
            if percentage_of_completion==100:
                add_activity_flow(action_performed_by=user, client=client,status=activity_flow_complete_status)
                # add_activity_flow(action_performed_by=client.created_by, client=client,status=activity_flow_complete_status)
            else:
                add_activity_flow(action_performed_by=user, client=client,status=activity_flow_update_status)
                # add_activity_flow(action_performed_by=client.created_by, client=client,status=activity_flow_update_status)

        if pending_status:
            print("mandatory_percentage_of_completion",mandatory_percentage_of_completion)
            if mandatory_percentage_of_completion==100:###For surveyform reminder
                
                remove_reminder=Reminder.objects.filter(status=pending_status,client=client).first()
                if remove_reminder:
                    remove_reminder.is_deleted=True
                    remove_reminder.save()
                    # percentage upadtion 
                    
                    try:
                        client = client_profile_completion(client=client,phase='pre-contract',percentage=10,sign='positive') 
                        return client
                    except Exception as e:
                        print("=========== exception in client_profile_completion  ===============",e)
            else:
                reminder=Reminder.objects.filter(status=pending_status, client=client)
                if not reminder:
                    client_obj=pending_status_save( pending_status=pending_status,client_id=client.id)
                    client.pre_contract_percent = client_obj.pre_contract_percent
                    
                    return client

    except Exception as e:
        print("error in parse surveyform")
        print(str(e))

    

def get_total_mandatory_labels(category_id,surveyform,client):
    child_category_list = CategoryAndSubCategory.objects.filter(parent=category_id)
    print(child_category_list)
    total_label_count = CategoryLabel.objects.filter(category__in=child_category_list, is_mandatory=True, parent=None,response_required=True).count()
    
    total_no_response_label_count = CategoryLabel.objects.filter(category__in=child_category_list,parent__response_required=False,
                                                           is_mandatory=True,parent__parent=None,response_required=True).count()
    total_sub_label_count = 0
    label_answer = ""
    if surveyform is not None:

        try:
            for subcategory in surveyform.form_data:
                category = CategoryAndSubCategory.objects.filter(id=subcategory['subcategory_id']).first()
                subcategory_label_count = 0
                subcategory_no_response_label_count = 0
                no_response_label_count = 0
                sub_label_count = 0
                label_list = subcategory['subcategory_data']
                subcategory_label_count=CategoryLabel.objects.filter(category=category, is_mandatory=True, parent=None,response_required=True).count()
                subcategory_no_response_label_count=CategoryLabel.objects.filter(category=category,parent__response_required=False,
                                                           is_mandatory=True,parent__parent=None,response_required=True).count()
                for label in label_list:
                    if (label['has_sublabels']):
                        if (label['answer']):
                            label_answer = label['answer']

                        for index in range(0, len(label['sub_labels'])):
                            for sublabel in (label['sub_labels'][index]['sub_label_data']):
                                if (label_answer):
                                    if ((label_answer in sublabel['answer_parent']) and sublabel['response_required'] and sublabel['is_mandatory']):
                                        sub_label_count = sub_label_count + 1
                                if (not (label['response_required']) and sublabel['response_required'] and sublabel['is_mandatory']):
                                    if (not (index == 0)):
                                        no_response_label_count = no_response_label_count + 1
                                if (sublabel['has_sublabels']):
                                    if (sublabel['answer']):  # to handle nested sublabels(3rd level)
                                        answer_parent = sublabel['answer']
                                        for i in range(0, len(sublabel['sub_labels'])):
                                            for nested_sublabel in (sublabel['sub_labels'][i]['sub_label_data']):
                                                if ((answer_parent in nested_sublabel['answer_parent']) and (nested_sublabel['is_mandatory'])):
                                                    sub_label_count = sub_label_count + 1
                                    elif (not (sublabel['response_required']))  and (label_answer in sublabel['answer_parent']):

                                        for nested_sublabel in (sublabel['sub_labels'][0]['sub_label_data']):
                                            if (nested_sublabel['is_mandatory']):
                                                sub_label_count = sub_label_count + (1*len(sublabel['sub_labels']))
                try:
                    total_subcategory_labels = subcategory_label_count + subcategory_no_response_label_count + no_response_label_count + sub_label_count
                    categorysummary, created = CategorySummary.objects.update_or_create(category=category,client=client,is_sub_category=True,
                                                                                        defaults={'total_mandatory_labels': total_subcategory_labels}, )
                except Exception as e:
                    print(str(e))
                total_no_response_label_count = total_no_response_label_count + no_response_label_count
                total_sub_label_count = total_sub_label_count + sub_label_count

        except Exception as e:
            print(str(e))
            

    return total_label_count + total_sub_label_count + total_no_response_label_count


def get_answered_mandatory_labels(surveyform,client):
    toatal_answered_count = 0

    if surveyform is not None:
        try:
            for subcategory in surveyform.form_data:
                answered_count = 0
                unknown_answer_count = 0
                label_list = subcategory['subcategory_data']
                for label in label_list:
                    if label['answer'] == 0:
                        label['answer'] = '0'

                    if label['has_sublabels'] is True:
                        for index in range(0, len(label['sub_labels'])):
                            for sublabel in (label['sub_labels'][index]['sub_label_data']):
                                if sublabel['answer'] == 0:
                                    sublabel['answer'] = '0'
                                if (sublabel['answer'] and sublabel['is_mandatory']):
                                    if ((label['answer'] and (label['answer'] in sublabel['answer_parent'])) or (
                                            label['response_required'] == False)):
                                        answered_count = answered_count + 1
                                        ###To track 'unknown' values for checklist tracking####
                                        if(str(sublabel['answer']).lower()=='unknown'):
                                            unknown_answer_count=unknown_answer_count+1
                                        elif(sublabel['component_type'])=='currencyField&Checkbox' and sublabel['answer'] == '0':
                                            unknown_answer_count = unknown_answer_count + 1
                                if sublabel['has_sublabels'] is True:  # to handle nested sublabels
                                    for i in range(0, len(sublabel['sub_labels'])):
                                        for nested_sublabel in (sublabel['sub_labels'][i]['sub_label_data']):
                                            if nested_sublabel['answer'] == 0:
                                                nested_sublabel['answer'] = '0'
                                            if (nested_sublabel['answer'] and nested_sublabel['is_mandatory']):
                                                if (sublabel['answer'] and (sublabel['answer'] in nested_sublabel['answer_parent'])):
                                                    answered_count = answered_count + 1
                                                    if (str(nested_sublabel['answer']).lower() == 'unknown'):
                                                        unknown_answer_count = unknown_answer_count + 1
                                                    elif (nested_sublabel['component_type']) == 'currencyField&Checkbox' and nested_sublabel['answer'] == '0':
                                                        unknown_answer_count = unknown_answer_count + 1
                                                elif (not (sublabel['response_required']) and label['answer'] and (label['answer'] in nested_sublabel['answer_parent'])):
                                                    answered_count = answered_count + 1
                                                    if (str(nested_sublabel['answer']).lower() == 'unknown'):
                                                        unknown_answer_count = unknown_answer_count + 1
                                                    elif (nested_sublabel['component_type']) == 'currencyField&Checkbox' and nested_sublabel['answer'] == '0':
                                                        unknown_answer_count = unknown_answer_count + 1

                    if (label['answer'] and label['is_mandatory']):
                        answered_count = answered_count + 1
                        if (str(label['answer']).lower() == 'unknown'):
                            unknown_answer_count = unknown_answer_count + 1
                        elif (label['component_type']) == 'currencyField&Checkbox' and label['answer'] == '0':
                            unknown_answer_count = unknown_answer_count + 1
                ##########sub category details save##############################
                try:
                    category=CategoryAndSubCategory.objects.filter(id=subcategory['subcategory_id']).first()
                    categorysummary, created = CategorySummary.objects.update_or_create(category=category,client=client,is_sub_category=True,
                                                                                  defaults={'answered_mandatory_labels': answered_count,'unknown_mandatory_labels':unknown_answer_count}, )
                except Exception as e:
                    print("some error"+str(e))

                toatal_answered_count = toatal_answered_count + answered_count
        except Exception as e:
            print(str(e))
            

    return toatal_answered_count


def get_total_labels(category_id,surveyform,client):
    child_category_list = CategoryAndSubCategory.objects.filter(parent=category_id)
    print(child_category_list)
   
    total_label_count = CategoryLabel.objects.filter(category__in=child_category_list, parent=None,response_required=True).count()  # main label count
    total_no_response_label_count = CategoryLabel.objects.filter(category__in=child_category_list,
                                                           parent__response_required=False, parent__parent=None,response_required=True).count()

    total_sub_label_count = 0
    label_answer = ""
    if surveyform is not None:
        try:
            for subcategory in surveyform.form_data:
                category = CategoryAndSubCategory.objects.filter(id=subcategory['subcategory_id']).first()
                subcategory_label_count=0
                subcategory_no_response_label_count=0
                no_response_label_count=0
                sub_label_count=0
                subcategory_label_count = CategoryLabel.objects.filter(category=category, parent=None,response_required=True).count()
                subcategory_no_response_label_count = CategoryLabel.objects.filter(category=category,
                                                           parent__response_required=False, parent__parent=None,response_required=True).count()
                label_list = subcategory['subcategory_data']
                for label in label_list:
                    if(label['label_slug'] == 'does_spouse_have_old_pensions__67'):#Handling marital status and spouse pension using slug#special scenario
                        surveyform = SurveyFormData.objects.filter(client_id=client.id,category_id=7)
                        for survey in surveyform:
                            if survey is not None:
                                for subcategory in survey.form_data:
                                    label_list = subcategory['subcategory_data']
                                    if subcategory['subcategory_slug_name']=='basic_info_8':
                                        for label in label_list:
                                            if label['label_slug'] == 'marital_status_18':
                                                if label['answer'] and (label['answer']).lower()=='single':
                                                    total_label_count=total_label_count-1


                    if (label['has_sublabels']):
                        #print(label['has_sublabels'])
                        if (label['answer']):
                            label_answer = label['answer']
                        #print("len of label[sublabels]",len(label['sub_labels']))
                        for index in range(0, len(label['sub_labels'])):
                            print("index value",index)
                            for sublabel in (label['sub_labels'][index]['sub_label_data']):
                                if (label_answer):
                                    if ((label_answer in sublabel['answer_parent']) and sublabel['response_required']):

                                        sub_label_count = sub_label_count + 1
                                if(not(label['response_required']) and sublabel['response_required']):
                                    #print("inside label is response reqrd false")
                                    if(not(index==0)):
                                        #print("no rsponse label",sublabel['label'])
                                        no_response_label_count=no_response_label_count+1

                                if (sublabel['has_sublabels']):
                                    if (sublabel['answer']):  # to handle nested sublabels(3rd level)
                                        answer_parent = sublabel['answer']
                                        for i in range(0, len(sublabel['sub_labels'])):
                                            for nested_sublabel in (sublabel['sub_labels'][i]['sub_label_data']):
                                                if (answer_parent in nested_sublabel['answer_parent']):
                                                  
                                                    sub_label_count = sub_label_count + 1
                                    elif (not (sublabel['response_required'])) and (label_answer in sublabel['answer_parent']) :
                                        #print("LEN",len(sublabel['sub_labels']))
                                        sub_label_count = sub_label_count + (len(sublabel['sub_labels'][0]['sub_label_data'])*len(sublabel['sub_labels']))

                ##########sub category details save##############################
                try:
                    total_subcategory_labels=subcategory_label_count +subcategory_no_response_label_count+ no_response_label_count + sub_label_count
                    categorysummary, created = CategorySummary.objects.update_or_create(category=category, client=client,is_sub_category=True,defaults={'total_labels': total_subcategory_labels}, )
                except Exception as e:
                    print("some error" + str(e))
                total_no_response_label_count=total_no_response_label_count+no_response_label_count
                total_sub_label_count=total_sub_label_count+sub_label_count


        except Exception as e:
            print(str(e))
            

    return total_label_count + total_no_response_label_count + total_sub_label_count


def get_total_answered_labels(surveyform,client):
   
    answered_count = 0
    if surveyform is not None:
        try:
            for subcategory in surveyform.form_data:

                label_list = subcategory['subcategory_data']
                for label in label_list:
                    if label['answer'] == 0:
                        label['answer'] = '0'   #to consider 0 values for calculating total filled answer fields
                    if (label['answer']):
                        answered_count = answered_count + 1
                        if (label['label_slug'] == 'does_spouse_have_old_pensions__67' and label['answer']):  # Handling marital status and spouse pension using slug#special scenario
                            surveyform = SurveyFormData.objects.filter(client_id=client.id, category_id=7)
                            for survey in surveyform:
                                if survey is not None:
                                    for subcategory in survey.form_data:
                                        label_list = subcategory['subcategory_data']
                                        if subcategory['subcategory_slug_name'] == 'basic_info_8':
                                            for label in label_list:
                                                if label['label_slug'] == 'marital_status_18':
                                                    if label['answer'] and (label['answer']).lower() == 'single':
                                                        answered_count = answered_count - 1
                    if label['has_sublabels'] is True:
                        for index in range(0, len(label['sub_labels'])):
                            for sublabel in (label['sub_labels'][index]['sub_label_data']):
                                if sublabel['answer'] == 0:
                                    sublabel['answer'] = '0'   #to consider 0 values for calculating total filled answer fields
                                if sublabel['answer']:
                                    if ((label['answer'] and (label['answer'] in sublabel['answer_parent'])) or (label['response_required']==False)):
                                        answered_count = answered_count + 1


                                if sublabel['has_sublabels'] is True:  # to handle nested sublabels
                                    for i in range(0,len(sublabel['sub_labels'])):
                                        for nested_sublabel in (sublabel['sub_labels'][i]['sub_label_data']):
                                            if nested_sublabel['answer'] == 0:
                                                nested_sublabel['answer'] = '0'    #to consider 0 values for calculating total filled answer fields
                                            if (nested_sublabel['answer']):
                                                if (sublabel['answer'] and (sublabel['answer'] in nested_sublabel['answer_parent'])):
                                                    answered_count = answered_count + 1
                                                elif(not(sublabel['response_required']) and label['answer'] and
                                                                                            (label['answer'] in nested_sublabel['answer_parent'])):
                                                    answered_count = answered_count + 1

                ##########sub category details save##############################
                try:
                    category = CategoryAndSubCategory.objects.filter(id=subcategory['subcategory_id']).first()
                    categorysummary, created = CategorySummary.objects.update_or_create(category=category, client=client,is_sub_category=True,
                                        defaults={'total_answered_labels': answered_count}, )
                except Exception as e:
                    print("some error" + str(e))


        except Exception as e:
            print(str(e))
            
    return answered_count


def get_percentage_of_completion(answered_labels,total_labels):
    percentage = 0
    try:

        if total_labels!=0:
            percentage = (answered_labels / total_labels) * 100
    except Exception as e:
        print(str(e))
        
    return percentage