from django.urls import path
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register('surveyform', views.SurveyformViewSet, basename='surveyform')


urlpatterns = router.urls