"""Face-recognition service used by attendance and employee enrollment endpoints.

The service owns business orchestration: it loads employees from the database,
keeps the provider registry in sync, applies cooldowns, and translates provider
results into application-level statuses. It never creates attendance records.
"""

from __future__ import annotations

import threading
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.attendance.models import AttendanceRule, AttendanceRecord
from apps.employees.models import Employee

from .insightface_provider import InsightFaceProvider


class FaceRecognitionService:
    """Coordinates camera access, face registration, and face identification."""

    def __init__(self, provider=None):
        self.provider = provider or InsightFaceProvider()
        self._lock = threading.RLock()
        self._cooldowns: dict[str, timezone.datetime] = {}
        self._synced_employee_ids: set[str] = set()
        self._enrollment_sessions: dict[str, dict] = {}

    def initialize(self):
        with self._lock:
            return self.provider.initialize()

    def start_camera(self, rule: AttendanceRule | None = None):
        rule = rule or AttendanceRule.get_active_rule()
        if rule is None:
            raise RuntimeError('No attendance rule is configured.')

        with self._lock:
            self.initialize()
            state = self.provider.start_camera(
                camera_index=rule.camera_index,
                resolution=rule.camera_resolution,
                fps=rule.camera_fps,
            )
            self._sync_registry()
            return state

    def stop_camera(self):
        with self._lock:
            return self.provider.stop_camera()

    def cleanup(self):
        with self._lock:
            self._cooldowns.clear()
            self._synced_employee_ids.clear()
            return self.provider.cleanup()

    def get_camera_status(self):
        return {
            'connected': getattr(self.provider, '_camera', None) is not None,
            'provider': 'insightface',
            'faces_loaded': len(self.provider.list_registered_faces()) if hasattr(self.provider, 'list_registered_faces') else 0,
        }

    def register_face(self, employee, *, capture_count=5):
        if getattr(self.provider, '_camera', None) is None:
            rule = AttendanceRule.get_active_rule()
            if rule is None:
                self.provider.initialize()
                self.provider.start_camera(camera_index=0, resolution='1280x720', fps=30)
            else:
                self.start_camera(rule)
        embedding = self._capture_embedding(capture_count=capture_count)
        metadata = {'employee_code': employee.employee_code, 'registered_at': timezone.now().isoformat()}

        with transaction.atomic():
            employee.face_registered = True
            if employee.face_registered_at is None:
                employee.face_registered_at = timezone.now()
            employee.face_last_updated = timezone.now()
            employee.face_embedding = embedding.tolist()
            employee.save(update_fields=['face_registered', 'face_embedding', 'face_registered_at', 'face_last_updated', 'updated_at'])
            self.provider.register_face(employee_id=employee.id, embedding=embedding.tolist(), metadata=metadata)
            self._synced_employee_ids.add(str(employee.id))
        return employee

    def update_face(self, employee, *, capture_count=5):
        if getattr(self.provider, '_camera', None) is None:
            rule = AttendanceRule.get_active_rule()
            if rule is None:
                self.provider.initialize()
                self.provider.start_camera(camera_index=0, resolution='1280x720', fps=30)
            else:
                self.start_camera(rule)
        embedding = self._capture_embedding(capture_count=capture_count)
        metadata = {'employee_code': employee.employee_code, 'updated_at': timezone.now().isoformat()}

        with transaction.atomic():
            employee.face_registered = True
            if employee.face_registered_at is None:
                employee.face_registered_at = timezone.now()
            employee.face_last_updated = timezone.now()
            employee.face_embedding = embedding.tolist()
            employee.save(update_fields=['face_registered', 'face_embedding', 'face_registered_at', 'face_last_updated', 'updated_at'])
            self.provider.update_face(employee_id=employee.id, embedding=embedding.tolist(), metadata=metadata)
            self._synced_employee_ids.add(str(employee.id))
        return employee

    def delete_face(self, employee):
        with transaction.atomic():
            self.provider.delete_face(employee.id)
            employee.face_registered = False
            employee.face_embedding = None
            employee.face_registered_at = None
            employee.face_last_updated = None
            employee.save(update_fields=['face_registered', 'face_embedding', 'face_registered_at', 'face_last_updated', 'updated_at'])
            self._synced_employee_ids.discard(str(employee.id))
        return employee

    def identify_faces(self, *, rule: AttendanceRule | None = None):
        rule = rule or AttendanceRule.get_active_rule()
        if rule is None:
            raise RuntimeError('No attendance rule is configured.')

        if getattr(self.provider, '_camera', None) is None:
            self.start_camera(rule)

        if not getattr(self.provider, '_camera', None):
            raise RuntimeError('Camera is not active.')

        snapshot = self.provider.identify_face(threshold=rule.face_confidence_threshold)
        detections = snapshot.get('detections', [])
        preview = snapshot.get('frame_preview')

        recognized = []
        ambiguous = []
        unknown_faces = []

        for detection in detections:
            employee = self._employee_for_detection(detection)
            if employee is None:
                unknown_faces.append(detection)
                continue

            if not self._is_employee_eligible(employee):
                continue

            if self._is_in_cooldown(employee.id, rule.recognition_cooldown_seconds):
                continue

            score = detection.get('best_score') or 0.0
            if detection.get('ambiguous'):
                ambiguous.append({'employee_id': str(employee.id), 'employee_name': self._employee_name(employee), 'confidence': score})
                continue

            today = timezone.localdate()
            already_attended = AttendanceRecord.objects.filter(employee=employee, date=today).exists()

            recognized.append({
                'employee_id': str(employee.id),
                'employee_name': self._employee_name(employee),
                'employee_code': employee.employee_code,
                'confidence': score,
                'bbox': detection.get('bbox'),
                'already_attended': already_attended,
            })
            self._cooldowns[str(employee.id)] = timezone.now()

            if not rule.allow_multiple_face_detection:
                break

        status = 'waiting'
        message = 'No face detected.' if not detections else 'Face detected.'
        if recognized:
            status = 'recognized'
            message = 'Face recognized.'
        elif ambiguous:
            status = 'ambiguous'
            message = 'Multiple employees matched this face.'
        elif unknown_faces:
            status = 'unknown'
            message = 'Unknown person.'

        return {
            'status': status,
            'message': message,
            'preview_frame': preview,
            'recognized_faces': recognized,
            'ambiguous_faces': ambiguous,
            'unknown_faces': unknown_faces,
            'faces_detected': len(detections),
        }

    def _employee_for_detection(self, detection):
        employee_id = detection.get('best_employee_id')
        if not employee_id:
            return None
        return Employee.objects.filter(id=employee_id).first()

    def _is_employee_eligible(self, employee):
        return employee.status == Employee.Status.ACTIVE and employee.face_registered and employee.face_embedding is not None

    def _is_in_cooldown(self, employee_id, cooldown_seconds):
        last_seen = self._cooldowns.get(str(employee_id))
        if last_seen is None:
            return False
        return timezone.now() - last_seen < timedelta(seconds=cooldown_seconds)

    def _employee_name(self, employee):
        return f'{employee.first_name} {employee.last_name}'.strip()

    def _capture_embedding(self, *, capture_count=5):
        import numpy as np

        self.initialize()
        if not getattr(self.provider, '_camera', None):
            raise RuntimeError('Camera is not active.')

        embeddings = []
        attempts = 0
        while len(embeddings) < capture_count and attempts < capture_count * 4:
            attempts += 1
            frame = self.provider.capture_frame()
            detections = self.provider.detect_faces(frame)
            if not detections:
                continue
            if len(detections) > 1:
                raise RuntimeError('Multiple faces detected during enrollment. Ask the employee to stand alone.')

            embedding = detections[0].get('embedding')
            if embedding:
                embeddings.append(np.asarray(embedding, dtype=np.float32))

        if not embeddings:
            raise RuntimeError('No face was captured during enrollment.')

        averaged = np.mean(np.stack(embeddings), axis=0)
        norm = np.linalg.norm(averaged)
        if norm == 0:
            raise RuntimeError('Failed to generate a usable face embedding.')
        return averaged / norm

    def enroll_step(self, employee):
        import numpy as np
        
        self.initialize()
        if not getattr(self.provider, '_camera', None):
            rule = AttendanceRule.get_active_rule()
            if rule is None:
                self.provider.start_camera(camera_index=0, resolution='1280x720', fps=30)
            else:
                self.start_camera(rule)
                
        frame = self.provider.capture_frame()
        detections = self.provider.detect_faces(frame)
        preview = self.provider._encode_preview(frame)
        
        session = self._enrollment_sessions.setdefault(str(employee.id), {'embeddings': []})
        message = 'Looking for face...'
        status = 'waiting'
        
        if detections:
            if len(detections) > 1:
                message = 'Multiple faces detected. Ask the employee to stand alone.'
                status = 'error'
            else:
                embedding = detections[0].get('embedding')
                if embedding:
                    session['embeddings'].append(np.asarray(embedding, dtype=np.float32))
                    message = f"Captured {len(session['embeddings'])}/5 frames"
                    status = 'capturing'
                    
        enrolled = False
        if len(session['embeddings']) >= 5:
            averaged = np.mean(np.stack(session['embeddings']), axis=0)
            norm = np.linalg.norm(averaged)
            if norm > 0:
                final_embedding = averaged / norm
                with transaction.atomic():
                    employee.face_registered = True
                    if employee.face_registered_at is None:
                        employee.face_registered_at = timezone.now()
                    employee.face_last_updated = timezone.now()
                    employee.face_embedding = final_embedding.tolist()
                    employee.save(update_fields=['face_registered', 'face_embedding', 'face_registered_at', 'face_last_updated', 'updated_at'])
                    self.provider.register_face(employee_id=employee.id, embedding=employee.face_embedding, metadata={'employee_code': employee.employee_code})
                    self._synced_employee_ids.add(str(employee.id))
                enrolled = True
                message = 'Face successfully registered!'
                status = 'success'
            self._enrollment_sessions.pop(str(employee.id), None)
            
        return {
            'preview_frame': preview,
            'message': message,
            'status': status,
            'enrolled': enrolled,
            'captured_count': len(session.get('embeddings', [])),
        }

    def _sync_registry(self):
        current_employee_ids = {str(employee.id) for employee in Employee.objects.filter(face_registered=True, face_embedding__isnull=False)}
        for employee in Employee.objects.filter(face_registered=True, face_embedding__isnull=False):
            self.provider.update_face(employee_id=employee.id, embedding=employee.face_embedding, metadata={'employee_code': employee.employee_code})

        stale_employee_ids = self._synced_employee_ids - current_employee_ids
        for employee_id in stale_employee_ids:
            self.provider.delete_face(employee_id)

        self._synced_employee_ids = current_employee_ids


def _build_provider():
    return InsightFaceProvider()


face_recognition_service = FaceRecognitionService(provider=_build_provider())
