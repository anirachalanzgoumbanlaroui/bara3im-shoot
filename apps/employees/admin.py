from django.contrib import admin

from .models import Employee, Bonus, Advance, Deduction


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
	list_display = (
		'employee_code', 'first_name', 'last_name', 'role', 'status',
		'fingerprint_registered', 'face_registered', 'created_at'
	)
	list_filter = ('role', 'status', 'fingerprint_registered', 'face_registered')
	search_fields = ('employee_code', 'first_name', 'last_name', 'phone_number')


@admin.register(Bonus)
class BonusAdmin(admin.ModelAdmin):
	list_display = ('employee', 'amount', 'date', 'reason', 'created_at')
	list_filter = ('date', 'employee')
	search_fields = ('employee__first_name', 'employee__last_name', 'reason')


@admin.register(Advance)
class AdvanceAdmin(admin.ModelAdmin):
	list_display = ('employee', 'amount', 'date', 'reason', 'created_at')
	list_filter = ('date', 'employee')
	search_fields = ('employee__first_name', 'employee__last_name', 'reason')


@admin.register(Deduction)
class DeductionAdmin(admin.ModelAdmin):
	list_display = ('employee', 'amount', 'date', 'reason', 'created_at')
	list_filter = ('date', 'employee')
	search_fields = ('employee__first_name', 'employee__last_name', 'reason')

