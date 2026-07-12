from django.contrib import admin
from .models import WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog

@admin.register(WorkDay)
class WorkDayAdmin(admin.ModelAdmin):
    list_display = ('date', 'photographer_unit_price', 'clown_unit_price', 'created_by')
    list_filter = ('date',)
    search_fields = ('date',)

@admin.register(DailyTeam)
class DailyTeamAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'work_day', 'photographer', 'clown', 'team_photo_count')
    list_filter = ('work_day',)
    search_fields = ('team_name', 'photographer__first_name', 'clown__first_name')

@admin.register(DailyEmployeePerformance)
class DailyEmployeePerformanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'work_day', 'team', 'photo_count', 'adjustment_type')
    list_filter = ('work_day', 'adjustment_type')
    search_fields = ('employee__first_name',)

@admin.register(DailyOperationLog)
class DailyOperationLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'work_day', 'user', 'created_at')
    list_filter = ('action', 'work_day')
    search_fields = ('action', 'user__username')
