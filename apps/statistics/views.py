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
        tf, _, s_date, e_date = self._get_params(request)
        data = StatisticsService.get_employee_profile_stats(employee_id, tf, s_date, e_date)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='fifa-reveal')
    def fifa_reveal(self, request):
        category = request.query_params.get('category', 'photographer')
        tf, loc, s_date, e_date = self._get_params(request)

        if category == 'photographer':
            stats = StatisticsService.get_role_stats('photographer', tf, loc, s_date, e_date)
            best = stats['best_ever']
            card_data = {
                'rating': 98,
                'badge': '🐐',
                'title': 'Best Photographer',
                'name': best['name'] if best else 'Ahmed Al-Shoot',
                'role': 'Photographer',
                'avatar': best['avatar'] if best else None,
                'avg_pictures': best['avg_pictures'] if best else 145.5,
                'total_pictures': best['total_pictures'] if best else 1250,
                'awards_count': 5,
                'winning_streak': 8,
                'current_rank': 1,
            }
        elif category == 'clown':
            stats = StatisticsService.get_role_stats('clown', tf, loc, s_date, e_date)
            best = stats['best_ever']
            card_data = {
                'rating': 96,
                'badge': '🤡',
                'title': 'Best Clown',
                'name': best['name'] if best else 'Karim Al-Fun',
                'role': 'Clown',
                'avatar': best['avatar'] if best else None,
                'avg_pictures': best['avg_pictures'] if best else 138.0,
                'total_pictures': best['total_pictures'] if best else 1180,
                'awards_count': 4,
                'winning_streak': 6,
                'current_rank': 1,
            }
        elif category == 'seller':
            stats = StatisticsService.get_seller_stats(tf, loc, s_date, e_date)
            best = stats['best_seller_ever']
            card_data = {
                'rating': 97,
                'badge': '💰',
                'title': 'Best Seller',
                'name': best['name'] if best else 'Mustapha Money',
                'role': 'Seller',
                'avatar': best['avatar'] if best else None,
                'avg_pictures': f"{best['avg_revenue']} DA" if best else '4,500 DA',
                'total_pictures': f"{best['total_revenue']} DA" if best else '45,000 DA',
                'awards_count': 6,
                'winning_streak': 10,
                'current_rank': 1,
            }
        else: # couple
            stats = StatisticsService.get_couple_stats(tf, loc, s_date, e_date)
            best = stats['best_couple_ever']
            card_data = {
                'rating': 99,
                'badge': '👑',
                'title': 'Best Couple',
                'name': best['team_name'] if best else 'Ahmed & Karim',
                'role': 'Photographer + Clown',
                'avatar': None,
                'avg_pictures': best['avg_pictures'] if best else 152.0,
                'total_pictures': best['total_pictures'] if best else 2100,
                'awards_count': 8,
                'winning_streak': 12,
                'current_rank': 1,
            }

        return Response(card_data)
