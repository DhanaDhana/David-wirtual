from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User, Group, Permission
from clients.permissions import IsAdvisor, IsAdministrator, IsOps, IsCompliance, IsAll

from clients.models import Client, Company, CategoryAndSubCategory, CategoryLabel,Staff,InstrumentsRecomended
from data_collection.models import SurveyFormData
from cap_outlook_service.outlook_services.models import Email, Event,Attendees
from rest_framework import viewsets, status
from datetime import timezone, timedelta,date
import datetime
import calendar
from dateutil.relativedelta import relativedelta
from django.db.models import Count
from django.conf import settings

def calculate_percentage(total,current_val):
    if current_val and current_val!=0 and total!=0:
        
        perc_res = (current_val/total)*100
        percentage=round(perc_res,2)
        
    else:
        percentage=0
    return percentage

def get_colour_scheme(obj):
    event_count=0
    no_client_flag = True
    attendees = Attendees.objects.filter(event_id=obj.id)
    attendee_list = [att.attendee for att in attendees if att.response_status != '1']


    and_set = None

    for attendee in attendees:
        try:
            client = User.objects.get(email=attendee.attendee, is_staff=False)
        except Exception as e:
            print("exception ",e)
            
        else:
            no_client_flag = False
            event_count += Attendees.objects.filter(attendee=client.email, event__event_start__lt=obj.event_start, event__organizer=obj.user.email).exclude(event__is_cancelled=True).count()
           
            event_count += Attendees.objects.filter(attendee=obj.user.email, event__event_start__lt=obj.event_start, event__organizer=client.email).exclude(event__is_cancelled=True).count()
            


            if attendee.attendee != obj.user.email and (obj.user.email in attendee_list or attendee.attendee in attendee_list) :
                third_scen1 = Attendees.objects.filter(attendee=attendee.attendee, event__event_start__lt=obj.event_start).exclude(event__organizer=obj.user.email).values_list('event')
                event_list1 = Event.objects.filter(id__in=third_scen1).exclude(is_cancelled=True)
                third_scen2 = Attendees.objects.filter(attendee=obj.user.email, event__event_start__lt=obj.event_start).exclude(event__organizer=attendee.attendee).values_list('event')
                event_list2 = Event.objects.filter(id__in=third_scen2).exclude(is_cancelled=True)

                final_list = event_list1 & event_list2
                event_count+=final_list.count()
                
 
    return no_client_flag, event_count

def calculateintercactiontype(strt_date,end_date,advisor_list,data,flag):
    
    unique_id=len(data)+1
    count_dict = {'first':0, 'second':0, 'client':0}
   
    event_obj=Event.objects.filter(user__id__in=advisor_list,event_start__date__range=(strt_date, end_date))
   
    for obj in event_obj:
        no_client_flag,event_count = get_colour_scheme(obj)
        if no_client_flag:
            print("no_client_flag")
            
        elif event_count==0:
            count_dict['first']+=1
        elif event_count in [1,2]:
            count_dict['second']+=1
        elif event_count>2:
            count_dict['client']+=1

    month = calendar.month_abbr[strt_date.month]
    year=strt_date.year
    if flag=='monthly':
        data.append({"id":unique_id,"type":"month","year":year,"month_name":month, 'first_meeting_count':count_dict['first'], 'second_meeting_count':count_dict['second'], 'client_meeting_count':count_dict['client']})
   
    if flag=='daily':

        strt_date =strt_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        data.append({"id":unique_id,"type":"day","year":year,"month_name":month,'start_date':strt_date, 'first_meeting_count':count_dict['first'], 'second_meeting_count':count_dict['second'], 'client_meeting_count':count_dict['client']})        
   
    if flag=='weekly':
        
        if strt_date.day+7!=end_date.day:
            end_date=strt_date + relativedelta(days=+6)
        strt_date =strt_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date =end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        data.append({"id":unique_id,"name":"week"+str(id),"type":"week","year":year,"month_name":month,'start_date':strt_date,'end_date':end_date, 'first_meeting_count':count_dict['first'], 'second_meeting_count':count_dict['second'], 'client_meeting_count':count_dict['client']})        
    return data

class ClientReferPercentageView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request, *args, **kwargs):
        advisor =self.request.query_params.get('advisor', None)
        
        refer_perc=0.00
        if advisor is not None:
            advisor_obj=Staff.objects.filter(id=advisor).first() 
           
                
            if advisor_obj:
                total_clients = Client.objects.filter(created_by=advisor_obj.user,is_deleted=False).count()
                print("total_clients ",total_clients)    
                adv_ref_count = Client.objects.filter(created_by=advisor_obj.user, referred_by__isnull=False).count()
                
                print("adv_ref_count ",adv_ref_count)
                refer_perc = calculate_percentage(total_clients,adv_ref_count)
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "Refer percentage fetched successfully",
            'data': refer_perc
        }
        return Response(response_data, status=status.HTTP_200_OK)


class ChecknewclientsView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request,*args, **kwargs):
        data =[]
        advisor =self.request.query_params.get('advisor', None)
        if advisor:
            advisor_obj=Staff.objects.filter(id=advisor).first() 
           

            if advisor_obj:
                for count in range(11,-1,-1):
                    new_client_count=0
                    exist_client_count=0
                    prev_cal=datetime.date.today() + relativedelta(months=-count)
                    strt_date=prev_cal.replace(day=1)
                    print("strt_date ",strt_date)
                    temp=count-1
                    end_date=datetime.date.today() + relativedelta(months=-temp)
                    end_date=end_date.replace(day=1) - timedelta(days=1)
                    
                    new_client_count = Client.objects.filter(referred_by=None, create_time__range=(strt_date, end_date), created_by=advisor_obj.user).count()
                    exist_client_count=Client.objects.filter(created_by=advisor_obj.user,create_time__range=(strt_date, end_date),referred_by__isnull=False).count()
                  
                    print("end_date ",end_date)
                  
                    name = calendar.month_abbr[strt_date.month]+" "+str(strt_date.strftime("%y"))
                    data.append({"name": name, "new_client": new_client_count, "existing_client": exist_client_count})
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "data fetched for new client vs existing client",
            'data':data
        }
        return Response(response_data)


class ToprefererView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request,*args, **kwargs):
        data = []
        advisor =self.request.query_params.get('advisor', None)
        if advisor:
            advisor_obj=Staff.objects.filter(id=advisor).first() 
            client_obj=Client.objects.filter(created_by=advisor_obj.user, referred_by__isnull=False).values('referred_by').annotate(total=Count('referred_by')).order_by('-total')[:10]
            for client_res in client_obj:
                user_obj=User.objects.filter(id=client_res['referred_by'],is_staff=False).first() 
                if user_obj:
                    user_name = user_obj.first_name+" "+user_obj.last_name
                    data.append({"name": user_name, "count": client_res['total']})
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "Top refer details fetched successfully.",
            'data':data
        }
        return Response(response_data)



class AverageageView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request, *args, **kwargs):
        data = []
        response_data = {}
        advisor =self.request.query_params.get('advisor', None)
        user = self.request.user
        
        if advisor:
            advisor_obj=Staff.objects.filter(id=advisor).first() 
            client_obj=Client.objects.filter(created_by=advisor_obj.user)
        else:
            client_obj = Client.objects.filter(created_by=user).order_by("-id")

        
        below_30=0
        below_40=0
        below_50=0
        below_60=0
        below_70=0
        below_80=0
        above_80=0
        
        try:
            for client_res in client_obj:
                got_age = False
                category = CategoryAndSubCategory.objects.filter(category_slug_name='personal_information_7').first()
                if category:
                    try:
                        surveyform = SurveyFormData.objects.filter(client_id=client_res.id, category_id=category.id).first()
                        if surveyform is not None:
                            for subcategory in surveyform.form_data:
                                label_list = subcategory['subcategory_data']
                                if subcategory['subcategory_slug_name'] == "basic_info_8":
                                    for label in label_list:
                                        if (label['label_slug'] == 'dob_84'):
                                            dob = label['answer']
                                            if dob:
                                                dob = datetime.datetime.strptime(dob, '%Y-%m-%dT%H:%M:%S.%fZ')
                                                today = date.today()
                                                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                                                if age<30:
                                                    below_30+=1
                                                elif age>=30 and age<40:
                                                    below_40+=1
                                                elif age>=40 and age<50:
                                                    below_50+=1
                                                elif age>=50 and age<60:
                                                    below_60+=1
                                                elif age>=60 and age<70:
                                                    below_70+=1  
                                                elif age>=70 and age<80:
                                                    below_80+=1 
                                                else :
                                                    above_80+=1
                                            got_age=True
                                            break
                                if got_age:
                                    break

                    except Exception as exp:
                        print('Error in survery form fetching  ',exp)

            
            data.append({"label_name":"Below 30","age_of_client":below_30})
            data.append({"label_name":"30 - 40","age_of_client":below_40})
            data.append({"label_name":"40 - 50","age_of_client":below_50})
            data.append({"label_name":"50 - 60","age_of_client":below_60})
            data.append({"label_name":"60 - 70","age_of_client":below_70})
            data.append({"label_name":"70 - 80","age_of_client":below_80})
            data.append({"label_name":"Above 80","age_of_client":above_80})
            
    
        except Exception as e:
            response_data['status_code'] = '400'
            response_data['status'] = True
            response_data['message'] = "Error "+str(e)
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'average age details fetched successfully.'
            response_data['data'] =data
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)





class AtpView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)
    
    def get(self, request,*args, **kwargs):
        user = self.request.user
        data={"total_client":0,"accept_ratio":0,"reject_ratio":0}
        
        
        confirm_client_count = 0
        advisor =self.request.query_params.get('advisor', None)
        prev_cal=datetime.date.today() + relativedelta(months=-1)
        strt_date=prev_cal.replace(day=1)
        if advisor:
            advisor_obj=Staff.objects.filter(id=advisor).first() 
            client_obj=Client.objects.filter(created_by=advisor_obj.user, create_time__gte=strt_date).order_by("-id")
            if client_obj:
                data['total_client'] = client_obj.count()
                confirm_client_count = client_obj.filter(is_confirmed_client=True).count()
                reject_count = client_obj.count() - confirm_client_count
                data['accept_ratio'] = calculate_percentage(data['total_client'],confirm_client_count)
                data['reject_ratio'] = calculate_percentage(data['total_client'],reject_count)
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "accept/reject ratio fetched successfully.",
            'data':data
        }
        return Response(response_data)



class MeetingbyMonthView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request):
        user = self.request.user
        data=[]
        week_flag=daily_flag=monthly_flag=False
        advisor =self.request.query_params.get('advisor', None)
        monthly =self.request.query_params.get('monthly', None)
        weekly =self.request.query_params.get('weekly', None)
        daily =self.request.query_params.get('daily', None)
        if daily is not None:
            daily_flag=True
        if weekly is not None:
            week_flag=True
        if monthly is not None:
            monthly_flag=True
        
        if advisor is not None:
            advisor_list=Staff.objects.filter(id=advisor).values_list('user__id')
            
            
        else:
            staff_obj = Staff.objects.filter(created_by=user).first() 
            advisor_list=Staff.objects.filter(user__groups__name='Advisor', company=staff_obj.company).values_list('user__id')

        if weekly is not None or advisor is not None and monthly_flag==False and  daily_flag==False:

            current_date = datetime.date.today()
            #  - timedelta(days=13)
            end_week = current_date - datetime.timedelta(days=current_date.isoweekday() % 7)
            
            strt_week = end_week - datetime.timedelta(days=21)
            print("strt_week ",strt_week," end_week ",end_week,"current_date ",current_date)

            end_day_count = current_date.day
            if strt_week.month== current_date.month:
          
                count = strt_week.day
                for i in range(4):
                    
                   
                    count_dict = {'first':0, 'second':0, 'client':0}
                    strt_week=strt_week.replace(day=count)
                    temp=count+6
                    count = count+7
                    
                    if end_day_count<temp:
                        temp = temp-(temp-current_date.day)
                    end_date=strt_week.replace(day=temp)
                    print("start_date",strt_week," end_date ",end_date," temp ",temp)
                    
                    data = calculateintercactiontype(strt_week,end_date,advisor_list,data,'weekly')
            else:
                new_current_date = current_date
                strt_month_last_day=new_current_date.replace(day=1)- datetime.timedelta(days=1)
                diff=strt_month_last_day.day-current_date.day
                for i in range(4):
                    if (strt_month_last_day.day-strt_week.day)>6:
                        end_date = strt_week.replace(day=strt_week.day+6)
                        print("\nsame month week ",strt_week,end_date)
                        data = calculateintercactiontype(strt_week,end_date,advisor_list,data,'weekly')
                        strt_week = strt_week.replace(day=strt_week.day+7)
                    else:
                        diff = strt_month_last_day.day-strt_week.day
                        
                        week_day_remains = 6-diff
                        next_month_date = current_date.replace(day=week_day_remains)
                        end_date = next_month_date
                        print("\ndiffrent month week ",strt_week,next_month_date)
                        data = calculateintercactiontype(strt_week,end_date,advisor_list,data,'weekly')
                        strt_week = next_month_date.replace(day=next_month_date.day+1)

        
        if daily is not None or advisor is not None and week_flag==False and  monthly_flag==False:
            
     
            for count in range(6,-1,-1):
                count_dict = {'first':0, 'second':0, 'client':0}
                start_date=datetime.datetime.today() + relativedelta(days=-count)
                print("start_date",start_date)
                
                temp=count-1
                end_date=datetime.datetime.today() + relativedelta(days=-count)
                print("end_date ",end_date)
                data = calculateintercactiontype(start_date,end_date,advisor_list,data,'daily')
        
       
        
        if monthly is not None or advisor is not None and week_flag==False and  daily_flag==False:
           
            for count in range(11,-1,-1):
                count_dict = {'first':0, 'second':0, 'client':0}
                prev_cal=datetime.date.today() + relativedelta(months=-count)
                strt_date=prev_cal.replace(day=1)
                print("strt_date",strt_date)
                
                temp=count-1
                end_date=datetime.date.today() + relativedelta(months=-temp)
                end_date=end_date.replace(day=1) - timedelta(days=1)
                print("end_date ",end_date)
               
               

                data = calculateintercactiontype(strt_date,end_date,advisor_list,data,'monthly')
                

           
        response_data = {
        'status_code': "200",
        'status': True,
        'message': "meeting list fetched successfully.",
        'data':data
        }
        return Response(response_data)


class RedingtonView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)
    
    def get(self, request):
        total=0
        other=0
        
        other_transfer=0
        advisor =self.request.query_params.get('advisor', None)
        if advisor:
            advisor_list=Staff.objects.filter(id=advisor).first()
            instr_rec_obj=InstrumentsRecomended.objects.filter(advisor=advisor_list, is_active=True)
            
            other = instr_rec_obj.filter(fund_risk='11').count()
            total=instr_rec_obj.count()
            other_list = instr_rec_obj.filter(fund_risk='11').values_list('id', flat=True)
            print(list(other_list))
            
            transfer_list = instr_rec_obj.exclude(map_transfer_from=None).values_list('map_transfer_from',flat=True)
            other_transfer = set(other_list)&set(transfer_list)
            print("other_transfer ",other_transfer)
            mapped_ins = instr_rec_obj.exclude(map_transfer_from=None).values_list('map_transfer_from').count()
            print("total ",total," other ",other," transfer",mapped_ins," other transfer",len(other_transfer))
        percentage=calculate_percentage(total-mapped_ins,other-len(other_transfer))
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "Adherence to CIP (%) fetched successfully.",
            'data':percentage
        }
        return Response(response_data)

