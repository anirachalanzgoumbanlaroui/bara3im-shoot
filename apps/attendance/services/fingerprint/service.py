"""Fingerprint service facade used by Django views and employee enrollment APIs."""

from django.conf import settings

from apps.employees.models import Employee

from .mock_provider import MockFingerprintProvider


class FingerprintService:
    """Wraps a pluggable provider so hardware-specific logic stays isolated."""

    def __init__(self, provider=None):
        self.provider = provider or MockFingerprintProvider()

    def connect(self):
        return self.provider.connect()

    def disconnect(self):
        return self.provider.disconnect()

    def enroll_employee(self, *, employee, samples=None, fingerprint_sample=None):
        self._ensure_connected()
        template = self.provider.enroll(
            employee_id=employee.id,
            samples=samples,
            fingerprint_sample=fingerprint_sample,
        )
        employee.fingerprint_registered = True
        employee.fingerprint_template_id = template['template_id']
        employee.fingerprint_registered_at = template['created_at']
        employee.save(update_fields=['fingerprint_registered', 'fingerprint_template_id', 'fingerprint_registered_at', 'updated_at'])
        return template

    def replace_employee_fingerprint(self, *, employee, samples=None, fingerprint_sample=None):
        self._ensure_connected()
        if employee.fingerprint_template_id:
            try:
                self.provider.delete_template(employee.fingerprint_template_id)
            except Exception:
                pass
        return self.enroll_employee(employee=employee, samples=samples, fingerprint_sample=fingerprint_sample)

    def delete_employee_fingerprint(self, employee):
        self._ensure_connected()
        if not employee.fingerprint_template_id:
            raise ValueError('Employee does not have a registered fingerprint.')
        self.provider.delete_template(employee.fingerprint_template_id)
        employee.fingerprint_registered = False
        employee.fingerprint_template_id = None
        employee.fingerprint_registered_at = None
        employee.save(update_fields=['fingerprint_registered', 'fingerprint_template_id', 'fingerprint_registered_at', 'updated_at'])
        return {'deleted': True}

    def identify_sample(self, fingerprint_sample):
        self._ensure_connected()
        return self.provider.identify(fingerprint_sample=fingerprint_sample)

    def list_templates(self):
        return self.provider.list_templates()

    def is_connected(self):
        return getattr(self.provider, '_connected', False)

    def _ensure_connected(self):
        if not self.is_connected():
            self.connect()


def _build_provider():
    provider_name = getattr(settings, 'FINGERPRINT_PROVIDER', 'mock')
    if provider_name == 'mock':
        return MockFingerprintProvider()
    return MockFingerprintProvider()


fingerprint_service = FingerprintService(provider=_build_provider())