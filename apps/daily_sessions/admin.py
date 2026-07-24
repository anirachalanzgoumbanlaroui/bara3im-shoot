from django.contrib import admin
from .models import Location, WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog, SellerDailyOperation


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'color_hex', 'created_at')
    search_fields = ('name',)


@admin.register(WorkDay)
class WorkDayAdmin(admin.ModelAdmin):
    list_display = ('date', 'location', 'status', 'photographer_unit_price', 'clown_unit_price', 'created_by')
    list_filter = ('location', 'status', 'date')
    search_fields = ('location__name',)


@admin.register(DailyTeam)
class DailyTeamAdmin(admin.ModelAdmin):
    list_display = ('team_name', 'work_day', 'photographer', 'clown', 'team_photo_count')
    list_filter = ('work_day__date', 'work_day__location')
    search_fields = ('team_name', 'photographer__first_name', 'clown__first_name')


@admin.register(DailyEmployeePerformance)
class DailyEmployeePerformanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'work_day', 'team', 'photo_count', 'adjustment_type')
    list_filter = ('work_day__date', 'work_day__location', 'adjustment_type')
    search_fields = ('employee__first_name',)


@admin.register(DailyOperationLog)
class DailyOperationLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'work_day', 'user', 'created_at')
    list_filter = ('action', 'work_day')
    search_fields = ('action', 'user__username')


@admin.register(SellerDailyOperation)
class SellerDailyOperationAdmin(admin.ModelAdmin):
    list_display = ('seller', 'work_day', 'amount', 'created_at')
    list_filter = ('work_day__date', 'work_day__location', 'seller')
    search_fields = ('seller__first_name', 'seller__last_name')
