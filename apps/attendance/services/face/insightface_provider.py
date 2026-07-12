"""InsightFace-based face-recognition provider.

This module isolates the third-party AI libraries from the attendance service.
It is intentionally low-level: it loads the model, opens the camera, extracts
embeddings, and compares vectors. It does not know anything about attendance
rules, employee status, or duplicate-record policy.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass, asdict
from typing import Any

from .interface import AbstractFaceRecognitionProvider


@dataclass(slots=True)
class _FaceCandidate:
    """Internal helper for returning detection and match information."""

    bbox: list[float]
    confidence: float
    embedding: list[float] | None
    best_employee_id: str | None = None
    best_score: float | None = None
    ambiguous: bool = False


class InsightFaceProvider(AbstractFaceRecognitionProvider):
    """Face-recognition provider backed by InsightFace, OpenCV, and ONNX Runtime."""

    def __init__(self):
        self._initialized = False
        self._camera = None
        self._face_app = None
        self._registry: dict[str, dict[str, Any]] = {}
        self._cv2 = None

    def initialize(self):
        if self._initialized:
            return {'initialized': True, 'provider': 'insightface'}

        try:
            import cv2  # type: ignore
            import insightface  # type: ignore
            import onnxruntime  # type: ignore  # noqa: F401
            from insightface.app import FaceAnalysis  # type: ignore
        except Exception as exc:  # pragma: no cover - dependency issue is environment specific.
            raise RuntimeError(
                'InsightFace dependencies are not available. Install insightface, opencv-python-headless, and onnxruntime.'
            ) from exc

        self._cv2 = cv2
        self._face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        # Reduce detection size to 320x320 for faster CPU inference
        self._face_app.prepare(ctx_id=0, det_size=(320, 320))
        self._initialized = True
        return {'initialized': True, 'provider': 'insightface'}

    def start_camera(self, *, camera_index=0, resolution='1280x720', fps=30):
        self._ensure_initialized()
        self._ensure_cv2()
        self.stop_camera()

        width, height = self._parse_resolution(resolution)
        camera = self._cv2.VideoCapture(int(camera_index))
        if not camera.isOpened():
            raise RuntimeError(f'Unable to open camera index {camera_index}.')

        camera.set(self._cv2.CAP_PROP_FRAME_WIDTH, width)
        camera.set(self._cv2.CAP_PROP_FRAME_HEIGHT, height)
        camera.set(self._cv2.CAP_PROP_FPS, fps)
        # Set buffer size to 1 to ensure we always get the most recent frame, eliminating latency/lag
        camera.set(self._cv2.CAP_PROP_BUFFERSIZE, 1)
        self._camera = camera
        return {
            'connected': True,
            'provider': 'insightface',
            'camera_index': camera_index,
            'camera_resolution': f'{width}x{height}',
            'camera_fps': fps,
        }

    def stop_camera(self):
        if self._camera is not None:
            self._camera.release()
            self._camera = None
        return {'connected': False, 'provider': 'insightface'}

    def capture_frame(self):
        self._ensure_camera()
        success, frame = self._camera.read()
        if not success:
            raise RuntimeError('Unable to capture a frame from the camera.')
        return frame

    def detect_faces(self, frame):
        self._ensure_initialized()
        faces = self._face_app.get(frame)
        detections = []
        for face in faces:
            bbox = face.bbox.tolist() if hasattr(face.bbox, 'tolist') else list(face.bbox)
            embedding = face.embedding.tolist() if getattr(face, 'embedding', None) is not None else None
            detections.append({
                'bbox': [float(value) for value in bbox],
                'confidence': float(getattr(face, 'det_score', 0.0)),
                'embedding': embedding,
            })
        return detections

    def identify_face(self, frame=None, *, threshold=0.65):
        self._ensure_initialized()
        if frame is None:
            frame = self.capture_frame()

        detections = self.detect_faces(frame)
        candidates = []
        for detection in detections:
            match = self._match_embedding(detection.get('embedding'), threshold=threshold)
            candidates.append(_FaceCandidate(
                bbox=detection['bbox'],
                confidence=detection['confidence'],
                embedding=detection.get('embedding'),
                best_employee_id=match['employee_id'] if match else None,
                best_score=match['score'] if match else None,
                ambiguous=match.get('ambiguous', False) if match else False,
            ))

        preview = self._encode_preview(frame)
        return {
            'frame_preview': preview,
            'frame_size': {'width': int(frame.shape[1]), 'height': int(frame.shape[0])},
            'detections': [asdict(candidate) for candidate in candidates],
        }

    def register_face(self, *, employee_id, embedding, metadata=None):
        self._registry[str(employee_id)] = {
            'embedding': self._normalize_embedding(embedding),
            'metadata': metadata or {},
        }
        return {'employee_id': str(employee_id), 'registered': True}

    def update_face(self, *, employee_id, embedding, metadata=None):
        return self.register_face(employee_id=employee_id, embedding=embedding, metadata=metadata)

    def delete_face(self, employee_id):
        self._registry.pop(str(employee_id), None)
        return {'employee_id': str(employee_id), 'deleted': True}

    def cleanup(self):
        self.stop_camera()
        self._registry.clear()
        self._face_app = None
        self._initialized = False
        return {'cleaned_up': True}

    def list_registered_faces(self):
        return {employee_id: entry['embedding'].tolist() for employee_id, entry in self._registry.items()}

    def _match_embedding(self, embedding, *, threshold):
        if embedding is None or not self._registry:
            return None

        query = self._normalize_embedding(embedding)
        scores = []
        for employee_id, entry in self._registry.items():
            score = self._cosine_similarity(query, entry['embedding'])
            scores.append((employee_id, score))

        scores.sort(key=lambda item: item[1], reverse=True)
        best_employee_id, best_score = scores[0]
        if best_score < threshold:
            return None

        ambiguous = len(scores) > 1 and math.isclose(best_score, scores[1][1], abs_tol=0.02)
        return {
            'employee_id': best_employee_id,
            'score': float(best_score),
            'ambiguous': ambiguous,
        }

    def _normalize_embedding(self, embedding):
        import numpy as np

        vector = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm

    def _cosine_similarity(self, left, right):
        import numpy as np

        left_vector = self._normalize_embedding(left)
        right_vector = self._normalize_embedding(right)
        return float(np.dot(left_vector, right_vector))

    def _encode_preview(self, frame):
        self._ensure_cv2()
        success, buffer = self._cv2.imencode('.jpg', frame)
        if not success:
            return None
        return base64.b64encode(buffer.tobytes()).decode('utf-8')

    def _parse_resolution(self, resolution):
        try:
            width, height = resolution.lower().split('x', 1)
            return int(width), int(height)
        except Exception:
            return 1280, 720

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def _ensure_camera(self):
        self._ensure_initialized()
        if self._camera is None:
            raise RuntimeError('Camera is not active.')

    def _ensure_cv2(self):
        if self._cv2 is None:
            self.initialize()
