"""Shared API exception handling for consistent JSON responses."""

from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(response.data, dict):
        # Top-level 'detail' key (e.g. authentication errors, permission errors)
        detail = response.data.get('detail')

        # Field-level validation errors (e.g. unique constraints, required fields)
        field_errors = {k: v for k, v in response.data.items() if k != 'detail'}

        payload = {'detail': detail or 'Request failed.'}
        if field_errors:
            payload['errors'] = field_errors
    else:
        payload = {'detail': 'Request failed.'}

    response.data = payload
    return response