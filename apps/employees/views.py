from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination

from django.utils import timezone

from apps.attendance.models import AttendanceLog, AttendanceRecord
from apps.attendance.services.fingerprint.service import fingerprint_service
from apps.attendance.services.face.service import face_recognition_service

from .models import Employee, Advance, Deduction
from .serializers import EmployeeSerializer, EmployeeListSerializer


class EmployeePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class IsAdminOrSelf(permissions.BasePermission):
    """
    Custom permission:
    - Admins can do anything.
    - Employees can only view their own profile.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'role', '') == 'admin':
            return True
        if view.action == 'me':
            return True
        if view.action in ['retrieve', 'update', 'partial_update']:
            return True
        return False

    def has_object_permission(self, request, view, obj):
        if getattr(request.user, 'role', '') == 'admin':
            return True
        return obj.user == request.user


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows employees to be viewed or edited.
    Includes filtering, searching, and ordering capabilities.
    """
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAdminOrSelf]
    pagination_class = EmployeePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = ['role', 'status']
    search_fields = ['first_name', 'last_name', 'employee_code', 'phone_number']
    ordering_fields = ['first_name', 'last_name', 'hiring_date', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list' and getattr(self.request.user, 'role', '') == 'admin':
            return EmployeeListSerializer
        return super().get_serializer_class()

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Endpoint for an employee to get their own profile."""
        try:
            employee = Employee.objects.get(user=request.user)
            serializer = self.get_serializer(employee)
            return Response(serializer.data)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee profile not found."}, status=404)

    # ── Admin: Lightweight list for the advance picker ────────────────────────

    @action(detail=False, methods=['get'], url_path='list-for-advance',
            permission_classes=[permissions.IsAuthenticated])
    def list_for_advance(self, request):
        """
        Admin: lightweight employee list for advance picker.
        GET /api/employees/list-for-advance/
        """
        if getattr(request.user, 'role', '') != 'admin':
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        employees = Employee.objects.filter(status=Employee.Status.ACTIVE).values(
            'id', 'first_name', 'last_name', 'employee_code', 'role'
        )
        return Response(list(employees))

    # ── Admin: Apply Advance ──────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='advance',
            permission_classes=[permissions.IsAuthenticated])
    def apply_advance(self, request, pk=None):
        """
        Admin endpoint: record an advance deduction for an employee.
        POST /api/employees/{id}/advance/
        Body: { "amount": 500, "reason": "optional" }
        """
        if getattr(request.user, 'role', '') != 'admin':
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        employee = self.get_object()
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')

        if not amount:
            return Response({'detail': 'amount is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({'detail': 'amount must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

        advance = Advance.objects.create(
            employee=employee,
            amount=amount,
            reason=reason or f'Advance applied by admin on {timezone.now().date()}',
        )

        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='advance_applied',
            description=f'Advance of {amount} DA applied. Reason: {reason or "N/A"}',
        )

        # Notify the employee
        try:
            from apps.notifications.services import notification_service
            notification_service.notify_user(
                user=employee.user,
                title='Advance Applied',
                description=f'An advance of {amount:.2f} DA has been deducted from your next payout. Reason: {advance.reason}',
                category='payroll',
                icon='payroll',
                reference_id=str(advance.id)
            )
        except Exception as e:
            # Prevent failure to notify from breaking the response
            pass

        return Response({
            'id': str(advance.id),
            'employee': str(employee.id),
            'employee_name': f'{employee.first_name} {employee.last_name}',
            'amount': float(advance.amount),
            'reason': advance.reason,
            'date': str(advance.date),
        }, status=status.HTTP_201_CREATED)

    # ── Standard employee CRUD actions ────────────────────────────────────────

    @action(detail=True, methods=['get'], url_path='fingerprint/status')
    def fingerprint_status(self, request, pk=None):
        employee = self.get_object()
        self.check_object_permissions(request, employee)
        return Response({
            'employee_id': str(employee.id),
            'fingerprint_registered': employee.fingerprint_registered,
            'fingerprint_template_id': employee.fingerprint_template_id,
            'fingerprint_registered_at': employee.fingerprint_registered_at,
        })

    @action(detail=True, methods=['get'], url_path='face/status')
    def face_status(self, request, pk=None):
        employee = self.get_object()
        self.check_object_permissions(request, employee)
        return Response({
            'employee_id': str(employee.id),
            'face_registered': employee.face_registered,
            'face_registered_at': employee.face_registered_at,
            'face_last_updated': employee.face_last_updated,
        })

    @action(detail=True, methods=['post'], url_path='fingerprint/enroll')
    def enroll_fingerprint(self, request, pk=None):
        employee = self.get_object()
        if employee.status != Employee.Status.ACTIVE:
            return Response({'detail': 'Inactive employees cannot enroll fingerprints.'}, status=status.HTTP_400_BAD_REQUEST)

        payload = request.data
        samples = payload.get('samples')
        sample = payload.get('fingerprint_sample')

        enrollment = fingerprint_service.enroll_employee(
            employee=employee,
            samples=samples,
            fingerprint_sample=sample,
        )

        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='fingerprint_enrolled',
            description=f"Fingerprint enrolled with template {enrollment['template_id']}."
        )

        return Response(self.get_serializer(employee).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='fingerprint/replace')
    def replace_fingerprint(self, request, pk=None):
        employee = self.get_object()
        samples = request.data.get('samples')
        sample = request.data.get('fingerprint_sample')

        enrollment = fingerprint_service.replace_employee_fingerprint(
            employee=employee,
            samples=samples,
            fingerprint_sample=sample,
        )

        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='fingerprint_replaced',
            description=f"Fingerprint replaced with template {enrollment['template_id']}."
        )

        return Response(self.get_serializer(employee).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path='fingerprint/delete')
    def delete_fingerprint(self, request, pk=None):
        employee = self.get_object()
        fingerprint_service.delete_employee_fingerprint(employee)
        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='fingerprint_deleted',
            description='Fingerprint template removed from employee profile.'
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='face/register')
    def register_face(self, request, pk=None):
        employee = self.get_object()
        if employee.status != Employee.Status.ACTIVE:
            return Response({'detail': 'Inactive employees cannot enroll a face.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            face_recognition_service.register_face(employee)
        except RuntimeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='face_registered',
            description='Face profile registered from the employee profile.'
        )
        return Response(self.get_serializer(employee).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='face/enroll_step')
    def enroll_face_step(self, request, pk=None):
        employee = self.get_object()
        if employee.status != Employee.Status.ACTIVE:
            return Response({'detail': 'Inactive employees cannot enroll a face.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            snapshot = face_recognition_service.enroll_step(employee)
            if snapshot.get('enrolled'):
                AttendanceLog.objects.create(
                    employee=employee,
                    admin=request.user,
                    action='face_registered',
                    description='Face profile registered from live enrollment stream.'
                )
            return Response(snapshot, status=status.HTTP_200_OK)
        except RuntimeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['put'], url_path='face/update')
    def update_face(self, request, pk=None):
        employee = self.get_object()

        try:
            face_recognition_service.update_face(employee)
        except RuntimeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='face_updated',
            description='Face profile replaced from the employee profile.'
        )
        return Response(self.get_serializer(employee).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path='face/delete')
    def delete_face(self, request, pk=None):
        employee = self.get_object()
        face_recognition_service.delete_face(employee)
        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='face_deleted',
            description='Face profile removed from employee profile.'
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Admin: Apply Late Penalty to an Attendance Record ─────────────────────────

class AttendanceLatePenaltyView(APIView):
    """
    Admin-only endpoint to apply a manual late penalty deduction.

    POST /api/employees/attendance/{record_id}/late-penalty/
    Body: { "amount": 100, "reason": "optional" }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, record_id):
        if getattr(request.user, 'role', '') != 'admin':
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            record = AttendanceRecord.objects.select_related('employee').get(pk=record_id)
        except AttendanceRecord.DoesNotExist:
            return Response({'detail': 'Attendance record not found.'}, status=status.HTTP_404_NOT_FOUND)

        if record.status != 'late':
            return Response(
                {'detail': 'Penalty can only be applied to late attendance records.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = request.data.get('amount')
        reason = request.data.get('reason', '')

        if not amount:
            return Response({'detail': 'amount is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({'detail': 'amount must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

        employee = record.employee

        deduction = Deduction.objects.create(
            employee=employee,
            amount=amount,
            reason=reason or f'Late penalty for {record.date} ({record.minutes_late} min late)',
        )

        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='late_penalty_applied',
            description=f'Late penalty of {amount} DA for record {record_id}. Reason: {reason or "N/A"}',
        )

        # Notify the employee
        try:
            from apps.notifications.services import notification_service
            notification_service.notify_user(
                user=employee.user,
                title='Late Penalty Applied',
                description=f'A late penalty of {amount:.2f} DA has been applied for your check-in on {record.date} ({record.minutes_late} min late).',
                category='payroll',
                icon='payroll',
                reference_id=str(deduction.id)
            )
        except Exception as e:
            # Prevent failure to notify from breaking the response
            pass

        return Response({
            'deduction_id': str(deduction.id),
            'employee': str(employee.id),
            'employee_name': f'{employee.first_name} {employee.last_name}',
            'amount': float(deduction.amount),
            'reason': deduction.reason,
            'attendance_record': str(record.id),
            'date': str(record.date),
            'minutes_late': record.minutes_late,
        }, status=status.HTTP_201_CREATED)
