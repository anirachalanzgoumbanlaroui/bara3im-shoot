"""Fingerprint provider abstractions used by the attendance service layer."""

from abc import ABC, abstractmethod


class AbstractFingerprintProvider(ABC):
    """Abstract hardware provider so the scanner implementation can be swapped later."""

    @abstractmethod
    def connect(self):
        raise NotImplementedError

    @abstractmethod
    def disconnect(self):
        raise NotImplementedError

    @abstractmethod
    def enroll(self, *, employee_id, samples=None, fingerprint_sample=None, template_id=None):
        raise NotImplementedError

    @abstractmethod
    def identify(self, *, fingerprint_sample=None):
        raise NotImplementedError

    @abstractmethod
    def delete_template(self, template_id):
        raise NotImplementedError

    @abstractmethod
    def list_templates(self):
        raise NotImplementedError