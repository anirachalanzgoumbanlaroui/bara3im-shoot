"""Abstract face-recognition provider contract.

The attendance service depends on this interface instead of a concrete AI engine
so InsightFace can be replaced later without touching business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class AbstractFaceRecognitionProvider(ABC):
    """Hardware and model abstraction for face-recognition engines."""

    @abstractmethod
    def initialize(self):
        """Load model weights and prepare the inference runtime."""
        raise NotImplementedError

    @abstractmethod
    def start_camera(self, *, camera_index=0, resolution='1280x720', fps=30):
        """Open the local camera device used for attendance capture."""
        raise NotImplementedError

    @abstractmethod
    def stop_camera(self):
        """Release the camera device."""
        raise NotImplementedError

    @abstractmethod
    def capture_frame(self):
        """Capture a single frame from the active camera."""
        raise NotImplementedError

    @abstractmethod
    def detect_faces(self, frame):
        """Detect faces and return bounding boxes plus embeddings."""
        raise NotImplementedError

    @abstractmethod
    def identify_face(self, frame=None, *, threshold=0.65):
        """Return recognition candidates for the provided frame."""
        raise NotImplementedError

    @abstractmethod
    def register_face(self, *, employee_id, embedding, metadata=None):
        """Store an embedding in the provider's fast lookup index."""
        raise NotImplementedError

    @abstractmethod
    def update_face(self, *, employee_id, embedding, metadata=None):
        """Replace an existing embedding in the provider's index."""
        raise NotImplementedError

    @abstractmethod
    def delete_face(self, employee_id):
        """Remove an embedding from the provider's index."""
        raise NotImplementedError

    @abstractmethod
    def cleanup(self):
        """Release resources and reset the provider state."""
        raise NotImplementedError
