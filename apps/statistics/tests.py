from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.daily_sessions.models import Location, WorkDay, DailyTeam, DailyEmployeePerformance
from apps.employees.models import Employee
from apps.statistics.services import StatisticsService

User = get_user_model()

class StatisticsTimelineTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin_stats', password='password')
        self.photo_user = User.objects.create_user(username='photographer_stats', password='password', role='photographer')
        self.clown_user = User.objects.create_user(username='clown_stats', password='password', role='clown')

        self.loc_ardis = Location.objects.create(name='ARDIS', icon='store', color_hex='#1565C0')
        self.loc_sabllet = Location.objects.create(name='SABLLET', icon='park', color_hex='#4CAF50')

        self.photographer = Employee.objects.create(
            user=self.photo_user,
            first_name='Karim',
            last_name='Photo',
            role='photographer',
            hiring_date='2026-01-01',
        )
        self.clown = Employee.objects.create(
            user=self.clown_user,
            first_name='Anis',
            last_name='Clown',
            role='clown',
            hiring_date='2026-01-01',
        )

    def test_generate_gap_filled_timeline_empty(self):
        res = StatisticsService._generate_gap_filled_timeline({})
        self.assertEqual(res, [])

    def test_generate_gap_filled_timeline_single_day(self):
        data = {'2026-09-03': 75}
        res = StatisticsService._generate_gap_filled_timeline(data, value_key='photos')
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['date'], '2026-09-03')
        self.assertEqual(res[0]['photos'], 75)
        self.assertTrue(res[0]['worked'])

    def test_generate_gap_filled_timeline_with_gap(self):
        data = {
            '2026-09-03': {'photos': 75, 'gross_earnings': 3750.0},
            '2026-09-05': {'photos': 62, 'gross_earnings': 3100.0},
        }
        res = StatisticsService._generate_gap_filled_timeline(data, value_key='photos')
        self.assertEqual(len(res), 3)

        # Day 1: 2026-09-03 (Worked)
        self.assertEqual(res[0]['date'], '2026-09-03')
        self.assertEqual(res[0]['photos'], 75)
        self.assertTrue(res[0]['worked'])

        # Day 2: 2026-09-04 (Gap / Off day - 0 photos, worked=False)
        self.assertEqual(res[1]['date'], '2026-09-04')
        self.assertEqual(res[1]['photos'], 0)
        self.assertFalse(res[1]['worked'])

        # Day 3: 2026-09-05 (Worked)
        self.assertEqual(res[2]['date'], '2026-09-05')
        self.assertEqual(res[2]['photos'], 62)
        self.assertTrue(res[2]['worked'])

    def test_location_scoping_in_analytics(self):
        # Workday 1: ARDIS on 2026-09-01
        wd1 = WorkDay.objects.create(
            location=self.loc_ardis,
            date='2026-09-01',
            status='completed',
            created_by=self.admin,
        )
        team1 = DailyTeam.objects.create(work_day=wd1, photographer=self.photographer, clown=self.clown, team_photo_count=50)
        DailyEmployeePerformance.objects.filter(work_day=wd1, employee=self.photographer).update(photo_count=50)

        # Workday 2: SABLLET on 2026-09-02
        wd2 = WorkDay.objects.create(
            location=self.loc_sabllet,
            date='2026-09-02',
            status='completed',
            created_by=self.admin,
        )
        team2 = DailyTeam.objects.create(work_day=wd2, photographer=self.photographer, clown=self.clown, team_photo_count=70)
        DailyEmployeePerformance.objects.filter(work_day=wd2, employee=self.photographer).update(photo_count=70)

        # Workday 3: ARDIS on 2026-09-03
        wd3 = WorkDay.objects.create(
            location=self.loc_ardis,
            date='2026-09-03',
            status='completed',
            created_by=self.admin,
        )
        team3 = DailyTeam.objects.create(work_day=wd3, photographer=self.photographer, clown=self.clown, team_photo_count=60)
        DailyEmployeePerformance.objects.filter(work_day=wd3, employee=self.photographer).update(photo_count=60)

        # Query ARDIS only
        analytics_ardis = StatisticsService.get_employee_analytics(
            employee_id=str(self.photographer.id),
            time_filter='all',
            location_id=str(self.loc_ardis.id),
        )
        timeline_ardis = analytics_ardis['timeline']

        # Bounded between 2026-09-01 and 2026-09-03
        self.assertEqual(len(timeline_ardis), 3)
        self.assertEqual(timeline_ardis[0]['date'], '2026-09-01')
        self.assertEqual(timeline_ardis[0]['photos'], 50)
        self.assertTrue(timeline_ardis[0]['worked'])

        # 2026-09-02 was at SABLLET, so for ARDIS it's an off day (photos=0, worked=False)
        self.assertEqual(timeline_ardis[1]['date'], '2026-09-02')
        self.assertEqual(timeline_ardis[1]['photos'], 0)
        self.assertFalse(timeline_ardis[1]['worked'])

        self.assertEqual(timeline_ardis[2]['date'], '2026-09-03')
        self.assertEqual(timeline_ardis[2]['photos'], 60)
        self.assertTrue(timeline_ardis[2]['worked'])

        # Total photos for ARDIS should be 110, not 180
        self.assertEqual(analytics_ardis['summary']['total_photos'], 110)
