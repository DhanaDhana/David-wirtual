from sys import prefix
from botocore.serialize import QuerySerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from django.template.defaultfilters import filesizeformat
from django.contrib.auth.models import User, Group, Permission
from django.http import FileResponse
from django.template import Context, Template
from django.core.files.storage import FileSystemStorage as server_storage
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from cap_services.settings import BASE_DIR,BASE_URL, MEDIA_ROOT, IS_S3
from cap_services.settings import MEDIA_PATH as MEDIA_URL
from decimal import Decimal
if IS_S3:
    from cap_services.settings import AWS_STORAGE_BUCKET_NAME as bucket
    from cap_services.settings import AWS_S3_ENDPOINT_URL as end_point_url
    from cap_services.settings import AWS_S3_REGION_NAME as region
    from cap_services.settings import AWS_ACCESS_KEY_ID as access_key
    from cap_services.settings import AWS_SECRET_ACCESS_KEY as secret_key
from .utils import render_to_pdf, add_task_activity, calculate_fee,illustration_appsummary_checklists, remove_ilustration_checklist, format_content_for_sr
from rest_framework.decorators import action
from rest_framework import renderers
from django.http import HttpResponse
import random, json, os, datetime
import string,math
import boto3
import ast
from django.utils import timezone as tz
from django.contrib.auth import authenticate
from .smart_search import authentication,post_individual_uk_aml,download_file,check_request_data,smart_search_log_save,second_cra,fetch_smart_search_data,fetch_ssid,search_previous_aml
from django.core.files.storage import default_storage
import requests
from rest_framework import viewsets, status, filters, serializers
from .models import Client, Company, Document, DocumentSetting, ClientLabelData, CategoryAndSubCategory, CategoryLabel, \
    Provider, Instrument, ClientInstrumentInfo, Templates, TemplateCategory, ActivityFlow, StatusCollection, \
    Reminder, ClientTask, TaskCollection, ClientTaskComments, Staff, Job_titles, Lender_names, pension_providers, \
    ClientAudioExtraction, Countries, TaskEvents, CategorySummary, ClientTaskTimeline, \
    FundRisk, FeeRuleConfig, Reason, DraftReccomendation, Function, InstrumentsRecomended, ExtractedData, \
    MasterKeywords, ExtractionKeywordMapping, ClientRecommendationNotification, TemplateAttachments, ClientCheckList, \
    ProductType, DraftCheckList, ATR, SRProviderContent, SRAdditionalCheckContent,IllustrationData,IllustrationKeywordMapping, \
    ClientCheckListArchive,Smartserachlog,Smartserach,RecommendationNotificationStatus,Errorlog
from .utils import pending_status_save, add_activity_flow,client_profile_completion,recommendation_notification_save

from .serializers import ClientSerializer, UserSerializer, CompanySerializer, DocumentSerializer, \
    DocumentSettingSerializer, ProviderSerializer, InstrumentSerializer, ClientInstrumentInfoSerializer, \
    TemplateSerializer, TemplateCategorySerializer, ActivityFlowSerializer, ReminderSerializer, CategorySerializer, \
    ClientTaskSerializer, ClientTaskCommentSerializer, StaffSerializer, JobtitleSerializer, LenderSerializer, \
    PensionproviderSerializer, \
    ClientAudioExtractionSerializer, InstrumentExtractedDataSerializer, CountrySerializer, TaskEventSerializer, \
    CategorySummarySerializer, \
    ClientTaskTimelineSerializer, DraftReccomendationSerializer, FeeRuleConfigSerializer, ReasonSerializer, \
    InstrumentsRecomendedSerializer, ClientRecommendationNotificationSerializer, ExtractedDataSerializer, \
    ClientCheckListSerializer, \
    AdvisorProfileSerializer ,ErrorlogSerializer
    # SmartSearchSerializer
from data_collection.models import SurveyFormData
# from .common.libreoffice import run as update_doc
# from .common.libreoffice import run_S3 as update_S3doc
import re
from django.core.files import File
import io
from pydub import AudioSegment
from pydub.silence import split_on_silence
import shutil
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docxcompose.composer import Composer

from cap_outlook_service.outlook_services.models import Email, OutlookLog
from data_collection.models import SurveyFormData, SubcategoryData, InstrumentExtractedData
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.db.models import Q, query
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.conf import settings


import speech_recognition as sr
import copy
import wave
from bson.objectid import ObjectId
from datetime import timezone, timedelta,date


from django.core.mail import send_mail, EmailMultiAlternatives
from .permissions import IsAdvisor, IsAdministrator, IsOps, IsCompliance, IsAll

from htmldocx import HtmlToDocx
from docx import Document as docx
from .models import get_doc_count
from .checklist import update_or_create_checklist,delete_checklist,update_checklist,check_advisor_decency
from django.db.models import Count
from outlook_app.utils import templatemailsend
import logging    
from cap_services.settings import AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
import boto3
import pathlib
import secrets
import logging    


logger = logging.getLogger('django.request')

def get_random_password():
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for i in range(8))
    return password

def check_password(passwd):
    SpecialSym = list(string.punctuation)
    val = True
    err_message = ''

    if len(passwd) != 8:
        err_message = 'length should 8'
        val = False

    if not any(char.isdigit() for char in passwd):
        err_message = 'Password should have at least one numeral'
        val = False

    if not any(char.isupper() for char in passwd):
        err_message = 'Password should have at least one uppercase letter'
        val = False

    if not any(char.islower() for char in passwd):
        err_message = 'Password should have at least one lowercase letter'
        val = False

    if not any(char in SpecialSym for char in passwd):
        err_message = 'Password should have at least one special character'
        val = False

    return {'val': val, 'err_message': err_message}


def blob_conversion(path, record_name):
    obj = wave.open(path, 'r')
    nchanels = obj.getnchannels()
    sampwidth = obj.getsampwidth()
    sampleRate = obj.getframerate()  # hertz
    duration = 1.0  # seconds
    frequency = 440.0  # hertz
    n = obj.getnframes()
    data = obj.readframes(n)
    import pathlib
    pathlib.Path(os.path.join(MEDIA_ROOT,'survey/')).mkdir(parents=True, exist_ok=True)
    obj1 = wave.open(MEDIA_ROOT + '/survey/' + record_name + '.wav', 'w')
    obj1.setnchannels(1)  # mono
    obj1.setsampwidth(2)
    obj1.setframerate(sampleRate)
    obj1.writeframesraw(data)
    obj1.close()
    obj.close()
    sound_path = MEDIA_ROOT + '/survey/' + record_name + '.wav'
    print("sound_path", sound_path)
    return sound_path



def audioconversion(path, Record, request):
    """
    Splitting the large audio file into chunks
    and apply speech recognition on each of these chunks
    """
    
    key =None
    r = sr.Recognizer()
    # open the audio file using pydub
    sound = AudioSegment.from_wav(path)
    # split audio sound where silence is 700 miliseconds or more and get chunks
    chunks = split_on_silence(sound,
    # experiment with this value for your target audio file
    min_silence_len = 500,
    # adjust this per requirement
    silence_thresh = sound.dBFS-14,
    # keep the silence for 1 second, adjustable as well
    keep_silence=500,
    )
    record_name = Record.split('.')[0]
    folder_name = MEDIA_ROOT+'/survey/'+'audio-chunks'+'_'+record_name
    print("Created new folder",folder_name)
    
    # create a directory to store the audio chunks
    if not os.path.isdir(folder_name):
        os.mkdir(folder_name)
    
    whole_text = ""
    # process each chunk
    for i, audio_chunk in enumerate(chunks, start=1):
        # export audio chunk and save it in the `folder_name` directory.
        chunk_filename = os.path.join(folder_name, f"chunk{i}.wav")
        audio_chunk.export(chunk_filename, format="wav")
        # recognize the chunk
        with sr.AudioFile(chunk_filename) as source:
            audio_listened = r.record(source)
            # try converting it to text
            try:
                text = r.recognize_google(audio_listened)
            except sr.UnknownValueError as e:
                print("UnknownValueError in audio:", str(e))
                # logger.exception("UnknownValueError in audio for value : {} - {}".format(str(e), request.path), extra={})
            else:
                text = f"{text.capitalize()}. "
                whole_text += text
    shutil.rmtree(folder_name)
    print("Extracted text ",whole_text,"\n","Removing folder ",folder_name)
    return whole_text



class CustomObtainAuthToken(ObtainAuthToken):

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        token, created = Token.objects.get_or_create(user=user)
        notification_count = 0
        company_id = None
        company_name = None

        if created:
            staff_obj = Staff.objects.filter(user__id=user.id).first()
            if staff_obj:
                notification_count = staff_obj.notification_count
                company = Company.objects.get(id=staff_obj.company_id)
                company_id = company.id
                company_name = company.name

                exclude_list = ['Can add staff', 'Can change staff', 'Can delete staff', 'Can view staff']
                user_group = Group.objects.filter(user=user).first()
                if user_group:
                    user_type = user_group.name
                    permissions = user_group.permissions.filter().exclude(name__in=exclude_list)
                else:
                    user_type = None
                    permissions = []

                permission_list = [perm.name for perm in permissions]
                login_data = {
                    'token': token.key, 'first_name': user.first_name,
                    'id': user.id, 'last_name': user.last_name,
                    'email': user.email, 'notification_count': notification_count,
                    'company': {'id': company_id, 'name': company_name},
                    'logged_in_user_type': user_type, 'permission_list': permission_list,
                    'staff_id':staff_obj.id
                }
                response_data = {
                    'status_code': "200",
                    'status': True,
                    'message': "User logged in successfully",
                    'data': login_data
                }
            else:
                response_data = {
                    'status_code': "400",
                    'status': False,
                    'message': "Unable to log in with provided credentials",
                }
                
        else:
            response_data = {
                'status_code': "400",
                'status': False,
                'message': "User already logged in! Please log out from all your active sessions and try again",
                'data': {"token": token.key, "is_user_already_logged_in": True}

            }
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class UserLogout(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request, format=None):
        request.user.auth_token.delete()  # TO DO : multiple tokens for single client
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "User logged out successfully.",
        }
        return Response(response_data)


class GroupPermissionView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request, format=None):
        exclude_list = ['Can add staff', 'Can change staff', 'Can delete staff', 'Can view staff']
        user_group = Group.objects.filter(user=request.user).first()
        if user_group:
            user_type = user_group.name
            permissions = user_group.permissions.filter().exclude(name__in=exclude_list)
        else:
            user_type = None
            permissions = []
        permission_list = [perm.name for perm in permissions]

        response_data = {
            'status_code': "200",
            'status': True,
            'message': "User Permission List",
            'data': {"logged_in_user_type": user_type, "permission_list": permission_list}
        }
        return Response(response_data)


def send_alternate_password(user, new_password):
    request_info = {}
    super_user = User.objects.filter(is_superuser=True).first()
    html = '<!DOCTYPE html> <html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"> <head> <meta charset="utf-8"> ' + \
           '<meta name="viewport" content="width=device-width"> <meta http-equiv="X-UA-Compatible" content="IE=edge"> <meta name="x-apple-disable-message-reformatting"> <title>Forgot Password</title> </head> ' + \
           '<body> <div style="max-width:600px; margin: 20px auto 10px auto; padding:20px; border-bottom: 1px solid #ddd; box-sizing: border-box; "> <div style="float:left;width:30%;"> <!--<img src="{{company_logo}}" ' + \
           'style="height: auto;width: 120px;"> --></div> <div style="float: right;width: 70%;"> <p style="margin-top: 0;margin-bottom: 0;text-align: right;"> <a href="http://www.latheandco.co.uk" target="_blank" ' + \
           'style="font-family:Open Sans, sans-serif; font-size:14px; text-decoration: none; color: #222; text-align: right;"> www.latheandco.co.uk </a> </p> </div> <div style="clear: both;"></div> </div> ' + \
           '<div style="max-width:560px; margin: 0 auto; padding: 20px;"> <p style="font-family: ' + "'Roboto'" + ', sans-serif;color: #222;font-size:14px;font-weight: 600; margin: 0; padding: 0;"> Hi {{advisor_name}}, </p> ' + \
           '<p style="font-family: ' + "'Roboto'" + ', sans-serif;color: #222;font-size:14px; line-height: 24px;"> We\'ve received a request to reset your password. Please find your new password below. </p> ' + \
           '<p style="font-family: ' + "'Roboto'" + ', sans-serif;color: #222;font-size:14px;font-weight: 600; background: #F2FDFF; border:1px dashed #8DDDE6 ; padding: 10px; text-align: center;"> {{password}} </p> ' + \
           '<br> <p style="font-family: ' + "'Roboto'" + ', sans-serif;color: #222;font-size:14px; line-height: 24px;"> If you didn\'t request a password reset, please let us know. </p> <p style="font-family: ' + "'Roboto'" + ', ' + \
           'sans-serif;color: #222;font-size:14px; line-height: 24px;"> Thanks, <br> <strong> -Team david </strong> </p> </div> <div style="max-width:560px; margin: 0 auto; border-top: 1px solid #ddd; padding: 20px;"> ' + \
           '<div style="float: left;width: 20%;"> <p style="font-family:' + "'Roboto'" + ', sans-serif;font-size:12px; padding: 0;color:#8A8A8A; text-align:left; font-size: 10px; margin: 0; padding: 0;">Powered by<br> ' + \
           '<img style="width: 57px;" src="{{static_image_path}}/david-logo.png"> </p> </div> <div style="float: left;box-sizing: border-box;"> <p style="font-family:' + "'Roboto'" + ', sans-serif;font-size:12px; padding: 0; ' + \
           'color:#8A8A8A; text-align:left; font-size: 11px; margin: 10px 0 0 0; padding: 0;"> View in Browser | Privacy Policy</p> </div> <div style="clear: both;"></div> </div> </body>.</html>'

    template = Template(html)
    advisor_name = user.first_name + ' ' + user.last_name
    company_logo = Document.objects.get(doc='advisors/company/Lathe_logo.png').doc.url
    context = Context({"advisor_name": advisor_name, "password": new_password,
                       'static_image_path': os.path.join(MEDIA_URL, 'web_images'), 'company_logo': company_logo})
    html = template.render(context)
    msg = EmailMultiAlternatives('Reset Your Password', '', super_user.email, [user.email])
    msg.attach_alternative(html, "text/html")
    msg.send()



class UserForgotPassword(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username', '')
        response_data = {}
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist as e:
                logger.exception("User doesnot exist : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'User does not exist'
            else:
                new_password = get_random_password()
                user.set_password(new_password)
                user.save()
                print('new password ===========> ', new_password)
                send_alternate_password(user, new_password)
                response_data['status_code'] = '200'
                response_data['status'] = True
                response_data['message'] = 'New password has been sent to your email account. Kindly check and reset with new password'
        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Username is required'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class UserResetPassword(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def post(self, request):
        existing_pwd = request.data.get('password', '')
        new_pwd = request.data.get('new_password', '')
        confirm_pwd = request.data.get('confirm_password', '')
        response_data = {}

        if not existing_pwd:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'password is required'
        elif not new_pwd:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'new password is required'
        elif not confirm_pwd:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'confirm password is required'
        else:
            user = authenticate(username=request.user.username, password=existing_pwd)
            if user is not None:
                if new_pwd != confirm_pwd:
                    response_data['status_code'] = '400'
                    response_data['status'] = False
                    response_data['message'] = 'new_password and confirm_password should be same'
                else:
                    valid_pwd = check_password(new_pwd)
                    if valid_pwd['val']:
                        user.set_password(new_pwd)
                        user.save()
                        response_data['status_code'] = '200'
                        response_data['status'] = True
                        response_data['message'] = 'Password has been changed successfully. '
                    else:
                        response_data['status_code'] = '400'
                        response_data['status'] = False
                        response_data['message'] = 'Invalid password'
            else:
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'Old Login Password is invalid'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = User.objects.all()
        staff_obj = Staff.objects.filter(user=self.request.user).first()
        staff_list = Staff.objects.filter(company__id=staff_obj.company.id).values_list('user__id',flat=True)
        client_obj = Client.objects.filter(created_by_id__in=list(staff_list)).values_list('created_by__id',flat=True)
        
        filter_options = dict(self.request.query_params)
        if "client_name" in filter_options:
            filter_options.pop('client_name')
            client_name = self.request.query_params.get('client_name', None)

            if client_name:
                first_name = client_name.split()[0]
                last_name = " ".join(client_name.split()[1:])
                queryset = queryset.filter(Q(first_name__icontains=first_name) | Q(last_name__icontains=first_name))
                if last_name:
                    queryset = queryset.filter(last_name__icontains=last_name)
                
        if 'type' in filter_options.keys():
            user_type = filter_options.pop('type')
            group = Group.objects.filter(name=user_type[0]).first()
            if group:
                queryset = queryset.filter(groups=group)
                
        # Company filter to be added based on self.request.user company
        if 'company' in filter_options.keys():
            filter_options.pop('company')
            staff_obj = Staff.objects.filter(user=self.request.user).first()
            staff_list = Staff.objects.filter(company__id=staff_obj.company.id).values_list('user__id',flat=True)
            queryset = queryset.filter(id__in=list(staff_list))

        # To check if the email id already existing during survey form edit.
        if 'survey_client' in filter_options.keys():
            survey_client_id = filter_options.pop('survey_client')
            if survey_client_id[0]:
                client=Client.objects.filter(id=survey_client_id[0]).first()
                if client:
                    queryset = queryset.exclude(id=client.user.id)

        for option in filter_options.copy():
            if not filter_options[option][0]:
                del filter_options[option]
            else:
                filter_options[option] = filter_options[option][0]
        print(queryset)
        queryset = queryset.filter(**filter_options)
        print(queryset)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'User List',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)


    @action(methods=['get'], detail=False, name='User exist_check')
    def exist(self, request, *args, **kwargs):
        response_data = {}
        data = {'alreadyExists': False}
        email = self.request.query_params.get('email', None)
        survey_client_id = self.request.query_params.get('survey_client', None)

        if email:
            queryset = User.objects.filter(username=email)
            # To check if the email id already existing during survey form edit.
            if survey_client_id:
                client=Client.objects.filter(id=survey_client_id).first()
                if client:
                    queryset = queryset.exclude(id=client.user.id)

            if queryset:
                data['alreadyExists'] = True

        response_data['status_code'] = '200'
        response_data['status'] = True
        response_data['message'] = 'client details fetched'
        response_data['data'] = data
        resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)



class CompanyViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    search_fields = ['^name', ]
    filter_backends = (filters.SearchFilter,)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        is_client_company = self.request.query_params.get('is_client_company', None)
        if is_client_company == 'false':
            queryset = queryset.filter(is_client_company=False)
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Company List',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)


class DocumentSettingViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = DocumentSettingSerializer

    def get_queryset(self):
        queryset = DocumentSetting.objects.all()
        filter_options = dict(self.request.query_params)
        for option in filter_options.copy():
            if not filter_options[option][0]:
                del filter_options[option]
            else:
                filter_options[option] = filter_options[option][0]
        queryset = queryset.filter(**filter_options)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'document settings info',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = DocumentSerializer
    queryset = Document.objects.all()

    def get_queryset(self):
        queryset = Document.objects.all()
        client_id = self.request.query_params.get('client_id', None)
        sr_flag = self.request.query_params.get('sr', None)
        fetch_recent_docs = self.request.query_params.get('fetch_recent_docs', None)
        task_id = self.request.query_params.get('task', None)
        if client_id is not None:
            queryset = queryset.filter(owner=client_id).order_by('-id')
            if sr_flag == 'true':
                queryset = queryset.filter(doc_type='8', is_active=True).order_by('-id').first()
            if task_id: #for showing only task related docs. If task is completed, get all docs based on task_id else get all active documents
                task_det = ClientTask.objects.filter(id=task_id).first()
                if task_det:
                    if task_det.task_status == '3':
                       queryset=queryset.filter(task=task_det).order_by('-id')
                    else:
                       queryset=queryset.filter(task__isnull=True, is_active=True).order_by('-id')
            if fetch_recent_docs == 'true':
                client_instrument_docs=['3','5','7','13','14','15','16','17']
                qset1 = queryset.exclude(doc_type__in=client_instrument_docs).order_by('doc_type','-id').distinct('doc_type')#common docs
                qset2 =queryset.filter(doc_type__in=client_instrument_docs)
                queryset = queryset.filter(id__in=qset1).order_by('-id')
                queryset=queryset | qset2
                queryset=queryset.order_by('-id')
                
        return queryset

    def url_to_dict(self, url, init_path):
        d = {}
        json_list = []
        s3client = boto3.client('s3',aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)        
        result = s3client.list_objects(Bucket=AWS_STORAGE_BUCKET_NAME,Prefix=url, Delimiter='/')
        if (os.path.basename(url[:-1]) not in ['cap', 'brochures']):
            pass
        else:
            if "CommonPrefixes" in result:
                for obj in result.get('CommonPrefixes'):
                    for path in obj.values():
                        old_path = path #store path with / at end
                        if(path[-1]=='/'):
                            path = path[:-1] #remove the end / from path
                         
                        d = {'item_name': os.path.basename(path)}
                        d['item_id'] = datetime.datetime.now().microsecond
                        d['item_size'] = ""
                        d['item_type'] = "folder"
                        d['children'] = self.url_to_dict(old_path, init_path)
                        json_list.append(d)
                if "Contents" in result:
                    for obj in result['Contents']:
                        print("here",obj['Key'])
                        path = obj['Key']
                        queryset = self.filter_queryset(self.get_queryset())
                        
                        if path.startswith(init_path):
                            result = path.replace(init_path, "", 1)               
                        queryset = queryset.filter(doc=result)
                        if queryset:
                            d = {'item_name': os.path.basename(queryset.first().doc.name)}
                            d['item_id'] = queryset.first().id
                            d['item_size'] = queryset.first().doc.size
                            d['item_path'] = queryset.first().doc.url
                            d['item_type'] = "file"
                            json_list.append(d)
            elif "Contents" in result:
                print("else case entered")
                for obj in result['Contents']:
                    print(obj['Key'])
                    path = obj['Key']
                    queryset = self.filter_queryset(self.get_queryset())
                    if path.startswith(init_path):
                        result = path.replace(init_path, "", 1)
                    queryset = queryset.filter(doc=result)
                    if queryset:
                        d = {'item_name': os.path.basename(queryset.first().doc.name)}
                        d['item_id'] = queryset.first().id
                        d['item_size'] = queryset.first().doc.size
                        d['item_path'] = queryset.first().doc.url
                        d['item_type'] = "file"
                        json_list.append(d)
            else :
                pass
        return json_list


    def path_to_dict(self, path, init_path):
        d = {}
        if os.path.isdir(path):
            if (os.path.basename(path) not in ['media', 'cap', 'brochures']):
                pass
            else:
                d = {'item_name': os.path.basename(path)}
                d['item_id'] = datetime.datetime.now().microsecond
                d['item_size'] = ""
                d['item_type'] = "folder"
                d['children'] = [self.path_to_dict(os.path.join(path, x), init_path) for x in os.listdir(path)]
        else:
            queryset = self.filter_queryset(self.get_queryset())
            if path.startswith(init_path):
                result = path.replace(init_path, "", 1)
            queryset = queryset.filter(doc=result)
            if queryset:
                d = {'item_name': os.path.basename(path)}
                d['item_id'] = queryset.filter(doc=result).first().id
                d['item_size'] = queryset.filter(doc=result).first().doc.size
                d['item_path'] = os.path.join(MEDIA_URL, str(queryset.filter(doc=result).first().doc))
                d['item_type'] = "file"
        return d

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if self.request.query_params.get('sr', None) == 'true':
            serializer = self.get_serializer(queryset)
        else:
            serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if self.request.query_params.get('fetch_recent_docs', None) == 'true':
            data = filter(None, data)

        get_attachment_path = self.request.query_params.get('get-attachment', None)
        if get_attachment_path == 'true':
            if IS_S3 :
                target_url = 'media/cap/'
                domain_url = 'media/'
                data = self.url_to_dict(url=target_url, init_path=domain_url )
            else :
                target_path = os.path.join(BASE_DIR, 'media')
                domain_path = os.path.join(BASE_DIR, 'media/')
                data = self.path_to_dict(path=target_path, init_path=domain_path)
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Document List Fetched',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        doc_id = request.data.get('id')
        serializer.is_valid(raise_exception=True)
        try:
            response = self.perform_update(serializer)
        except Exception as e:
            logger.exception("Error in updating document : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})
            response_data['status_code'] = '400'
            response_data['status'] = True
            response_data['message'] = 'Error in replacing the document'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'You have succesfully replaced the document'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_doc = request.query_params.get('task_doc', None)

        if request.data.get('owner') is None:
            raise serializers.ValidationError({"owner": ["owner is required"]})
        if request.data.get('doc_type') in ['3', '4', '5', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18']:
            if request.data.get('owner') == '':
                raise serializers.ValidationError({"owner": ["owner can not be blank"]})
        else:
            if request.data.get('owner') != '':
                raise serializers.ValidationError({"owner": ["owner should be blank"]})
        if task_doc=='true':
            task_obj = ClientTask.objects.filter(client=request.data.get('owner')).exclude(task_status='3')
            if not task_obj :
                raise serializers.ValidationError({"file": ["Task file already closed, cannot upload document"]})
        try:
            checks = DocumentSetting.objects.get(type=request.data.get('doc_type'))
            if request.data.get('doc').name.split('.')[-1] in ast.literal_eval(checks.allowed_format):
                if request.data.get('doc').size > int(checks.max_size_limit):
                    raise serializers.ValidationError({"file": ["File exceeds the limit"]})
            else:
                raise serializers.ValidationError({"file": ["File type is not supported"]})
        except DocumentSetting.DoesNotExist as e:
            logger.exception("DocumentSetting doesnot exist : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})

        try:
            response = super().create(request)
            response_data = {
                "status_code": "201",
                "status": True,
                "message": 'Document uploaded successfully',
                "data":response.data['id']
            }
        except Exception as e:
            print(str(e))
            logger.exception("Error in uploading document : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})

            response_data = {
                "status_code": "400",
                "status": False,
                "message": 'Document uploaded failed',
            }
            
        return Response(response_data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        data = super().retrieve(request, *args, **kwargs).data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Document Details',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        response_data = {}
        try:
            client_instrument_id = self.request.query_params.get('client_instrument_id', None)
            if client_instrument_id is not None:
                if instance.doc_type == '3':
                    client_instrument_obj = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                    client_instrument_obj.signed_loa = None
                    client_instrument_obj.loa_mail_sent = False
                    client_instrument_obj.reminder_count = 0
                    client_instrument_obj.pdf_data = None
                    client_instrument_obj.data_extracted = None
                    client_instrument_obj.is_recommended = False
                    client_instrument_obj.instrument_status = StatusCollection.objects.get(status='1.51')
                    client_instrument_obj.data_extraction_status = '0'
                    client_instrument_obj.save()
                    pending_status = StatusCollection.objects.get(status='1.23')  # signed loa upload  pending status

                elif instance.doc_type == '5':
                    client_instrument_obj = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                    client_instrument_obj.pdf_data = None
                    client_instrument_obj.data_extracted = None
                    client_instrument_obj.is_recommended = False
                    client_instrument_obj.instrument_status = StatusCollection.objects.get(status='1.53')
                    client_instrument_obj.data_extraction_status = '0'
                    client_instrument_obj.save()
                    InstrumentsRecomended.objects.filter(client_instrumentinfo=client_instrument_obj).delete()
                    pending_status = StatusCollection.objects.get(status='1.28')
                    ExtractedData.objects.filter(client_instrumentinfo=client_instrument_obj).delete()
                    reminder_status = StatusCollection.objects.get(status='1.32')  # Data extraction pending
                    for rem in Reminder.objects.filter(client_instrument=client_instrument_obj, status=reminder_status):
                        rem.is_deleted = True
                        rem.save()

                elif instance.doc_type == '7':
                    client_instrument_obj = ClientInstrumentInfo.objects.get(id=client_instrument_id)
                    client_instrument_obj.pdf_data = None
                    client_instrument_obj.is_recommended = False
                    client_instrument_obj.instrument_status = StatusCollection.objects.get(status='1.55')
                    client_instrument_obj.data_extraction_status = '0'
                    client_instrument_obj.save()
                    ExtractedData.objects.filter(client_instrumentinfo=client_instrument_obj).delete()
                    InstrumentsRecomended.objects.filter(client_instrumentinfo=client_instrument_obj).delete()
                    reminder_status = StatusCollection.objects.get(status='1.32')  # Data extraction pending
                    for rem in Reminder.objects.filter(client_instrument=client_instrument_obj,status=reminder_status):
                        rem.is_deleted = True
                        rem.save()

            response = super().destroy(request)
            remove_reminder = Reminder.objects.filter(client_instrument=client_instrument_obj).first()
            if remove_reminder:
                remove_reminder.is_deleted = True
                remove_reminder.save()
            pending_status_save(client_instrument=client_instrument_obj, pending_status=pending_status)

        except Exception as e:
            logger.exception("Error in deleting document : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})
            response_data['status_code'] = '400'
            response_data['status'] = True
            response_data['message'] = 'Error in deleting the document'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'File has been successfully deleted'

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK

        return Response(response_data, status=resp_status)


class ClientViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ClientSerializer

    def fetch_surveyform_details(self, data, client_id):
        data['about'] = None
        data['job_title'] = None
        data['ni_number'] = None
        data['reminder_count'] = None
        data['joining_date'] = None
        if client_id is not None:
           
            reminder_queryset = Reminder.objects.filter(client__id=client_id, reminder_date__lte=datetime.date.today(), snooze_status='2')
            data['reminder_count'] = reminder_queryset.count()
            client_obj = Client.objects.filter(id=client_id).first()
            create_time = client_obj.create_time
            
            data['joining_date'] = create_time.date()


        try:
            category = CategoryAndSubCategory.objects.filter(category_slug_name='personal_information_7').first()
            if category:
                surveyform = SurveyFormData.objects.filter(client_id=client_id, category_id=category.id).first()
            if surveyform is not None:
                for subcategory in surveyform.form_data:
                    label_list = subcategory['subcategory_data']
                    if subcategory['subcategory_slug_name'] == "basic_info_8":
                        for label in label_list:
                            if (label['label_slug'] == 'ni_number_130'):
                                data['ni_number'] = label['answer']
            category2 = CategoryAndSubCategory.objects.filter(category_slug_name='occupation_info_11').first()
            if category2:
                surveyform = SurveyFormData.objects.filter(client_id=client_id, category_id=category2.id).first()
            if surveyform is not None:
                for subcategory in surveyform.form_data:
                    label_list = subcategory['subcategory_data']
                    if subcategory['subcategory_slug_name'] == "employment_12":
                        for label in label_list:
                            if (label['label_slug'] == 'job_title_50'):
                                data['job_title'] = label['answer']

            category3 = CategoryAndSubCategory.objects.filter(category_slug_name='plans___atr_27').first()
            if category3:
                surveyform = SurveyFormData.objects.filter(client_id=client_id, category_id=category3.id).first()
            if surveyform is not None:
                for subcategory in surveyform.form_data:
                    label_list = subcategory['subcategory_data']
                    if subcategory['subcategory_slug_name'] == "about_31":
                        for label in label_list:
                            if (label['label_slug'] == 'tell_us_about_yourself___151'):
                                data['about'] = label['answer']
        except Exception as e:
            logger.exception("Error in fetching Survey for client : {} - {}".format(str(e), self.request.path), extra={'status_code': 400, 'request': self.request})
        return data

    
    def get_queryset(self):
        queryset = Client.objects.all()
        name = self.request.query_params.get('name', None)
        email = self.request.query_params.get('email', None)
        mob_number = self.request.query_params.get('mob_number', None)
        company = self.request.query_params.get('company', None)
        referred_by = self.request.query_params.get('referred_by', None)
        referred_date = self.request.query_params.get('referred_date', None)
        recently_added_client_list = self.request.query_params.get('recently_added_client_list', None)
        client_list_added_by_me = self.request.query_params.get('client_list_added_by_me', None)
        enable_cold_calling = self.request.query_params.get('enable_cold_calling', None)
        
        advisor = self.request.query_params.get('advisor', None)
        daily = self.request.query_params.get('daily', None)
        weekly = self.request.query_params.get('weekly', None)
        monthly = self.request.query_params.get('monthly', None)
        limit = self.request.query_params.get('limit', None)

        #To check if mobile number already exists during survey edit
        survey_client_id = self.request.query_params.get('survey_client', None)
        if survey_client_id:
            queryset = queryset.exclude(id=survey_client_id)
            if mob_number is not None:
                queryset = queryset.filter(phone_number__exact=mob_number)
            return queryset

        staff_obj = Staff.objects.filter(user=self.request.user).first()
        user_id_list = Staff.objects.filter(company=staff_obj.company).values_list('user__id', flat=True)
        queryset = queryset.filter(created_by__id__in=user_id_list)
        queryset = queryset.order_by('-create_time') 

        if client_list_added_by_me == 'true':
            queryset = queryset.filter(created_by=self.request.user).order_by('-create_time')  # [:4]
        if name is not None:
            queryset = queryset.annotate(full_name=Concat('user__first_name', V(' '), 'user__last_name')).filter(full_name__icontains=name)
        if email is not None:
            queryset = queryset.filter(user__email__contains=email)
        if mob_number is not None:
            queryset = queryset.filter(phone_number__contains=mob_number)
        if company is not None:
            queryset = queryset.filter(company__name__icontains=company)
        if referred_by is not None:
            queryset = queryset.annotate(full_name=Concat('referred_by__first_name', V(' '), 'referred_by__last_name')).filter(full_name__icontains=referred_by)
        if referred_date is not None:
            queryset = queryset.filter(referred_date=referred_date)

        if enable_cold_calling is not None:
            queryset = queryset.filter(enable_cold_calling=enable_cold_calling)
        if advisor is not None:
            if daily=='true' or monthly=='true' or weekly=='true':
                """ when api called from dashboard, the id passed for advisor is Staff id.  From client list the advisor id passed is user id. So to identify the source of api we make use of 
                daily, monthly, weekly filter status"""
                staff = Staff.objects.filter(id=advisor).first()
                queryset = queryset.filter(created_by=staff.user)
            else:
                queryset = queryset.filter(created_by=advisor)

        if monthly is not None:
            start_date= datetime.date.today().replace(day=1)
            queryset = queryset.filter(create_time__gte=start_date)[:10]
        if weekly is not None:
            week_srt = datetime.date.today() - datetime.timedelta(days=datetime.date.today().isoweekday() % 7)
            queryset = queryset.filter(create_time__gte=week_srt)[:10]
        if daily is not None:
            start_date= datetime.date.today() 
            queryset = queryset.filter(create_time__gte=start_date)[:10]

        if recently_added_client_list  == 'true':
            queryset = queryset[:10]        

        # #To check if mobile number already exists during survey edit
        # survey_client_id = self.request.query_params.get('survey_client', None)
        # if survey_client_id:
        #     queryset = queryset.exclude(id=survey_client_id)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        count = offset = limit = None
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            count = self.paginator.count
            offset = self.paginator.offset
            limit = self.paginator.limit
        else:
            serializer = self.get_serializer(queryset, many=True)
            data = serializer.data

        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Client List',
            "count": count,
            "offset": offset,
            "limit": limit,
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        data = super().retrieve(request, *args, **kwargs).data
        instance = self.get_object()
        profile_data = self.request.query_params.get('profile_data', None)
        if profile_data:
            data = self.fetch_surveyform_details(data, instance.id)
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Client Details',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        if type(serializer.initial_data) == list:
            for item in serializer.initial_data:
                referred_mail = item.pop('referred_person_email')
                if referred_mail:
                    try:
                        referred_id = User.objects.get(email=referred_mail).id
                        item['referred_by_id'] = referred_id
                    except User.DoesNotExist as e:
                        logger.exception("Error in reffering client : {} - {}".format(str(e), self.request.path), extra={'status_code': 400, 'request': self.request})
            serializer.is_valid(raise_exception=True)
        serializer.save()

    def create(self, request, *args, **kwargs):
        response_data = {}
        error_list = []
        client = "client"
        many = isinstance(request.data, list)
        if many:
            client = "clients"
            email_list = []
            phone_list = []
            counter = 0
            result_list = list.copy(request.data)
            for item in result_list:
                counter = counter + 1
                if item['user']['email'] in email_list or item['phone_number'] in phone_list:
                    request.data.remove(item)
                    error_list.append(item)
                else:
                    email_list.append(item['user']['email'])
                    phone_list.append(item['phone_number'])
        serializer = self.get_serializer(data=request.data, many=many)

        if not many:
            referred_user = request.data.get('referred_by_id', '')
            username = request.data.get('user').get('username')
            if referred_user:
                try:
                    user = User.objects.get(id=referred_user)
                    
                except User.DoesNotExist as e:
                    logger.exception("Invalid reffered_by user : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})    
                    raise serializers.ValidationError({"referred_by_id": ["Invalid referred_by user"]})
            if username:
                try:
                    user = User.objects.get(username=username)
                    # logger.exception("User with same email exist : {}".format(request.path), extra={'status_code': 400, 'request': request})
                    raise serializers.ValidationError({"email": ["A user with that email already exists."]})
                except User.DoesNotExist:
                    print("User does not exist exception..!!")
            serializer.is_valid(raise_exception=True)

        try:
            self.perform_create(serializer)
        except Exception as e:
            logger.exception("Error in adding the clients : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})            
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Error in adding the clients'
        else:
            response_data['status_code'] = '201'
            response_data['status'] = True
            if error_list:
                for i in error_list:

                    if 'referred_person_email' not in i:
                        i['referred_person_email'] = User.objects.get(id=i.get('referred_by_id', None)).email
                response_data['data'] = error_list
                response_data['message'] = 'You have added ' + str(counter - len(error_list)) + '/' + str(
                    counter) + ' clients details.Below profiles are already added.'
            else:
                response_data['message'] = 'You have successfully added the' + " " + client + " " + 'details'

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '201':
            resp_status = status.HTTP_201_CREATED
        return Response(response_data, status=resp_status)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data)
        username = request.data.get('user').get('username')
        referred_user = request.data.get('referred_by_id', '')
        serializer.is_valid(raise_exception=True)
        if referred_user:
            try:
                user = User.objects.get(id=referred_user)
            except User.DoesNotExist:
                logger.exception("Invalid referred_by user in client update : {} ".format(request.path), extra={'status_code': 400, 'request': request})
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'Invalid referred_by user'
        try:
            user = User.objects.exclude(id=instance.user.id).get(username=username)
            # logger.exception("User with same email exist : {}".format(request.path), extra={'status_code': 400, 'request': request})
            raise serializers.ValidationError({"email": ["A user with that email already exists."]})
        except User.DoesNotExist:
            print("User does not exist exception..!!")
        response = self.perform_update(serializer)
        response_data['status_code'] = '200'
        response_data['status'] = True
        response_data['message'] = 'You have updated the client details'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


    @action(methods=['get'], detail=False, name='User exist_check')
    def exist(self, request, *args, **kwargs):
        response_data = {}
        data = {'alreadyExists': False}
        ph_number=request.query_params.get('mob_number', None)
        survey_client_id = request.query_params.get('survey_client', None)

        if ph_number:
            queryset=Client.objects.filter(phone_number__exact=ph_number)
             #To check if mobile number already exists during survey edit
            if survey_client_id:
                queryset = queryset.exclude(id=survey_client_id)

            if queryset:
                data['alreadyExists'] = True

        response_data['status_code'] = '200'
        response_data['status'] = True
        response_data['message'] = 'client details fetched'
        response_data['data'] = data
        resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)



class ProviderViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer
    search_fields = ['^name', ]
    filter_backends = (filters.SearchFilter,)

    def get_queryset(self):
        queryset = Provider.objects.all()
        recently_added_provider_list = self.request.query_params.get('recently_added_provider_list', None)
        client_id = self.request.query_params.get('client_id', None)
        provider_type = self.request.query_params.get('provider_type', None)
        if recently_added_provider_list == 'true':
            client_instrument_list = ClientInstrumentInfo.objects.filter(created_by=self.request.user, is_active=True).order_by('-create_time')
            if client_instrument_list is not None:
                provider_list = []
                provider_list_maxlen = 10  # recently added 10 providers
                for client_instrument in client_instrument_list:
                    provider_list_maxlen = provider_list_maxlen - 1
                    provider_list.append(client_instrument.provider.id)
                    if (provider_list_maxlen == 0):
                        break

                queryset = queryset.filter(id__in=provider_list)
        if client_id is not None:
            providerlist = []
            client_instrument_list = ClientInstrumentInfo.objects.filter(client=client_id, provider_type=provider_type, is_active=True)
            for client_instrument in client_instrument_list:
                providerlist.append(client_instrument.provider.id)
            queryset = queryset.filter(id__in=providerlist)
        return queryset

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Instrument provider List'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'No such Provider'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class InstrumentViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = Instrument.objects.all()
    serializer_class = InstrumentSerializer

    def get_queryset(self):
        queryset = Instrument.objects.all()
        provider_id = self.request.query_params.get('provider_id', None)
        client_id = self.request.query_params.get('client_id', None)
        if provider_id is not None:
            queryset = queryset.filter(provider=provider_id)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Instrument List',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)


class ClientInstrumentInfoViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = ClientInstrumentInfo.objects.all()
    serializer_class = ClientInstrumentInfoSerializer

    def get_queryset(self):
        queryset = ClientInstrumentInfo.objects.filter(is_active=True)

        client_id = self.request.query_params.get('client_id', None)
        is_recommended = self.request.query_params.get('is_recommended', None)
        if client_id is not None:
            queryset = queryset.filter(client=client_id)

        if is_recommended:
            queryset = queryset.filter(is_recommended=True)
        queryset = queryset.order_by('provider_type', '-create_time')
        queryset=queryset.filter(parent__isnull=True)
        return queryset

    def get_serializer(self, *args, **kwargs):
        if "data" in kwargs:
            data = kwargs["data"]
            # check if many is required
            if isinstance(data, list):
                kwargs["many"] = True
        return super(ClientInstrumentInfoViewSet, self).get_serializer(*args, **kwargs)

    def create(self, request, *args, **kwargs):
        response_data = {}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response = super().create(request)
            client_instr_count = len(request.data)
            client = Client.objects.filter(id=request.data[0]['client_id']).first()
            client_profile_completion(client=client,phase='pre-contract',percentage=10,sign='positive',client_instr_count=client_instr_count,obj='client-instrument-info') 
            
            if client.client_stage=='0':
                client.client_stage='1'
                client.save()
        except Exception as e:
            logger.exception("Could not create client instrument : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})            
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Invalid data'
        else:
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'You have successfully added the instrument details'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '201':
            resp_status = status.HTTP_201_CREATED

        return Response(response_data, status=resp_status)

    def list(self, request, *args, **kwargs):

        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data['status_code'] = "200"
        response_data['status'] = True
        response_data['message'] = 'Client Instrument List'
        response_data['data'] = data
        resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)

    def perform_update(self, serializer, data_reset):
        if data_reset:
            instance = serializer.save(signed_loa=None, loa_mail_sent=False, reminder_count=0, pdf_data=None, data_extracted=None, instrument_status=StatusCollection.objects.get(status='1.49'), data_extraction_status='0')
            extracted_data = ExtractedData.objects.filter(client_instrumentinfo=instance.id).first()
            if extracted_data:
                ExtractedData.objects.filter(client_instrumentinfo=instance.id).delete()
        else:
            serializer.save()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data_reset = False
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        client_instrument_id = instance.id
        clientinstrument = ClientInstrumentInfo.objects.filter(id=client_instrument_id).first()
        serializer.is_valid(raise_exception=True)
        try:
            if 'provider_type' in request.data:
                data_reset = True
            response = self.perform_update(serializer, data_reset)
        except Exception as e:
            logger.exception("Could not update client instrument : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})            
            response_data['status_code'] = '400'
            response_data['status'] = True
            response_data['message'] = 'Error in updating the provider type'
        else:
            if (instance.provider_type == 1):
                remove_reminder = Reminder.objects.filter(client_instrument__id=client_instrument_id).first()
                if remove_reminder:
                    remove_reminder.is_deleted = True
                    remove_reminder.save()
                pending_status = StatusCollection.objects.get(status='1.21')  # loa download pending status
                pending_status_save(client_instrument=clientinstrument, pending_status=pending_status)
            if (instance.provider_type == 2):
                remove_reminder = Reminder.objects.filter(client_instrument__id=client_instrument_id).first()
                if remove_reminder:
                    remove_reminder.is_deleted = True
                    remove_reminder.save()

            ExtractedData.objects.filter(client_instrumentinfo=clientinstrument).delete()
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'You have updated the instrument details'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


    def destroy(self, request, pk=None):
        response_data = {}
        record_to_delete = ClientInstrumentInfo.objects.filter(id=pk).first()
        if record_to_delete:
            instruments_recomended_obj = InstrumentsRecomended.objects.filter(client_instrumentinfo=record_to_delete).first()
            if instruments_recomended_obj:
                draft_recommendation_obj = DraftReccomendation.objects.filter(client=record_to_delete.client, is_active=True).first()
                if draft_recommendation_obj:
                    draft_recommendation_obj.instrument_recommended.remove(record_to_delete.id)
                    draft_recommendation_obj.save()

                instruments_recomended_obj.is_deleted = True
                instruments_recomended_obj.save()
                remove_ilustration_checklist(instruments_recomended_obj)
                client_profile_completion(client=record_to_delete.client,phase='pre-contract',percentage=20,sign='negative',advisor=instruments_recomended_obj.advisor,obj='instrument-recomended') 
               

            #removing reminders related to the product
            reminders_to_remove = Reminder.objects.filter(client=record_to_delete.client, client_instrument=record_to_delete)
            for reminder in reminders_to_remove:
                reminder.is_deleted=True
                reminder.save()
            
            activity_flow_update_status = StatusCollection.objects.get(status='1.74')
            add_activity_flow(action_performed_by=self.request.user, client=record_to_delete.client, status=activity_flow_update_status, client_instrument=record_to_delete)
            client_profile_completion(client=record_to_delete.client,phase='pre-contract',percentage=10,sign='negative',obj='client-instrument-info')
            
            
            ###clones deletion##
            ClientInstrumentInfo.objects.filter(client=record_to_delete.client, is_recommended=True,parent=record_to_delete, is_active=True).update(is_deleted=True)
            
            ClientCheckList.objects.filter(client=record_to_delete.client,client_instrument__parent=record_to_delete).update(is_deleted=True)
            clone_instruments_recomended = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=record_to_delete.client,client_instrumentinfo__parent=record_to_delete)
            for clone_instrument in clone_instruments_recomended:
                draft_recommendation_obj = DraftReccomendation.objects.filter(client=record_to_delete.client,is_active=True).first()
                if draft_recommendation_obj:
                    draft_recommendation_obj.instrument_recommended.remove(clone_instrument.id)
                    draft_recommendation_obj.save()

                clone_instrument.is_deleted = True
                clone_instrument.save()
            ###delte parent clientinstrument
            ClientInstrumentInfo.objects.filter(id=pk).update(is_deleted=True)
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'Client Instrument deleted successfully'
        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Client Instrument not found'

        if response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        elif response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)

    @action(methods=['get'], detail=False, name='instrument_count')
    def count(self, request, *args, **kwargs):
        response_data = {}
        count = self.filter_queryset(self.get_queryset()).count()
        response_data['status_code'] = '200'
        response_data['status'] = True
        response_data['message'] = 'client instrument count fetched'
        response_data['data'] = [{'instrument_count': count}]
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)

    @action(methods=['post'], detail=False, name='bulk-update')
    def bulk_recommend(self, request, *args, **kwargs):
        response_data = {}
        error = False
        client_instrument_list = request.data.pop('instrument_list')
        client_id = self.request.query_params.get('client_id', None)
        if client_instrument_list is not None:
            print("\n\nclient instrument list   :::  ", client_instrument_list)
            try:
                ClientInstrumentInfo.objects.filter(id__in=client_instrument_list, is_active=True).update(
                    is_recommended=True)
                if client_id:
                    un_recommended_list = ClientInstrumentInfo.objects.filter(client=client_id, is_recommended=True,parent__isnull=True, is_active=True).exclude(id__in=client_instrument_list)
                for instrument in un_recommended_list:
                    instrument.is_recommended = False  # Used save() instead of bulk update,to invoke post save signal
                    instrument.save()

                try:
                    client = Client.objects.filter(id=client_id).first()
                    advisor=Staff.objects.filter(user=client.created_by).first()
                    recommendation_status_obj = RecommendationNotificationStatus.objects.filter(status_value=18).first()
                    recommendation_notification_save(client=client_id, advisor=client.created_by.id,recommendation_status=recommendation_status_obj, is_answer=True)
                    recommended_producttypes = InstrumentsRecomended.objects.filter(
                        client_instrumentinfo__client=client, is_active=True).values_list(
                        'client_instrumentinfo__instrument__product_type__fund_type', flat=True)
                    recommended_producttypes = ClientInstrumentInfo.objects.filter(client=client,is_recommended=True,is_active=True).values_list('instrument__product_type__fund_type', flat=True)
                    draftchecklist = DraftCheckList.objects.filter(category_name='8')  # bulk recommend instruments

                    for checklist in draftchecklist:
                        print(checklist.id, checklist)
                        checklist_product_types = list(checklist.product_type.all().values_list('fund_type', flat=True))
                        producttype_exist = any(item in checklist_product_types for item in list(recommended_producttypes))
                        if producttype_exist:
                            update_or_create_checklist(client, checklist.id, advisor)
                        else:
                            delete_checklist(client, checklist)
                except Exception as e:
                    print(str(e))
                    print("checklist update error")
                    logger.exception("Error in bulk recommend checklist update: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})            
            except Exception as e:
                print(str(e))
                error = True
                logger.exception("Error in bulk recommend : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})            

        if error:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Failed to recommend instruments'
            resp_status = status.HTTP_400_BAD_REQUEST
        else:
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'Instruments recommended successfully'
            resp_status = status.HTTP_201_CREATED

        return Response(response_data, status=resp_status)


class PassthroughRenderer(renderers.BaseRenderer):
    """
        Return data as-is. View should supply a Response.
    """
    media_type = ''
    format = ''

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


def check_sr_path_exist(client):
    if not os.path.exists(os.path.join(MEDIA_ROOT, 'client_' + str(client.id) + '/')):
        os.mkdir(os.path.join(MEDIA_ROOT, 'client_' + str(client.id) + '/'))

    if not os.path.exists(os.path.join(MEDIA_ROOT, 'client_' + str(client.id) + '/sr/')):
        os.mkdir(os.path.join(MEDIA_ROOT, 'client_' + str(client.id) + '/sr/'))


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = Templates.objects.all()
    serializer_class = TemplateSerializer

    def get_queryset(self):
        queryset = Templates.objects.all()
        category_id = self.request.query_params.get('category_id', None)
        if category_id is not None:
            queryset = queryset.filter(category=category_id)
        return queryset

    def get_loa_mail_template(self, request, data):
        loa_doc = None
        header = data.pop('template_header')
        footer = data.pop('template_footer')
        content = data.pop('content')
        client_instrument_id = request.query_params.get('client_instrument_id', None)
        try:
            signed_loa = ClientInstrumentInfo.objects.get(id=client_instrument_id).signed_loa.doc
            client = ClientInstrumentInfo.objects.get(id=client_instrument_id).client
        except Exception as e:
            logger.exception("Exception LOA mail tempate get : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            return None

        advisor_name=client.created_by.first_name.title()
        advisor_full_name = client.created_by.first_name.title() + ' ' + client.created_by.last_name.title()
        client_name = client.user.first_name.title() + ' ' + client.user.last_name.title()
        if signed_loa is not None:
            print("signed loa")
            

            if signed_loa.name.split('.')[1] == 'pdf':
                loa_doc = os.path.join(MEDIA_URL, str(signed_loa).split('.')[0] + '_preview' + '.jpg')
                if IS_S3:
                    file_key='media/'+str(signed_loa).split('.')[0] + '_preview' + '.jpg'
                    s3Client = boto3.client('s3',region_name=region,endpoint_url=end_point_url,aws_access_key_id=access_key,aws_secret_access_key=secret_key)
                    loa_doc = s3Client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': file_key},ExpiresIn=120)
                else:
                    loa_doc = os.path.join(MEDIA_URL, str(signed_loa).split('.')[0] + '_preview' + '.jpg')
            else:
                loa_doc = os.path.join(MEDIA_URL, signed_loa.name)
                if IS_S3:
                    loa_doc = signed_loa.doc.url
                else:
                    loa_doc = os.path.join(MEDIA_URL, signed_loa.name)

        try:
            staff = Staff.objects.filter(user=client.created_by).first()
            if staff:
                company_url = staff.company.url
                company_logo = staff.company.logo.url
                phone_number = staff.phone_number
                phone_number2 = staff.phone_number2
                designation = staff.designation

            else:
                company_logo = Document.objects.get(doc='advisors/company/Lathe-logo.png').doc.url
                company_url = " "
                phone_number = None
                phone_number2 = None
                designation = None
        except Exception as e:
            logger.exception("Exception staff details fetch in LOA mail tempate get : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            company_logo = " "
            company_url = " "
            phone_number = None
            phone_number2 = None
            designation = None
        context = Context({"loa_doc_image": loa_doc, "advisor_full_name": advisor_full_name,"advisor_name": advisor_name, "client_name": client_name,
                           "company_logo": company_logo,"company_website": company_url,
                           "phone_number":phone_number,"phone_number2":phone_number,"designation":designation,
                           "static_image_path": os.path.join(MEDIA_URL, 'advisors/company')})
        attachment = '<p style="margin: 20px 0 0 30px; padding: 0;">1 Attachment</p><p style="text-align: center;"><img src={{loa_doc_image}} style="width:100%"></p>'
        html = header.render(context) + content.render(context) + footer.render(context) + attachment
        template = Template(html)
        html = template.render(context)
        return html

    def retrieve(self, request, *args, **kwargs):
        response_data = {}
        data = super().retrieve(request, *args, **kwargs).data
        # To handle static files #To do #
        template = Template(data['template_header'])
        template_footer = Template(data['template_footer'])
        template_content = Template(data['content'])
        try:
            staff = Staff.objects.filter(user=request.user).first()
            if staff:
                company_url = staff.company.url
                company_logo = staff.company.logo.url
                phone_number = staff.phone_number
                phone_number2 = staff.phone_number2
                designation = staff.designation
            else:
                company_logo = Document.objects.get(doc='advisors/company/Lathe-logo.png').doc.url
        except Exception as e:
            print("exception in template fetching ",e)
            logger.exception("Exception tempate fetch: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                

            company_logo = " "
            company_url = " "
            phone_number = None
            phone_number2 = None
            designation = None
        advisor_name = request.user.first_name.title()
        advisor_full_name = request.user.first_name.title() + ' ' + request.user.last_name.title()
        client_instrument_id = request.query_params.get('client_instrument_id', None)
        client = ClientInstrumentInfo.objects.get(id=client_instrument_id).client
        client_name = client.user.first_name.title() + ' ' + client.user.last_name.title()
        '''context = Context(
            {"company_logo": company_logo, "static_image_path": os.path.join(MEDIA_URL, 'advisors/company'),
             "company_website": company_url, "advisor_name": advisor_name, "client_name": client_name,"phone_number":phone_number, \
             "phone_number2":phone_number,"designation":designation,"advisor_full_name":advisor_full_name})
        data['template_header'] = template.render(context)
        data['template_footer'] = template_footer.render(context)
        data['content'] = template_content.render(context)'''
        # To handle loa_mail_preview
        template_type = self.request.query_params.get('type', None)
        if template_type == 'loa_mail':
            data['template_header'] = template
            data['template_footer'] = template_footer
            data['content'] = template_content
            data['mail_template_html'] = self.get_loa_mail_template(request, data)

        else:
            file_key = 'media/advisors/company/payment-details.jpg'
            s3Client = boto3.client('s3',region_name=region,endpoint_url=end_point_url,aws_access_key_id=access_key,aws_secret_access_key=secret_key)
            payment_image_url= s3Client.generate_presigned_url(ClientMethod='get_object', Params={'Bucket': bucket, 'Key': file_key},ExpiresIn=120)

            context = Context(
                {"company_logo": company_logo, "static_image_path": os.path.join(MEDIA_URL, 'advisors/company'),
                 "company_website": company_url, "advisor_name": advisor_name, "client_name": client_name,"payment_image_url":payment_image_url,
                 "phone_number": phone_number, "phone_number2": phone_number, "designation": designation, "advisor_full_name": advisor_full_name})
            data['template_header'] = template.render(context)
            data['template_footer'] = template_footer.render(context)
            data['content'] = template_content.render(context)

        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Template details fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'Not found'
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
    
        data = json.loads(json.dumps(data))
        for data_val in data:
            templates_info = data_val['template_attachment_url']
            attachment_list = []

            if templates_info:
                for templates_obj in templates_info:
                    attachment_dict = {}
                    templates_data = TemplateAttachments.objects.filter(id=templates_obj).first()
                    if templates_data:
                        attachment = data_val['template_attachment_url']
                        attachment_dict = {"item_path": str(templates_data.attachment_url.url),
                                           "watchable_attachment": templates_data.watchable_attachment,'doc_name': str(templates_data.attachment_url)}
                        attachment_list.append(attachment_dict)
                        
            del (data_val['template_attachment_url'])
            data_val['template_attachment_path'] = attachment_list
            
        try:
            staff = Staff.objects.filter(user=request.user).first()
            if staff:
                company_url = staff.company.url
                company_logo = None
                if staff.company.logo:
                    company_logo = staff.company.logo.url
                phone_number = staff.phone_number
                phone_number2 = staff.phone_number2
                designation = staff.designation

            else:
                company_doc_obj = Document.objects.filter(doc='advisors/company/Lathe-logo.png').first()
                company_logo = None
                if company_logo:
                    company_logo = company_doc_obj.doc.url
                company_url = " "
                phone_number=None
                phone_number2=None
                designation=None
        except Exception as e:
            logger.exception("Exception in template listing : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            company_logo = " "
            company_url = " "
            phone_number=None
            phone_number2=None
            designation=None
            print("exception in templates",e)
        advisor_name = request.user.first_name.title() 
        advisor_full_name = request.user.first_name.title() + ' ' + request.user.last_name.title()
       
       
        file_key = 'media/advisors/company/payment-details.jpg'
        s3Client = boto3.client('s3',region_name=region,endpoint_url=end_point_url,aws_access_key_id=access_key,aws_secret_access_key=secret_key)
        payment_image_url= s3Client.generate_presigned_url(ClientMethod='get_object', Params={'Bucket': bucket, 'Key': file_key},ExpiresIn=120)

        context = Context(
            {"company_logo": company_logo, "static_image_path": os.path.join(os.path.join(BASE_URL, 'api/media/advisors/company')),
             "advisor_name": advisor_name, "company_website": company_url,"payment_image_url":payment_image_url,
             "client_first_name": "(CLIENT FIRST NAME)", "client_full_name": "(CLIENT FULL NAME)",
             "client_name": "(CLIENT FIRST NAME & SURNAME)",
             "mortgage_broker_name": "(MORTGAGE BROKER NAME)", "referrer_name": "(REFERRER NAME)","phone_number":phone_number,\
             "phone_number2":phone_number2,"designation":designation,"advisor_full_name":advisor_full_name})

        for item in data:
            template = Template(item['template_header'])
            template_footer = Template(item['template_footer'])
            template_content = Template(item['content'])
            item['template_header'] = template.render(context)
            item['template_footer'] = template_footer.render(context)
            item['content'] = template_content.render(context)

        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Template details fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'Not found'
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)

    # to force download the LOA Template
    @action(methods=['get'], detail=True, renderer_classes=(PassthroughRenderer,))
    def download(self, request, *args, **kwargs):
        instance = self.get_object()
        # to save activity log/status#
        client_instrument_id = self.request.query_params.get('client_instrument_id', None)
        client_instrument = ClientInstrumentInfo.objects.get(id=client_instrument_id)
        try:
            print("Inside try BLOCK")
            NI_number = ' '
            Date_Of_Birth = ' '
            address = ' '
            postcode=street_2=region=flat=building=street_1=town=' '

            category = CategoryAndSubCategory.objects.filter(category_slug_name='personal_information_7').first()
            if category:
                surveyform = SurveyFormData.objects.filter(client_id=client_instrument.client.id,
                                                           category_id=category.id).first()
               
            if surveyform is not None:
                print("inside surveyform")

                for subcategory in surveyform.form_data:
                    label_list = subcategory['subcategory_data']
                    print(subcategory['subcategory_slug_name'])
                    if subcategory['subcategory_slug_name'] in ['basic_info_8', 'contact_details_10']:
                        print("inside basic info")
                        for label in label_list:
                            if (label['label_slug'] == 'ni_number_130'):
                                print("inside ni number")
                                NI_number = label['answer']

                            if (label['label_slug'] == 'flat_174'):
                                flat = label['answer'].strip()
                                if flat:
                                    address = address+flat+"\n"
                            if (label['label_slug'] == 'building_168'):
                                building = label['answer'].strip()
                                if building:
                                    address = address+building+"\n"

                            if (label['label_slug'] == 'street_1_169'):
                                street_1 = label['answer'].strip()
                                if street_1:
                                    address = address+street_1+"\n"
                                
                            if (label['label_slug'] == 'street_2_170'):
                                street_2 = label['answer'].strip()
                                if street_2:
                                    address = address+street_2+"\n"
                            if (label['label_slug'] == 'town_171'):
                                town = label['answer'].strip()
                                if town:
                                    address = address+town+"\n"

                            if (label['label_slug'] == 'region_172'):
                                region = label['answer'].strip()
                                if region:
                                    address = address+region+"\n"
                            
                            if (label['label_slug'] == 'postcode_173') and label['answer']:
                                
                                postcode= label['answer'].strip()
                                if postcode:
                                    address = address+postcode

                            if (label['label_slug'] == 'dob_84'):
                                date_time_str = label['answer']
                                if date_time_str:
                                    date_time_obj = datetime.datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                                    Date_Of_Birth = date_time_obj.strftime("%d-%m-%Y")
        except Exception as e:
            print("exception is", str(e))
            logger.exception("Exception in survey fetch for LOA mail tempate download : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                

        client_name = client_instrument.client.user.first_name.title() + ' ' + client_instrument.client.user.last_name.title()
        provider_name = client_instrument.provider.name
        # Inorder to update activity flow
        status = StatusCollection.objects.get(status='1.20')  # loa downloaded
        client_instrument.instrument_status = status
        client_instrument.save()
        try:
            status = StatusCollection.objects.get(status='1.21')  # loa download pending status
            remove_reminder = Reminder.objects.filter(client_instrument=client_instrument, status=status).first()
            if remove_reminder:
                remove_reminder.is_deleted = True
                remove_reminder.save()
            # To update pending actions

            other_stage_status = Reminder.objects.filter(
                client_instrument=client_instrument)  # trying to download loa in some later stage
            if not (other_stage_status):
                pending_status = StatusCollection.objects.get(status='1.23')  # signed loa upload pending status
                pending_status_save(client_instrument=client_instrument, pending_status=pending_status)
        except Exception as e:
            print(e)
            logger.exception("Exception in reminder remove of LOA mail tempate download : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                

        template = Template(instance.content)
        advisor_name = client_instrument.client.created_by.first_name.title() + ' ' + client_instrument.client.created_by.last_name.title()  # To do
        try:
            staff = Staff.objects.filter(user=client_instrument.client.created_by).first()
            if staff:
                company_url = staff.company.url
                company_logo = staff.company.logo.url

            else:
                company_logo = Document.objects.get(doc='advisors/company/Lathe-logo.png').doc.url
        except Exception as e:
            logger.exception("Exception in staff get for LOA mail tempate download : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            company_logo = " "
            company_url = " "
        current_date = date.today().strftime("%d/%m/%Y")

        context = Context({"client_name": client_name, "advisor_name": advisor_name, "company_logo": company_logo,
                           "ni_number": NI_number, "dob": Date_Of_Birth, "provider": provider_name, 'address': address, 
                           "company_website": company_url, "current_date":current_date})
        
        html = template.render(context)
        print(html)
        pdf = render_to_pdf(instance.content, context)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            filename = 'LOA_DOC_%s.pdf' % ("12341231")
            response['Content-Disposition'] = "attachment; filename= %s" % (filename)
            return response
        return HttpResponse("Not found")

    # @action(methods=['post'], detail=True, renderer_classes=(PassthroughRenderer,))
    @action(methods=['post'], detail=True)
    def generate_sr(self, request, *args, **kwargs):
        
        instance = self.get_object()
        client = Client.objects.filter(id=self.request.data['client']).first()
        data = None
        response_data = {}
        template = Templates.objects.filter(template_name='SR template').first()
        if not template:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'SR document template missing'
            resp_status = status.HTTP_400_BAD_REQUEST
            return Response(response_data, status=resp_status)        

        if client:
            today = str(datetime.datetime.now().date().strftime("%d-%m-%Y"))
            client_name = client.user.first_name.title()+" "+client.user.last_name.title()
            first_name = client.user.first_name.title()
            salutation_title =""
            address = ""
            postcode=street_2=region=flat=building=street_1=town=""
            Date_Of_Birth = None
            has_cash_asset = False
            own_property = False
            mortgage_exist = False
            salary = 0
            employer = None
            will_made = False
            long_term_plan = None
            retirement_age = None
            employement_status = None
            employee_contribution = None
            employer_contribution = None
            asset_list = []
            atr = {}
            type_of_pension = None
            pension_value = None
            previous_employer = None
            previous_employer_pension = None
            private_pension_list = []
            pension_tansfer_reccommendation_list = []
            gia_tansfer_reccommendation_list = []
            isa_tansfer_reccommendation_list = []
            signature = None

            product_charges_noted = False
            category = CategoryAndSubCategory.objects.filter(category_slug_name='personal_information_7').first()
            category_list = ['basic_info_8', 'contact_details_10', 'assets_24', 'property_details_22', 'employment_12',
                             'will_23', 'financial_plans_28', 'employer_benefits_16', 'attitude_to_risk_29',
                             'previous_employment_13', 'private_pensions_17']

            if category:
                surveyform = SurveyFormData.objects.filter(client_id=client.id)
                for survey in surveyform:
                    if survey is not None:
                        for subcategory in survey.form_data:
                            label_list = subcategory['subcategory_data']
                            if subcategory['subcategory_slug_name'] in category_list:
                                for label in label_list:      
                                   
                                    if (label['label_slug'] == 'flat_174'):
                                        flat = label['answer'].strip()
                                        if flat:
                                            address = address+flat+"\n"
                                    if (label['label_slug'] == 'building_168'):
                                        building = label['answer'].strip()
                                        if building:
                                            address = address+building+"\n"
                                    
                                    if (label['label_slug'] == 'street_1_169'):
                                        street_1 = label['answer'].strip()
                                        if street_1:
                                            address = address+street_1+"\n"
                                        
                                        
                                    if (label['label_slug'] == 'street_2_170'):
                                        street_2 = label['answer'].strip()
                                        if street_2:
                                            address = address+street_2+"\n"
                                    if (label['label_slug'] == 'town_171'):
                                        town = label['answer'].strip()
                                        if town:
                                            address = address+town+"\n"
                                       
                                    if (label['label_slug'] == 'region_172'):
                                        region = label['answer'].strip()
                                        if region:
                                            address = address+region+"\n"
                                        
                                    if (label['label_slug'] == 'postcode_173') and label['answer']:
                                        
                                        postcode= label['answer'].strip()
                                        if postcode:
                                            address = address+postcode
                                            
                                   
                                    if label['label_slug'] == 'title_16':
                                        salutation_title = label['answer'] 
                                    if label['label_slug'] == 'dob_84':
                                        date_time_str = label['answer']
                                        if date_time_str:
                                            Date_Of_Birth = datetime.datetime.strptime(date_time_str,
                                                                                       "%Y-%m-%dT%H:%M:%S.%fZ")
                                        
                                    if label['label_slug'] == 'add_assets_123':
                                        for sublabel in label['sub_labels']:
                                            asset_name = None
                                            asset_value = None
                                            for sub_lab in sublabel['sub_label_data']:
                                                if sub_lab['label_slug'] == 'type_of_asset_75':
                                                    asset_name = sub_lab['answer']
                                                    if sub_lab['answer'] == 'Cash':
                                                        has_cash_asset = True
                                                if sub_lab['label_slug'] == 'amount_128':
                                                    asset_value = Decimal(sub_lab['answer'])
                                                   
                                                    
                                            asset_list.append({'asset_name': asset_name, 'asset_value': asset_value})


                                    if label['label_slug'] == 'rent_or_own_property_27' and label['answer'] == 'Own':
                                        
                                        own_property = True

                                    if label['label_slug'] == 'have_outstanding_mortgage_157' and label['answer'] == 'Yes':
                                       
                                        for sub in label['sub_labels'][0]['sub_label_data']:
                                            if sub['label_slug'] == 'amount_mortgage_outstanding_30' and float(sub['answer']) > 0:
                                                
                                                mortgage_exist = True

                                    if label['label_slug'] == 'employer_trading_name_49':
                                        employer = label['answer']

                                    if label['label_slug'] == 'salary_51':
                                        salary = Decimal(label['answer'])
                                        
                                        
                                    if label['label_slug'] == 'has_a_will_been_made__44' and label['answer'] == 'Yes':
                                        
                                        will_made = True

                                    if label[
                                        'label_slug'] == 'in_the_long_term__25___do_you_have_any_major_plans_you_think_will_affect_you_financially__139':
                                        for sub in label['sub_labels'][0]['sub_label_data']:
                                            if sub['label_slug'] == 'retirement_age_143':
                                                retirement_age = sub['answer']
                                            if sub['label_slug'] == 'notes_144':
                                                long_term_plan = sub['answer']

                                    if label['label_slug'] == 'status_48':
                                        employement_status = label['answer']

                                    if label['label_slug'] == 'pension_contributions_137':
                                        for sub in label['sub_labels'][0]['sub_label_data']:
                                            if sub['label_slug'] == 'employee_contribution_140':
                                                employee_contribution = sub['answer']
                                            if sub['label_slug'] == 'employer_contribution_141':
                                                employer_contribution = sub['answer']

                                    if label['label_slug'] == 'current_atr_82' and label['answer']:
                                        
                                        atr = ATR.objects.filter(risk_type=label['answer']).first()
                                        print(atr.risk_graph.url, ' ------------')

                                    if label['label_slug'] == 'type_of_pension_61':
                                        type_of_pension = label['answer']

                                    if label['label_slug'] == 'pension_value_106':
                                        pension_value = label['answer']

                                    if label['label_slug'] == 'name_of_employer_110':
                                        previous_employer = label['answer']

                                    if label['label_slug'] == 'pension_64':
                                        for sublabel in label['sub_labels'][0]['sub_label_data']:
                                            for sub in sublabel['sub_labels'][0]['sub_label_data']:
                                                if sub['label_slug'] == 'value_132':
                                                    previous_employer_pension = sub['answer']

                                    if label['label_slug'] == 'do_you_have_any__68':
                                        for outer in label['sub_labels'][0]['sub_label_data']:
                                            for sublabel in outer['sub_labels']:
                                                private_pension_dict = {'provider': "", 'value': ""}
                                                for sub in sublabel['sub_label_data']:
                                                    if sub['label_slug'] == 'provider_112':
                                                        private_pension_dict['provider'] = sub['answer']
                                                    if sub['label_slug'] == 'value_113':
                                                        private_pension_dict['value'] = sub['answer']
                                                        private_pension_list.append(private_pension_dict)
                                                        break

           
           
            instr_recc = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client, is_active=True)

            pensions = instr_recc.filter(client_instrumentinfo__instrument__product_type__fund_type='Pension')
            isas = instr_recc.filter(client_instrumentinfo__instrument__product_type__fund_type='ISA')
            gias = instr_recc.filter(client_instrumentinfo__instrument__product_type__fund_type='GIA')

            new_instrs = instr_recc.filter(client_instrumentinfo__provider_type='2')
            existing_instrs = instr_recc.filter(client_instrumentinfo__provider_type='1')
            existing_transfers = instr_recc.filter(client_instrumentinfo__provider_type='1',function_list__in=['1']).distinct()

            
            ext_pension_transfers = pensions.filter(function_list__in=['1'], map_transfer_from=None).distinct()
            
            new_pension_transfers = pensions.filter(function_list__in=['1'], map_transfer_from__isnull=False).distinct()
            pension_transfer_list = pensions.filter(function_list__in=['1']).distinct()
            
            existing_pension_regulars = pensions.filter(client_instrumentinfo__provider_type='1', function_list__in=['2', '3']).distinct()
            new_pension_regulars = pensions.filter(client_instrumentinfo__provider_type='2', function_list__in=['2', '3']).distinct()

            ext_pensions = pensions.filter(client_instrumentinfo__provider_type='1').distinct()

            pension_lumpsum_list = pensions.filter(function_list__in=['2']).distinct()
            pension_regulars_list = pensions.filter(function_list__in=['3']).distinct()



            # Setting list of dict to print "My Reccomendation" table in SR
            # pension_tansfer_reccommendation_list
            for pen_tnx in pension_transfer_list:
                save_dict = {'existing':[], 'new':None, 'amount':0}
                if pen_tnx.map_transfer_from.all():
                    for map_from in pen_tnx.map_transfer_from.all():
                        exisiting_dict = {'ins':map_from, 'charges':0}
                        if map_from.amount:
                            save_dict['amount'] += map_from.amount
                        for data in ExtractedData.objects.filter(client_instrumentinfo=map_from.client_instrumentinfo):
                            if data.master_keywords.keyword_slug == 'charges':
                                value = 0.00
                                if data.extracted_value:
                                    try:
                                        value = float(data.extracted_value)
                                    except Exception as e:
                                        # logger.exception("Exception in SR generate charges type conversion : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                                        value = 0.00
                                exisiting_dict['charges'] = value
                        save_dict['existing'].append(exisiting_dict)
                    save_dict['new'] = pen_tnx
                    save_dict['amount'] += (pen_tnx.amount-save_dict['amount'])
                    pension_tansfer_reccommendation_list.append(save_dict)

           

            existing_pension_extracted_data = []
            for ext_pen in ext_pension_transfers:
                d_dict = {}
                d_dict['instrument_name'] = ext_pen.client_instrumentinfo.instrument.instrument_name
                for data in ExtractedData.objects.filter(client_instrumentinfo=ext_pen.client_instrumentinfo):
                    if data.master_keywords.keyword_slug == 'charges':
                        value = 0.00
                        if data.extracted_value:
                            try:
                                value = float(data.extracted_value)
                            except Exception as e:
                                # logger.exception("Exception in SR generate charges type conversion : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                                value = 0.00
                        d_dict['charges'] = value
                        product_charges_noted = True  #for sr checlist purpose        
                existing_pension_extracted_data.append(d_dict)



            pension_total_value = 0
            for pen_trns in pension_transfer_list:
                pension_total_value = pension_total_value + pen_trns.amount

            pension_lumpsum_total_value = 0
            for pen_lump in pension_lumpsum_list:
                pension_lumpsum_total_value += pen_lump.amount
            
            pension_reg_total_value = 0
            for pen_reg in pension_regulars_list:
                pension_reg_total_value += pen_reg.amount

            pension_total_transfer_value = 0
            for pen_trnsfr in pension_transfer_list:
                pension_total_transfer_value += pen_trnsfr.amount

            vanguard_fund = False
            for ins in instr_recc:
                if ins.fund_risk and ins.fund_risk.get_fund_name_display() == 'Other':
                    vanguard_fund = True
                    vanguard_fund = SRAdditionalCheckContent.objects.filter(condition_check='vanguard_fund').first()
                    break 
            

            existing_isa_requlars = isas.filter(client_instrumentinfo__provider_type='1', function_list__in=['2','3']).distinct()
            new_isa_requlars = isas.filter(client_instrumentinfo__provider_type='2', function_list__in=['2','3']).distinct()
            
            existing_isa_transfers = isas.filter(function_list__in=['1'], map_transfer_from=None).distinct()
            new_isa_transfers = isas.filter(function_list__in=['1'], map_transfer_from__isnull=False).distinct()
            isa_transfer_list = isas.filter(function_list__in=['1']).distinct()



            for isa_tnx in isa_transfer_list:
                save_dict = {'existing':[], 'new':None, 'amount':0}
                if isa_tnx.map_transfer_from.all():
                    for map_from in isa_tnx.map_transfer_from.all():
                        exisiting_dict = {'ins':map_from, 'charges':0}
                        if map_from.amount:
                            save_dict['amount'] += map_from.amount
                        for data in ExtractedData.objects.filter(client_instrumentinfo=map_from.client_instrumentinfo):
                            if data.master_keywords.keyword_slug == 'charges':
                                value = 0.00
                                if data.extracted_value:
                                    try:
                                        value = float(data.extracted_value)
                                    except Exception as e:
                                        # logger.exception("Exception in SR generate charges type conversion : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                                        value = 0.00
                                exisiting_dict['charges'] = value
                                product_charges_noted = True  #for sr checlist purpose
                        save_dict['existing'].append(exisiting_dict)
                    save_dict['new'] = isa_tnx
                    save_dict['amount'] += (isa_tnx.amount-save_dict['amount'])

                    isa_tansfer_reccommendation_list.append(save_dict)

            isa_transfer_total_value = 0

            for isa_trns in isa_transfer_list:
                isa_transfer_total_value = isa_transfer_total_value + isa_trns.amount

            regular_new_isa_contibution_value = 0
            for new_isa_reg in new_isa_requlars:
                regular_new_isa_contibution_value += new_isa_reg.amount
               
            existing_gia_requlars = gias.filter(client_instrumentinfo__provider_type='1', function_list__in=['2','3']).distinct()
            new_gia_requlars = gias.filter(client_instrumentinfo__provider_type='2', function_list__in=['2','3']).distinct()
            
            existing_gia_transfers = gias.filter(function_list__in=['1'], map_transfer_from=None).distinct()
            new_gia_transfers = gias.filter(function_list__in=['1'], map_transfer_from__isnull=False).distinct()
            gia_transfer_list = gias.filter(function_list__in=['1']).distinct()


            for gia_tnx in gia_transfer_list:
                save_dict = {'existing':[], 'new':None, 'amount':0}
                if gia_tnx.map_transfer_from.all():
                    for map_from in gia_tnx.map_transfer_from.all():
                        exisiting_dict = {'ins':map_from, 'charges':0}
                        if map_from.amount:
                            save_dict['amount'] += map_from.amount
                        for data in ExtractedData.objects.filter(client_instrumentinfo=map_from.client_instrumentinfo):
                            if data.master_keywords.keyword_slug == 'charges':
                                value = 0.00
                                if data.extracted_value:
                                    try:
                                        value = float(data.extracted_value)
                                    except Exception as e:
                                        # logger.exception("Exception in SR generate charges type conversion : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                                        value = 0.00
                                exisiting_dict['charges'] = value
                                product_charges_noted = True  #for sr checlist purpose
                        save_dict['existing'].append(exisiting_dict)
                    save_dict['new'] = gia_tnx
                    save_dict['amount'] += (gia_tnx.amount-save_dict['amount'])

                    gia_tansfer_reccommendation_list.append(save_dict)

           
           
            gia_transfer_total_value = 0

            for gia_trns in gia_transfer_list:
                gia_transfer_total_value = gia_transfer_total_value + gia_trns.amount
           

            regular_new_gia_contibution_value = 0
            for new_gia_reg in new_gia_requlars:
                regular_new_gia_contibution_value += new_gia_reg.amount

            
            pension_flag = False
            pension_ext_reg_flag = False
            pension_new_reg_flag = False
            isa_txr_flag = False
            isa_new_reg_flag = False
            isa_ext_reg_flag = False
            gia_txr_flag = False
            gia_new_reg_flag = False
            gia_ext_reg_flag = False

            gia_new_lump_sum_flag = False
            gia_new_regular_flag = False
            isa_new_lump_sum_flag = False
            isa_new_regular_flag = False
            pension_new_lump_sum_flag = False
            pension_new_regular_flag = False

            if new_gia_requlars.filter(function_list__in=['2']).count() > 0:
                gia_new_lump_sum_flag = True
            if new_isa_requlars.filter(function_list__in=['2']).count() > 0:
                isa_new_lump_sum_flag = True
            if new_pension_regulars.filter(function_list__in=['2']).count() > 0:
                pension_new_lump_sum_flag = True
            if new_gia_requlars.filter(function_list__in=['3']).count() > 0:
                gia_new_regular_flag = True
            if new_isa_requlars.filter(function_list__in=['3']).count() > 0:
                isa_new_regular_flag = True
            if new_pension_regulars.filter(function_list__in=['3']).count() > 0:
                pension_new_regular_flag = True

            if (ext_pension_transfers.count() > 0) or (new_pension_transfers.count() > 0):
                pension_flag = True

            if existing_pension_regulars.count() > 0:
                pension_ext_reg_flag = True

            if new_pension_regulars.count() > 0:
                pension_new_reg_flag = True

            if (existing_gia_transfers.count() > 0) or (new_gia_transfers.count() > 0):
                gia_txr_flag = True

            if existing_gia_requlars.count() > 0:
                gia_ext_reg_flag = True

            if new_gia_requlars.count() > 0:
                gia_new_reg_flag = True
                product_charges_noted = True

            if (existing_isa_transfers.count() > 0) or (new_isa_transfers.count() > 0):
                isa_txr_flag = True

            if existing_isa_requlars.count() > 0:
                isa_ext_reg_flag = True

            if new_isa_requlars.count() > 0:
                isa_new_reg_flag = True
                product_charges_noted = True

            # Existing  instument data  ----------->>
            existing_instr_list = []
            for ext_instr in instr_recc.filter(map_transfer_from=None, client_instrumentinfo__provider_type='1'):
                data_dict = {"transfer_value": "", "policy_no": "", "fund_value": "", "provider_name": "","product_type": ""}
                
                for ext_instr_data in ExtractedData.objects.filter(client_instrumentinfo__id=ext_instr.client_instrumentinfo.id):
                    if ext_instr_data.master_keywords.keyword_slug == 'transfer_value':
                        # print(' ======  ', ext_instr_data.extracted_value)
                        if ext_instr_data.extracted_value:
                            value = re.sub(',', '', ext_instr_data.extracted_value)
                            value = re.sub('£', '', value)
                            data_dict['transfer_value'] = value
                        else:
                            data_dict['transfer_value'] = 0

                    if ext_instr_data.master_keywords.keyword_slug == 'policy_no':
                        if ext_instr_data.extracted_value:
                            data_dict['policy_no'] = ext_instr_data.extracted_value
                        else:
                            data_dict['policy_no'] = None

                    if ext_instr_data.master_keywords.keyword_slug == 'fund_value':
                        if ext_instr_data.extracted_value:
                            value = re.sub(',', '', ext_instr_data.extracted_value)
                            value = re.sub('£', '', value)
                            data_dict['fund_value'] = value
                        else:
                            data_dict['fund_value'] = 0

                    data_dict['provider_name'] = ext_instr.client_instrumentinfo.instrument.instrument_name
                    data_dict['product_type'] = ext_instr.client_instrumentinfo.instrument.product_type.fund_type

                existing_instr_list.append(data_dict)

            
            # <<-------------------- Existing  instument data

            # Pension instrument data  ----------->>

            # Gurantee and tax free cash availability check declaratioms
            # gurantee = False
            guarantee_list = []
            tax_free_cash = False
            tax_free_count = 0
           

            pension_instr_list = []
            for pension in ext_pensions:
               
                data_dict = {"transfer_value":"", "policy_no":"", "fund_value":"", "provider_name":"", "product_type":""}    
                
                data_dict['provider_name'] = pension.client_instrumentinfo.instrument.instrument_name
                data_dict['product_type'] = pension.client_instrumentinfo.instrument.product_type.fund_type
                for pension_instr_data in ExtractedData.objects.filter(client_instrumentinfo__id = pension.client_instrumentinfo.id):
                    if pension_instr_data.master_keywords.keyword_slug == 'policy_no':
                        if pension_instr_data.extracted_value:
                            data_dict['policy_no'] = pension_instr_data.extracted_value
                        else:
                            data_dict['policy_no'] = None

                    if pension_instr_data.master_keywords.keyword_slug == 'transfer_value':
                        if pension_instr_data.extracted_value:      
                            value = re.sub(',', '', pension_instr_data.extracted_value)
                            data_dict['transfer_value'] = value
                        else:
                            data_dict['transfer_value'] = 0
                    if pension_instr_data.master_keywords.keyword_slug == 'fund_value':
                        if pension_instr_data.extracted_value:
                            value = re.sub(',', '', pension_instr_data.extracted_value)
                            data_dict['fund_value'] = value
                        else:
                            data_dict['fund_value'] = 0

                    # Gurantee and tax free cash availability check  value setting
                    if pension_instr_data.master_keywords.keyword_slug == 'gurantees':
                        if pension_instr_data.select_value.lower() == 'yes':
                            
                            guarantee_list.append({'instr':pension, 'value':True})
                        else:
                            guarantee_list.append({'instr':pension, 'value':False})

                    if pension_instr_data.master_keywords.keyword_slug == 'tax_free_cash' and pension_instr_data.select_value.lower() == 'yes':
                        
                        tax_free_cash = True
                        tax_free_count += 1
                   

                pension_instr_list.append(data_dict)
            # <<-------------------- Pension instrument data

            transfer_list = instr_recc.filter(function_list__in=['1']).distinct().values_list('client_instrumentinfo')
            
            total_value = 0
            

            provider_list = instr_recc.exclude(map_transfer_from=None, function_list__in=['1']).values_list('client_instrumentinfo__provider')
            provider_content_list = []
            sr_provider_contents = SRProviderContent.objects.filter(provider__in=provider_list)
            for provider_content in sr_provider_contents:
                prov_content = format_content_for_sr(provider_content.content)
                provider_content_list.append({'provider_name':provider_content.provider.name, 'content':prov_content})

            currentMonth = datetime.datetime.now().month
            currentdate = datetime.datetime.now().day
            financial_year = datetime.datetime.now().year

            # April 5th starting of new year
            if (currentMonth <= 4 and currentdate < 5) or (currentMonth < 4):
                financial_year = financial_year - 1

            # All extratced data for APpendix section
            extracted_data_list = []
            for instr in existing_instrs:
                data_dict = {}
                data_dict['Provider Name'] = instr.client_instrumentinfo.provider.name
                for extracted_data in ExtractedData.objects.filter(
                        client_instrumentinfo__id=instr.client_instrumentinfo.id):
                    for keyword in MasterKeywords.objects.all():
                        if extracted_data.master_keywords.keyword_slug == keyword.keyword_slug:
                            data_dict[extracted_data.master_keywords.keyword] = extracted_data.extracted_value
                extracted_data_list.append(data_dict)

            client_age = None
            if Date_Of_Birth:
                today_datetime = datetime.date.today()
                client_age = today_datetime.year - Date_Of_Birth.year - (
                            (today_datetime.month, today_datetime.day) < (Date_Of_Birth.month, Date_Of_Birth.day))

            cover_img = MEDIA_ROOT + "/master/sr_images/SR_cover.jpg"
            cover_doc = MEDIA_ROOT + "/master/sr_document/SR_cover_page_window.docx"
            head_logo = MEDIA_ROOT + "/master/sr_images/SR_head_logo.png"
            platform_comparison_img = MEDIA_ROOT + "/master/sr_images/SR_platform_comparison.png"

            if IS_S3:
                cover_doc = Document.objects.filter(doc_type=19).first().doc.open()

            
            total_initial_fee_percent = 0
            total_ongoing_fee_percent = 0
            total_dfm_fee_percent = 0
            total_amount = 0
            weighted_amount = 0
            count = 0

            charge_valid_instrs = instr_recc.filter(function_list__in=['1'], map_transfer_from__isnull=False)
            charge_valid_instrs = charge_valid_instrs | instr_recc.exclude(function_list__in=['1'])
            charge_valid_instrs = charge_valid_instrs.distinct()

            for ins in charge_valid_instrs:
                count = count+1
                if ins.amount:
                    total_amount = total_amount + ins.amount
                    
            total_initial_fee_percent, total_dfm_fee_percent, total_ongoing_fee_percent = calculate_fee(amount=total_amount, inst_rec=charge_valid_instrs)

            total_fee_percent = total_dfm_fee_percent + total_ongoing_fee_percent
            
            for ins in charge_valid_instrs:
                amount_calculated = ins.amount * total_fee_percent / 100
                weighted_amount = weighted_amount + round(amount_calculated,2)

            total_inital_fee_amount = total_amount * total_initial_fee_percent / 100
            
            total_fee_amount = weighted_amount

            
            advisor_staff = Staff.objects.filter(user=client.created_by).first()
            
            if advisor_staff:
                signature = advisor_staff.signature
                advisor = advisor_staff.user.first_name.title() + ' ' + advisor_staff.user.last_name.title()


            to_instrs = instr_recc.filter(map_transfer_from__isnull=False).distinct()
            reason_count = to_instrs.values_list('reason').count()

            age_less_than_retirement = False
            if retirement_age and int(retirement_age) < 55:
               
                age_less_than_retirement = True

            template = Template(template.content)
            context = Context( 
                            {   
                                "signature":signature,
                                "cover_img":cover_img,
                                "head_logo":head_logo,
                                "platform_comparison_img":platform_comparison_img,
                                "advisor_name":advisor,
                                "salutation_title":salutation_title,
                                "client_name": client_name, 
                                "first_name":first_name,
                                'today':today, 
                                "address":address, 
                                "client_age": client_age,
                                # "new_instruments":new_instrs,
                                "existing_instruments":existing_instr_list,
                                # "existing_transfers":existing_transfers,

                                "existing_pension_extracted_data":existing_pension_extracted_data,

                                "pension_tansfer_reccommendation_list":pension_tansfer_reccommendation_list,
                                "isa_tansfer_reccommendation_list":isa_tansfer_reccommendation_list,
                                "gia_tansfer_reccommendation_list":gia_tansfer_reccommendation_list,

                                "ext_pension_transfers":ext_pension_transfers,
                                "new_pension_transfers":new_pension_transfers,
                                "pension_total_value":pension_total_value,
                                "pension_total_fund_value":pension_total_transfer_value,
                                
                                "existing_isa_transfers":existing_isa_transfers,
                                "new_isa_transfers":new_isa_transfers,
                                "isa_transfer_total_value":isa_transfer_total_value,
                                
                                "existing_gia_transfers":existing_gia_transfers,
                                "new_gia_transfers":new_gia_transfers,
                                "gia_transfer_total_value":gia_transfer_total_value,
                                
                                "existing_gia_requlars":existing_gia_requlars,
                                "new_gia_requlars":new_gia_requlars,
                                "regular_new_gia_contibution_value":regular_new_gia_contibution_value,

                                "existing_isa_requlars":existing_isa_requlars,
                                "new_isa_requlars":new_isa_requlars,
                                "regular_new_isa_contibution_value":regular_new_isa_contibution_value,

                                "existing_pension_regulars":existing_pension_regulars,
                                "new_pension_regulars":new_pension_regulars,

                                "pension_flag":pension_flag,
                                "pension_ext_reg_flag":pension_ext_reg_flag,
                                "pension_new_reg_flag":pension_new_reg_flag,
                                
                                "isa_txr_flag":isa_txr_flag,
                                "isa_new_reg_flag":isa_new_reg_flag,
                                "isa_ext_reg_flag":isa_ext_reg_flag,

                                "gia_txr_flag":gia_txr_flag,
                                "gia_new_reg_flag":gia_new_reg_flag,
                                "gia_ext_reg_flag":gia_ext_reg_flag,

                                "gia_new_lump_sum_flag":gia_new_lump_sum_flag,
                                "gia_new_regular_flag":gia_new_regular_flag,
                                "isa_new_lump_sum_flag":isa_new_lump_sum_flag,
                                "isa_new_regular_flag":isa_new_regular_flag,
                                "pension_new_lump_sum_flag":pension_new_lump_sum_flag,
                                "pension_new_regular_flag":pension_new_regular_flag,

                                "vanguard_fund":vanguard_fund,
                                "pension_instruments":pension_instr_list,
                                # "total_value":total_value,
                                "has_cash_asset":has_cash_asset,
                                "own_property":own_property, 
                                "mortgage_exist":mortgage_exist,
                                "employer":employer,
                                "salary":salary,
                                "will_made":will_made,
                                "long_term_plan":long_term_plan,
                                "retirement_age":retirement_age,
                                "employement_status":employement_status,
                                "employee_contribution":employee_contribution,
                                "employer_contribution":employer_contribution,
                                "asset_list":asset_list,
                                "atr":atr,
                                "recomended_instruments":to_instrs,
                                # "provider_contents":provider_content,
                                "provider_contents":provider_content_list,
                                "financial_year":financial_year,
                                "guarantee_list":guarantee_list,
                                "tax_free_cash":tax_free_cash,
                                "tax_free_count":tax_free_count,
                                "appendix_list":extracted_data_list,

                                "total_initial_fee_percent":total_initial_fee_percent,
                                "total_amount":total_amount,
                                "total_inital_fee_amount":total_inital_fee_amount,
                                "total_dfm_fee_percent":total_dfm_fee_percent,
                                "total_ongoing_fee_percent":total_ongoing_fee_percent,
                                "total_fee_percent":total_fee_percent,
                                "total_fee_amount":total_fee_amount,

                                "pension_lumpsum_total_value" : pension_lumpsum_total_value,
                                "pension_reg_total_value" :pension_reg_total_value,


                                "type_of_pension":type_of_pension,
                                "pension_value":pension_value,
                                "previous_employer":previous_employer,
                                "previous_employer_pension":previous_employer_pension,
                                "private_pension_list":private_pension_list,
                                "age_less_than_retirement":age_less_than_retirement
                            }
                        )

            html = template.render(context)
            document = docx()
           

            paragraph = document.add_paragraph()
            run = paragraph.add_run()
            fldChar = OxmlElement('w:fldChar')  # creates a new element
            fldChar.set(qn('w:fldCharType'), 'begin')  # sets attribute on element
            fldChar.set(qn('w:dirty'), 'true')
            instrText = OxmlElement('w:instrText')
            instrText.set(qn('xml:space'), 'preserve')  # sets attribute on element
            instrText.text = 'TOC \\o "1-3" \\h \\z \\u \\img'  # change 1-3 depending on heading levels you need
            fldChar2 = OxmlElement('w:fldChar')
            fldChar2.set(qn('w:fldCharType'), 'separate')
            fldChar3 = OxmlElement('w:t')
            fldChar3.text = "Right-click to update field."
            fldChar2.append(fldChar3)
            fldChar4 = OxmlElement('w:fldChar')
            fldChar4.set(qn('w:fldCharType'), 'end')
            r_element = run._r
            r_element.append(fldChar)
            r_element.append(instrText)
            r_element.append(fldChar2)
            r_element.append(fldChar4)
            p_element = paragraph._p
            new_parser = HtmlToDocx()
            new_parser.add_html_to_document(html, document)
            
            count = get_doc_count(client, '8')  # doc_type 8 for sr
            if not IS_S3:
                check_sr_path_exist(client)
            print("document save")

            doc_io = io.BytesIO()
            master = docx(cover_doc)
            composer = Composer(master)
            composer.append(document)
            composer.save(doc_io)
            doc_io.seek(0)
            obj = Document.objects.create(uploaded_by=request.user, owner=client, doc_type='8')
            obj.doc.save('SR_c' + str(client.id) + '_' + today + '_v' + str(count) + '.docx', File(doc_io))
            if not client.pre_contract_date:
                client.pre_contract_date = datetime.date.today()
            client.save()
            
            #profile percentage calculation 
            sr_count=Document.objects.filter(owner=client, doc_type='8',is_active=True,is_deleted=False).count()
            if sr_count==1:
                client_profile_completion(client=client,phase='pre-contract',percentage=10,sign='positive')
                
                client.client_stage='2'
                client.save()

            if obj:
               
                data = {'id': obj.id, 'owner': obj.owner.id, 'doc': obj.doc.url, 'doc_type': obj.doc_type,
                        'create_time': obj.create_time}
                try:
                    if IS_S3:
                        df = server_storage()
                        full_path = os.path.join(df.base_location, obj.doc.name)
                        pathlib.Path(os.path.split(full_path)[0]).mkdir(parents=True, exist_ok=True)
                        df.save(full_path, obj.doc.open())
                        update_index = update_doc(full_path, True,False)
                        _report_doc = File(open(full_path, mode='rb'))
                        path = default_storage.save(obj.doc.name, _report_doc)
                    else:
                        update_index = update_doc(obj.doc.path, True)
                except Exception as e:
                    logger.exception("Exception in SR generate - Document table of content index is not updated : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                    print("Document table of content index is not updated", e)


                # SR checklist section
                draftchecklist=DraftCheckList.objects.filter(category_name='12')#SR related checklists
                recommended_producttypes_list = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
                advisor = Staff.objects.filter(user=client.created_by).first()
                provider_list_applicable = Provider.objects.filter(id__in=provider_list).values_list('name')
                is_provider_applicable = False
                for provider in provider_list_applicable:
                    if provider in ['Quilter', 'Fidelity', 'Aegon']:
                        is_provider_applicable=True
                        break

                for checklist in draftchecklist:
                    all_products = True if not (list(checklist.product_type.all())) else False
                    checklist_product_types = list(checklist.product_type.all().values_list('fund_type', flat=True))
                    producttype_exist = any(item in checklist_product_types for item in list(recommended_producttypes_list))
                    checklist_applicable = False
                    if producttype_exist or all_products:
                        if not (existing_instrs and not new_instrs and not existing_transfers): #for transfer and new types
                            if checklist.id in [33,34] and is_provider_applicable: #1.Does the criteria for the provider selection meet the requirements of the client?, 2.Is there research on file to justify the provider (including platform/wrap)?
                                if provider_content: #pass condition
                                    result='passed'
                                else:
                                    result='failed'
                                update_or_create_checklist(client, checklist.id, advisor, result=result)
                                checklist_applicable = True

                        if pension_transfer_list or isa_transfer_list:
                            if checklist.id in [36,61]: #1.What are the reasons for considering a transfer?     2.Does the report confirm (potential) risks and disadvantages of the recommended transfer for the client to consider?
                                update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                checklist_applicable = True

                        if pension_flag or pension_ext_reg_flag or pension_new_reg_flag or gia_txr_flag or gia_ext_reg_flag or gia_new_reg_flag or isa_txr_flag or isa_ext_reg_flag or isa_new_reg_flag:
                            if checklist.id in [37]: #If limited advice has been given does the report confirm this?
                                update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                checklist_applicable = True

                        if pension_flag or pension_new_reg_flag or gia_txr_flag or gia_new_reg_flag or isa_txr_flag or isa_new_reg_flag:
                            if checklist.id in [35,38,39]: #1.Is there evidence on file to confirm a KFD and illustration have been issued to client?   2.Have alternative products been considered?,
                                                           #3.Have reasons been given for discounting these?
                                update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                checklist_applicable = True

                            if checklist.id in [40] and is_provider_applicable: #Are full details of the product reccomendation included? Type of pension? e.g. PP, SIPP Transfer Amount?
                                if provider_content:
                                    result='passed'
                                else:
                                    result='failed'
                                update_or_create_checklist(client, checklist.id, advisor, result=result)
                                checklist_applicable = True

                        if pension_flag or gia_txr_flag or isa_txr_flag:
                           

                            if checklist.id in [54]: #Have product charges been noted?
                                update_or_create_checklist(client, checklist.id, advisor, result='amber') #client feedbacked to always give as amber

                             
                                checklist_applicable = True

                        if checklist.id in [42,43,44,45,46]:#1.What are the client’s objectives? e.g. Retirement age, income required in retirement,  #2.Are the details of the priority each objective has been given clear?,
                                                              #3.Explanation of why these have been agreed with client?,   4.What are the timescales for each objective?,   5.Does the report record the client’s objectives and priorities?
                            update_or_create_checklist(client, checklist.id, advisor, result='passed')
                            checklist_applicable = True

                        if checklist.id in [50]: #Does the report record how the recommendation benefits the client?
                            if pension_flag or gia_txr_flag or isa_txr_flag:
                                if reason_count>0:
                                    update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                else:
                                    update_or_create_checklist(client, checklist.id, advisor, result='failed')
                                checklist_applicable = True


                        if checklist.id in [51]: #Has the report been signed and dated by the adviser?
                            if signature:
                                update_or_create_checklist(client, checklist.id, advisor, result='passed')
                            else:
                                update_or_create_checklist(client, checklist.id, advisor, result='failed')
                            checklist_applicable = True


                        if checklist.id in [53,60]: #1.Have advice charges been recorded (ongoing and initial)?,   2.Does the report confirm the level of future service the client has selected?
                            if (total_initial_fee_percent or total_initial_fee_percent==0) and (total_ongoing_fee_percent or total_ongoing_fee_percent==0):
                                update_or_create_checklist(client, checklist.id, advisor, result='passed')
                            else:
                                update_or_create_checklist(client, checklist.id, advisor, result='failed')
                            checklist_applicable = True

                        if pension_flag or pension_new_reg_flag or gia_txr_flag or gia_new_reg_flag or isa_txr_flag or isa_new_reg_flag:
                            if checklist.id in [55]: #The report should contain relevant statements summarising the client’s personal and financial situation.
                                update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                checklist_applicable = True

                            if checklist.id in [62]:  #Have any relevant tax implications been recorded?
                                update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                checklist_applicable = True

                        if pension_flag or pension_new_reg_flag:
                            if checklist.id in [56,59]: #1.Does the report contain details of the client’s employer’s workplace pension scheme?,   2.Does the report document that a nomination of a beneficiary was discussed?,
                                                           # 3.Does the report confirm (potential) risks and disadvantages of the recommended transfer for the client to consider?
                                update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                checklist_applicable = True

                            if checklist.id in [57]: #Are the clients pensions/assets and projected income from those explained and detailed?
                                if asset_list:
                                    update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                else:
                                    update_or_create_checklist(client, checklist.id, advisor, result='failed')
                                checklist_applicable = True

                            if checklist.id in [58]: #Does the report confirm whether contributions are being made into any pension arrangements?
                                if employee_contribution and employer_contribution:
                                    update_or_create_checklist(client, checklist.id, advisor, result='passed')
                                else:
                                    update_or_create_checklist(client, checklist.id, advisor, result='failed')
                                checklist_applicable = True

                        # if (pension_flag or pension_new_reg_flag or isa_txr_flag or ) and checklist.id in [62]:  #Have any relevant tax implications been recorded?
                        #     update_or_create_checklist(client, checklist.id, advisor, result='passed')
                        #     checklist_applicable = True


                        if not checklist_applicable:
                            delete_checklist(client, checklist)

                    else:
                        delete_checklist(client, checklist)


                    ######checklist resets###########
                try:
                    draftchecklists = DraftCheckList.objects.filter(category_name__in=['7','10','13'])
                    for checklist in draftchecklists:
                        if checklist.category_name == '13':
                            recommended_producttypes = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client, function_list__function_type='1',is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
                        else:
                            recommended_producttypes = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
                        all_products = True if not (list(checklist.product_type.all())) else False
                        checklist_product_types = list(checklist.product_type.all().values_list('fund_type', flat=True))
                        producttype_exist = any(item in checklist_product_types for item in list(recommended_producttypes))
                        if producttype_exist or all_products:
                            if checklist.id in [48,22]:
                                print("pass checklist  ")
                                pass
                               
                            else:
                                update_or_create_checklist(client, checklist.id, advisor)

                        else:
                            delete_checklist(client, checklist)

                except Exception as e:
                    logger.exception("Exception in SR generate - Error in checklist resets : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                    print("Error in checklist resets", e)

                ######checklist resets###########

            else:
                response_data['status_code'] = "400"
                response_data['status'] = False
                response_data['message'] = 'SR document could not be generated'
                resp_status = status.HTTP_400_BAD_REQUEST
        else:

            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'Invalid client details mentioned'
            resp_status = status.HTTP_400_BAD_REQUEST

        if data:

            status_collection = StatusCollection.objects.get(status='1.73')  
            add_activity_flow(action_performed_by=request.user, client=client, status=status_collection)
            

            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'SR document generated successfully'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)



class TemplateCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = TemplateCategory.objects.all()
    serializer_class = TemplateCategorySerializer

    def get_queryset(self):
        queryset = TemplateCategory.objects.all()
        type = self.request.query_params.get('type', None)
        if type is not None:
            queryset = queryset.filter(temp_type=type)
        return queryset

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Template categories fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'Not found'
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)


class ActivityFlowViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = ActivityFlow.objects.all()
    serializer_class = ActivityFlowSerializer

    def get_queryset(self):
        queryset = ActivityFlow.objects.all()
        client_id = self.request.query_params.get('client_id', None)
        if client_id is not None:
            queryset = queryset.filter(client=client_id)
        queryset = queryset.order_by('id')
        return queryset

    def list(self, request, *args, **kwargs):
        response_data = {}
        data = {}
        PRE_CONTRACT = []
        ATP = []
        POST_CONTRACT = []
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        initial_data = serializer.data

        for activity in initial_data:
            stage = activity.pop('stage')
            if (stage == 'PRE'):
                PRE_CONTRACT.append(activity)
            elif (stage == 'ATP'):
                ATP.append(activity)
            elif (stage == 'POST'):
                POST_CONTRACT.append(activity)
        data = {'PRE_CONTRACT': PRE_CONTRACT, 'ATP': ATP, 'POST_CONTRACT': POST_CONTRACT}
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Activity flow fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'Not found'
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)


class ReminderViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = Reminder.objects.all()
    serializer_class = ReminderSerializer

    def get_queryset(self):
        queryset = Reminder.objects.all()
        user = self.request.user
        staff_list_obj = []
        user_list = Staff.objects.filter(user=user,user__groups__name__in=['Ops', 'Compliance','Administrator']).first()
        if user_list:
            staff_list=Staff.objects.filter(company=user_list.company)
            for staff_result in staff_list:
                staff_list_obj.append(staff_result.user)
            queryset = queryset.filter(owned_by__in=staff_list_obj)
        else:
            queryset = queryset.filter(owned_by=self.request.user)  # owned_by is a single user/advisor #need to rework incase of multiple owners
        userid = self.request.query_params.get('clientid', None)
        print("user id is", userid)
        state = self.request.query_params.get('state', None)
        due_date = self.request.query_params.get('due_date', None)
        pending_with = self.request.query_params.get('pending_with', None)
        if pending_with:
            print("inside condition pending_with")
            queryset = queryset.filter(pending_with=pending_with)
        if userid:
            print("inside condition")
            clientid = Client.objects.filter(user__id=userid).first()
            print(clientid, ' client')

            if clientid:
                
                queryset = queryset.filter(client=clientid)
                print(queryset)

        if due_date:
            queryset = queryset.filter(due_date=due_date)

        queryset.filter(snooze_status='1', reminder_date__lte=datetime.date.today()).update(snooze_status='2', snooze_duration=0)  # To disable snooze, if reminder date has arrived.
        if (state == 'active'):
            queryset = queryset.filter(reminder_date__lte=datetime.date.today())  # To avoid pending actions whose reminder date is not arrived yet.
            queryset = queryset.filter(snooze_status='2')  # To avoid snoozed reminders          ##'2'=disabled
        print("before returning condition")
        return queryset



    def list(self, request, *args, **kwargs):
        response_data = {}

        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.order_by('-reminder_date', '-id')
        serializer = self.get_serializer(queryset, many=True)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            count = self.paginator.count
            offset = self.paginator.offset
            limit = self.paginator.limit
        if page is None:
            data = serializer.data
            count = offset = limit = None
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Pending actions fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'No Pending actions'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK
        response_data['count']=count
        response_data['offset']=offset
        response_data['limit']=limit
        staff_updation = Staff.objects.filter(user__id=request.user.id).update(notification_count=0)
        update_viewed_flag = queryset.update(is_viewed=True)


        return Response(response_data, status=resp_status)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            

            snooze_enable = self.request.query_params.get('snooze_enable', None)
            snooze_duration_unit = request.data['snooze_duration_unit']

            pre_reminder_date = instance.reminder_date
            if snooze_enable is not None:

                if (snooze_enable == 'true'):
                    print("inside reminder snooze")

                    snooze_duration = request.data['snooze_duration']
                    reminder_date = pre_reminder_date + timedelta(int(snooze_duration))
                    
                    if (snooze_duration_unit == 'week'):
                        snooze_duration = request.data['snooze_duration'] * 7

                    new_reminder = Reminder.objects.create(pending_with=instance.pending_with,
                                                           owned_by=instance.owned_by, \
                                                           sent_to_group=instance.sent_to_group, client=instance.client,
                                                           status=instance.status, \
                                                           client_instrument=instance.client_instrument,
                                                           due_date=instance.due_date, \
                                                           snooze_status='1', mail_needed=instance.mail_needed, \
                                                           mail_count=instance.mail_count, comment=instance.comment,
                                                           snooze_duration_unit=snooze_duration_unit,
                                                           snooze_duration=snooze_duration, reminder_date=reminder_date)
                    instance.is_deleted = True

                else:
                    print("im here in false")

                    snooze_status = '2'  # disabling snooze status

                    snooze_duration = instance.snooze_duration

                    reminder_date = pre_reminder_date - timedelta(int(snooze_duration))
                    snooze_duration = 0  # updated to zero while disabling
                    new_reminder = Reminder.objects.create(pending_with=instance.pending_with,
                                                           owned_by=instance.owned_by, \
                                                           sent_to_group=instance.sent_to_group, client=instance.client,
                                                           status=instance.status, \
                                                           client_instrument=instance.client_instrument,
                                                           due_date=instance.due_date, \
                                                           snooze_status=snooze_status,
                                                           mail_needed=instance.mail_needed, \
                                                           mail_count=instance.mail_count, comment=instance.comment,
                                                           snooze_duration_unit=snooze_duration_unit,
                                                           snooze_duration=snooze_duration, reminder_date=reminder_date)
                    instance.is_deleted = True

                peding_actions = new_reminder.status.get_status_display()
                if new_reminder.comment:
                    peding_actions = peding_actions + "-" + new_reminder.comment

                instrument_id = new_reminder.client_instrument.id if new_reminder.client_instrument else None
                new_reminder_dict = {
                    "id": new_reminder.id,
                    "pending_actions": peding_actions,
                    "pending_with": new_reminder.pending_with,
                    "due_date": new_reminder.due_date,
                    "reminder_date": new_reminder.reminder_date,
                    "client": new_reminder.client.user.first_name + " " + new_reminder.client.user.last_name,
                    "snooze_status": new_reminder.get_snooze_status_display(),
                    "snooze_duration": new_reminder.snooze_duration,
                    "snooze_duration_unit": new_reminder.get_snooze_duration_unit_display(),
                    "mail_needed": new_reminder.mail_needed,
                    "mail_count": new_reminder.mail_count,
                    "client_instrument_id": instrument_id

                }

                instance.save()


        except Exception as e:
            logger.exception("Exception in Reminder snoozing : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Error in snoozing'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'You have updated the snooze settings'
            response_data['data'] = new_reminder_dict
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK

        return Response(response_data, status=resp_status)


class ReminderPendingView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request):
        search_keyword = self.request.query_params.get('search', None)
        provider_list = Provider.objects.filter(Q(name__icontains=search_keyword))
        group_list = Group.objects.filter(Q(name__icontains=search_keyword), name__in=['Ops', 'Compliance'])
      

        staff_flag = True
        userid = self.request.user.id
        if userid:
            staff = Staff.objects.filter(user__id=userid).first()
            if staff:
                company_id = staff.company.id
                if company_id:
                    user_list = Staff.objects.filter(company__id=company_id).exclude(user__id=userid)
                    
                    staff_flag = False

        reminderpending = []
        if staff_flag:
            user_list = []

        for providers in provider_list:
            reminderpending.append({"id": providers.id, "name": providers.name, "type": "Provider"})

        for users in user_list:
            if users.user.is_staff == True:
            # if users.user.is_staff == True:
                reminderpending.append(
                    {"id": users.user.id, "name": users.user.first_name + " " + users.user.last_name, "type": "User"})
        for group in group_list:
            reminderpending.append({"id": group.id, "name": group.name, "type": "Group"})


        reminderpending.append({"id": len(reminderpending) + 1, "name": 'Me'})
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "Pending reminder details fetched successfully",
            'data': reminderpending
        }

        return Response(response_data, status=status.HTTP_200_OK)


class ReminderNotificationView(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request):

        userid = self.request.user.id
        notification_pending = 0
        user_list = Staff.objects.filter(user=self.request.user,user__groups__name__in=['Ops', 'Compliance','Administrator']).first()
        
        if userid and not user_list:
            staff = Staff.objects.filter(user__id=userid).first()
            if staff:
                notification_pending = staff.notification_count
        notification = {"notification_count": notification_pending}
        
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "Notification fetched successfully",
            'data': notification
        }

        return Response(response_data, status=status.HTTP_200_OK)


class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = CategoryAndSubCategory.objects.filter(parent=None).order_by('category_order')
        return queryset

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Category list fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'Not found'
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)


class CategorySummaryViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = CategorySummarySerializer

    def get_queryset(self):
        queryset = CategorySummary.objects.all()
        client_id = self.request.query_params.get('client_id', None)
        if client_id:
            queryset = queryset.filter(client__id=client_id)

        return queryset

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(is_sub_category=False)
        queryset = queryset.order_by('category__category_order')
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Category Summary list fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "400"
            response_data['status'] = False
            response_data['message'] = 'Not found'
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)


class CountryViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = CountrySerializer
    queryset = Countries.objects.all()
    search_fields = ['^name', ]
    filter_backends = (filters.SearchFilter,)

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Country list fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "200"
            response_data['status'] = False
            response_data['message'] = 'No Such country'
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class JobtitleViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = JobtitleSerializer
    queryset = Job_titles.objects.all()
    search_fields = ['^name', ]
    filter_backends = (filters.SearchFilter,)

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Job title list fetched'
            response_data['data'] = data


        else:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Not found'
            response_data['data'] = data

        resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class LenderViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = LenderSerializer
    queryset = Lender_names.objects.all()
    search_fields = ['^name', ]
    filter_backends = (filters.SearchFilter,)

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Lender list fetched'
            response_data['data'] = data


        else:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Not found'
            response_data['data'] = data
        resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class PensionProviderViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = PensionproviderSerializer
    queryset = pension_providers.objects.all()
    search_fields = ['^name', ]
    filter_backends = (filters.SearchFilter,)

    def list(self, request, *args, **kwargs):
        response_data = {}
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        if data:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Provider list fetched'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK

        else:
            response_data['status_code'] = "200"
            response_data['status'] = True
            response_data['message'] = 'Not found'
            response_data['data'] = data
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class ClientAudioExtractionViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ClientAudioExtractionSerializer
    queryset = ClientAudioExtraction.objects.all()

    def create(self, request, *args, **kwargs):
        response_data = {}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            response = super().create(request)
            audio_obj = ClientAudioExtraction.objects.filter(id=response.data['id']).first()
            date_string = datetime.datetime.now()
            full_time_stamp = date_string.timestamp()
            time_stamp = str(full_time_stamp).split('.')[0]
            audio_obj.recording_name =  "Record-"+str(response.data['id'])+"_"+time_stamp
            audio_obj.save()
            if audio_obj.client_id:
                try:
                    user = audio_obj.client_id.created_by
                    client = audio_obj.client_id
                    category_id = audio_obj.category_id
                    activity_flow_update_status = StatusCollection.objects.get(status='1.9')
                    add_activity_flow(action_performed_by=request.user, client=client, status=activity_flow_update_status,
                                      comment=category_id)
                except Exception as e:
                    print(e)
                    logger.exception("Exception in Audio extraction : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                

           
            # TO DO update recording_data value same as recording_blob
            if IS_S3:
                blob_path = audio_obj.recording_blob.open()
            else:
                blob_path = audio_obj.recording_blob.path
            audio_from_blob = blob_conversion(blob_path, audio_obj.recording_name)
            if audio_from_blob:
                if not IS_S3:
                    audio_obj.audio_data = audio_from_blob
                else:
                    name = audio_from_blob.partition(MEDIA_ROOT)[-1]
                    audio = File(open(audio_from_blob, mode='rb'), name='WAV')
                    default_storage.save(name.strip('/'), audio)
                    audio_obj.audio_data.name = name.strip('/')
                audio_obj.save()
              
                text = audioconversion(audio_from_blob,audio_obj.recording_name, request)
                if text:
                    audio_obj.recording_text = text
                    audio_obj.save()
                   
                    try:
                        if user:
                            activity_flow_update_status = StatusCollection.objects.get(status='1.10')
                            add_activity_flow(action_performed_by=request.user, client=client,
                                              status=activity_flow_update_status, comment=category_id)
                    except Exception as e:
                        print(e)
                       
        except sr.UnknownValueError as e:
            logger.exception("Exception in Audio extraction - Low clarity audio file: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'Low clarity audio file'
            audio_obj.recording_text = "Low clarity audio file"
            audio_obj.save()

        except sr.RequestError as e:
            print("exception in speech recognition.... ", str(e))
            logger.exception("Exception in speech recognition - No results from speech recognition service: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'No results from speech recognition service'
            audio_obj.recording_text = "No results to show"
            audio_obj.save()
        except Exception as e:
            logger.exception("Exception in speech recognition - Invalid data: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            print("exception in speech recognition: ", str(e))
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Invalid data'
            audio_obj.recording_text = "Invalid data"
            audio_obj.save()
        else:
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'Recording saved successfully'

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '201':
            resp_status = status.HTTP_201_CREATED
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK

        return Response(response_data, status=resp_status)

    def get_queryset(self):
        queryset = ClientAudioExtraction.objects.all()
        filter_options = dict(self.request.query_params)
        for option in filter_options.copy():
            if not filter_options[option][0]:
                del filter_options[option]
            else:
                filter_options[option] = filter_options[option][0]
        queryset = queryset.filter(**filter_options).order_by('-id')
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data_val = serializer.data
        data = []
        for listval in data_val:
            data_new = copy.copy(listval)
            data.append(data_new)
        for listval in data:
            del (listval['advisor_id'])
            del (listval['client_id'])
            del (listval['audio_data'])
            del (listval['category_id'])

        response_data = {
            "status_code": "201",
            "status": True,
            "message": 'Recording fetched successfully',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None):
        response_data = {}
        record_to_delete = ClientAudioExtraction.objects.filter(id=pk).first()

        if record_to_delete:
            record_to_delete.is_deleted = True
            record_to_delete.save()
            try:
                user = record_to_delete.client_id.created_by
                client = record_to_delete.client_id
                category_id = record_to_delete.category_id
                activity_flow_update_status = StatusCollection.objects.get(status='1.69')
                add_activity_flow(action_performed_by=request.user, client=client, status=activity_flow_update_status,
                                  comment=category_id)
            except Exception as e:
                print(e)
                logger.exception("Exception in audio data delete: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                


            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'Record Deleted Successfully'

        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Record Not Found'

        if response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        elif response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST

        return Response(response_data, status=resp_status)


class ClientTaskViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ClientTaskSerializer

    def get_queryset(self):
        client = self.request.query_params.get('client', None)
        task_status = self.request.query_params.get('status', None)
        created_date = self.request.query_params.get('created', None)
        assigned_to_id = self.request.query_params.get('assigned', None)
        latest_task = self.request.query_params.get('task', None)

        queryset = ClientTask.objects.all().order_by('-id')

         # to get task details when admin or ops or compliance navigate to task details from client edit section
        if 'pk' in self.kwargs:
            queryset = ClientTask.objects.filter(id=self.kwargs['pk'])
        else:
            group = self.request.user.groups.first()
            if not group.name == 'SuperAdmin':  
                queryset = queryset.filter( Q(advisor__user=self.request.user) | Q(ops__user=self.request.user) | Q(administrator__user=self.request.user) | Q(compliance__user=self.request.user) )
        
        if client:
            
            queryset = queryset.filter(Q(client__user__first_name__icontains=client) | Q(client__user__last_name__icontains=client))

        if task_status:
            queryset = queryset.filter(task_status=task_status)

        if created_date:
            queryset = queryset.filter(create_time__date=created_date)

        if assigned_to_id:
            queryset = queryset.filter(assigned_to__id=assigned_to_id)

        if latest_task:
            queryset = queryset.filter(current_sub_task__task_name__icontains=latest_task)            
           
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        count = offset = limit = None
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            count = self.paginator.count
            offset = self.paginator.offset
            limit = self.paginator.limit
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Client Task List',
            "count": count,
            "offset": offset,
            "limit": limit,
            "data": data
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


    def perform_create(self, serializer):
        response,active_task=serializer.save()
        return response,active_task

        
    def create(self, request, *args, **kwargs):
        response_data = {}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        response,active_task=self.perform_create(serializer)
        if response:
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'Client task created successfully'
            response_data['task_id']=response.id
        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            if active_task:
                response_data['message'] = 'Client task could not be created as an active task already present for the client'
            else:
                response_data['message'] = 'Client task could not be created as Ops Lead user not found'

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '201':
            resp_status = status.HTTP_201_CREATED

        return Response(response_data, status=resp_status)


    def retrieve(self, request, *args, **kwargs):
        data = super().retrieve(request, *args, **kwargs).data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Task Details',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        print(request.data)
        
        admin_checklist_verification = request.data.get('is_admin_checklist_verified', None)
        compliance_checklist_verification = request.data.get('is_compliance_checklist_verified', None)
        advisor_checklist_verification = request.data.get('is_advisor_checklist_verified', None)

        admin_task_verify = request.data.get('is_admin_verified', None)
        ops_task_verify  = request.data.get('is_ops_verified', None)
        compliance_task_verify  = request.data.get('is_compliance_verified', None)
        kyc_confirmed =  request.data.get('is_kyc_confirmed', None)
        advisor_approved = request.data.get('advisor_approved', None) 

        response_data = {}
        client_taskobj=[]
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        message = 'Task verified'
        
        
        if instance.task_status=='3':
            raise serializers.ValidationError({"task": ["You can't update closed file contents"]})
        try:
            response = self.perform_update(serializer)
            
            if admin_checklist_verification: 
                message = "Administrator checklist verified"
            elif compliance_checklist_verification:
                message = "Compliance checklist verified"
            elif advisor_checklist_verification:
                message = "Advisor checklist verified"                
            
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            if serializer and serializer.data:
                client_taskobj=serializer.data

            if ops_task_verify:
                message = "Task verified by Ops Lead user"
            if admin_task_verify:
                message = "Task verified by Administrator and assigned to Compliance Team"
               
            if compliance_task_verify:
                message = "Task verified by Compliance Team and assigned to Administrator"
            if kyc_confirmed:
                message = "KYC details confirmed"
            if advisor_approved:
                message = "Task file approved and closed"
           
            
            
        except Exception as e:
            print(e)    
            logger.exception("Exception in task verification: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            
            compliance_user = Staff.objects.filter(user__groups__name='Compliance', company=instance.advisor.company).first()
            if ((instance.administrator) and (not compliance_user or compliance_user is None)):
                raise serializers.ValidationError({"task": ["Client task could not be verified as compliance team is not found"]})
            else:
                raise serializers.ValidationError({"task": ["Error while task verification"]})
           
           
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = message
            response_data['data'] =client_taskobj
       
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)

    @action(methods=['post'], detail=True)
    def assign_task(self, request, *args, **kwargs):

        instance = self.get_object()
        response_data = {}
        task = None
        assigned_to = None
        
        if 'task_id' in self.request.data.keys():
            task = ClientTask.objects.filter(id=self.request.data['task_id']).first()
        if 'assigned_to' in self.request.data.keys():
            assigned_to = Staff.objects.filter(id=self.request.data['assigned_to']).first()
        
        if not task or not assigned_to:
            if not task:
                response_data['message'] = 'Task details not found'
            if not assigned_to:
                response_data['message'] = 'Assignee details not found'
            response_data['status_code'] = "400"
            response_data['status'] = False
            resp_status = status.HTTP_400_BAD_REQUEST
        
        else:
           
            if task.assigned_to == assigned_to:
                response_data['message'] = 'Task already assigned to the same user.'
                response_data['status_code'] = "400"
                response_data['status'] = False
                resp_status = status.HTTP_400_BAD_REQUEST
                return Response(response_data, status=resp_status)

            group = assigned_to.user.groups.first()
            if group.name == 'Ops':
                updated = ClientTask.objects.filter(id=self.request.data['task_id']).update(assigned_to=assigned_to, ops=assigned_to)
            elif group.name == 'Administrator':
                updated = ClientTask.objects.filter(id=self.request.data['task_id']).update(assigned_to=assigned_to, administrator=assigned_to)
                ClientCheckList.objects.filter(client=task.client).update(administrator=assigned_to)
                task_collection = TaskCollection.objects.filter(task_slug='task_assigned').first()
                add_task_activity(client_task=instance, task_collection=task_collection, created_by=instance.ops, assigned_to=assigned_to, task_status='3')
            elif group.name == 'Compliance':
                updated = ClientTask.objects.filter(id=self.request.data['task_id']).update(assigned_to=assigned_to, compliance=assigned_to)
                ClientCheckList.objects.filter(client=task.client).update(compliance=assigned_to)

            else:
                updated = ClientTask.objects.filter(id=self.request.data['task_id']).update(assigned_to=assigned_to, advisor=assigned_to)

            task = ClientTask.objects.filter(id=self.request.data['task_id']).first()
           
            if updated:
                created_by = Staff.objects.filter(user=self.request.user).first()
                task_collection = TaskCollection.objects.filter(task_slug='task_assigned').first()
               
                task.current_sub_task = task_collection
                task.save()
               
                if group.name=='Administrator':
               
                    result = templatemailsend("task_assignment-notification_mail",self.request.user,task.client.id,assigned_to=assigned_to, task=task)
                    if result:
                        print("task_assignment-notification_mail has been sent..... ")
                
                if group.name=='Compliance':
                    result = templatemailsend("compliance_task_assignment",self.request.user,task.client.id,assigned_to=assigned_to, task=task)
                    if result:
                        print("==================task_assignment-ops_mail has been sent ================================ ")
                
                response_data['status_code'] = "200"
                response_data['status'] = True
                response_data['message'] = 'Task assigned successfully'
                resp_status = status.HTTP_200_OK
            else:
                response_data['status_code'] = "400"
                response_data['status'] = False
                response_data['message'] = 'Could not assign the task'
                resp_status = status.HTTP_400_BAD_REQUEST

        return Response(response_data, status=resp_status)



class ClientTaskTimelineViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ClientTaskTimelineSerializer

    def get_queryset(self):
        client_task_id = self.request.query_params.get('client_task', None)
        queryset = ClientTaskTimeline.objects.all().order_by('create_time')
        
        if client_task_id:
            try:
                client_task = ClientTask.objects.get(id=client_task_id)
                queryset = queryset.filter(client_task=client_task)
                return queryset
            except Exception as e:
                print(e)
                logger.exception("Exception in task timeline - Invalid task specified: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                raise serializers.ValidationError({"client": ["Invalid client task specified"]})
        else:
            raise serializers.ValidationError({"client": ["Please provide client task details"]})

    def list(self, request, *args, **kwargs):
        final_data = []
        queryset = self.filter_queryset(self.get_queryset())
        client_task_id = self.request.query_params.get('client_task', None)
        client_task = ClientTask.objects.get(id=client_task_id)
        group_list = TaskCollection.objects.all().order_by('group_order').values("task_group").distinct()
        next_task_grp=""
        for group in group_list:
            is_active=False
            q_set = queryset.filter(task_collection__task_group=group['task_group'])
                     
            if not client_task.administrator and client_task.ops and group['task_group'] == 'Ops Lead':
                is_active = True

            if not client_task.compliance and client_task.administrator and group['task_group'] == 'Administrator':
                is_active = True

            if not client_task.is_in_final and client_task.compliance and group['task_group'] == 'Compliance':
                is_active = True

            if client_task.is_in_final:
                if group['task_group'] == 'Final':
                    is_active = True
                # if group['task_group'] == 'Administrator':
                    # is_active = True
            
            
            # if group['task_group'] == 'Final':
            #     # group['task_group'] = 'Advisor'
            #     group['task_group'] = 'Administrator'
                    

            
            serializer = self.get_serializer(q_set, many=True)
            sub_data = {"group":group['task_group'],"is_active":"", "data":""}    
            sub_data["is_active"] = is_active    
            sub_data["data"] = serializer.data
            final_data.append(sub_data)

        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Client Task Timeline',
            "data": final_data
        }
        return Response(response_data, status=status.HTTP_200_OK)


class ClientTaskCommentViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ClientTaskCommentSerializer

    def get_queryset(self):
        task_id = self.request.query_params.get('task_id', None)
        queryset = ClientTaskComments.objects.all().order_by('-create_time')
           

        if task_id:
            try:
                queryset = queryset.filter(task__id=task_id)
            except Exception as e:
                print(e)
                logger.exception("Exception in task comment - Invalid task specified: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                raise serializers.ValidationError({"task": ["Invalid task specified"]})
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Client Task Comment List',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        response_data = {}
        error_msg = None
        user_id = request.data['commented_by']
        staff = Staff.objects.filter(user__id=user_id).first()
        task = ClientTask.objects.filter(id=request.data['task_id']).first()
        if not task:
            error_msg = "Invalid task specified"
        if task.task_status=='3':
            
            error_msg = "Task file already closed, cannot add comments"

        elif not error_msg:
            if staff:
                created = ClientTaskComments.objects.create(comment=request.data['comment'], task=task,
                                                            commented_by=staff)

                comment_list = ClientTaskComments.objects.filter(task__id=request.data['task_id']).order_by('-create_time')
                comments = [{'id': com.id, 'comment': com.comment,
                             'commented_by_user': com.commented_by.user.first_name + ' ' + com.commented_by.user.last_name,
                             'commented_by_user_type': com.commented_by.user.groups.name, 'create_time': com.create_time} for
                            com in comment_list]

                if created:
                    response_data['status_code'] = '201'
                    response_data['status'] = True
                    response_data['message'] = 'Comment added successfully'
                    response_data['data'] = comments
                    resp_status = status.HTTP_200_OK
        if error_msg:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = error_msg
            resp_status = status.HTTP_400_BAD_REQUEST

        return Response(response_data, status=resp_status)


class StaffViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = StaffSerializer


    def get_queryset(self):
        staff_type = self.request.query_params.get('type', None)
        company_id = self.request.query_params.get('company', None)
        staff_name  =  self.request.query_params.get('staff_name', None)
        is_advisor =  self.request.query_params.get('is_advisor', None)
        user = self.request.user
        queryset = Staff.objects.all()
        
        if staff_name is not None :
            first_name = staff_name.split()[0]
            last_name = " ".join(staff_name.split()[1:])
            queryset = queryset.filter(Q(user__first_name__icontains=first_name) | Q(user__last_name__icontains=first_name))
            
            if last_name:
                queryset = queryset.filter(user__last_name__icontains=last_name)

        if staff_type:
            group = Group.objects.filter(name=staff_type).first()
            advisor_group = Group.objects.filter(name='Advisor').first()
            if group and is_advisor is None:
                
                queryset = queryset.filter(user__groups=group)
            elif advisor_group and is_advisor is not None:
                staff_obj = Staff.objects.filter(user=user).first() 
                queryset = queryset.filter(user__groups=advisor_group, company=staff_obj.company)
                
            else:
                raise serializers.ValidationError({"type": ["Invalid staff type specified"]})
        
        if company_id:
            company = Company.objects.filter(id=company_id).first()
            if company:
                queryset = queryset.filter(company=company)
            else:
                raise serializers.ValidationError({"company": ["Invalid company specified"]})

        if is_advisor:
            queryset = queryset.order_by('user__username')
       
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        data = serializer.data
        count = offset = limit = None
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            count = self.paginator.count
            offset = self.paginator.offset
            limit = self.paginator.limit
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Staff List',
            "count": count,
            "offset": offset,
            "limit": limit,
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        response_data = {}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            group = Group.objects.get(name=request.data.pop('user_type'))
        except Exception as e:
            logger.exception("Exception in staff create - Invalid group: {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            print("Group Error : ", e)

        try:
            response = super().create(request)
            user = User.objects.get(id=response.data['user']['id'])
            user.is_staff = True
            user.save()
            # Adding user group
            group.user_set.add(user)

            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'Staff added successfully'

        except Exception as e:
            print(e)
            logger.exception("Exception in staff create : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Unable to add staff'

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '201':
            resp_status = status.HTTP_201_CREATED

        return Response(response_data, status=resp_status)



class InstrumentExtractedDataViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = InstrumentExtractedDataSerializer
    queryset = InstrumentExtractedData.objects.all()

    def get_queryset(self):
        queryset = InstrumentExtractedData.objects.all()
        instrumentdocument_id = self.request.query_params.get('instrumentdocument_id', None)
       

        if instrumentdocument_id is not None:
            queryset = queryset.filter(instrumentdocument_id=instrumentdocument_id)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data_val = serializer.data
        if data_val:
            response_data = {
                "status_code": "201",
                "status": True,
                "message": 'Extracted data fetched successfully',
                "data": data_val

            }
            resp_status = status.HTTP_200_OK
        else:
            response_data = {
                "status_code": "400",
                "status": False,
                "message": 'Data not extracted'

            }
            resp_status = status.HTTP_400_BAD_REQUEST

        return Response(response_data, resp_status)


class TaskEventViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = TaskEventSerializer

    def get_queryset(self):
        queryset = TaskEvents.objects.all()
        now = datetime.datetime.utcnow()
        client_id = self.request.query_params.get('client', None)
        client = Client.objects.filter(id=client_id).first()
        if client:
            queryset = queryset.filter(client_id=client_id, event__is_cancelled=False, event__event_start__gt=now).order_by('-id').first()
            print("queryset ",queryset)
        else:
            raise serializers.ValidationError({"client": ["Invalid Client Id"]})
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset)

        data = serializer.data

        if data['event']:
            response_data = {
                "status_code": "200",
                "status": True,
                "message": 'Next Scheduled Task Meeting',
                "data": data
            }
        else:
            response_data = {
                "status_code": "200",
                "status": True,
                "message": 'No Scheduled Task Meeting',
                "data": None
            }
        return Response(response_data, status=status.HTTP_200_OK)


class SaveExtractedKeywordsView(APIView):

    def get(self, request, *args, **kwargs):
        instrument_list = self.request.query_params.get('instrument_list', None)
        client_id = self.request.query_params.get('client_id', None)
        flag = False

        def replaceSpecial(spl, string):
            regex = re.compile(r'[' + spl + ']')
            return regex.sub("", string)

        def getFormatedVal(val):
            formatted_val = replaceSpecial("\x8c\n", val)
            return formatted_val.strip()

        if instrument_list:
            flag = True
            data = []
            updated_instrument_list = list(instrument_list.split(","))
            for instrument_id in updated_instrument_list:
                client_inst_info = ClientInstrumentInfo.objects.filter(id=instrument_id, is_active=True)
                for client_inst_obj in client_inst_info:
                    client_inst_id = client_inst_obj.id
                    data_dict = {}
                    data_dict['instrument_id'] = client_inst_obj.instrument.id
                    data_dict['client_instrument_id'] = client_inst_id
                    data_dict['instrument_name'] = client_inst_obj.instrument.instrument_name
                   
                    product_type_obj = client_inst_obj.instrument.product_type
                    if product_type_obj:
                        product_type = ProductType.objects.filter(id=product_type_obj.id).first()
                        data_dict['product_type'] = product_type.fund_type
                    else:
                        data_dict['product_type'] = None
                    provider_type = client_inst_obj
                    data_dict['provider_type'] = provider_type.get_provider_type_display()

                    extracted_data = ExtractedData.objects.filter(client_instrumentinfo=client_inst_id).order_by(
                        'master_keywords__masterlabel_order')
                    if extracted_data:
                        extr_data_list = []

                       
                        for extracted_data_obj in extracted_data:
                            extracted_description = ''
                            if extracted_data_obj.extracted_description and extracted_data_obj.extracted_description is not None and extracted_data_obj.extracted_description != '':

                                '''formatting description values to list or table type '''

                                invested_table = "<table>"
                                formatted_list_value = ""
                                table_flag = False
                                list_flag = False
                              
                                try:
                                    if isinstance(eval(extracted_data_obj.extracted_description), list):
                                        descriptionStringToJson = json.loads(extracted_data_obj.extracted_description)
                                        for Datas in descriptionStringToJson:

                                            if len(Datas) > 1:
                                                invested_table = invested_table + " <tr>"
                                                for cols in Datas:
                                                    invested_table = invested_table + " <td> " + cols + "</td>"
                                                    table_flag = True
                                                invested_table = invested_table + " </tr>"

                                            else:
                                                for cols in Datas:
                                                    formatted_value = getFormatedVal(cols)
                                                    if formatted_value and formatted_value is not None and formatted_value != '':
                                                        formatted_list_value = formatted_list_value + '<p>' + cols + '</p>'
                                                        list_flag = True
                                    else:
                                        extracted_description = '<p>' + extracted_data_obj.extracted_description + '</p>'
                                except Exception as e:
                                    logger.exception("Exception in Extracted data get : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                                    print("exception ...", str(e))
                                    extracted_description = '<p>' + extracted_data_obj.extracted_description + '</p>'
                                if list_flag:
                                   
                                    extracted_description = formatted_list_value
                                   
                                if table_flag:
                                    invested_table = invested_table + " </table>"
                                    extracted_description = invested_table
                                    
                                '''formatting ends here '''
                            #################
                            extr_data_list.append({"extracted_data_id": extracted_data_obj.id,
                                                   "master_keyword": extracted_data_obj.master_keywords.keyword,
                                                   "label_description":extracted_data_obj.master_keywords.label_description,
                                                   "extracted_value": extracted_data_obj.extracted_value,
                                                   "extracted_description": extracted_description,
                                                   "select_value" : extracted_data_obj.select_value,
                                                   "label": extracted_data_obj.master_keywords.keyword_slug,
                                                   "value_type": extracted_data_obj.master_keywords.value_type,
                                                   'masterlabel_order': extracted_data_obj.master_keywords.masterlabel_order})
                        data_dict['extracted_data'] = extr_data_list
                        data.append(data_dict)
                    else:
                        extr_data_list = []
                        data_dict['extracted_data'] = extr_data_list
                        data.append(data_dict)
        if client_id:
            flag = True
            data = []
            
            client_inst_info = ClientInstrumentInfo.objects.filter(client=client_id, is_recommended=True,parent__isnull=True, is_active=True).order_by(
                'provider_type', 'create_time')
            for client_inst_obj in client_inst_info:
                client_inst_id = client_inst_obj.id

                data_dict = {}
                data_dict['instrument_id'] = client_inst_obj.instrument.id
                data_dict['client_instrument_id'] = client_inst_id
                data_dict['instrument_name'] = client_inst_obj.instrument.instrument_name
               
                product_type_obj = client_inst_obj.instrument.product_type
                if product_type_obj:
                    product_type = ProductType.objects.filter(id=product_type_obj.id).first()
                    data_dict['product_type'] = product_type.fund_type
                else:
                    data_dict['product_type'] = None
                
                

                provider_type = client_inst_obj
                data_dict['provider_type'] = provider_type.get_provider_type_display()
                extracted_data = ExtractedData.objects.filter(client_instrumentinfo=client_inst_id).order_by(
                    'master_keywords__masterlabel_order')
                if extracted_data:
                    extr_data_list = []

                    for extracted_data_obj in extracted_data:

                        extracted_description = ''
                        if extracted_data_obj.extracted_description and extracted_data_obj.extracted_description is not None and extracted_data_obj.extracted_description != '':

                            '''formatting description values to list or table type '''

                           
                            invested_table = "<table>"
                            formatted_list_value = ""
                            table_flag = False
                            list_flag = False
                           
                            try:
                                
                                if isinstance(eval(extracted_data_obj.extracted_description), list):
                                    descriptionStringToJson = json.loads(extracted_data_obj.extracted_description)
                                    for Datas in descriptionStringToJson:

                                        if len(Datas) > 1:
                                            invested_table = invested_table + " <tr>"
                                            for cols in Datas:
                                                invested_table = invested_table + " <td> " + cols + "</td>"
                                                table_flag = True
                                            invested_table = invested_table + " </tr>"

                                        else:
                                            for cols in Datas:
                                                formatted_value = getFormatedVal(cols)
                                                if formatted_value and formatted_value is not None and formatted_value != '':
                                                    formatted_list_value = formatted_list_value + '<p>' + cols + '</p>'
                                                    list_flag = True
                                else:
                                    extracted_description = '<p>' + extracted_data_obj.extracted_description + '</p>'
                            except Exception as e:
                                logger.exception("Exception in Extracted data get : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                                print("exception ...", str(e))
                                extracted_description = '<p>' + extracted_data_obj.extracted_description + '</p>'
                            if list_flag:
                                
                                extracted_description = formatted_list_value
                               
                            if table_flag:
                                invested_table = invested_table + " </table>"
                                extracted_description = invested_table
                                
                            '''formatting ends here '''
                        
                        keyword_slug = extracted_data_obj.master_keywords.keyword_slug
                        if keyword_slug in ['tax_free_cash','gurantees']:
                            if data_dict['product_type'] in  ["Pension"]:
                                mandatory_for =["Pension"]
                            else:
                                mandatory_for=[]
                        else:
                            mandatory_for=[]
                        
                        ##################
                        extr_data_list.append({"master_keyword": extracted_data_obj.master_keywords.keyword,
                                               "label_description": extracted_data_obj.master_keywords.label_description,
                                               "extracted_value": extracted_data_obj.extracted_value,
                                               "extracted_description": extracted_description,
                                               "select_value" : extracted_data_obj.select_value,
                                               "label": extracted_data_obj.master_keywords.keyword_slug,
                                               "value_type": extracted_data_obj.master_keywords.value_type,
                                               'masterlabel_order': extracted_data_obj.master_keywords.masterlabel_order,'mandatory_for':mandatory_for})
                    data_dict['extracted_data'] = extr_data_list
                    data.append(data_dict)

                else:
                    data_dict['extracted_data'] = []
                    data.append(data_dict)

        if flag:
            response_data = {
                "status_code": "200",
                "status": True,
                "message": 'Extracted data  fetched',
                "data": data
            }
        else:
            response_data = {
                "status_code": "400",
                "status": False,
                "message": 'Not found'
            }

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)

    def post(self, request, *args, **kwargs):
        update_flag = self.request.query_params.get('update', None)
        data = request.data
        
        draftchecklist = DraftCheckList.objects.filter(id=48).first()
        
        if update_flag:
            client_instrument_info = ClientInstrumentInfo.objects.filter(id=data['client_instrument_id'], data_extraction_status='2', is_active=True)
        else:
            client_instrument_info = ClientInstrumentInfo.objects.filter(id=data['client_instrument_id'], data_extraction_status='1', is_active=True)
        print(client_instrument_info, ' ---------------------------------- ')
        
        if client_instrument_info:
            try:
                client_instrument = ClientInstrumentInfo.objects.filter(id=data['client_instrument_id'], is_active=True).first()
                if client_instrument:
                   
                    for slug, value in data['extracted_keywords'].items():
                        
                        extracted_mapping = ExtractionKeywordMapping.objects.filter(master_keywords__keyword_slug=slug, instrument=client_instrument.instrument).first()
                        if extracted_mapping:
                            if update_flag:
                                ext_obj = ExtractedData.objects.filter(client_instrumentinfo=client_instrument, master_keywords=extracted_mapping.master_keywords, extraction_keyword=extracted_mapping).first()
                               
                                if value['value'] is not None:
                                    ext_obj.extracted_value = value['value']
                                ext_obj.select_value = value['choice_value']
                                ext_obj.save()
                                try:#tfc checklist update
                                    if extracted_mapping.master_keywords.keyword_slug=='tax_free_cash':
                                        result='amber'
                                        if ext_obj.select_value:
                                            if ext_obj.select_value.lower() == 'yes':
                                                result = 'amber'
                                            if ext_obj.select_value.lower() == 'no':
                                                result = 'passed'
                                        update_checklist(client_instrument.client, [48], result,client_instrument=client_instrument)
                                except Exception as e:
                                    logger.exception("Exception in checklist update in Extracted data save : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                                    print("checklist not updated")
                            else:
                                if value['is_value_based']:
                                    ExtractedData.objects.create(client_instrumentinfo=client_instrument, master_keywords=extracted_mapping.master_keywords, extraction_keyword=extracted_mapping, extracted_value=value['val'])
                                else:
                                    ExtractedData.objects.create(client_instrumentinfo=client_instrument, master_keywords=extracted_mapping.master_keywords, extraction_keyword=extracted_mapping, extracted_description=value['val'])
                        else:
                            if update_flag:
                                
                                master_key = MasterKeywords.objects.filter(keyword_slug=slug).first()
                                ext_obj = ExtractedData.objects.filter(client_instrumentinfo=client_instrument, master_keywords=master_key).first()
                               
                                if value['value'] is not None:
                                    ext_obj.extracted_value = value['value']
                                ext_obj.select_value = value['choice_value']
                                ext_obj.save()
                                try:###tfc checklist update
                                    if master_key.keyword_slug=='tax_free_cash':
                                        result = 'amber'
                                        if ext_obj.select_value:
                                            if ext_obj.select_value.lower() == 'yes':
                                                result = 'amber'
                                            if ext_obj.select_value.lower() == 'no':
                                                result = 'passed'
                                        update_checklist(client_instrument.client, [48], result,client_instrument=client_instrument)


                                except Exception as e:
                                    #logger.exception("Exception in checklist update in Extracted data save : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})
                                    print("checklist not updated")
                            else:
                                master_key = MasterKeywords.objects.filter(keyword_slug=slug).first()
                                ExtractedData.objects.create(client_instrumentinfo=client_instrument, master_keywords=master_key, extracted_value=value['val'])


                ClientInstrumentInfo.objects.filter(id=data['client_instrument_id'],is_active=True).update(data_extraction_status='2')
                reminder_status = StatusCollection.objects.get(status='1.32')  # Data extraction pending
               

                for rem in Reminder.objects.filter(client_instrument=client_instrument, status=reminder_status):
                    rem.is_deleted = True
                    rem.save()


                status_collection = StatusCollection.objects.get(status='1.31')  # Data extraction completed
               
                if 'document_path' in data:
                    doc_path = data['document_path']
                    doc_obj = Document.objects.filter(doc__contains=doc_path.split('/media/')[-1]).first()
                    if doc_obj:
                        add_activity_flow(action_performed_by=doc_obj.uploaded_by, client=client_instrument.client, status=status_collection, client_instrument=client_instrument)
                    else:
                        add_activity_flow(action_performed_by=client_instrument.pdf_data.uploaded_by, client=client_instrument.client, status=status_collection, client_instrument=client_instrument)
                else:
                    add_activity_flow(action_performed_by=client_instrument.pdf_data.uploaded_by, client=client_instrument.client, status=status_collection, client_instrument=client_instrument)


                response_data = {}
                response_data['status_code'] = '200'
                response_data['status'] = True
                response_data['message'] = 'Extracted Data saved to DB'
                return Response(response_data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.exception("Exception in Extracted data save : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                print("\n\n Exception is saving extracted values. The error is : ", e, "\n\n\n")
                response_data = {}
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'Could not save extracted data'
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        else:
            print("\n\n Error is saving extracted values as Client Instrument Document not found \n\n\n")
            response_data = {}
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Client Instrument Document not found'
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)




class FundRiskViewSet(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request, *args, **kwargs):

        fund_risk_obj = FundRisk.objects.all()
        function_obj = Function.objects.all()
        data = []
        for fund in fund_risk_obj:
            name = fund.get_fund_name_display()
            data.append({"id": fund.id, "name": name, "type": "FundRisk"})

        for function in function_obj:
            name = function.get_function_type_display()
            data.append({"id": function.id, "name": name, "type": "Function"})

        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Fund/Function Details Fetched',
            "data": data
        }

        return Response(response_data, status=status.HTTP_200_OK)


class FeeRuleConfigViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = FeeRuleConfigSerializer

    def get_queryset(self):
        queryset = FeeRuleConfig.objects.all()
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Fee Details Fetched',
            "data": data
        }

        return Response(response_data, status=status.HTTP_200_OK)


class ReasonViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ReasonSerializer

    def get_queryset(self):
        
        queryset = Reason.objects.all()
        function_list = self.request.query_params.getlist('function', None)
        if function_list:
            function_list = function_list[0].split(',')

        if function_list:  
            queryset = queryset.filter(function_id__in=function_list).order_by('function')

        prod_type = self.request.query_params.get('product_type')
        if prod_type:
            
            queryset = queryset.filter(product_type__fund_type=prod_type)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Reasons Fetched',
            # "data": grouped_data
            "data": data
        }

        return Response(response_data, status=status.HTTP_200_OK)


class DraftReccomendationViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = DraftReccomendationSerializer
    queryset = DraftReccomendation.objects.all()

    def get_queryset(self):
        queryset = DraftReccomendation.objects.all()
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = DraftReccomendation.objects.filter(client=client_id)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'DraftReccomendation Details Fetched',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        serializer.is_valid(raise_exception=True)
        try:
            response = self.perform_update(serializer)
            status_collection = StatusCollection.objects.get(status='1.38')  
            add_activity_flow(client=instance.client, status=status_collection, action_performed_by=request.user)

        except Exception as e:
            logger.exception("Exception in draft recommendation update : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '400'
            response_data['status'] = True
            response_data['message'] = 'Error in adding advisor comments'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'You have succesfully added advisor comments'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)

    


class InstrumentsRecomendedViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = InstrumentsRecomendedSerializer
    queryset = InstrumentsRecomended.objects.all()

    def get_queryset(self):
        queryset = InstrumentsRecomended.objects.all()
        client_id = self.request.query_params.get('client_id')
        task_id = self.request.query_params.get('task')
        if task_id: #for showing only task related instruments. If task is completed, get all intruments based on task_id else get all active instruments
            task_det = ClientTask.objects.filter(id=task_id).first()
            if task_det:
                if task_det.task_status == '3':
                   queryset=queryset.filter(task=task_det)
                else:
                   queryset=queryset.filter(task__isnull=True, is_active=True)
        else:
           queryset=queryset.filter(is_active=True)
        if client_id:
            queryset = queryset.filter(client_instrumentinfo__client=client_id).order_by('client_instrumentinfo__provider_type', 'id')

        if client_id and task_id:
           
            map_transfer_ids = queryset.values_list('map_transfer_from')
            transfer_ids = [id[0] for id in map_transfer_ids if id[0] ]
            queryset = queryset.exclude(id__in=transfer_ids)

        return queryset

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'InstrumentsRecomended Details Fetched',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        try:
            data = super().retrieve(request, *args, **kwargs).data
            instance = self.get_object()
        except Exception as e:
            print(str(e))
            logger.exception("Exception in instruments recommended retrieve : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                

        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Instrument Recommended Details',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def perform_update(self, serializer,old_instances):
        print(old_instances)
        instance=serializer.save()
        ############draft update checklists##########
        client=instance.client_instrumentinfo.client
        draftchecklist = DraftCheckList.objects.filter(category_name__in=['7', '13','10'])  # draft update checklists#instrument recommended PUT
        for checklist in draftchecklist:
            if checklist.category_name=='13':
                recommended_producttypes = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,function_list__function_type='1',is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
            else:
                recommended_producttypes = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
            all_products = True if not (list(checklist.product_type.all())) else False
            checklist_product_types = list(checklist.product_type.all().values_list('fund_type', flat=True))
            producttype_exist = any(item in checklist_product_types for item in list(recommended_producttypes))


            if producttype_exist or all_products:
                advisor=Staff.objects.filter(user=instance.client_instrumentinfo.client.created_by)
                if checklist.id == 48:
                    transfer_instruments = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,function_list__function_type='1',client_instrumentinfo__provider_type='1',client_instrumentinfo__instrument__product_type__fund_type__in=checklist_product_types,
                                                                                is_active=True)
                    client_instrument_list=[]
                    for instrument in transfer_instruments:
                        client_instrument_list.append(instrument.client_instrumentinfo)
                        ext_obj = ExtractedData.objects.filter(client_instrumentinfo=instrument.client_instrumentinfo,
                                                               master_keywords__keyword_slug='tax_free_cash').first()
                        if ext_obj.select_value:
                            if ext_obj.select_value.lower() == 'yes':
                                update_or_create_checklist(client, checklist.id,advisor,client_instrument=instrument.client_instrumentinfo,result='amber')

                            if ext_obj.select_value.lower() == 'no':
                                update_or_create_checklist(client, checklist.id, advisor,client_instrument=instrument.client_instrumentinfo,result='passed')
                        else:
                            update_or_create_checklist(client, checklist.id, advisor,client_instrument=instrument.client_instrumentinfo,result='amber')
                    ClientCheckList.objects.filter(draft_checklist=checklist, client=client).exclude(client_instrument__in=client_instrument_list).update(is_deleted=True)
                elif checklist.id==22:
                  
                    if ((list(instance.function_list.all())[0]).function_type=='1') and (instance.client_instrumentinfo.instrument.product_type.fund_type in checklist_product_types):
                        age = client.age
                        retire_age = client.retire_age
                        advisor_decency_charge=None
                        print(advisor_decency_charge)
                        if age and retire_age:
                            diff = retire_age - age
                            if diff<=0:
                                advisor_decency_charge=0.3
                            elif diff <= 10:
                                advisor_decency_charge = math.ceil(diff) * 0.3
                            elif diff > 10:
                                advisor_decency_charge = 4
                        print(advisor_decency_charge)
                        check_advisor_decency(client,instance,advisor_decency_charge=advisor_decency_charge)
                    else:
                        delete_checklist(client, checklist, instrument_recommended=instance,client_instrument=instance.client_instrumentinfo)

                else:
                    update_or_create_checklist(client, checklist.id, advisor)
            else:
                delete_checklist(client, checklist)
        ###################illustration checklist#####################################
        try:
            print(0)
            released_transfers = [item for item in old_instances if item not in instance.map_transfer_from.all()]
            print(released_transfers)
           
            if instance.map_transfer_from.all():
                print(1)
               
                client_instrumentlist = []
                for instrument in instance.map_transfer_from.all():
                    if instrument.client_instrumentinfo not in client_instrumentlist:
                        client_instrumentlist.append(instrument.client_instrumentinfo)
                print("before list")
                if client_instrumentlist:
                    print(client_instrumentlist)
                    client_checklists=ClientCheckList.objects.filter(client=instance.client_instrumentinfo.client, client_instrument__in=client_instrumentlist)
                    print(client_checklists)
                    for checklist in client_checklists:
                        if checklist.draft_checklist.id==22 or checklist.draft_checklist.category_name=='9' or checklist.draft_checklist.category_name=='14':
                            delete_checklist(instance.client_instrumentinfo.client, checklist=checklist.draft_checklist,
                                         client_instrument=checklist.client_instrument)
                        #delete_checklist(instance.client_instrumentinfo.client, checklist=checklist,
                        #                 client_instrument=client_instrumentlist)

            if released_transfers:
                print("inside released transfers")
                #if old_instances:
                print("old instance have mapfrom")
                for instrument in released_transfers:
                    print("inside ")
                    ########decency checklist#####
                    try:
                        dchecklist = DraftCheckList.objects.filter(id=22).first()
                        checklist_product_type = list(dchecklist.product_type.all().values_list('fund_type', flat=True))
                        if ((list(instrument.function_list.all())[0]).function_type == '1') and (instrument.client_instrumentinfo.instrument.product_type.fund_type in checklist_product_type):
                            age = client.age
                            retire_age = client.retire_age
                            advisor_decency_charge = None
                            print(advisor_decency_charge)
                            if age and retire_age:
                                diff = retire_age - age
                                if diff <= 0:
                                    advisor_decency_charge = 0.3
                                elif diff <= 10:
                                    advisor_decency_charge = math.ceil(diff) * 0.3
                                elif diff > 10:
                                    advisor_decency_charge = 4
                            print(advisor_decency_charge)
                            check_advisor_decency(client, instrument, advisor_decency_charge=advisor_decency_charge)
                    except Exception as e:
                        print("error in transfer release decency",e)
                        # else:
                        #    remove_checklists = delete_checklist(client, checklist, instrument_recommended=instance,
                        #                                         client_instrument=instance.client_instrumentinfo)
                        ####illustration & appsummary checklist####
                    if instrument.client_instrumentinfo.illustration:
                        illustration_appsummary_checklists(instrument.client_instrumentinfo,'16')
                    if instrument.client_instrumentinfo.app_summary:
                        illustration_appsummary_checklists(instrument.client_instrumentinfo,'13')

            '''
            providerid=instance.client_instrumentinfo.provider.id
            print(3)
            if providerid in [10,12]:#for aegon and fidelity only
                product_type=instance.client_instrumentinfo.instrument.product_type
                c_instrument=ClientInstrumentInfo.objects.filter(client=instance.client_instrumentinfo.client,provider__id=providerid,instrument__product_type=product_type,illustration__isnull=False,is_recommended=True,is_active=True).order_by('-illustration__id').first()
                
                if c_instrument:
                    print(4)
                    Illustration_checklist_run(c_instrument)'''
        except Exception as e:
            print("error in illustration checklist update"+str(e))
            logger.exception("Exception in checklist update in instruments recommended create : {} - {}".format(str(e), self.request.path), extra={'status_code': 400, 'request': self.request})                



    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        serializer.is_valid(raise_exception=True)
        try:
            print('before doing db update')

            response = self.perform_update(serializer,list(instance.map_transfer_from.all()))
            status_collection = StatusCollection.objects.get(status='1.72')  
            add_activity_flow(action_performed_by=request.user, client=instance.client_instrumentinfo.client, status=status_collection, client_instrument=instance.client_instrumentinfo)
           

            print("serilaizer data ",serializer.data)
        except Exception as e:
            print(e)
            logger.exception("Exception in instruments recommended update : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '400'
            response_data['status'] = True
            response_data['message'] = 'Error in updating product details'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'You have succesfully updated product details'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)

    def create(self, request, *args, **kwargs):
        response_data = {}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            advisor = request.data['advisor_id']
            advisor = Staff.objects.filter(user__id=advisor).first()
           
            request.data['advisor'] = advisor.id
            request.data.pop('advisor_id')

            client = None
            parent_client_instrument = request.data.get('client_instrumentinfo', None)
            if parent_client_instrument:   #clone
                response_data = {}
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                try:
                   
                    parent_client_instrumentinfo=ClientInstrumentInfo.objects.filter(id=parent_client_instrument, is_active=True).first()
                    client_instrumentinfo = ClientInstrumentInfo.objects.filter(id=parent_client_instrument, is_active=True).first()
                    if client_instrumentinfo:
                        client_instrumentinfo.id=None
                        client_instrumentinfo.parent = parent_client_instrumentinfo
                        client_instrumentinfo.fund_research = None
                        client_instrumentinfo.critical_yield = None
                        client_instrumentinfo.illustration = None
                        client_instrumentinfo.weighted_average_calculator = None
                        client_instrumentinfo.app_summary = None
                        client_instrumentinfo.save()
                    
                    print(client_instrumentinfo.id)
                    request.data['client_instrumentinfo'] = client_instrumentinfo.id
                    response = super().create(request)
                except Exception as e:
                    logger.exception("Exception in instruments recommended create : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                    print(e)

               
                client = client_instrumentinfo.client
                staff_user=Staff.objects.filter(user=client.created_by).first()
                instruments_recomended_obj = InstrumentsRecomended.objects.filter(advisor=advisor, client_instrumentinfo=client_instrumentinfo, is_active=True).last()
                print(instruments_recomended_obj)
                draft_recommendation_obj = DraftReccomendation.objects.filter(advisor=advisor, client=client, is_active=True).last()
                
                draft_recommendation_obj.instrument_recommended.add(instruments_recomended_obj)
                draft_recommendation_obj.save()
                try:
                    draftchecklist = DraftCheckList.objects.filter(category_name__in=['7','13'])  # transfer draft update checklists#instrument recommended PUT
                    for checklist in draftchecklist:
                        if checklist.category_name == '13':
                            recommended_producttypes = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client, function_list__function_type='1',is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
                        else:
                            recommended_producttypes = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client, is_active=True).values_list('client_instrumentinfo__instrument__product_type__fund_type', flat=True)
                        all_products = True if not (list(checklist.product_type.all())) else False
                        checklist_product_types = list(checklist.product_type.all().values_list('fund_type', flat=True))
                        producttype_exist = any(item in checklist_product_types for item in list(recommended_producttypes))

                        if producttype_exist or all_products:
                            if checklist.id == 22:
                               
                                if ((list(instruments_recomended_obj.function_list.all())[0]).function_type == '1') and (instruments_recomended_obj.client_instrumentinfo.instrument.product_type.fund_type in checklist_product_types):
                                    age = client.age
                                    retire_age = client.retire_age
                                    advisor_decency_charge = None
                                    print(advisor_decency_charge)
                                    if age and retire_age:
                                        diff = retire_age - age
                                        if diff <= 0:
                                            advisor_decency_charge = 0.3
                                        elif diff <= 10:
                                            advisor_decency_charge = math.ceil(diff) * 0.3
                                        elif diff > 10:
                                            advisor_decency_charge = 4
                               
                                    check_advisor_decency(client, instruments_recomended_obj,advisor_decency_charge=advisor_decency_charge)
                                else:
                                    delete_checklist(client, checklist,instrument_recommended=instruments_recomended_obj,client_instrument=instruments_recomended_obj.client_instrumentinfo)
                            elif checklist.id == 48:#exclude tfc checklist on instrument clone
                                pass
                            else:
                                update_or_create_checklist(client, checklist.id, staff_user)
                        else:
                            delete_checklist(client, checklist)
                except:
                    logger.exception("Exception in checklist update in instruments recommended create : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                

                ###adding illustration checklists
                try:
                    client_instrumentlist = []
                    draftchecklists = DraftCheckList.objects.filter(category_name=9)
                    if instruments_recomended_obj.map_transfer_from.all():
                       
                        for instrument in instruments_recomended_obj.map_transfer_from.all():
                            if instrument.client_instrumentinfo not in client_instrumentlist:
                                client_instrumentlist.append(instrument.client_instrumentinfo)
                    if client_instrumentlist:
                      
                        for checklist in draftchecklists:
                            delete_checklist(instruments_recomended_obj.client_instrumentinfo.client, checklist=checklist,client_instrument=client_instrumentlist)
                    providerid = instruments_recomended_obj.client_instrumentinfo.provider.id
                    if providerid in [10, 12]:  # for aegon and fidelity only
                        checklist = DraftCheckList.objects.filter(id=30).first()  # Is there sufficient information to justify the advice ?
                        staffuser = Staff.objects.filter(user=instruments_recomended_obj.client_instrumentinfo.client.created_by).first()
                        update_or_create_checklist(instruments_recomended_obj.client_instrumentinfo.client, checklist.id, staffuser)
                       
                except Exception as e:
                    print("error in adding illustration checklist for new clone")
                    logger.exception("Exception in adding illustration checklist for new clone : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})

                comment = client_instrumentinfo.instrument.instrument_name
                activity_flow_update_status = StatusCollection.objects.get(status='1.80')
                add_activity_flow(action_performed_by=self.request.user, client=client, status=activity_flow_update_status, comment=comment)
               

            else:
                print(1)
                instrument_id_list = request.data.get('instrument_id', None)
                client = request.data.get('client_id', None)
                fund_object_value = None
                if instrument_id_list and client:
                    survey_data = SurveyFormData.objects.filter(client_id=client, category_id=27).last()
                    if survey_data and survey_data.form_data[0]['subcategory_data'][0]['answer']:
                       
                        fund_val = None
                        fund_risk = survey_data.form_data[0]['subcategory_data'][0]['answer']
                        fund_obj = FundRisk.objects.all()
                        for fund_res in fund_obj:
                            risk = fund_res.get_fund_name_display()
                            if risk == fund_risk:
                                fund_val = fund_res.fund_name
                                fund_object_value = FundRisk.objects.filter(fund_name=fund_val).first()
                    
                    client_ins_map_from = InstrumentsRecomended.objects.filter(client_instrumentinfo__client__id=client, is_active=True, advisor=advisor).values_list('map_transfer_from')
                    exclude_list = [ id[0] for id in client_ins_map_from if id[0] ]

                    client_ins_map_to = InstrumentsRecomended.objects.filter(client_instrumentinfo__client__id=client, is_active=True, advisor=advisor, map_transfer_from__isnull=False).distinct()
                    for to_ins in client_ins_map_to:
                        exclude_list.append(to_ins.id)

                    for instrument_id in instrument_id_list:
                        print(2)
                        instr_present_in_map_from = False    
                        instrument_info_id = ClientInstrumentInfo.objects.filter(id=instrument_id, is_active=True).first()
                        extracted_data_obj = ExtractedData.objects.filter(client_instrumentinfo=instrument_info_id)

                        transfer_value = None
                        if extracted_data_obj:

                            for ext_data in extracted_data_obj:



                                if ext_data.master_keywords.keyword_slug == 'transfer_value':
                                    try:
                                        value = (ext_data.extracted_value.replace(',', '')).replace('£', '')
                                        transfer_value = float(value)
                                    except Exception as e:
                                        print('Cannot convert transfer_value to float type. So setting transfer_value as None....!!')
                                        transfer_value = None

                        instruments_recomended = InstrumentsRecomended.objects.filter(client_instrumentinfo=instrument_info_id, is_active=True).first()
                       
                        if transfer_value == '':
                            transfer_value = None

                        if not instruments_recomended:
                           
                            dfm_fee = FeeRuleConfig.objects.filter(charge_name='DFM fee').first()
                            ongoing_fee = FeeRuleConfig.objects.filter(charge_name='Ongoing fee').first()
                            initial_fee = FeeRuleConfig.objects.filter(charge_name='Initial fee').first()

                            if ongoing_fee and dfm_fee and initial_fee:
                                instruments_recomended_obj = InstrumentsRecomended.objects.create(advisor=advisor, client_instrumentinfo=instrument_info_id, fund_risk=fund_object_value, amount=transfer_value,\
                                                                dfm_fee=dfm_fee.default_value, initial_fee=initial_fee.default_value, ongoing_fee=ongoing_fee.default_value)
                            else:
                                instruments_recomended_obj = InstrumentsRecomended.objects.create(advisor=advisor, client_instrumentinfo=instrument_info_id, fund_risk=fund_object_value, amount=transfer_value)
                            
                            status_collection = StatusCollection.objects.filter(status='1.71').first()
                            add_activity_flow(action_performed_by=self.request.user, client=instrument_info_id.client, status=status_collection, client_instrument=instrument_info_id)
                            # add_activity_flow(action_performed_by=instrument_info_id.created_by, client=instrument_info_id.client, status=status_collection, client_instrument=instrument_info_id)
                            
                        else:
                           
                            if transfer_value is not None and instruments_recomended.id not in exclude_list: 
                                instruments_recomended.amount = transfer_value
                            if fund_object_value is not None:
                                instruments_recomended.fund_risk = fund_object_value
                            instruments_recomended.save()
                    client = instrument_info_id.client

                    recomended_instruments_obj = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client, is_active=True)
                    for recomended_instruments in recomended_instruments_obj:
                        client_instrumentinfo = recomended_instruments.client_instrumentinfo
                        if (client_instrumentinfo.id) in instrument_id_list or (client_instrumentinfo.parent.id in instrument_id_list):
                            pass
                        else:
                            recomended_instruments.is_deleted = True
                            recomended_instruments.save()


                instr_count = len(instrument_id_list)
                client_profile_completion(client=client,advisor=advisor,phase='pre-contract',percentage=20,sign='positive',instr_count=instr_count,obj='instrument-recomended') 
                
                
                # chek draft_recommendation obj is exist for current clientinstrument_id_list  
                instruments_recommended = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client, advisor=advisor, is_active=True)
                instruments_recommended_list = []
                for instruments_recommended_obj in instruments_recommended:
                    instruments_recommended_list.append(instruments_recommended_obj.id)
                draft_recommendation_check = DraftReccomendation.objects.filter(advisor=advisor, client=client, is_active=True).first()
                if draft_recommendation_check:
                    print(11)
                    draft_recommendation_check.instrument_recommended.set(instruments_recommended_list)
                    draft_recommendation_check.save()
                else:
                    print(12)
                    draft_recommendation_obj = DraftReccomendation.objects.create(advisor=advisor, client=client)
                    draft_recommendation_obj.instrument_recommended.set(instruments_recommended_list)
                    draft_recommendation_obj.save()

                
        except Exception as e:
            print(e)
            logger.exception("Exception in instrument recommended add : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                

            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Invalid data'
        else:
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'You have successfully added the InstrumentsRecomended details'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '201':
            resp_status = status.HTTP_201_CREATED

        return Response(response_data, status=resp_status)

    def destroy(self, request, pk=None):
        response_data = {}
        record_to_delete = InstrumentsRecomended.objects.filter(id=pk).first()

        if record_to_delete:
            record_to_delete.is_deleted = True
            record_to_delete.save()
            remove_ilustration_checklist(record_to_delete)
            #delete corresponding clientinstrument also
            ClientInstrumentInfo.objects.filter(id=record_to_delete.client_instrumentinfo.id).update(is_deleted=True)


            client_profile_completion(client=record_to_delete.client_instrumentinfo.client,phase='pre-contract',percentage=20,sign='negative',obj='instrument-recomended') 
           

            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'Recommended Instrument Deleted Successfully'

        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Corresponding Record Not Found'

        if response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        elif response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST

        return Response(response_data, status=resp_status)


class ClientRecommendationNotificationViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ClientRecommendationNotificationSerializer
    queryset = ClientRecommendationNotification.objects.all()

    def get_queryset(self):
        queryset = ClientRecommendationNotification.objects.all()
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = ClientRecommendationNotification.objects.filter(client=client_id)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'DraftNotification Details Fetched',
            "data": data
        }

        return Response(response_data, status=status.HTTP_200_OK)

    def perform_update(self,serializer):
        instance=serializer.save()
        return instance

    def update(self, request, *args, **kwargs):

        instance = self.get_object()
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        serializer.is_valid(raise_exception=True)
        try:
            response = self.perform_update(serializer)

        except Exception as e:
            logger.exception("Exception in updating DraftNotification Details : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '400'
            response_data['status'] = True
            response_data['message'] = 'Error in updating DraftNotification Details'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'You have succesfully updated DraftNotification Details'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


   
class ExtractedDataViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ExtractedDataSerializer

    def get_queryset(self):
        queryset = ExtractedData.objects.all()
        client_instrument_id = self.request.query_params.get('client_instrument', None)
        client_instrument = ClientInstrumentInfo.objects.filter(id=client_instrument_id, is_active=True).first()
        if client_instrument:
            queryset = queryset.filter(client_instrumentinfo=client_instrument)
        else:
            raise serializers.ValidationError({"client_instrument": ["Invalid Client Instrument Id"]})
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Extracted Data list',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)


class ClientChecklistViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ClientCheckListSerializer

    def get_queryset(self):
        task_obj=None
        queryset = ClientCheckList.objects.all()
        print(queryset.count(), ' c1')
        client_id = self.request.query_params.get('client_id', None)
        task_id = self.request.query_params.get('task_id', None)
        
        is_administrator = self.request.query_params.get('is_administrator', None)
        is_compliance = self.request.query_params.get('is_compliance', None)
        is_ops=self.request.query_params.get('is_ops', None)

        if task_id:
            task_obj = ClientTask.objects.filter(id=task_id).first()
            if task_obj and task_obj.task_status == '3':
                queryset = ClientCheckListArchive.objects.filter(task=task_obj)
        print(queryset.count(), ' c2')

        client = Client.objects.filter(id=client_id).first()
        print(client)
        if not client:
            raise serializers.ValidationError({"client": ["Invalid Client Id"]})

        queryset = queryset.filter(client=client)
        user_company = Staff.objects.filter(user=self.request.user).values_list('company')  # Need to update here for compliance/administrator requests
        print("HERE IN UPDATE")
        if client and not is_administrator and not is_compliance: #advisor checklist
            if task_obj:
                staff_user = task_obj.advisor
            else:
                group = self.request.user.groups.first()
                
                staff_user = Staff.objects.filter(user__groups__name='Advisor', user=client.created_by).first()

            queryset = queryset.filter(user=staff_user, owner_group='Advisor')


        elif client and is_administrator and task_obj and task_obj.administrator: #admin checklist
            queryset = queryset.filter(administrator=task_obj.administrator, owner_group='Compliance') #Admin checklist and Compliance checklist are same
        elif client and is_compliance and task_obj: #compliance checklist
           
            queryset = queryset.filter(owner_group='Compliance')
       
        print("HERE IN UPDATE 3")
        queryset = queryset.order_by('id')

        print(queryset)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Client check list fetched',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):

        instance = self.get_object()
        previous_colourcode=instance.colour_code
        is_administrator = self.request.query_params.get('is_administrator', None)
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        serializer.is_valid(raise_exception=True)
        try:
            response = self.perform_update(serializer)
            print("AFTER UPDATE 1")
            print(type(self.request.user))
            updated_color_code = request.data.get('colour_code')

            advisor_obj = Staff.objects.filter(user= self.request.user,user__groups__name='Advisor').first() 
            if advisor_obj:
                if updated_color_code.lower() =='green':
                    activity_flow_update_status = StatusCollection.objects.get(status='1.78')
                if updated_color_code.lower() =='red':
                    activity_flow_update_status = StatusCollection.objects.get(status='1.79')
                comment = instance.draft_checklist.checklist_names
                add_activity_flow(action_performed_by=self.request.user, client=instance.client, status=activity_flow_update_status, comment=comment)
            
            ##verfication flag reset scenario
            if not(previous_colourcode==instance.colour_code) and not(instance.colour_code=='Green'):
                clienttask = ClientTask.objects.filter(client=instance.client).exclude(task_status='3').last()
                if clienttask:
                    if instance.draft_checklist.checklist_group == 'Advisor':
                        if clienttask.is_advisor_checklist_verified:
                            clienttask.is_advisor_checklist_verified = False
                    elif instance.draft_checklist.checklist_group == 'Compliance':
                        if clienttask.is_admin_checklist_verified and is_administrator:
                            
                            clienttask.is_admin_checklist_verified = False
                        if clienttask.is_compliance_checklist_verified:
                            clienttask.is_compliance_checklist_verified = False
                    clienttask.save()
            ######################################
            print("AFTER UPDATE 2")

        except Exception as e:
            logger.exception("Exception in updating checklist : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Error in updating checklist'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'You have succesfully updated client checklist'
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class CheckConnectionViewSet(APIView):

    def get(self, request, format=None):
        response_data = {
            'status_code': "200",
            'status': True,
            'message': "Ping Success ",
        }
        return Response(response_data)


class AdvisorProfileViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = AdvisorProfileSerializer
    

    def get_queryset(self):
        queryset = Staff.objects.all()
        user_id = self.request.query_params.get('user_id', None)
        user = User.objects.filter(id=user_id).first()
        if user:
            queryset = queryset.filter(user=user)
        else:
            raise serializers.ValidationError({"user": ["Invalid User Id"]})
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data[0]
        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Advisor details fetched',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)



    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        response_data = {}
        serializer = self.get_serializer(instance, data=request.data, partial=True)
      
        serializer.is_valid(raise_exception=True)
        

        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        email = request.data.get('email')
        company_id = request.data.get('company_id')
        phone_number = request.data.get('phone_number')
        user_id = self.request.query_params.get('user_id', None)
        
        error_list = {}
        if not email:
            error_list['email'] = ["Email cannot be blank"]
        if not first_name:
            error_list['first_name'] = ["First name cannot be blank"]
        if not last_name:
            error_list['last_name'] = ["Last name cannot be blank"]
        if error_list:
            raise serializers.ValidationError(error_list)

        try:
            user = User.objects.exclude(id=user_id).get(email=email)
            raise serializers.ValidationError({"email": ["A user with that email already exists"]})

        except User.DoesNotExist:
            User.objects.filter(id=user_id).update(first_name=first_name, last_name=last_name, email=email, username=email)

        try:
            response = self.perform_update(serializer)
            company = Company.objects.filter(id=company_id).first()
            Staff.objects.filter(id=instance.id).update(company=company)
            staffinstance = Staff.objects.filter(id=instance.id).first()
            try:
                draftchecklist = DraftCheckList.objects.filter(id=7).first()
                if staffinstance.advisor_terms_and_agreement:
                    # client_checklist1, created = ClientCheckList.objects.update_or_create(draft_checklist=draftchecklist1, group='Advisor',user=staffinstance,
                    ClientCheckList.objects.filter(draft_checklist=draftchecklist, user=staffinstance).update(colour_code='Green')
                else:
                    ClientCheckList.objects.filter(draft_checklist=draftchecklist,client__is_confirmed_client=False,user=staffinstance).update(colour_code='Red')
            except Exception as e:
                print(str(e))
                logger.exception("Exception in profile update : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                




        except Exception as e:
            print(e)
            logger.exception("Exception in  profile update : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Error in updating profile details'
        else:
            response_data['status_code'] = '200'
            response_data['status'] = True
            response_data['message'] = 'You have succesfully updated profile details'

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)

def get_doclabel(id):

    doc_name= Document.objects.filter(doc_type=id, is_active=True).first()   
    if doc_name:
        doc_type=doc_name.get_doc_type_display()
    else :
        doc_type=None
    return doc_type


class DraftReccomendationDocumentViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = Document.objects.all()

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        clientid = self.request.query_params.get('client_id', None)
        if clientid:
            queryset = queryset.filter(owner=clientid, is_active=True)
        data = {'common_docs': [], 'instrument_list': []}
        common_doc_list = {'AML', 'Authority to Proceed', 'Suitability Report', 'ATR', 'Platform Costs'}
        for common_doc in common_doc_list:
            doc_details = {'name': None, 'file_name': None, 'file_path': None, 'doc_type': None, 'doc_id': None}
            doc_details['name'] = common_doc
            if common_doc == 'AML':
                doc_details['doc_type'] = '9'
                doc_details['doc_label']=get_doclabel('9')
            if common_doc == 'Authority to Proceed':
                doc_details['doc_type'] = '10'
                doc_details['doc_label']=get_doclabel('10')
            if common_doc == 'Suitability Report':
                doc_details['doc_type'] = '8'
                doc_details['doc_label']=get_doclabel('8')
            if common_doc == 'ATR':
                doc_details['doc_type'] = '11'
                doc_details['doc_label']=get_doclabel('11')
            if common_doc == 'Platform Costs':
                doc_details['doc_type'] = '12'
                doc_details['doc_label']=get_doclabel('12')

            file = queryset.filter(doc_type=doc_details['doc_type']).last()
            if file:

                doc_details['file_name'] = os.path.basename(file.doc.name)
                doc_details['file_path'] = file.doc.url

                doc_details['doc_id'] = file.id
            data['common_docs'].append(doc_details)

        client_instrument_list=ClientInstrumentInfo.objects.filter(client=clientid,is_recommended=True, is_active=True).order_by('-id') 
        count=0

        for clientinstrument in client_instrument_list:
            
            instrument_recommended=InstrumentsRecomended.objects.filter(client_instrumentinfo=clientinstrument,is_active=True).first()
            if instrument_recommended:
                clientinstrumentdict = {}
                clientinstrumentdict['instrument_id'] = clientinstrument.id
                
                try:
                    fun_type=str((list(instrument_recommended.function_list.all())[0]).get_function_type_display())
                except:
                    fun_type=''
                clientinstrumentdict['instrument_name'] = clientinstrument.instrument.instrument_name + '-' + fun_type
                clientinstrumentdict['doc_list'] = []

                client_instrument_docs = ['Fund Research', 'Critical Yield', 'Illustration', 'Weighted Average Calculator',
                                      'LOA Response Info','Application Summary']
                for doc in client_instrument_docs:
                    instrument_doc_dict = {'name': None, 'file_name': None, 'file_path': None, 'doc_type': None,
                                       'doc_id': None,'mapped_instruments':[]}
                    if doc == 'Fund Research':
                        instrument_doc_dict['name'] = 'Fund Research'
                        instrument_doc_dict['doc_type'] = '14'
                        instrument_doc_dict['doc_label']=get_doclabel('14')
                        if clientinstrument.fund_research:
                            instrument_doc_dict['file_name'] = os.path.basename(clientinstrument.fund_research.doc.name)
                            instrument_doc_dict['file_path'] = clientinstrument.fund_research.doc.url
                            instrument_doc_dict['doc_id'] = clientinstrument.fund_research.id
                            instrument_doc_dict['mapped_instruments'] = []

                    elif doc == 'Critical Yield':
                        instrument_doc_dict['name'] = 'Critical Yield'
                        instrument_doc_dict['doc_type'] = '15'
                        instrument_doc_dict['doc_label']=get_doclabel('15')
                        if clientinstrument.critical_yield:
                            instrument_doc_dict['file_name'] = os.path.basename(clientinstrument.critical_yield.doc.name)
                            instrument_doc_dict['file_path'] = clientinstrument.critical_yield.doc.url
                            instrument_doc_dict['doc_id'] = clientinstrument.critical_yield.id
                            instrument_doc_dict['mapped_instruments'] = []
                    elif doc == 'Illustration':
                        instrument_doc_dict['name'] = 'Illustration'
                        instrument_doc_dict['doc_type'] = '16'
                        instrument_doc_dict['doc_label']=get_doclabel('16')
                        if clientinstrument.illustration:
                            instrument_doc_dict['file_name'] = os.path.basename(clientinstrument.illustration.doc.name)
                            instrument_doc_dict['file_path'] = clientinstrument.illustration.doc.url
                            instrument_doc_dict['doc_id'] = clientinstrument.illustration.id
                            mapped_queryset=ClientInstrumentInfo.objects.filter(illustration=clientinstrument.illustration.id,client=clientinstrument.client,is_recommended=True,is_active=True)
                            for instrument in list(mapped_queryset):
                                instrument_doc_dict['mapped_instruments'].append(instrument.id)
                    elif doc == 'Application Summary':
                        instrument_doc_dict['name'] = 'Application Summary'
                        instrument_doc_dict['doc_type'] = '13'
                        instrument_doc_dict['doc_label']=get_doclabel('13')
                        if clientinstrument.app_summary:
                            instrument_doc_dict['file_name'] = os.path.basename(clientinstrument.app_summary.doc.name)
                            instrument_doc_dict['file_path'] = clientinstrument.app_summary.doc.url
                            instrument_doc_dict['doc_id'] = clientinstrument.app_summary.id
                            mapped_queryset = ClientInstrumentInfo.objects.filter(app_summary=clientinstrument.app_summary.id, client=clientinstrument.client,is_recommended=True, is_active=True)
                            for instrument in list(mapped_queryset):
                                instrument_doc_dict['mapped_instruments'].append(instrument.id)
                    elif doc == 'Weighted Average Calculator':
                        instrument_doc_dict['name'] = 'Weighted Average Calculator'
                        instrument_doc_dict['doc_type'] = '17'
                        instrument_doc_dict['doc_label']=get_doclabel('17')
                        if clientinstrument.weighted_average_calculator:
                            instrument_doc_dict['file_name'] = os.path.basename(
                                clientinstrument.weighted_average_calculator.doc.name)
                            instrument_doc_dict['file_path'] = clientinstrument.weighted_average_calculator.doc.url
                            instrument_doc_dict['doc_id'] = clientinstrument.weighted_average_calculator.id
                            instrument_doc_dict['mapped_instruments'] = []
                    elif doc == 'LOA Response Info':
                        instrument_doc_dict['name'] = 'LOA Response Info'
                        if (clientinstrument.provider_type) == '1':
                            instrument_doc_dict['doc_type'] = '5'
                            instrument_doc_dict['doc_label']=get_doclabel('5')
                        if (clientinstrument.provider_type) == '2':
                            instrument_doc_dict['doc_type'] = '7'
                            instrument_doc_dict['doc_label']=get_doclabel('7')
                        if clientinstrument.pdf_data:
                            instrument_doc_dict['file_name'] = os.path.basename(clientinstrument.pdf_data.doc.name)
                            instrument_doc_dict['file_path'] = clientinstrument.pdf_data.doc.url
                            instrument_doc_dict['doc_id'] = clientinstrument.pdf_data.id
                            instrument_doc_dict['mapped_instruments'] = []

                    clientinstrumentdict['doc_list'].append(instrument_doc_dict)

                data['instrument_list'].append(clientinstrumentdict)

        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Draft recommendation doc list fetched',
            "data": data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        client_instrument_list=request.data['client_instrument_list']
        doc_id=request.data['doc_id']
       
        try:
            doc_obj=Document.objects.filter(id=doc_id).first()
            for instrument in client_instrument_list:
               
                if doc_obj.doc_type=='13':
                    ClientInstrumentInfo.objects.filter(id=instrument).update(app_summary=doc_obj)
                elif doc_obj.doc_type=='16':
                    ClientInstrumentInfo.objects.filter(id=instrument).update(illustration=doc_obj)

        except Exception as e:
            print(str(e))
            logger.exception("Error in mapping document : {} - {}".format(str(e), request.path),
                             extra={'status_code': 400, 'request': request})

        response_data = {
            "status_code": "201",
            "status": True,
            "message": 'Draft Document mapped successfully'
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(methods=['get'], detail=False, name='instrument_list')
    def instrument_list(self, request, *args, **kwargs):
        response_data = {}
        data=[]
        client_instrument = request.query_params.get('client_instrument')
        clientinstrument=ClientInstrumentInfo.objects.filter(id=client_instrument).first()
        #
        if clientinstrument:
            queryset1=ClientInstrumentInfo.objects.filter(provider=clientinstrument.provider,client=clientinstrument.client,parent__isnull=True,is_active=True,is_recommended=True)
            queryset2=ClientInstrumentInfo.objects.filter(parent=clientinstrument,client=clientinstrument.client,is_active=True,is_recommended=True)
            queryset=queryset1|queryset2
        for c_instrument in queryset:
            instrument_data={"id":c_instrument.id,"name":c_instrument.instrument.instrument_name}
            data.append(instrument_data)
        response_data['status_code'] = '200'
        response_data['status'] = True
        response_data['message'] = 'Instrument list fetched'
        response_data['data'] = data
        if response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)


class ProfileViewSet(APIView):
    permission_classes = (IsAuthenticated, IsAll,)

    def get(self, request, *args, **kwargs):
        user = self.request.user
       
        confirm_client_count=0
        staff_list_obj=[]
        data={"convesrion_rate":0,"pre_contract":0,"atp":0,"post_contract":0,"total_client":0}
       
        user_list = Staff.objects.filter(user=user,user__groups__name__in=['Ops', 'Compliance','Administrator']).first()
        if user_list:
            staff_list=Staff.objects.filter(company=user_list.company)
            for staff_result in staff_list:
                staff_list_obj.append(staff_result.user)
            client_obj=Client.objects.filter(created_by__in=staff_list_obj).order_by("-id")
           
        
        else:
            advisor_obj=Staff.objects.filter(user=self.request.user).first() 
            client_obj=Client.objects.filter(created_by=advisor_obj.user).order_by("-id")
            staff_list_obj.append(advisor_obj.user)
        
        
        
        if client_obj:
            data['total_client'] = client_obj.count()
           
            confirm_client_count = client_obj.filter(client_stage='2').count()
            data['atp'] = confirm_client_count

        data['pre_contract'] = Client.objects.filter(created_by__in=staff_list_obj,client_stage='1').order_by("-id").count()
        data['post_contract'] = Client.objects.filter(created_by__in=staff_list_obj,client_stage='3').order_by("-id").count()
        task_closed_client_count=Client.objects.filter(created_by__in=staff_list_obj,client_stage='0').order_by("-id").count()
        print("confirm_client_count ",confirm_client_count," total client ", data['total_client']," pre_contract ",data['pre_contract']," post_contract ",data['post_contract'] )
        total_closed_post=data['post_contract']+task_closed_client_count
        print("task_closed_client_count ",task_closed_client_count)

        if data['total_client'] and data['total_client']!=0 and total_closed_post!=0 :
            perc_res = (total_closed_post/data['total_client'])*100
            percentage=round(perc_res,2)
            
        else:
            percentage=0
        data['convesrion_rate'] = percentage
       


        response_data = {
            "status_code": "200",
            "status": True,
            "message": 'Profile  Details Fetched',
            "data": data
        }

        return Response(response_data, status=status.HTTP_200_OK)



class SmartsearchViewSet(APIView):

    permission_classes = (IsAuthenticated, IsAll,)


    def post(self, request, *args, **kwargs):
        smart_search_token = authentication()
        # print("\n smart search token ",smart_search_token,type(smart_search_token),"\n")
        client = request.data.get('client_id', None)
       
        ssid = request.data.get('ssid', None)
        client_task_id = request.data.get('client_task_id', None)
        
        response_data = {}
        client = Client.objects.filter(id=client).first()
        client_task_obj = ClientTask.objects.filter(id=client_task_id).first()
        advisor = Staff.objects.filter(user=client.created_by)
        administrator=Staff.objects.filter(user=self.request.user).first()
        prev_ssid = fetch_ssid(client)

        is_prev_data = False
        if (prev_ssid is not None and prev_ssid!='') and  ssid is None:
            smart_search_obj,status_code = search_previous_aml(client,client_task_id,smart_search_token,administrator,prev_ssid)
            

        else:
            smart_search_obj=None
            status_code = None
        
        data = {"doc_path":None,"result":None,"ssid":None,'is_kyc_confirmed':None}
       
        if len(str(smart_search_token))==3:
            response_data['status_code'] = '400'
            response_data['message']='Please contact technical team '
        elif (smart_search_obj is not None and status_code =='200') and ssid is None:
            is_prev_data = True
            print("old check")
            data['doc_path']= smart_search_obj.document_path.url
            data['result']= smart_search_obj.status
            data['ssid']= smart_search_obj.ssid
            data['is_kyc_confirmed']= smart_search_obj.task.is_kyc_confirmed
            ssid = smart_search_obj.ssid
            response_data['status_code']='200'
            response_data['message'] = "KYC details fetched successfully"

        if (client and ssid is None) and (smart_search_obj is None and status_code!='200') :
            
            try:
                print("initial.....")
                smart_search_json=post_individual_uk_aml(client)
               
                headers={'Authorization': 'Bearer '+smart_search_token,'Accept-Version': '2'} 
                response = requests.post(settings.SMART_SEARCH_URL+"aml",headers=headers,json=smart_search_json)
                
                # print("\n response ",response.content)
                response_data['status_code']=str(response.status_code)
                # print("status_code ",str(response.status_code))
                

                response_data['data'] = json.loads(response.content.decode('utf-8'))
                
                try:
                    response_content = response_data['data']
                    # print("response_content ",response_content)
                    if str(response.status_code)=='200':
                        smart_search_obj = smart_search_log_save(smart_search_json,response_content,settings.SMART_SEARCH_URL+"aml","post")
                        # Smartserachlog.objects.create(request_msg=smart_search_json,response_msg= response_content )
                        print("smart_search_obj ",smart_search_obj)
                        if smart_search_obj:
                            doc_path = response_content['data']['links']['pdf']['href']
                            ssid = response_content['data']['attributes']['ssid']
                            search_result = response_content['data']['attributes']['result']
                            print("search_result ===============",search_result,".........")
                            is_update=False
                            result = download_file(url = doc_path,client_id=client,ssid=ssid,search_result=search_result,advisor=administrator,smart_search_log_obj=smart_search_obj,is_update=is_update,client_task_obj=client_task_obj,smart_search_obj=None)
                                     
                            if result:
                                print("client_task_obj ",client_task_obj)
                                data['doc_path'] = result.document_path.url
                                data['result'] = result.status
                                data['ssid'] =result.ssid
                                data['is_kyc_confirmed']= client_task_obj.is_kyc_confirmed

                    else:
                        smart_search_obj = smart_search_log_save(smart_search_json,response_data['data'],settings.SMART_SEARCH_URL+"aml","post")
                        response_data['status_code'] = str(response.status_code)
                        if str(response.status_code)=='400':
                            response_data['message']="We haven't been able to find this address. This sometimes happens if a property is a house which has been converted into a flat for example. Please check the address and try again"
                        else:
                            response_data['message']='Something went wrong'
                except Exception as e:
                    print("error while create an entry to Smartserachlog",e)
                    logger.exception("Exception in creating an entry to Smartserachlog : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                


                
            except Exception as e:
                print("exception ",e)
                logger.exception("Exception in KYC smartsearch : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                
                response_data['status_code'] = '400'

                response_data['message']='Please verify your name and address'

        
        elif client is None:
            response_data['status_code']='400'
            response_data['message'] = "No client details"

        #search existing request data is differ from current request data 
        else :
            if ssid is not None and not is_prev_data:
                # and not is_prev_data
                print("==========================second cra check =======================================")
                
                try:
                    smart_search_json=post_individual_uk_aml(client)
                    data,status_code = check_request_data(client,smart_search_json,smart_search_token,client_task_obj,administrator)
                except Exception as e:
                    print("Exception while survey form data parsing ....")
                    logger.exception("Exception in survery parsing for KYC smartsearch : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})                


                if data:
                    response_data['status_code'] = status_code
                    if status_code=='400':
                        response_data['message']="We haven't been able to find this address. This sometimes happens if a property is a house which has been converted into a flat for example. Please check the address and try again"
                        update_or_create_checklist(client,47,advisor,result='failed')

                    if status_code=='403':
                        response_data['message']='This check is not eligible for multi-source Individual AML'
                        update_or_create_checklist(client,47,advisor,result='failed')
                        response_data_obj = {"data":"This check is not eligible for multi-source Individual AML"}
                        smart_search_obj = smart_search_log_save(smart_search_json,response_data_obj,settings.SMART_SEARCH_URL+"aml","post")

                    if status_code=='404':
                        response_data['message']='No results found from given ssid'
                        update_or_create_checklist(client,47,advisor,result='failed')
        if (data.get('result',None)=='pass'):#47#smartsearch checklist
            update_or_create_checklist(client,47,advisor,result='passed')
        elif (data.get('result',None)=='refer'):
            update_or_create_checklist(client,47,advisor,result='failed')


        if response_data['status_code'] == '400' :
            smartsearch_obj = Smartserach.objects.filter(client=client,task=client_task_obj).last()
            if smartsearch_obj is not None:
                smartsearch_obj.status=None
                smartsearch_obj.save()
            resp_status = status.HTTP_400_BAD_REQUEST            
            response_data = {
                'status_code': "400",
                'status': False,
                'message': response_data['message'],
                'data': data
            }

        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
            response_data = {
                'status_code': "200",
                'status': True,
                'message': "KYC details fetched successfully",
                'data': data
            }
       
        else:    # handle all other status 
            smartsearch_obj = Smartserach.objects.filter(client=client,task=client_task_obj).last()
            if smartsearch_obj is not None:
                smartsearch_obj.status=None
                smartsearch_obj.save()
            resp_status = status.HTTP_400_BAD_REQUEST           
            response_data = {
                'status_code': "400",
                'status': False,
                'message': response_data['message'],
                'data': data
            }

        return Response(response_data, status=resp_status)



    def get(self, request, *args, **kwargs):
        client_id = self.request.query_params.get('client_id', None)
        client_task_id = self.request.query_params.get('client_task_id', None)
        client_obj = Client.objects.filter(id=client_id).first()
        staff_obj = Staff.objects.filter(user=self.request.user).first()
        client_task_obj = ClientTask.objects.filter(id=client_task_id).first()
        smart_search_obj = Smartserach.objects.filter(client=client_obj,task=client_task_obj).last()
        if smart_search_obj:
            data={"doc_path":smart_search_obj.document_path.url,"result":smart_search_obj.status,"ssid":smart_search_obj.ssid}
            response_data = {
                "status_code": "200",
                "status": True,
                "message": 'KYC Details Fetched',
                "data": data
            }
        else:
            data={}
            response_data = {
            "status_code": "400",
            "status": False,
            "message": 'No results found',
            "data": data
        }
        if response_data['status_code']=='200':
            resp_status = status.HTTP_200_OK
        else:
            resp_status = status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=resp_status)



    def put(self, request, *args, **kwargs):
        
        ssid = request.data.get('ssid')
        client_id = request.data.get('client_id')
        client = Client.objects.filter(id=client_id).first()
        
        response_data ={}
        status_flag = False
        try:
            smartsearch_obj  = Smartserach.objects.filter(ssid = ssid,client=client).first()
            status_value = smartsearch_obj.status
            
            if status_value =="refer":
                smart_search_token = authentication()
                print("\n smart search token ",smart_search_token,type(smart_search_token),"\n")
                status_code = second_cra(ssid,smart_search_token,smartsearch_obj)
                
            else:
                status_flag = True
                status_code = True
            
        except Exception as e:
            logger.exception("Error in updating kyc status : {} - {}".format(str(e), request.path), extra={'status_code': 400, 'request': request})
            response_data['status_code'] = '400'
            response_data['status'] = True
            response_data['message'] = 'Error in updating kyc status'
        else:
            if not status_flag and status_code: 
                try:
                    
                    # client_task_update = ClientTask.objects.filter(id=smartsearch_obj.task.id).update(is_kyc_confirmed=True,kyc_confirmed_on=tz.now())
                    client_profile_completion(client=smartsearch_obj.client,phase='post-contract',percentage=10,sign='positive')
                    advisor = Staff.objects.filter(user=smartsearch_obj.client.created_by)
                    update_or_create_checklist(smartsearch_obj.client,47,advisor,result='passed')
                    client_task_obj = ClientTask.objects.filter(id=smartsearch_obj.task.id).first()
                    
                    if client_task_obj.kyc_ever_confirmed:
                        
                        task_collection = TaskCollection.objects.filter(task_slug='kyc_reconfirmed').first()
                        # client_task_obj.kyc_confirmed=True
                    else:
                        
                        task_collection = TaskCollection.objects.filter(task_slug='confirm_kyc').first()
                        client_task_obj.kyc_ever_confirmed=True
                    add_task_activity(client_task=client_task_obj, task_collection=task_collection, created_by=client_task_obj.administrator, task_status='3')
                    client_task_obj.current_sub_task = task_collection
                    client_task_obj.is_kyc_confirmed=True
                    client_task_obj.kyc_confirmed_on=tz.now()
                    client_task_obj.save()
                    
                except Exception as e:
                    print("exception while updating status of client task ")
                if smartsearch_obj.status=='refer':
                    response_data['status_code'] = '400'
                    response_data['status'] = False
                    response_data['message'] = 'Unfortunately we are unable to update status in smart search please contact smart search team'
                else:
                    response_data['status_code'] = '200'
                    response_data['status'] = True
                    response_data['message'] = 'You have succesfully updated the status'
            elif not status_code:
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'ssid details cannot be found'

            else:
                response_data['status_code'] = '400'
                response_data['status'] = False
                response_data['message'] = 'Smart search result is already pass,cannot be updated'
            
        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '200':
            resp_status = status.HTTP_200_OK
        return Response(response_data, status=resp_status)




class ErrorlogViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsAll,)
    serializer_class = ErrorlogSerializer

    def post(self, request, *args, **kwargs):
        response_data = {}
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response=self.perform_create(serializer)

        if response:
            response_data['status_code'] = '201'
            response_data['status'] = True
            response_data['message'] = 'Error log created successfully'
            
        else:
            response_data['status_code'] = '400'
            response_data['status'] = False
            response_data['message'] = 'Error log could not be created'

        if response_data['status_code'] == '400':
            resp_status = status.HTTP_400_BAD_REQUEST
        elif response_data['status_code'] == '201':
            resp_status = status.HTTP_201_CREATED

        return Response(response_data, status=resp_status)



# class smartsearchdataViewSet(APIView):
#     permission_classes = (IsAuthenticated, IsAll,)

#     def get(self, request, *args, **kwargs):
        
#         client_id = self.request.query_params.get('client_id', None)
#         client_task_id = self.request.query_params.get('client_task_id', None)
#         ssid = self.request.query_params.get('ssid', None)

#         client_obj = Client.objects.filter(id=client_id).first()
#         staff_obj = Staff.objects.filter(user=self.request.user).first()
#         client_task_obj = ClientTask.objects.filter(id=client_task_id).first()
        
#         # advisor = Staff.objects.filter(user=client.created_by)
#         administrator=Staff.objects.filter(user=self.request.user).first()
#         try:
#             smart_search_token = authentication()
#             # print("\n smart search token ",smart_search_token,type(smart_search_token),"\n")
#             smart_search_obj,status_code = fetch_smart_search_data(ssid,smart_search_token,client_obj,administrator,client_task_obj)
#         except Exception as e:
#             pass
#         data={}
#         if status_code=='200':
            
#             resp_status = status.HTTP_200_OK
#             data={"doc_path":smart_search_obj.document_path.url,"result":smart_search_obj.status,"ssid":smart_search_obj.ssid}
           
#             response_data = {
#                 "status_code": "200",
#                 "status": True,
#                 "message": 'KYC details fetched successfully',
#                 "data": data
#             }
#         else:
#             resp_status = status.HTTP_400_BAD_REQUEST
#             response_data = {
#                 "status_code": "400",
#                 "status": False,
#                 "message": 'No KYC Details',
#                 "data": data
#             }
        
        
            
#         return Response(response_data, status=resp_status)