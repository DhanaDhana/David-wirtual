from django.shortcuts import render,HttpResponse
from rest_framework.views import APIView
from .serializers import userSerializer
from django.contrib.auth.models import User
from rest_framework.response import Response
from clients.models import Staff,Provider
from .serializers import SpStatementInfoSerializer,Income_IssuedSerializer
from .models import Provider_StatementInfo,Income_Issued
from clients.serializers import UserSerializer,StaffSerializer
from clients.models import Staff,Client,Provider
from django.db.models import Q
from rest_framework import status
import datetime
from datetime import date
import calendar
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework import viewsets
from rest_framework import permissions

# from datetime import datetime
from clients.permissions import IsAdvisor, IsAdministrator, IsOps, IsCompliance, IsAll
# from django.contrib.auth.models import User, Group, Permission

def home(request):
    return HttpResponse("hello")
    

class IsSuperUser(IsAdminUser):
    required_groups=['SuperAdmin']
    
    def has_permission(self, request, view):
        superadmin = request.user.groups.filter(name__in=self.required_groups).exists()
        return bool(request.user and request.user.is_superuser or superadmin)

    
    
    
class searchAdvisorsForMonthlyIssue(APIView):
    permission_classes = (IsAuthenticated,IsAll,IsSuperUser)
    
    def get(self,request):
        
        user=self.request.user
        name = self.request.query_params.get('name', None)
        month = self.request.query_params.get('month', None)
        year=self.request.query_params.get('year',None)
        provider=self.request.query_params.get('provider',None)
        
        # issue=self.request.query_params.get('issue',None)
        
        spstatement_info_qs=Provider_StatementInfo.objects.all()
        income_issue_qs=Income_Issued.objects.all()
        
        response_data={}
        staff_ids=[]
        data=[]
        
         # name splitting (firstname & lastname)
        if name:
            first_name=name.split()[0]
            last_name = " ".join(name.split()[1:])
                  
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] ='advisor not found'
            return Response(response_data)
        
        
        # ytd date range 
        start_date=datetime.date.min.replace(year = int(year))
        current_month=date.today().month
        if current_month == month:
            end_date = date.today()
        else:
            month_year_param= datetime.datetime(int(year),int(month),1)
            month_year_given = month_year_param.replace(day=28) + datetime.timedelta(days=4)
            end_date = month_year_given - datetime.timedelta(days=month_year_given.day)
    
        if provider is not None:
            queryset=income_issue_qs.filter(issued_type=1,statement__month_year__month=month,statement__month_year__year=year,statement__provider=provider)
        else:
            queryset=income_issue_qs.filter(issued_type=1,statement__month_year__month=month,statement__month_year__year=year)
            
        statement_list=queryset.values_list('statement',flat=True).distinct("statement")
        for i in statement_list:
                statement_search=queryset.filter(statement=i).values_list('statement__advisor',flat=True)
                advisor_id=statement_search[0]
                staff_ids.append(advisor_id)  
                
        staff_id_no_duplicates = list(set(staff_ids))
        
        if staff_id_no_duplicates:
            for result in staff_id_no_duplicates:
                
                income_qs=queryset.filter(statement__advisor=result)
                staff_qs=Staff.objects.filter(id=result,user__first_name__istartswith=first_name,user__last_name__istartswith=last_name,created_by=user)
                
                if staff_qs and income_qs:
                    staff_first_name=staff_qs.values_list("user__first_name")
                    staff_last_name=staff_qs.values_list("user__last_name")
     
                    providerStatementInfo_obj=queryset.filter(statement__advisor=result)
                    res_qs=income_issue_qs.filter(statement__advisor=result,issued_type=1,statement__month_year__range=[start_date,end_date])
                    total_fee_list=res_qs.values_list('statement__total_monthly_fee',flat=True)
                    
                    ongoingIncomeAdvisor=providerStatementInfo_obj.values_list('statement__ongoing_fee',flat=True)
                    intialIncomeAdvisor=providerStatementInfo_obj.values_list('statement__initial_fee',flat=True)
                    intialIncomeAdvisor=providerStatementInfo_obj.values_list('statement__initial_fee',flat=True)
                    totalIncomeAdvisor=providerStatementInfo_obj.values_list('statement__total_monthly_fee',flat=True)
                    
                    data.append(
                        {
                        'id':result,
                         'ytd': sum(total_fee_list),
                         'first_name':staff_first_name[0][0],
                         'last_name':staff_last_name[0][0],
                         'ongoing':sum(ongoingIncomeAdvisor),
                         'intial':sum(intialIncomeAdvisor),
                         'total_fee':sum(totalIncomeAdvisor)
                         })
                    
                else:
                    pass
             
            if data:
                response_data['status_code'] = "200"
                response_data['status'] = True
                response_data['message'] ='advisor details fetched'
                response_data['data'] =data
            
            else:
                response_data['status_code'] = "400"
                response_data['status'] = False
                response_data['message'] ='advisor not found'
                
            # print(data)
            return Response(response_data)
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] ='no advisor details found on given month_year'
            
            return Response(response_data)
        
                   
                
class providerUnderAdvisorViewset(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,IsSuperUser,IsAll)
    serializer_class = Income_IssuedSerializer
    queryset = Income_Issued.objects.all()
    

    def get_queryset(self):
        
        queryset=Income_Issued.objects.all()
        advisor = self.request.query_params.get('advisor', None)    
        account_type = self.request.query_params.get('account',None)
        user = self.request.user

        if advisor:
            queryset = queryset.filter(statement__advisor=advisor,issued_type=2,account_type=1)
            return queryset
            
  
    def list(self, request, *args, **kwargs):
        
        response_data={}
        data=[]
        queryset = self.filter_queryset(self.get_queryset())
        print(f'query={queryset}')
       
        
        if queryset is not None:
            income_issue_id = queryset.values_list('id',flat=True)
            
            for i in income_issue_id:
                provider_id = queryset.values_list('statement__provider__name','statement__provider__id').get(id=i)
                client_id = queryset.values_list('statement__client__user__first_name','statement__client__user__last_name','statement__client__id').get(id=i)
                
                suggested_reason= queryset.values_list('suggested_reason__reason_name').get(id=i)
                amount= queryset.values_list('amount').get(id=i)
                
                income_type= queryset.values_list('income_type').get(id=i)
                start_date =  queryset.values_list('statement__month_year',flat=True).get(id=i)
                end_date = date.today()
                day_count =(end_date - start_date).days
                
               
                income_obj = queryset.filter(id=i)
                serializer = self.get_serializer(income_obj, many=True)
                provider_serial=serializer.data
                
                for details in provider_serial:
                    income_type=details['income_type']
                
              
                data.append(
                    {
                        'provider_id': f'{provider_id[1]}',
                        'provider_name': f'{provider_id[0]}',
                        'client_id':client_id[2],
                        'unmatched_type':income_type,
                        'amount':amount[0],
                        'client_name':f'{client_id[0]} {client_id[1]}',
                        'suggested_reason':suggested_reason[0],
                        'day-count': day_count
                    })
                        
        else:      
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'advisor id not given'
            resp_status = status.HTTP_400_BAD_REQUEST
            return Response(response_data,status=resp_status)
  
    
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'provider and client details retrieve'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK  
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'not found'
            resp_status = status.HTTP_400_BAD_REQUEST
            
        return Response(response_data,status=resp_status)

        
class providerDetailsInMonthlyIssue(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,IsSuperUser,IsAll)
    serializer_class = Income_IssuedSerializer
    queryset = Income_Issued.objects.all()
    

    def get_queryset(self):
        
        queryset=Income_Issued.objects.all()
        
        month = self.request.query_params.get('month', None)
        year=self.request.query_params.get('year',None)  
        
        
        queryset = queryset.filter(statement__month_year__month=month,statement__month_year__year=year,issued_type=1)
        return queryset
            
    def list(self, request, *args, **kwargs): 
        
        month = self.request.query_params.get('month', None)
        year=self.request.query_params.get('year',None)
        
        queryset = self.filter_queryset(self.get_queryset())
        
        data=[]
        response_data={}
        
        # ytd date range 
        start_date=datetime.date.min.replace(year = int(year))
        current_month=date.today().month
    
        if current_month == month:
            end_date = date.today()
        else:
            month_year_param= datetime.datetime(int(year),int(month),1)
            month_year_given = month_year_param.replace(day=28) + datetime.timedelta(days=4)
            end_date = month_year_given - datetime.timedelta(days=month_year_given.day)
            
        
        if queryset is not None:
            provider_obj=queryset.values_list('statement__provider__id',flat=True).distinct('statement__provider')
            print(provider_obj)
            for provider in provider_obj:
                
                prov = queryset.filter(statement__provider__id=provider)
            
                provider_name = queryset.values_list('statement__provider__name',flat=True).distinct('statement__provider')
                ytd_obj=Income_Issued.objects.filter(statement__provider=provider,statement__month_year__range=[start_date,end_date])
                ytd_list=ytd_obj.values_list('statement__total_monthly_fee',flat=True)
                print(ytd_list)
                
                print(provider_name)
                
                intial_fee=prov.values_list('statement__initial_fee',flat=True)
                ongoing_fee=prov.values_list('statement__ongoing_fee',flat=True)
                total_monthly_fee=prov.values_list('statement__total_monthly_fee',flat=True)
              
                serializer = self.get_serializer(prov, many=True)
            
                data.append(
                    {
                        'provider_id': provider,
                        'provider_name': provider_name[0],
                        'intial_fee':sum(intial_fee),
                        'ongoing_fee':sum(ongoing_fee),
                        'total_monthly_fee':sum(total_monthly_fee),
                        'ytd':sum(ytd_list)
                    })
                
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'provider and client details retrieve'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK  
            return Response(response_data)
            
        else:
            pass
            
            
           
            
class advisorDetailsInMonthlyIssue(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,IsSuperUser,IsAll)
    serializer_class = Income_IssuedSerializer
    queryset = Income_Issued.objects.all()
    
    def get_queryset(self):
        
        queryset=Income_Issued.objects.all()
        
        provider = self.request.query_params.get('provider', None)
        month = self.request.query_params.get('month', None)
        year=self.request.query_params.get('year',None)  
        
        if provider is not None:
            queryset = queryset.filter(statement__month_year__month=month,statement__month_year__year=year,issued_type=1,statement__provider=provider)
            return queryset
        else:
            queryset = queryset.filter(statement__month_year__month=month,statement__month_year__year=year,issued_type=1)
            return queryset
            
    def list(self, request, *args, **kwargs): 
        
        month = self.request.query_params.get('month', None)
        year=self.request.query_params.get('year',None)
        
        queryset = self.filter_queryset(self.get_queryset())
        print(queryset)
        
        data=[]
        response_data={}
        
        # ytd date range 
        start_date=datetime.date.min.replace(year = int(year))
        current_month=date.today().month
    
        if current_month == month:
            end_date = date.today()
        else:
            month_year_param= datetime.datetime(int(year),int(month),1)
            month_year_given = month_year_param.replace(day=28) + datetime.timedelta(days=4)
            end_date = month_year_given - datetime.timedelta(days=month_year_given.day)
            
        
        if queryset is not None:
            advisor_obj=queryset.values_list('statement__advisor',flat=True).distinct('statement__advisor')
            print(advisor_obj)
            for advisor in advisor_obj:
                
                advisor_qs = queryset.filter(statement__advisor=advisor)
            
                advisor_name = Staff.objects.filter(id=advisor).values_list('user__first_name','user__last_name').distinct('id')
                print(advisor_name)
                
                ytd_obj=Income_Issued.objects.filter(statement__advisor=advisor,statement__month_year__range=[start_date,end_date])
                ytd_list=ytd_obj.values_list('statement__total_monthly_fee',flat=True)
                print(ytd_list)
                
                # print(provider_name)
                
                intial_fee=advisor_qs.values_list('statement__initial_fee',flat=True)
                ongoing_fee=advisor_qs.values_list('statement__ongoing_fee',flat=True)
                total_monthly_fee=advisor_qs.values_list('statement__total_monthly_fee',flat=True)
              
                serializer = self.get_serializer(advisor_qs, many=True)
            
                data.append(
                    {
                        'provider_id':advisor,
                        'provider_name': advisor_name[0][0],
                        'intial_fee':sum(intial_fee),
                        'ongoing_fee':sum(ongoing_fee),
                        'total_monthly_fee':sum(total_monthly_fee),
                        'ytd':sum(ytd_list)
                    })
                
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'provider and client details retrieve'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK  
            return Response(response_data)
            
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'not found'
            return Response(response_data)
            
            
            
            
class clientDetailsInMonthlyIssue(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,IsSuperUser,IsAll)
    serializer_class = Income_IssuedSerializer
    queryset = Income_Issued.objects.all()
    
    def get_queryset(self):
        queryset=Income_Issued.objects.all()
        
        advisor = self.request.query_params.get('advisor', None)
        month = self.request.query_params.get('month', None)
        year=self.request.query_params.get('year',None)  
        
        if advisor is not None:
            queryset = queryset.filter(statement__month_year__month=month,statement__month_year__year=year,issued_type=1,statement__advisor=advisor)
            return queryset
        else:
            queryset = queryset.filter(statement__month_year__month=month,statement__month_year__year=year,issued_type=1)
            return queryset
            
    def list(self, request, *args, **kwargs): 
        
        data=[]
        response_data={}
        
        month = self.request.query_params.get('month', None)
        year=self.request.query_params.get('year',None)
        
        queryset = self.filter_queryset(self.get_queryset())
      
 
        # ytd date range 
        start_date=datetime.date.min.replace(year = int(year))
        current_month=date.today().month
    
        if current_month == month:
            end_date = date.today()
        else:
            month_year_param= datetime.datetime(int(year),int(month),1)
            month_year_given = month_year_param.replace(day=28) + datetime.timedelta(days=4)
            end_date = month_year_given - datetime.timedelta(days=month_year_given.day)
            
        
        if queryset is not None:
            
            provider_statement_obj=queryset.values_list('statement',flat=True).distinct('statement')
            # print(client_obj)
            
            for statement_id in provider_statement_obj:
                
                statement_qs = queryset.filter(statement=statement_id)
            
                client_obj = statement_qs.values_list("statement__client","statement__client__user__first_name","statement__client__user__last_name")
                # print(client_name)
                
                ytd_obj=Income_Issued.objects.filter(statement__advisor=client_obj[0][0],issued_type=1,statement__month_year__range=[start_date,end_date])
                ytd_list=ytd_obj.values_list('statement__total_monthly_fee',flat=True)
                # print(ytd_list)
                
                # print(provider_name)
                
                intial_fee=statement_qs.values_list('statement__initial_fee',flat=True)
                ongoing_fee=statement_qs.values_list('statement__ongoing_fee',flat=True)
                total_monthly_fee=statement_qs.values_list('statement__total_monthly_fee',flat=True)
              
                serializer = self.get_serializer(statement_qs, many=True)
            
                data.append(
                    {
                        'client_id': client_obj[0][0],
                        'client_name': client_obj[0][1],
                        'intial_fee': intial_fee[0],
                        'ongoing_fee': ongoing_fee[0],
                        'total_monthly_fee':total_monthly_fee[0],
                        'ytd': sum(ytd_list)
                    })
                
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'provider and client details retrieve'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK  
            return Response(response_data)
            
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'not found'
            return Response(response_data)           
            
            
            
            
            
            
class searchAdvisorPendingIssue(APIView):
    permission_classes = (IsAuthenticated,IsSuperUser,IsAll)
    
    def get(self,request):
        
        user=self.request.user
        
        name = self.request.query_params.get('name', None)
        sp_id= self.request.query_params.get('sp_id', None)
        account= self.request.query_params.get('account', None)
        provider=self.request.query_params.get('provider', None)
        
        spstatement_info_qs=Provider_StatementInfo.objects.all()
        income_issue_qs=Income_Issued.objects.all()
        
        response_data={}
        staff_ids=[]
        data=[]
        
        # name splitting (firstname & lastname)
        if name:
            first_name=name.split()[0]
            last_name = " ".join(name.split()[1:])
                  
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] ='advisor not found'
            return Response(response_data)
        
        if account is not None:
            account_type_qs=income_issue_qs.filter(issued_type=2,account_type=account)
            statement_list=account_type_qs.values_list('id',flat=True).distinct('id')
          
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] ='invalid account type'
            return Response(response_data)
            
            
        for i in statement_list:
            
            staff_id=income_issue_qs.values_list('statement__advisor',flat=True).get(id=i)
            staff_qs=Staff.objects.filter(id=staff_id,user__first_name__istartswith=first_name,user__last_name__istartswith=last_name,created_by=user)
            if staff_qs:
                advisor_name=staff_qs.values_list("user__first_name","user__last_name")
                data.append(
                        {
                            'income_issued_id':i,
                            'advisor_id':staff_id,
                            'advisor_name':f'{advisor_name[0][0]} {advisor_name[0][1]}',
                            # 'intial_fee':intial,
                            # 'unmatched_percentage':unmatched_percentage
                            })
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] ='advisor details fetched'
            response_data['data'] =data
            
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] ='advisor not found'
        
        return Response(response_data)
        
        
        
class advisorDetailsInPending(APIView):
    permission_classes = (IsAuthenticated,IsSuperUser,IsAll)
    income_issue_qs=Income_Issued.objects.all()
    
    def get(self,request):
        
        user=self.request.user
        data=[]
        response_data={}
        income_issue_qs=Income_Issued.objects.all()
        advisor= self.request.query_params.get('advisor', None)
        account= self.request.query_params.get('account', None)
        
        queryset = income_issue_qs.filter(statement__advisor=advisor,issued_type=2,account_type=account)
        
        initial_fee=queryset.values_list('statement__initial_fee',flat=True)
        ongoing_fee=queryset.values_list('statement__ongoing_fee',flat=True)
        total_monthly_fee=queryset.values_list('statement__total_monthly_fee',flat=True)
        
        
        total_statement_under_advisor = income_issue_qs.filter(statement__advisor=advisor).values_list('statement').distinct('statement')
        total_pending_issue= income_issue_qs.filter(statement__advisor=advisor,issued_type=2).values_list('statement').distinct('statement')
        unmatched_percentage = (len(total_pending_issue)/len(total_statement_under_advisor))*100
        
        
        data.append(
                        {
                            'advisor_id':advisor,
                            'intial_fee':sum(initial_fee),
                            'ongoing_fee':sum(ongoing_fee),
                            'total_monthly_fee':sum(total_monthly_fee),
                            'unmatched_percentage':unmatched_percentage
                            })
        
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] ='advisor details fetched'
            response_data['data'] =data
            
        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] ='advisor not found'
                

        return Response(response_data)
                    
        
    
    
        
        
        
        
        
        
        
