"""In-memory fingerprint provider used for development and validation."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone as dt_timezone

from .providers import AbstractFingerprintProvider


class MockFingerprintProvider(AbstractFingerprintProvider):
    """Simulates enrollment and matching without real hardware."""

    def __init__(self):
        self._connected = False
        self._templates = {}

    def connect(self):
        self._connected = True
        return {'connected': True, 'provider': 'mock'}

    def disconnect(self):
        self._connected = False
        return {'connected': False, 'provider': 'mock'}

    def enroll(self, *, employee_id, samples=None, fingerprint_sample=None, template_id=None):
        self._assert_connected()
        captures = list(samples or [])
        if fingerprint_sample:
            captures.append(fingerprint_sample)
        normalized = [str(capture).strip() for capture in captures if str(capture).strip()]
        if not normalized:
            raise ValueError('At least one fingerprint capture is required.')
        if len(set(normalized)) > 1:
            raise ValueError('All fingerprint captures must match during enrollment.')
        if len(normalized) < 3:
            raise ValueError('Enrollment requires the same finger to be captured at least three times.')

        sample_hash = hashlib.sha256(normalized[0].encode('utf-8')).hexdigest()
        template_id = template_id or f'tpl_{uuid.uuid4().hex}'
        template = {
            'template_id': template_id,
            'employee_id': str(employee_id),
            'sample_hash': sample_hash,
            'capture_count': len(normalized),
            'created_at': datetime.now(dt_timezone.utc),
        }
        self._templates[template_id] = template
        return template

    def identify(self, *, fingerprint_sample=None):
        self._assert_connected()
        if not fingerprint_sample:
            raise ValueError('A fingerprint sample is required for identification.')

        sample_hash = hashlib.sha256(str(fingerprint_sample).strip().encode('utf-8')).hexdigest()
        for template in self._templates.values():
            if template['sample_hash'] == sample_hash:
                return template
        return None

    def delete_template(self, template_id):
        self._assert_connected()
        self._templates.pop(template_id, None)
        return {'deleted': True, 'template_id': template_id}

    def list_templates(self):
        self._assert_connected()
        return list(self._templates.values())

    def _assert_connected(self):
        if not self._connected:
            raise RuntimeError('Fingerprint provider is not connected.')