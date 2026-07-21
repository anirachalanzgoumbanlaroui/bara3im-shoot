from django.contrib import admin
from .models import Location, DailyLocation, WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog, SellerDailyOperation

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'color_hex', 'created_at')
    search_fields = ('name',)

@admin.register(DailyLocation)
class DailyLocationAdmin(admin.ModelAdmin):
    list_display = ('location', 'work_day', 'created_at')
    list_filter = ('location', 'work_day')
    search_fields = ('location__name',)

@admin.register(WorkDay)
class WorkDayAdmin(admin.ModelAdmin):
    list_display = ('date', 'photographer_unit_price', 'clown_unit_price', 'created_by')
    list_filter = ('date',)
    search_fields = ('date',)

@admin.register(DailyTeam)
class DailyTeamAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'daily_location', 'photographer', 'clown', 'team_photo_count')
    list_filter = ('daily_location__work_day__date', 'daily_location__location')
    search_fields = ('team_name', 'photographer__first_name', 'clown__first_name')

@admin.register(DailyEmployeePerformance)
class DailyEmployeePerformanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'work_day', 'daily_location', 'team', 'photo_count', 'adjustment_type')
    list_filter = ('work_day', 'daily_location__location', 'adjustment_type')
    search_fields = ('employee__first_name',)

@admin.register(DailyOperationLog)
class DailyOperationLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'work_day', 'user', 'created_at')
    list_filter = ('action', 'work_day')
    search_fields = ('action', 'user__username')

@admin.register(SellerDailyOperation)
class SellerDailyOperationAdmin(admin.ModelAdmin):
    list_display = ('seller', 'daily_location', 'amount', 'created_at')
    list_filter = ('daily_location__work_day__date', 'daily_location__location', 'seller')
    search_fields = ('seller__first_name', 'seller__last_name')
