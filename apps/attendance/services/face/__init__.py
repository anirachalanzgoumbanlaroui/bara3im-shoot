"""Face recognition provider implementations used by the attendance service."""

from .insightface_provider import InsightFaceProvider
from .interface import AbstractFaceRecognitionProvider
from .service import FaceRecognitionService, face_recognition_service
