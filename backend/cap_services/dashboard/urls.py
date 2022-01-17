from django.urls import path
from . import views
from rest_framework import routers

router = routers.DefaultRouter()

urlpatterns = [

path('clients-refer/', views.ClientReferPercentageView.as_view(), name='clients-refer'),
path('check-newclients/', views.ChecknewclientsView.as_view(), name='check-newclients'),
path('top-referer/', views.ToprefererView.as_view(), name='top-referer'),
path('average-age/', views.AverageageView.as_view(), name='average-age'),
# path('advisor-list/', views.AdvisorView.as_view(), name='advisor-list'),
path('accept-ratio/', views.AtpView.as_view(), name='accept-ratio'),
path('interaction-type/', views.MeetingbyMonthView.as_view(), name='interaction-type'),
path('redington/', views.RedingtonView.as_view(), name='redington'),


]

urlpatterns += router.urls