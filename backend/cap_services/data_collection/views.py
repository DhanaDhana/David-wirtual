from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework import viewsets, status, filters, serializers
from clients.models import Job_titles,Lender_names,pension_providers,Company,RecommendationNotificationStatus,\
                            StatusCollection,User,AutotriggerMail,Reminder,Client,CategoryAndSubCategory,CategorySummary,\
                            ClientCheckList,DraftCheckList,Staff,InstrumentsRecomended,Document
from clients.checklist import atr_completed_check,update_checklist,update_or_create_checklist,check_advisor_decency
from outlook_app.utils import templatemailsend
from .models import SurveyFormData
from .serializers import SurveyFormDataSerializer
from .utils import parse_surveyform_summary
from clients.utils import recommendation_notification_save
from clients.utils import pending_status_save
from decimal import Decimal

import datetime,math
import logging    
logger = logging.getLogger('django.request')
# Create your views here.



class SurveyformViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, )
    queryset = SurveyFormData.objects.all()
    serializer_class = SurveyFormDataSerializer

    def get_queryset(self):
        queryset = SurveyFormData.objects.all()
        client_id = self.request.query_params.get('client_id', None)
        # print("client_id",client_id)
        category_id = self.request.query_params.get('category_id', None)
        if client_id is not None:
             queryset=queryset.filter(client_id=client_id)
        if category_id is not None:
             queryset=queryset.filter(category_id=category_id)
        return queryset


    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'survey form fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'Not found'
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)



    def create(self, request, *args, **kwargs):
        response_data = {}
        total_mandatory_labels=0
        total_answered_mandatory_labels=0
        error=""
        is_updated=False
        data=[]
        result_list=[]
        net_worth_dict={}
        result_list = list.copy(request.data)
        updated_category_id = self.request.query_params.get('updated_category_id', None)
       

        updated_category_id_list = list(updated_category_id.split(","))
        client_id = self.request.query_params.get('client_id', None)
        
        mortgage_details_dict = {}
        income_asset_details = {}
        send_mortage = False        

        try:
            for item in result_list:

                surveyform = SurveyFormData.objects.get(id=item['id'])


                if(surveyform.client_id==item['client_id']):
                    
                    client = Client.objects.filter(id=client_id).first()
                    if item['category_id'] == 27:#plans&atr
                        for subcategory in item['data']:
                            if subcategory['subcategory_slug_name']=='attitude_to_risk_29':
                                print(subcategory['subcategory_data'])
                                is_updated = surveyform.atr_values_is_updated(subcategory['subcategory_data'])
                    if is_updated  and client.is_confirmed_client:
                       
                        check_list = [41]
                        print("UPDATING AS AMBER%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
                        update_checklist(client, check_list, 'amber')



                    surveyform.form_data=item['data']
                    surveyform.save()
                    try:
                        client_obj=parse_surveyform_summary(surveyform,updated_category_id_list, request.user)
                        if client_obj:
                            client.pre_contract_percent = client_obj.pre_contract_percent
                            client.save()
                       
                        user = User.objects.filter(id=surveyform.advisor_id).first()
                        staff_user=Staff.objects.filter(user=user).first()
                        category_summary = CategorySummary.objects.filter(client__id=surveyform.client_id,category__id=surveyform.category_id).first()
                        total_answered_mandatory_labels=total_answered_mandatory_labels+category_summary.answered_mandatory_labels
                        total_mandatory_labels=total_mandatory_labels+category_summary.total_mandatory_labels
                        trigger_mail_obj = AutotriggerMail.objects.filter(client=client_id).first()
                        if not trigger_mail_obj:
                            trigger_mail_obj = AutotriggerMail.objects.create(client=client, advisor=user)

                        if((surveyform.category['category_slug_name']=='occupation_info_11' ) and (str(surveyform.category['category_id']) in updated_category_id_list )):
                        
                        
                            
                            for subcategory in surveyform.form_data:
                                label_list = subcategory['subcategory_data']
                                if subcategory['subcategory_slug_name'] == "employment_12":
                                    for label in label_list:
                                        if (label['label_slug'] == 'job_title_50'):
                                           
                                            Job_titles.objects.get_or_create(name=label['answer'])
                                        if (label['label_slug'] == 'employer_trading_name_49'):
                                            Company.objects.get_or_create(name=label['answer'])
                                        if (label['label_slug'] == 'any_other_income__91'):
                                            for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                if (sublabel['label_slug'] == "employment_details_any_other_income_148"):
                                                    for index in range(0,len(sublabel['sub_labels'])):
                                                        for nested_sublabel in (sublabel['sub_labels'][index]['sub_label_data']):
                                                            if (nested_sublabel['label_slug']=='job_title_94') :
                                                                Job_titles.objects.get_or_create(name=sublabel['answer'])
                                                            if (nested_sublabel['label_slug']=='employer_trading_name_93') :
                                                                Company.objects.get_or_create(name=label['answer'])



                        
                        elif ((surveyform.category['category_slug_name'] == 'net_worth_summary_21') and (str(surveyform.category['category_id']) in updated_category_id_list)):
                            for subcategory in surveyform.form_data:
                                label_list = subcategory['subcategory_data']
                               

                                cash_flag_set = False
                                property_flag_set = False
                                stock_flag_set = False
                                
                                if subcategory['subcategory_slug_name'] == "assets_24":
                                    try:
                                        label = subcategory['subcategory_data']
                                        Net_Worth = 0
                                        for label_data in label:
                                            for index in range(0,len(label_data['sub_labels'])):
                                                print('\n\n\n\n ============================= INDEX ',index,' ================================\n\n\n')
                                                cash_flag=False
                                                stock_flag = False
                                                property_flag = False
                                                for sublabel in (label_data['sub_labels'][index]['sub_label_data']):
                                                    if sublabel['label_slug']=='type_of_asset_75':
                                                        
                                                        if sublabel['answer'].lower()=='stock':
                                                            stock_flag = True   
                                                            print('stock')

                                                        if sublabel['answer'].lower()=='cash' or sublabel['answer'].lower()=='cash isa':
                                                            cash_flag= True
                                                            print('cash')
       
                                                        if sublabel['answer'].lower()=='property':
                                                            print('property')
                                                            property_flag_set = True
                                                            property_flag = True   
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=10).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                            
                                                          
                                                        else:
                                                            if not property_flag_set:
                                                                print('property status removal')
                                                                property_flag = False   
                                                                recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=10).first()
                                                                recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                                    if sublabel['label_slug']=='amount_128':
                                                        if sublabel['answer']:
                                                            Net_Worth=Net_Worth+Decimal(sublabel['answer'])
                                                        if sublabel['answer'] and Decimal(sublabel['answer'])> 50000 and cash_flag:
                                                            print("more than or equal 50K")
                                                            
                                                            cash_flag_set = True
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=8).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                        else:
                                                            if not cash_flag_set:
                                                                print('cash status removal')
                                                                recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=8).first()
                                                                recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                                        
                                                        if sublabel['answer'] and Decimal(sublabel['answer'])>50000 and stock_flag:
                                                            print("more than  50K stock ")
                                                           
                                                            stock_flag_set = True
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=9).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                        else:
                                                            if not stock_flag_set:
                                                                print('stock status removal')
                                                                recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=9).first()
                                                                recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                        
                                        print("asset total amount ",Net_Worth)
                                       
                                    except Exception as e:
                                        print("error in draft reminder-Assets")
                                        print(str(e))                  
                                        logger.exception("Exception in survey - Draft reminder (assets) : {} - {}".format(str(e), request.path), extra={})


                                   
                        #draft recommendation
                        if (surveyform.category['category_slug_name'] =='personal_information_7'):
                            mortgage_left = False
                            #checklist notes
                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=19).first()
                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_answer=True)
                            for subcategory in surveyform.form_data:
                                try:
                                    label_list = subcategory['subcategory_data']
                                    if subcategory['subcategory_slug_name'] == "basic_info_8":
                                        print("in basic info")
                                        for label in label_list:
                                            if label['label_slug'] == 'dob_84':
                                                date_time_str = label['answer']
                                                if date_time_str:
                                                    born_date = datetime.datetime.strptime(date_time_str,"%Y-%m-%dT%H:%M:%S.%fZ")
                                                    today = datetime.date.today()
                                                    today=datetime.datetime.now()
                                                   
                                                    print("born_month",born_date.month)
                                                    age_y = (today.year - born_date.year)
                                                    age_m = (today.month - born_date.month)
                                                    age_date=(today.day-born_date.day)
                                                    if age_m < 0:
                                                        age_y = age_y - 1
                                                        age_m = age_m + 12
                                                   


                                                    print(age_y,age_m)
                                                    client.age=age_y+(age_m/12)
                                                    client.save()
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=20).first()
                                                    if (age_y>75 or (age_y==75 and age_m>0)):
                                                        print("above 75 scenario")
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,
                                                                                         is_answer=False)
                                                    else:
                                                        print("age is below 75 ,so green checklist")
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                                        draftchecklist = DraftCheckList.objects.filter(id=52).first()#For clients over 75 does the report evidence that the client was given the opportunity to have a
                                                                                                                     # friend or relative accompany them at the meeting?
                                                        update_or_create_checklist(client,draftchecklist.id,staff_user,result='passed')
                                                else:
                                                    client.age = None
                                                    client.save()
                                    elif subcategory['subcategory_slug_name'] =='relationship___dependencies_9':
                                        for label in label_list:
                                            if (label['label_slug'] =='good_schools_in_the_area__pay_for_education__42'):
                                                if label['answer'].lower()=='paying':
                                                    try:
                                                        recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=1).first()
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                    
                                                    except Exception as e:
                                                        print(str(e)) 
                                                        logger.exception("Exception in survey - relationship dependencies : {} - {}".format(str(e), request.path), extra={})

                                                else:
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=1).first()
                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                            if (label['label_slug'] =='will_you_contribute_to_uni_funds__43'):
                                                

                                                if (label['answer']).lower()=='yes':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=2).first()
                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                if (label['answer']).lower()=='no':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=2).first()
                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                    elif subcategory['subcategory_slug_name'] == 'will_23':
                                        for label in label_list:
                                            if (label['label_slug'] == 'are_you_interested_in_addressing__46'):
                                                
                                                pending_status = StatusCollection.objects.filter(status='1.70').first()

                                                if (label['answer']).lower() == 'yes':
                                                    print("inside will intrst")
                                                    for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                        if sublabel['label_slug']=='sent_recommendation_mail_154':
    
                                                           
                                                            if sublabel['answer']!='off' and not(trigger_mail_obj.will_referral_mail_sent) and pending_status:

                                                               
                                                                try:
                                                                   
                                                                    pending_status_save(pending_status=pending_status, client_id=surveyform.client_id)

                                                                except Exception as e:
                                                                    print(str(e))
                                                                    print("not added reminder")
                                                                    logger.exception("Exception in survey - will : {} - {}".format(str(e), request.path), extra={})

                                                else:
                                                    if pending_status:
                                                        remove_reminder = Reminder.objects.filter(status=pending_status, client__id=surveyform.client_id).first()
                                                        if remove_reminder:
                                                            remove_reminder.is_deleted = True
                                                            remove_reminder.save()
                                    elif subcategory['subcategory_slug_name'] == "property_details_22":

                                        recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=16).first()
                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)

                                        
                                        for label in label_list:

                                            if (label['label_slug'] == 'have_outstanding_mortgage_157' and label['answer'].lower() == 'yes'):
                                                mortgage_left = True
                                                for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                    if ((sublabel['label_slug'] == 'amount_mortgage_outstanding_30') and sublabel['answer']):
                                                        mortgage_details_dict['amount_mortgage_outstanding'] = sublabel['answer']
                                                    if (sublabel['label_slug'] == 'tie_in_period_end_date_90' and sublabel['answer']):
                                                        date_time_obj = datetime.datetime.strptime(sublabel['answer'],"%Y-%m-%dT%H:%M:%S.%fZ")
                                                        mortgage_details_dict['tie_in_period'] = date_time_obj.strftime("%m-%Y")

                                            
                                            if (label['label_slug'] == 'rent_or_own_property_27' and label['answer'] == 'Own'):
                                                mortgage_details_dict['property_type'] = label['answer']
                                                for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                    if ((sublabel['label_slug'] == 'value_of_the_property_28') and sublabel['answer']):
                                                        mortgage_details_dict['property_value'] = sublabel['answer']


                                          
                                            
                                            if (label['label_slug'] == 'lender_31'):
                                                Lender_names.objects.get_or_create(name=label['answer'])
                                            
                                            if label['label_slug']=='rent_or_own_property_27' and label['answer'].lower()=='own':
                                                for sublabel_data in (label['sub_labels'][0]['sub_label_data']):
                                                    
                                                    try:
                                                        if (sublabel_data['label_slug'] == 'do_you_plan_to_do_any_renovations__35'):
                                                            if (sublabel_data['answer']).lower() == 'yes':
                                                                recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=14).first()
                                                                recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                
                                                            if (sublabel_data['answer']).lower()=='no':
                                                                recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=14).first()
                                                                if recommendation_status_obj:
                                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                                    
                                                        if (sublabel_data['label_slug'] == 'do_you_plan_to_stay_at_the_property_102'):
                                                            if (sublabel_data['answer']).lower() == 'yes':
                                                                recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=13).first()
                                                                if recommendation_status_obj:
                                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)

                                                            if (sublabel_data['answer']).lower()=='no':
                                                                
                                                                recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=13).first()
                                                                recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                    except Exception as e:
                                                        print("========error in rent or own property====",e)
                                                        logger.exception("Exception in survey - property details : {} - {}".format(str(e), request.path), extra={})

                                            
                                            if (label['label_slug'] == 'do_you_overpay_the_mortgage__36'):
                                                if (label['answer']).lower() == 'yes':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=15).first()
                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
    
                                                if (label['answer']).lower()=='no':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=15).first()
                                                    if recommendation_status_obj:
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                            
                                            if (label['label_slug'] == 'interest_only_or_repayment_33'):
                                                if (label['answer']).lower() != 'interest only':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=17).first()
                                                    if recommendation_status_obj:
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)

                                                if (label['answer']).lower()=='interest only':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=17).first()
                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)


                                           
                                        
                                        if 'amount_mortgage_outstanding' in mortgage_details_dict and  mortgage_details_dict['amount_mortgage_outstanding']:
                                            net_worth_dict['amount_mortgage_outstanding'] = mortgage_details_dict['amount_mortgage_outstanding']
                                           
                                        else:
                                            net_worth_dict['amount_mortgage_outstanding']=0
                                       
                                        if 'property_value' in mortgage_details_dict and mortgage_details_dict['property_value']:
                                            net_worth_dict['property_value']=mortgage_details_dict['property_value']
                                            
                                        else:
                                            net_worth_dict['property_value']=0  
                                        
                                      

                                        print('\n\n\nmortgage details',mortgage_details_dict, ' \n\n==============')
                                        #checking for values for sending mortgage mail
                                        if 'property_type' in mortgage_details_dict.keys() and mortgage_details_dict['property_type'] == 'Own':
                                            if 'property_value' in mortgage_details_dict.keys() and 'amount_mortgage_outstanding' in mortgage_details_dict.keys() and 'tie_in_period' in mortgage_details_dict.keys():
                                                send_mortage = True
                                      

                                        if send_mortage:
                                       
                                            if mortgage_left and trigger_mail_obj and not trigger_mail_obj.mortgagebroker_mail_sent:
                                               
                                                result = templatemailsend("mortgage_broker_mail", user, client.id,mortgage_details_dict=mortgage_details_dict)
                                                if (result):
                                                    trigger_mail_obj.mortgagebroker_mail_sent = True
                                                    trigger_mail_obj.save()


                                except Exception as e:
                                    print("error in views")
                                    print(str(e)) 
                                    logger.exception("Exception in survey - Personal info : {} - {}".format(str(e), request.path), extra={})
                            surveyform.update_client_profile(item['data'])


                        
                        if ((surveyform.category['category_slug_name'] in ['income___expenditure_summary_14','occupation_info_11'] ) and (str(surveyform.category['category_id']) in updated_category_id_list)):

                            income_expenditure_details = {}
          
                            for subcategory in surveyform.form_data:
                                label_list = subcategory['subcategory_data']
                                try:

                                    if subcategory['subcategory_slug_name'] =='income___expenditure_15':
                                        for label in label_list:
                                            if (label['label_slug'] =='are_you_willing_to_consider_a_portion_of_spare_income_towards_financial_planning__60'):
                                                if (label['answer']).lower()=='yes':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=7).first()
                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
    
                                                if (label['answer']).lower()=='no':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=7).first()
                                                    if recommendation_status_obj:
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                            #############################Checklist####################################
                                            try:

                                                if(label['label_slug']=='net_monthly_income_54'):
                                                    income_expenditure_details['monthly_income']=Decimal(label['answer'])
                                                    print('monthly income is',income_expenditure_details['monthly_income'])
                                                if (label['label_slug'] == 'regular_monthly_expenses_55'):
                                                    income_expenditure_details['monthly_expenses'] = Decimal(label['answer'])
                                            except Exception as e:
                                                print("Exception occured as ", e)

                                        
                                        try:
                                            draftchecklist1 = DraftCheckList.objects.filter(id=1).first()
                                            draftchecklist2 = DraftCheckList.objects.filter(id=2).first()
                                          

                                            if (category_summary.answered_mandatory_labels == category_summary.total_mandatory_labels):



                                                if (income_expenditure_details['monthly_income'] > income_expenditure_details['monthly_expenses']):
                                                    update_or_create_checklist(client,draftchecklist1.id,staff_user,result='passed')
                                                    update_or_create_checklist(client,draftchecklist2.id,staff_user,result='passed')
                                                    

                                                else:
                                                    update_or_create_checklist(client,draftchecklist1.id,staff_user,result='failed')
                                                    update_or_create_checklist(client,draftchecklist2.id,staff_user,result='failed')
                                                   


                                            else:
                                                update_or_create_checklist(client, draftchecklist1.id,staff_user,result='failed')
                                                update_or_create_checklist(client, draftchecklist2.id,staff_user,result='failed')

                                        except Exception as e:
                                            print("draft checklist not created")
                                            print(str(e))
                                            logger.exception("Exception in survey - draft checklist (income expenditure) : {} - {}".format(str(e), request.path), extra={})


                                    ##########################checklist ##############################
                                    if subcategory['subcategory_slug_name'] =='employer_benefits_16':
                                       
                                        draftchecklist = DraftCheckList.objects.filter(id=3).first()
                                        sub_category_summary=CategorySummary.objects.filter(client__id=surveyform.client_id,category__id=subcategory['subcategory_id']).first()
                                        if (sub_category_summary.total_mandatory_labels == (sub_category_summary.answered_mandatory_labels-sub_category_summary.unknown_mandatory_labels)):

                                            update_or_create_checklist(client, draftchecklist.id,staff_user, result='passed')
                                           


                                        else:
                                            update_or_create_checklist(client, draftchecklist.id,staff_user, result='failed')
                                           

                                    #######################checklist########################################
                                        for label in label_list:
                                            if (label['label_slug'] =='over_the_annual_allowance_62'):
                                                if (label['answer']).lower()=='yes':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=4).first()
                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                if (label['answer']).lower()=='no':
                                                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=4).first()
                                                    recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)


                                                ####template mail send#################
                                            
                                            if (label['label_slug'] == 'insurance__protection_109'):
                                                
                                                try:
                                                    if (label['answer']) and (label['answer']).lower() == "unknown":      
                                                        
                                                        if trigger_mail_obj and not trigger_mail_obj.insurance_check_mail_sent:
                                                            
                                                            pending_status = StatusCollection.objects.filter(status='1.76').first()
                                                            for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                                if sublabel['label_slug']=='hr_insurance__email_156':
                                                                    print("sublabel['label_slug']",sublabel['label_slug'])
                                                                    if sublabel['answer']!='off' and not(trigger_mail_obj.insurance_check_mail_sent) and pending_status:
                                                                        try:
                                                                            pending_status_save(pending_status=pending_status, client_id=surveyform.client_id)
                                                                            print("\n\n=================================insurance_check mail reminder=============================")
                                                                        except Exception as e:
                                                                            print(str(e))
                                                                            logger.exception("Exception in survey - insurance protection : {} - {}".format(str(e), request.path), extra={})

                                                except Exception as e:
                                                    print(str(e))
                                                    
                                                   

                                    if subcategory['subcategory_slug_name'] =='employment_12':
                                        salary = 0
                                        for label in label_list:
                                            if (label['label_slug'] =='salary_51') and label['answer']:
                                                
                                                salary = label['answer']
                                                    
                                            if (label['label_slug'] =='bonus_53'):
                                                try :
                                                    bonus_percentage= float(salary)*0.3
                                                   
                                                    if label['answer']:
                                                        bonus = label['answer']
                                                    else:
                                                        bonus=0
                                                    if bonus :
                                                        if Decimal(bonus) > Decimal(bonus_percentage) :
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=3).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                            
                                                        else:
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=3).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)             
                                                except Exception as e:
                                                    print("error here")
                                                    print(str(e))      
                                                    logger.exception("Exception in survey - employment : {} - {}".format(str(e), request.path), extra={})
                                                    
                                    if (subcategory['subcategory_slug_name'] =='previous_employment_13'):
                                        
                                        for label in label_list:
                                            try:
                                                
                                                if (label['label_slug'] =='pension_64'):
                                                   
                                                    if (label['answer']).lower()=='yes':
                                                        for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                            for index in range(0,len(sublabel['sub_labels'])):
                                                                sublabel_new = sublabel['sub_labels'][index]['sub_label_data'][0]
                                                                if sublabel_new['label_slug']=='value_132' and sublabel_new['answer']:
                                                                    
                                                                        if 'prev_emp_pension'in net_worth_dict and  net_worth_dict['prev_emp_pension']:
                                                                            
                                                                            net_worth_dict['prev_emp_pension']=Decimal(net_worth_dict['prev_emp_pension'])+Decimal(sublabel_new['answer'])
                                                                            
                                                                        else:
                                                                            net_worth_dict['prev_emp_pension']=sublabel_new['answer']
                                                                            
                                                        if 'prev_emp_pension' in net_worth_dict and  net_worth_dict['prev_emp_pension']:
                                                            prev_emp_pension=Decimal(net_worth_dict['prev_emp_pension'])
                                                        else:
                                                            prev_emp_pension=0


                                                        recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=11).first()
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                
                                                    if (label['answer']).lower()=='no':
                                                        recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=11).first()
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                                if (label['label_slug'] =='does_spouse_have_old_pensions__67'):
                                                    
                                                    if (label['answer']).lower()=='yes':
                                                        recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=12).first()
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                    
                                                    if (label['answer']).lower()=='no':
                                                        recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=12).first()
                                                        recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                            except Exception as e:
                                                print("error in draft reminder",str(e))
                                                logger.exception("Exception in survey - draft reminder (previous employment) : {} - {}".format(str(e), request.path), extra={})

                                            #######template mail send #################
                                            if ((label['label_slug'] == 'do_you_have_fully_funded_state_pension__66') and (label['answer'].lower() == "unsure")):

                                                pending_status = StatusCollection.objects.filter(status='1.75').first()
                                                user = User.objects.filter(id=surveyform.advisor_id).first()
                                                client = Client.objects.filter(id=client_id).first()

                                                if trigger_mail_obj and not (trigger_mail_obj.br19_mail_sent):
                                                   
                                                   
                                                    for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                        if sublabel['label_slug']=='send_br_email_155':      
                                                            
                                                            if sublabel['answer']!='off' and not(trigger_mail_obj.br19_mail_sent)and pending_status:
                                                                try:
                                                                    pending_status_save(pending_status=pending_status, client_id=surveyform.client_id)
                                                                    print("\n\n====================reminder send br mail ======================")

                                                                except Exception as e:
                                                                    print(str(e))
                                                                    logger.exception("Exception in survey - draft reminder (state pension) : {} - {}".format(str(e), request.path), extra={})




                                    if subcategory['subcategory_slug_name'] =='private_insurance_20':
                                        medical_conditions_smoke =False
                                        medical_conditions=False
                                        for label in label_list:
                                            if (label['label_slug']=='do_you_have_any__69') and label['answer'].lower()=='yes':
                                                
                                                #TO DO
                                                
                                                for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                    if sublabel['label_slug']=='is_it_joint_or_single_life__70':
                                                        if sublabel['answer'].lower()=='joint':
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=5).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)
                                                        else:
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=5).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)    
                                                    
                                                    if sublabel['label_slug']=='do_you_smoke__72':
                                                        if (sublabel['answer']).lower()=='yes':
                                                            medical_conditions_smoke=True  
                                                        else:
                                                            medical_conditions_smoke =False  
                                                    if sublabel['label_slug']=='do_you_have_any_medical_conditions_of_note__73':
                                                        if (sublabel['answer']).lower()=='yes':
                                                            medical_conditions=True
                                                            
                                                        else:
                                                            medical_conditions =False
                                                        if medical_conditions or medical_conditions_smoke:   
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=6).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj)   
                                                        if not medical_conditions and not medical_conditions_smoke:
                                                            recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=6).first()
                                                            recommendation_notification_save(client=surveyform.client_id,advisor=surveyform.advisor_id,recommendation_status=recommendation_status_obj,is_deleted=True)
                                                                
                                                                


    
                                except Exception as e:
                                    print("error in draft recommendation reminders")
                                    print(str(e))
                                    logger.exception("Exception in survey - draft reminders : {} - {}".format(str(e), request.path), extra={})


                               
                                if subcategory['subcategory_slug_name'] in ['private_pensions_17','previous_employment_13','private_insurance_20','employer_benefits_16']:
                                    for label in label_list:
                                        if (label['label_slug'] in ['pension_64',"do_you_have_any__68","do_you_have_any__69","type_of_pension_61"]):
                                            for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                #print("sublabel is",sublabel['label'])
                                                if (sublabel['label_slug'] in ['provider_115','provider_142']):
                                                    try:
                                                        pension_providers.objects.get_or_create(name=sublabel['answer'])
                                                    except Exception as e:
                                                        print("couldnt create1"+str(e))
                                                        logger.exception("Exception in survey - could not add provider : {} - {}".format(str(e), request.path), extra={})

                                                if (sublabel['label_slug'] in ['provider_value_funds__150','value__provider__type__funds__145']):
                                                    for nested_sublabel in (sublabel['sub_labels'][0]['sub_label_data']):
                                                        if (nested_sublabel['label_slug'] in ['provider_112','provider_133']):
                                                           
                                                            try:
                                                                pension_providers.objects.get_or_create(name=nested_sublabel['answer'])
                                                            except Exception as e:
                                                                print("couldnt create2" + str(e))
                                                                logger.exception("Exception in survey - could not add pension provider : {} - {}".format(str(e), request.path), extra={})


                        if ((surveyform.category['category_slug_name'] == 'plans___atr_27') and (str(surveyform.category['category_id']) in updated_category_id_list)):
                            for subcategory in surveyform.form_data:
                                label_list = subcategory['subcategory_data']
                                try:
                                    ##########################checklist ##############################
                                    if subcategory['subcategory_slug_name'] == 'attitude_to_risk_29':
                                        atr_result=atr_completed_check(client)
                                        
                                        check_list=[8,9,10,13,14,15,16,18]
                                        update_checklist(client,check_list,atr_result)
                                    elif subcategory['subcategory_slug_name'] == 'financial_plans_28':
                                        for label in label_list:
                                            if (label['label_slug'] == 'in_the_long_term__25___do_you_have_any_major_plans_you_think_will_affect_you_financially__139'):
                                                for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                    if sublabel['label_slug']=='retirement_age_143':
                                                        if not sublabel['answer']:
                                                            client.retire_age =None
                                                        else:
                                                            client.retire_age=int(sublabel['answer'])
                                                        client.save()

                                except Exception as e:
                                    print("error here")
                                    print("atr exception"+str(e))
                                    logger.exception("Exception in survey - plans and atr : {} - {}".format(str(e), request.path), extra={})

                        #loop for networth calculation
                        if (surveyform.category['category_slug_name'] in ['net_worth_summary_21','occupation_info_11','income___expenditure_summary_14'] ):
                            for subcategory in surveyform.form_data:
                                label_list = subcategory['subcategory_data']
                                print(subcategory['subcategory_slug_name'])
                                if subcategory['subcategory_slug_name'] == 'income___expenditure_15':
                                    for label in label_list:
                                        if (label['label_slug'] == 'net_monthly_income_54') and label['answer']:
                                            income_asset_details['monthly_income'] = Decimal(label['answer'])
                                if subcategory['subcategory_slug_name'] == "assets_24":
                                    try:
                                        label = subcategory['subcategory_data']
                                        Net_Worth = 0
                                        net_cash_amount=0
                                        for label_data in label:
                                            for index in range(0,len(label_data['sub_labels'])):
                                                print('\n\n\n\n ============================= INDEX loop ',index,' ================================\n\n\n')
                                                cash = False
                                                for sublabel in (label_data['sub_labels'][index]['sub_label_data']):
                                                    if sublabel['label_slug'] == 'type_of_asset_75'and (sublabel['answer'] == 'Cash'):
                                                       
                                                        cash = True
                                                        
                                                    if sublabel['label_slug']=='amount_128' and sublabel['answer']:
                                                        
                                                        Net_Worth=Net_Worth+Decimal(sublabel['answer'])
                                                        if cash:
                                                            print("ASSETS CASH")
                                                            net_cash_amount=net_cash_amount+Decimal(sublabel['answer'])
                                        
                                        net_worth_dict['net_asset_amount'] = Net_Worth
                                        income_asset_details['asset_cash_amount'] = net_cash_amount
                                    except Exception as e:
                                        print("exception assets",e)
                                        logger.exception("Exception in survey - assets : {} - {}".format(str(e), request.path), extra={})

                                ####
                                if subcategory['subcategory_slug_name'] == "private_pensions_17":
                                    for label in label_list:
                                        try:
                                            if (label['label_slug'] =='do_you_have_any__68'):
                                                if (label['answer']).lower()=='yes':
                                                    for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                        for index in range(0,len(sublabel['sub_labels'])):
                                                            sublabel_new = sublabel['sub_labels'][index]['sub_label_data']
                                                            for sub_data in sublabel_new:
                                                                if sub_data['label_slug']=='value_113':
                                                                    if sub_data['answer']:
                                                                        if 'private_pensions'in net_worth_dict and  net_worth_dict['private_pensions']:
                                                                            net_worth_dict['private_pensions']=Decimal(net_worth_dict['private_pensions'])+Decimal(sub_data['answer'])
                                                                        else:
                                                                            net_worth_dict['private_pensions']=sub_data['answer']
                                                                        
                                                  
                                                        
                                        except Exception as e:
                                            print("exception pvt_pension",e)
                                            logger.exception("Exception in survey - pvt pensions : {} - {}".format(str(e), request.path), extra={})

                                if (subcategory['subcategory_slug_name'] =='previous_employment_13'):
                                        
                                    for label in label_list:
                                        try:
                                            if label['label_slug'] == 'do_you_have_fully_funded_state_pension__66':
                                                if not label['answer']:
                                                    print("""""No ANSWER""")
                                                    result='failed'
                                                elif (label['answer']).lower() == 'yes':
                                                    result='passed'
                                                elif (label['answer']).lower() == 'unsure':
                                                    result='amber'
                                                update_checklist(client,[12], result)
                                            if (label['label_slug'] =='pension_64'):
                                                
                                                if (label['answer']).lower()=='yes':
                                                    for sublabel in (label['sub_labels'][0]['sub_label_data']):
                                                        for index in range(0,len(sublabel['sub_labels'])):
                                                            sublabel_new = sublabel['sub_labels'][index]['sub_label_data'][0]
                                                            if sublabel_new['label_slug']=='value_132':
                                                                if sublabel_new['answer']:
                                                                    if 'prev_emp_pension'in net_worth_dict and  net_worth_dict['prev_emp_pension'] and index!=0:
                                                                        net_worth_dict['prev_emp_pension']=Decimal(net_worth_dict['prev_emp_pension'])+Decimal(sublabel_new['answer'])
                                                                    else:
                                                                        net_worth_dict['prev_emp_pension']=sublabel_new['answer']
                                                                        
                                                    if 'prev_emp_pension' in net_worth_dict and  net_worth_dict['prev_emp_pension']:
                                                        prev_emp_pension=Decimal(net_worth_dict['prev_emp_pension'])
                                                    else:
                                                        prev_emp_pension=0

                                        except Exception as e:
                                            print("exception previous_employment_13",e)
                                            logger.exception("Exception in survey - previous employment : {} - {}".format(str(e), request.path), extra={})

                                    
                                if (subcategory['subcategory_slug_name'] =='employer_benefits_16'):
                                    for label in label_list:
                                        try:
                                            if (label['label_slug'] =='pension_value_106'):
                                                
                                                if label['answer'] is not None and label['answer']!='':
                                                    net_worth_dict['employer_benefits_pension'] =Decimal(label['answer'])
                                        except Exception as e:
                                            print("exception employer_benefits",e)
                                            logger.exception("Exception in survey - employer benefits : {} - {}".format(str(e), request.path), extra={})

                                
                    except Exception as e:
                        print("Not inserted")
                        print(str(e))
                        error=str(e)
                        logger.exception("Exception in survey add : {} - {}".format(str(e), request.path), extra={})

                else:
                    print(surveyform.client_id,item['client_id'])
                    print("Client ID mismatch found",item['id'])

            ###checklist update
            checklist_result='failed'
           
            if income_asset_details.get('monthly_income', None) and income_asset_details.get('asset_cash_amount', None):
               
                if Decimal(income_asset_details.get('asset_cash_amount', None)) > 3 * Decimal(income_asset_details.get('monthly_income', None)):
                    checklist_result='passed'

            update_checklist(client, [17], checklist_result)
            advisor_decency_charge=None
            if client.age and client.retire_age:
                diff = client.retire_age - client.age
                if diff <= 0:
                    advisor_decency_charge = 0.3
                if diff<=10:
                    advisor_decency_charge = math.ceil(diff) * 0.3
                elif diff>10:
                    advisor_decency_charge = 4
            recommended_instruments = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,function_list__function_type='1',is_active=True)
            for instrument in recommended_instruments:
                check_advisor_decency(client, instrument, advisor_decency_charge=advisor_decency_charge,update_flag=True)


            print("net_worth_dict-final ",net_worth_dict)
            if 'prev_emp_pension' in net_worth_dict and  net_worth_dict['prev_emp_pension']:
                prev_emp_pension=Decimal(net_worth_dict['prev_emp_pension'])
            else:
                prev_emp_pension=0
           
            if 'private_pensions' in net_worth_dict and  net_worth_dict['private_pensions']:
                private_pensions=Decimal(net_worth_dict['private_pensions'])
            else:
                private_pensions=0
            
            if 'employer_benefits_pension' in net_worth_dict and  net_worth_dict['employer_benefits_pension']:
                employer_benefits_pension=Decimal(net_worth_dict['employer_benefits_pension'])
            else:
                employer_benefits_pension=0

            if 'net_asset_amount' in net_worth_dict and  net_worth_dict['net_asset_amount']:
                net_asset_amount=Decimal(net_worth_dict['net_asset_amount'])
            else:
                net_asset_amount=0
            amount_mortgage_outstanding=0
            property_value=0
            if 'amount_mortgage_outstanding' in net_worth_dict:
                amount_mortgage_outstanding = Decimal(net_worth_dict['amount_mortgage_outstanding'])
            if 'property_value' in net_worth_dict:
                property_value = Decimal(net_worth_dict['property_value'])
            
            total_networth = net_asset_amount+(property_value-amount_mortgage_outstanding)+prev_emp_pension+private_pensions+employer_benefits_pension
            client.net_worth=total_networth
            client.save()


           
            
           
            draftchecklist1 = DraftCheckList.objects.filter(id=4).first()#Is all relevant information regarding the client documented?
            draftchecklist2 = DraftCheckList.objects.filter(id=30).first()#Is there sufficient information to justify the advice ?
            update_or_create_checklist(client, draftchecklist2.id, staff_user)
            if(total_mandatory_labels==total_answered_mandatory_labels):
                update_or_create_checklist(client, draftchecklist1.id, staff_user,result='passed')
               

                
            else:
                update_or_create_checklist(client, draftchecklist1.id, staff_user, result='failed')
                



        except Exception as e:
            print("here the error***************")
            print(str(e))
            logger.exception("Exception in survey data add : {} - {}".format(str(e), request.path), extra={})            
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Error in adding the data'+str(error)

        else:
            try:
                if client_id is not None:
                    queryset = SurveyFormData.objects.all()
                    queryset = queryset.filter(client_id=client_id)
                    serializer = self.get_serializer(queryset, many=True)
                    data = serializer.data
            except Exception as err:
                print("Exception occured as ", err)

            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'You have successfully saved the survey form details'+str(error)
            if data:
                response_data['data'] = data

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '201':
            resp_status = status.HTTP_201_CREATED
        return Response(response_data, status=resp_status)




