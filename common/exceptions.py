"""Shared API exception handling for consistent JSON responses."""

from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data.get('detail') if isinstance(response.data, dict) else None
    if detail is None and isinstance(response.data, dict):
        detail = 'Request failed.'

    payload = {'detail': detail}
    if isinstance(response.data, dict) and len(response.data) > 1:
        payload['errors'] = response.data
    elif isinstance(response.data, dict) and detail is None:
        payload['errors'] = response.data

    response.data = payload
    return response