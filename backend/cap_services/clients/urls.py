from django.urls import path
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register('clients', views.ClientViewSet, basename='clients')
router.register('users', views.UserViewSet, basename='users')
router.register('companies', views.CompanyViewSet, basename='companies')
router.register('docs', views.DocumentViewSet, basename='documents')
router.register('doc-settings', views.DocumentSettingViewSet, basename='doc_settings')
router.register('client-categories', views.CategorySummaryViewSet, basename='client_categories_survey_form')
router.register('instrument-providers', views.ProviderViewSet, basename='instrument-providers')
router.register('instruments', views.InstrumentViewSet, basename='instruments')
router.register('client-instruments-info', views.ClientInstrumentInfoViewSet, basename='client-instruments-info')
router.register('template', views.TemplateViewSet, basename='template')
router.register('template-categories', views.TemplateCategoryViewSet, basename='template-categories')
router.register('activity-flow', views.ActivityFlowViewSet, basename='activity-flow')
router.register('pending-actions', views.ReminderViewSet, basename='pending-actions')
router.register('advisor-profile', views.AdvisorProfileViewSet, basename='advisor-profile')

router.register('job-titles', views.JobtitleViewSet, basename='job-titles')
router.register('countries', views.CountryViewSet, basename='countries')
router.register('lenders', views.LenderViewSet, basename='lenders')
router.register('pension-providers', views.PensionProviderViewSet, basename='pension-providers')
router.register('audio-extraction',views.ClientAudioExtractionViewSet,basename='audio-extraction')
router.register('extracted-data',views.InstrumentExtractedDataViewSet,basename='extracted-data')

router.register('client-tasks', views.ClientTaskViewSet, basename='client-tasks')
router.register('staffs', views.StaffViewSet, basename='staffs')
router.register('comments', views.ClientTaskCommentViewSet, basename='comments')
router.register('task-event', views.TaskEventViewSet, basename='task-event')
router.register('client-task-timeline', views.ClientTaskTimelineViewSet, basename='client-task-timeline')
router.register('extracted-keyword-data', views.ExtractedDataViewSet, basename='extracted-data')

router.register('client-checklist', views.ClientChecklistViewSet, basename='client-checklist')
router.register('fee-details', views.FeeRuleConfigViewSet, basename='fee-details')
router.register('reason-details', views.ReasonViewSet, basename='reason-details')
router.register('draft-recommendation', views.DraftReccomendationViewSet, basename='draft-recommendation')
router.register('draft-recommendation-documents', views.DraftReccomendationDocumentViewSet, basename='draft-recommendation-documents')
router.register('instrument-recommended', views.InstrumentsRecomendedViewSet, basename='instrument-recommended')
router.register('draft-recommendation-details', views.ClientRecommendationNotificationViewSet, basename='draft-recommendation-details')
router.register('error-log', views.ErrorlogViewSet, basename='error-log')


urlpatterns = [
    path('login/', views.CustomObtainAuthToken.as_view(), name='api_login'),
    path('logout/', views.UserLogout.as_view(), name='api_logout'),
    path('forgot-password/', views.UserForgotPassword.as_view(), name='forgot_password'),
    path('reset-password/', views.UserResetPassword.as_view(), name='reset_password'),
    #path('survey-form/', views.UpdateSurveyForm.as_view(), name='survey_form_submit'),
    path('reminder/pending-with/', views.ReminderPendingView.as_view(), name='pending-with'),
    path('reminder/notification-count/', views.ReminderNotificationView.as_view(), name='notification-count'),
    path('get-permissions/', views.GroupPermissionView.as_view(), name='get-permissions'),
    path('save_extracted/', views.SaveExtractedKeywordsView.as_view(), name='save-extracted'),
    #path('illustration_extracted/', views.IllustrationExtractedView.as_view(), name='illustration-extracted'),
    path('fund-details/', views.FundRiskViewSet.as_view(), name='fund-details'),
    path('check-connection', views.CheckConnectionViewSet.as_view(), name='check-connection'),
    path('profile-details/', views.ProfileViewSet.as_view(), name='profile-details'),
    path('smart-search/', views.SmartsearchViewSet.as_view(), name='smart-search-details'),
    # path('error-log/', views.ErrorlogViewSet.as_view(), name='error-log'),
    
    # path('smart-search-details/', views.smartsearchdataViewSet.as_view()),

    

]

urlpatterns += router.urls