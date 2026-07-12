from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """GET /api/health/ — Returns service status. No auth required."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'ok'})
