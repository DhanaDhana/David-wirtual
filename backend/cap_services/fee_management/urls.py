from django.urls import path
from . import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register('suspence-acc-provider',views.providerUnderAdvisorViewset, basename='provider-suspence-account')
router.register('all-sp-monthly-issue',views.providerDetailsInMonthlyIssue, basename='provider-suspence-account')
router.register('advisorlist-monthly-issue',views.advisorDetailsInMonthlyIssue, basename='provider-suspence-account')
router.register('clientlist-monthly-issue',views.clientDetailsInMonthlyIssue, basename='provider-suspence-account')



urlpatterns = [
    path('advisor/monthly-issue/',views.searchAdvisorsForMonthlyIssue.as_view(),name = 'advisormonthlyissue'),
    path('search-advisor-pending-issue/',views.searchAdvisorPendingIssue.as_view(),name = 'advisorPendingIssue'),
    path('advisor-list-pending-issue/',views.advisorDetailsInPending.as_view(),name = 'advisorListPending'),
]


urlpatterns += router.urls