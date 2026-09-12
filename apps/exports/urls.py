from django.urls import path
from apps.exports import views

urlpatterns = [
    path('center/', views.ExportCenterOverviewView.as_view(), name='export_center_overview'),
    path('center', views.ExportCenterOverviewView.as_view()),
    path('employee/<str:employee_id>/excel/', views.EmployeeExcelExportView.as_view(), name='export_employee_excel'),
    path('employee/<str:employee_id>/excel', views.EmployeeExcelExportView.as_view()),
    path('employees/excel/', views.AllEmployeesExcelExportView.as_view(), name='export_all_employees_excel'),
    path('employees/excel', views.AllEmployeesExcelExportView.as_view()),
    path('daily/<str:workday_id>/excel/', views.DailyWorkDayExcelExportView.as_view(), name='export_daily_id_excel'),
    path('daily/<str:workday_id>/excel', views.DailyWorkDayExcelExportView.as_view()),
    path('daily/excel/', views.DailyWorkDayExcelExportView.as_view(), name='export_daily_query_excel'),
    path('daily/excel', views.DailyWorkDayExcelExportView.as_view()),
    path('date-range/excel/', views.DateRangeExcelExportView.as_view(), name='export_date_range_excel'),
    path('date-range/excel', views.DateRangeExcelExportView.as_view()),
    path('statistics/excel/', views.StatisticsExcelExportView.as_view(), name='export_statistics_excel'),
    path('statistics/excel', views.StatisticsExcelExportView.as_view()),
    path('database/excel/', views.DatabaseExcelExportView.as_view(), name='export_database_excel'),
    path('database/excel', views.DatabaseExcelExportView.as_view()),
]
