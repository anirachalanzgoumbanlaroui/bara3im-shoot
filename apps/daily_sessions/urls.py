from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WorkDayViewSet, DailyTeamViewSet, 
    DailyEmployeePerformanceViewSet, DailyOperationLogViewSet,
    SellerDailyOperationViewSet
)

app_name = 'daily_sessions'

router = DefaultRouter()
router.register(r'daily-sessions/work-days', WorkDayViewSet, basename='workday')
router.register(r'daily-sessions/teams', DailyTeamViewSet, basename='dailyteam')
router.register(r'daily-sessions/performances', DailyEmployeePerformanceViewSet, basename='dailyemployeeperformance')
router.register(r'daily-sessions/logs', DailyOperationLogViewSet, basename='dailyoperationlog')
router.register(r'daily-sessions/seller-operations', SellerDailyOperationViewSet, basename='sellerdailyoperation')

urlpatterns = [
    path('', include(router.urls)),
]
