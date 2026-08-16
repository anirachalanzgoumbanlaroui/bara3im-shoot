from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .services import StatisticsService


class StatisticsViewSet(viewsets.ViewSet):
    """
    Unified Statistics Center ViewSet.
    Fast, cached, and automatically aggregated statistics for Bara3im Shoot.
    """
    permission_classes = [IsAuthenticated]

    def _get_params(self, request):
        tf = request.query_params.get('time_filter', 'this_month')
        loc = request.query_params.get('location')
        s_date = request.query_params.get('start_date')
        e_date = request.query_params.get('end_date')
        return tf, loc, s_date, e_date

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_overview(tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='photographers')
    def photographers(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_role_stats('photographer', tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='clowns')
    def clowns(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_role_stats('clown', tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='sellers')
    def sellers(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_seller_stats(tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='couples')
    def couples(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_couple_stats(tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='attendance')
    def attendance(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_attendance_stats(tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='financial')
    def financial(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_financial_stats(tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='comparisons')
    def comparisons(self, request):
        tf, _, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_comparison_stats(tf, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='awards')
    def awards(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_awards_stats(tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='insights')
    def insights(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_insights(tf, loc, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='employee-profile/(?P<employee_id>[^/.]+)')
    def employee_profile(self, request, employee_id=None):
        """Legacy basic profile — kept for compatibility."""
        tf, _, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_employee_profile_stats(employee_id, tf, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='employee-analytics/(?P<employee_id>[^/.]+)')
    def employee_analytics(self, request, employee_id=None):
        """
        Comprehensive employee analytics profile.
        Returns timeline, partners list, location split, company comparison,
        consistency metric, and performance trend — all pre-aggregated by Django.

        Query params:
            time_filter : today|this_week|this_month|last_month|this_year|all_time|custom
            location    : location UUID (optional)
            start_date  : YYYY-MM-DD (required when time_filter=custom)
            end_date    : YYYY-MM-DD (required when time_filter=custom)
        """
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_employee_analytics(employee_id, tf, loc, s_date, e_date)
        if 'error' in data:
            return Response(data, status=404)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='nadjib')
    def nadjib(self, request):
        tf, loc, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_nadjib_winner(tf, loc, s_date, e_date)
        return Response(data or {})

    @action(detail=False, methods=['get'], url_path='fifa-reveal')
    def fifa_reveal(self, request):
        category = request.query_params.get('category', 'nadjib')
        tf, loc, s_date, e_date = self._get_params(request)
        card_data = StatisticsService.get_fifa_reveal(category, tf, loc, s_date, e_date)
        return Response(card_data)
