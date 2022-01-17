from django.urls import path
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register('mailfolder', views.MailFolderViewSet, basename='mailfolder')
router.register('mail', views.EmailViewSet, basename='mail')
router.register('event', views.EventViewSet, basename='event')
router.register('outlook-cred', views.OutlookCredViewSet, basename='outlook_cred')


urlpatterns = [
   
   path('signin', views.OauthSignIn.as_view(), name='signin'),
   path('callback', views.OauthCallback.as_view(), name='callback'),

   path('mark-mail-read/', views.MarkMailAsRead.as_view(), name='mark_mail_read'),
   path('mail-recipients/', views.GetMailRecipients.as_view(), name='mail_recipients'),
   path('move-to-folder/', views.MoveToFolder.as_view(), name='move_to_folder'),
   path('mark-rsvp/', views.MarkRSVP.as_view(), name='mark_rsvp'),
   path('sync-outlook/', views.SyncOutlook.as_view(), name='sync_outlook'),
   path('get-next-meeting/', views.GetNextMeeting.as_view(), name='get_next_meeting'),
   path('parse-loa_mails/', views.ParseLOAMails.as_view(), name='parse_loa_mails')

]

urlpatterns += router.urls