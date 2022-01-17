import requests
import json
import datetime
import hashlib
from django.conf import settings
import requests
import shutil
from django.core.files import File
from os.path import basename
from urllib.request import urlretrieve, urlcleanup
from urllib.parse import urlsplit
import random
import math,os,sys
from pathlib import Path
# import xmltojson

from .models import Smartserach,CategoryAndSubCategory,Smartserachlog,ClientTask,Staff,Client,TaskCollection

from data_collection.models import SurveyFormData
from .utils import client_profile_completion,add_task_activity

headers={'Accept-Version': '2'}

def authentication():
    try :
        original_token =settings.SMART_SEARCH_TOKEN+str(datetime.date.today())
        company_token = hashlib.md5(original_token.encode())
 
        request_json= {
                "company_name": settings.COMPANY_NAME,
                "company_token": company_token.hexdigest(),
                "user_email": settings.SMART_SEARCH_EMAIL,
                
             }
        response = requests.post(settings.SMART_SEARCH_URL+"auth/token",headers=headers,json=request_json)
        print("smart search authentication status code ",response.status_code)
        if response:
            response_data = response.json()
            access_token = response_data['data']['attributes']['access_token']

            smart_search_log_save(request_json,response_data,settings.SMART_SEARCH_URL+"auth/token","post")
            return access_token
        else:
            response_data = {"data":"Html content smart search token not generated"}
            smart_search_log_save(request_json,response_data,settings.SMART_SEARCH_URL+"auth/token","post")
            return response.status_code
    
    except Exception as e:
        print("error in smart search token generation: ",e)
        return '400'
def smart_search_log_save(request,response,url,method):
   
    try:
       
        smart_search_obj = Smartserachlog.objects.create(request_msg=request,response_msg=response,request_url=url,method=method.upper() )
    except Exception as e:
        print("exception in log ",e)
    return smart_search_obj

def post_individual_uk_aml(client):
    
    title =""
    address=""

    dob=""
    risk_level=""
    cra=""
    postcode=""
    street_2=""
    region=""
    duration=""
    flat=""
    building=""
    street_1=""
    town=""
    risk_level="normal"

    category = CategoryAndSubCategory.objects.filter(category_slug_name='personal_information_7').first()
    if category:
        try:
            surveyform = SurveyFormData.objects.filter(client_id=client.id, category_id=category.id).first()
           
            if surveyform is not None:
                for subcategory in surveyform.form_data:
                    
                    label_list = subcategory['subcategory_data']
                    if subcategory['subcategory_slug_name'] == "basic_info_8":
                        for label in label_list:
                            if (label['label_slug'] == 'title_16'):
                                title = label['answer']
                            if (label['label_slug'] == 'dob_84'):
                                dob = label['answer']
                                if dob:
                                    dob = datetime.datetime.strptime(dob, "%Y-%m-%dT%H:%M:%S.%fZ")
                                    dob = dob.strftime("%d-%m-%Y")
                            

                    if subcategory['subcategory_slug_name'] =='contact_details_10':
                        for label in label_list:
                            
                            if (label['label_slug'] == 'building_168'):
                                building = label['answer']
                            
                            if (label['label_slug'] == 'street_1_169'):
                                street_1 = label['answer']
                              
                            if (label['label_slug'] == 'town_171'):
                                town = label['answer']
                               
                            if (label['label_slug'] == 'region_172'):
                                region = label['answer']
                               
                            if (label['label_slug'] == 'postcode_173'):
                               
                                postcode = label['answer']
                                    
                           
                            
        except Exception as e:
            print("Error while survey form parse",e)
        
        address =[{"flat":flat,"building":building,"street_1":street_1,"street_2":street_2,"town":town,"region":region,"postcode":postcode,"duration":duration}]

    client_name = {"title":title,"first":client.user.first_name,"middle":"","last":client.user.last_name}

    try:
 
        smart_search_json = {"client_ref":str(client.id),"cra":cra,"risk_level":risk_level,"name":client_name,"addresses":address}
        print("smart_search_json....",smart_search_json)  
       
    except Exception as e:
        print("Error while form json",e)   

    return smart_search_json    



def random_generator():

    digits = [i for i in range(0, 10)]  
    random_str = ""
    for i in range(6):

        index = math.floor(random.random() * 10)
        random_str += str(digits[index])
    return random_str
    

def download_file(**kwargs):
    url = kwargs.get('url',None)
    client_id = kwargs.get('client_id',None)
    ssid = kwargs.get('ssid',None)
    search_result = kwargs.get('search_result',None)
    advisor = kwargs.get('advisor',None)
    smart_search_log_obj = kwargs.get('smart_search_log_obj',None)
    is_update = kwargs.get('is_update',None)
    client_task_obj = kwargs.get('client_task_obj',None)
    smart_search_obj = kwargs.get('smart_search_obj',None)
    second_cra = kwargs.get('second_cra',None)
    
    try:
        smart_search_res =None
        random_num =random_generator()
        filename = str(client_id.id)+'_' +str(datetime.datetime.now().date().strftime("%d-%m-%Y"))+"_"+str(random_num)+".pdf"

        tempname,_ = urlretrieve(url,filename)
        if is_update is True:
        
            smart_search_obj.document_path.save(tempname, File(open(tempname, 'rb')))
            smart_search_obj.status=search_result
            smart_search_obj.smartserachlog=smart_search_log_obj
            smart_search_obj.ssid=ssid
            smart_search_obj.save()
        if is_update is False:
            
            try:
                smart_search_res = Smartserach.objects.create(created_by=advisor,client=client_id,smartserachlog=smart_search_log_obj,status=search_result,ssid=ssid,task=client_task_obj)
                
                smart_search_res.document_path.save(tempname, File(open(tempname, 'rb')))
                
            except Exception as e:
                print("exception in Smartserach add ",e)
        if second_cra is True:
            
            smart_search_obj.document_path.save(tempname, File(open(tempname, 'rb')))
            smart_search_obj.status=search_result
            smart_search_obj.save()
        
        file_to_remove = Path(tempname)
        try:
            file_to_remove.unlink()
        except Exception as e:
            print("exception while file removal",e)
            


        return smart_search_res
    except Exception as e:
        print("exception in Smartserach - download_file",e)
    finally:
        urlcleanup()

def fetch_ssid(client):
    category = CategoryAndSubCategory.objects.filter(category_slug_name='personal_information_7').first()
    if category:
        try:
            smart_search_obj=None
            status_code=None
            surveyform = SurveyFormData.objects.filter(client_id=client.id, category_id=category.id).first()
            NI_number = None
            ssid=None
            
            if surveyform is not None:
                for subcategory in surveyform.form_data:
                    
                    label_list = subcategory['subcategory_data']
                    if subcategory['subcategory_slug_name'] == "basic_info_8":
                        for label in label_list:
                            if (label['label_slug'] == 'ssid_175'):
                                
                                ssid = label['answer']
                                if ssid =='':
                                    ssid=None
                                
        except Exception as e:
            print("Exception while fetch previous ssid")
        print("previous ssid ",ssid)
        return ssid



def check_request_data(client,smart_search_json,smart_search_token,client_task_obj,administrator):
    print("==============================check_request_data============================")
    json_check=False
    ssid_check = False
    data = {"doc_path":None,"result":None,"ssid":None}

    try:
        
        smart_search_obj = Smartserach.objects.filter(client=client).last()
        
        advisor=smart_search_obj.created_by
        prev_ssid = fetch_ssid(client)
        if prev_ssid=='':
            prev_ssid=None
        
        if smart_search_obj.ssid == str(prev_ssid) or prev_ssid is None:
            ssid_check=True
         
       
        request_msg = json.dumps(smart_search_obj.smartserachlog.request_msg, sort_keys=True)
        smart_search_json = json.dumps(smart_search_json, sort_keys=True)
        
        print("smart_search_json from survey",smart_search_json)
        print("\n\n request_msg from log",request_msg)
        
        if request_msg==smart_search_json:
            json_check=True
            
        
        if json_check and ssid_check:
            print("\n======== prev req data and current  data are same ======================")
            status_code='200'
            data={"doc_path":smart_search_obj.document_path.url,"result":smart_search_obj.status,"ssid":smart_search_obj.ssid,'is_kyc_confirmed':client_task_obj.is_kyc_confirmed}
            return data,status_code
        if not json_check or not ssid_check:
            print(json_check,ssid_check)
            if client_task_obj.kyc_ever_confirmed:
                task_collection = TaskCollection.objects.filter(task_slug='kyc_reconfirm_pending').first()
                add_task_activity(client_task=client_task_obj, task_collection=task_collection, created_by=client_task_obj.administrator, task_status='3')
                client_task_obj.current_sub_task = task_collection
                client_task_obj.save()

                    
            print("\n=================prev req data and current  data are different================")
            headers={'Authorization': 'Bearer '+smart_search_token,'Accept-Version': '2'}
            # fetch_smart_search_data
            if not json_check:
                print("address changed .....")
                response = requests.post(settings.SMART_SEARCH_URL + "aml", headers=headers, json=smart_search_json)
                status_code=str(response.status_code)
                response_data = json.loads(response.content.decode('utf-8'))

            if not ssid_check:
                print("ssid  changed .....")
                response_data = {}
                smart_search_res_data,status_code=fetch_smart_search_data(prev_ssid,smart_search_token,client,administrator,client_task_obj)
                


            print("status_code after recheck",status_code)
            

            if client_task_obj.is_kyc_confirmed:
                client_profile_completion(client=client_task_obj.client,phase='post-contract',percentage=10,sign='negative') 
            
            client_task_obj.is_kyc_confirmed=False
            client_task_obj.save()

            
            if status_code=='200' and ssid_check:
                try:
                    # response_data = json.loads(response.content.decode('utf-8'))
                    ssid = response_data['data']['attributes']['ssid']
                    smart_search_log_obj = smart_search_log_save(smart_search_json,response_data,settings.SMART_SEARCH_URL + "aml","post")
                    doc_path = response_data['data']['links']['pdf']['href']
                    search_result = response_data['data']['attributes']['result']

                    print("search_result in check_request_data ===============",search_result)
                    is_update=True
                    
                    smart_search_log_obj = Smartserachlog.objects.filter(id=smart_search_obj.smartserachlog.id).first()
                    download_file(url = doc_path,client_id=client,ssid=ssid,search_result=search_result,advisor=administrator,
                    smart_search_log_obj=smart_search_log_obj,is_update=is_update,client_task_obj=client_task_obj,smart_search_obj=smart_search_obj)
                    data={"doc_path":smart_search_obj.document_path.url,"result":smart_search_obj.status,"ssid":smart_search_obj.ssid,'is_kyc_confirmed':client_task_obj.is_kyc_confirmed}
                except Exception as e:
                    print("can't update data",e)
                #code for second cra and reset  kyc flag
            elif not ssid_check and status_code=='200':
                data={"doc_path":smart_search_res_data.document_path.url,"result":smart_search_res_data.status,"ssid":smart_search_res_data.ssid,'is_kyc_confirmed':client_task_obj.is_kyc_confirmed}

            else:
                
                smart_search_log_obj = smart_search_log_save(smart_search_json,response_data,settings.SMART_SEARCH_URL + "aml","post")
                data={"doc_path":None,"result":None,"ssid":None,'is_kyc_confirmed':client_task_obj.is_kyc_confirmed}
              
            return data,status_code
    except Exception as e:
        print("Error in second cra call",e)  
        response_data={"data":"We haven't been able to find this address. This sometimes happens if a property is a house which has been converted into a flat for example. Please check the address and try again"}
        
        smart_search_log_obj = smart_search_log_save(json.loads(smart_search_json),response_data,settings.SMART_SEARCH_URL + "aml","post")

        data={"doc_path":None,"result":None,"ssid":None,'is_kyc_confirmed':client_task_obj.is_kyc_confirmed}
        status_code='400'
        return data,status_code



def second_cra(ssid,smart_search_token,smart_search_obj):
    try:
        headers={'Authorization': 'Bearer '+smart_search_token,'Accept-Version': '2'}
        smart_search_json = {"result":"pass"}
        response = requests.post(settings.SMART_SEARCH_URL+"aml/"+str(ssid)+"/aml",headers=headers,json=smart_search_json)
        status_code=str(response.status_code)
        print("status_code ",status_code)
        
        if status_code=='200':
            try:
                response_data = json.loads(response.content.decode('utf-8'))
                # print(response_data)
                smart_search_log_obj = smart_search_log_save(smart_search_json,response_data,settings.SMART_SEARCH_URL+"aml/"+str(ssid)+"/aml","put")
                doc_path = response_data['data']['links']['pdf']['href']
                if "relationships" in response_data['data'] and "child" in response_data['data']['relationships']:
                    search_result=response_data['data']['relationships']['child']['data']['attributes']['result']
                else:
                    search_result = response_data['data']['attributes']['result']
                
                print("search_result second_cra ===============",search_result)
                second_cra=True
                # smart_search_obj = smartsearch_obj
                download_file(url = doc_path,search_result=search_result,second_cra = second_cra,
                                smart_search_obj=smart_search_obj,client_id=smart_search_obj.client)
                # data={"doc_path":smartsearch_obj.document_path.url,"result":smartsearch_obj.status,"ssid":smartsearch_obj.ssid,'is_kyc_confirmed':client_task_obj.is_kyc_confirmed}
                status = True
            except Exception as e:
                status = False
                print("second cra update failed",e)
        else:
            
            
            status = False
            # response_data = response.content
            # json_data= xmltojson.parse(response_data)
            # print(json_data)
            json_data = {"data":"No data"}
            smart_search_log_obj = smart_search_log_save(smart_search_json,json_data,settings.SMART_SEARCH_URL+"aml/"+str(ssid)+"/aml","put")
         
        # return status
    except Exception as e:
        print("can't update data while generating token ",e)
        status = False
    return status

def fetch_smart_search_data(ssid,smart_search_token,client_obj,administrator,client_task_obj):
    try:
        headers={'Authorization': 'Bearer '+smart_search_token,'Accept-Version': '2'}
        
        response = requests.get(settings.SMART_SEARCH_URL+"aml/"+str(ssid),headers=headers)
        print("response ",response.status_code,ssid)
        status=str(response.status_code)
        if status=='200' or status=='201':
            response_data = json.loads(response.content.decode('utf-8'))
            
            smart_search_json = {}
            
            # smart_search_json = {"client_ref":str(client_obj.id),"cra":"","risk_level":response_data['data']['attributes']['risk_level'],"name":response_data['data']['attributes']['name'],"addresses":response_data['data']['attributes']['addresses']}
            # print("smart_search_json in ssid fetch ",smart_search_json)
            smart_search_json = post_individual_uk_aml(client_obj)
            print("smart_search_json in ssid fetch ",smart_search_json)
            

            smart_search_check = Smartserach.objects.filter(ssid=ssid,client=client_task_obj.client).last()
            if not smart_search_check:
                smart_search_log_obj = smart_search_log_save(smart_search_json,response_data,settings.SMART_SEARCH_URL+"aml/"+str(ssid),"get")
                doc_path = response_data['data']['links']['pdf']['href']
                if "relationships" in response_data['data']  and "child" in response_data['data']['relationships']:
                    search_result=response_data['data']['relationships']['child']['data']['attributes']['result']
                else:
                    search_result = response_data['data']['attributes']['result']
                smart_search_obj=download_file(url = doc_path,search_result=search_result,is_update=False,
                                client_id=client_obj,advisor=administrator,client_task_obj=client_task_obj,
                                ssid=ssid,smart_search_log_obj=smart_search_log_obj)
            else:   
                smart_search_obj=smart_search_check
                smart_search_log_update = Smartserachlog.objects.filter(id=smart_search_obj.smartserachlog.id).update(request_msg=smart_search_json)
                if "relationships" in smart_search_obj.smartserachlog.response_msg['data']  and "child" in smart_search_obj.smartserachlog.response_msg['data']['relationships']:
                    smart_search_obj.status=smart_search_obj.smartserachlog.response_msg['data']['relationships']['child']['data']['attributes']['result']
                else:
                    smart_search_obj.status=smart_search_obj.smartserachlog.response_msg['data']['attributes']['result']
                smart_search_obj.save()
                status='200'
        else:
            smart_search_obj=None
            response_data={"response":"No results found from given ssid"}
            smart_search_json = {}
            smart_search_log_obj = smart_search_log_save(smart_search_json,response_data,settings.SMART_SEARCH_URL+"aml/"+str(ssid),"get")

            print("No results found from given ssid")
            
        return smart_search_obj,status
    except Exception as e:
        print("exception in fetch smart search data",e)
        status = '400'
        return None,status

                            
def search_previous_aml(client,client_task_id,smart_search_token,administrator,ssid):
        
        try:
            
            if ssid is not None:
                client_id = client.id
                client_task_id = client_task_id
                client_obj = Client.objects.filter(id=client_id).first()
                client_task_obj = ClientTask.objects.filter(id=client_task_id).first()

                try:    
                    smart_search_obj,status_code =  fetch_smart_search_data(ssid,smart_search_token,client_obj,administrator,client_task_obj)
                    if smart_search_obj is not None and status_code=='200':
                        if client_task_obj.is_kyc_confirmed:
                            client_profile_completion(client=client_task_obj.client,phase='post-contract',percentage=10,sign='negative')
                        client_task_obj.is_kyc_confirmed=False
                        if client_task_obj.kyc_ever_confirmed:
                            task_collection = TaskCollection.objects.filter(task_slug='kyc_reconfirm_pending').first()
                            add_task_activity(client_task=client_task_obj, task_collection=task_collection, created_by=client_task_obj.administrator, task_status='3')
                            client_task_obj.current_sub_task = task_collection
                        client_task_obj.save()                        

                except Exception as e:
                    print("exception in fetch_smart_search_data ")
        
        except Exception as e:
            print("exception in search_previous_aml",e)
        return smart_search_obj,status_code