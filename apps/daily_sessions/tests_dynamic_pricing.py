from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.daily_sessions.models import Location, WorkDay, DailyTeam, DailyEmployeePerformance
from apps.employees.models import Employee
from apps.daily_sessions.services import DailyOperationsService

User = get_user_model()

class DynamicPricingTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testadmin', password='password')
        self.location = Location.objects.create(name='Test Location', icon='stadium', color_hex='#FF5722')
        self.photographer = Employee.objects.create(
            first_name='Photo', last_name='Grapher', role='photographer', national_id='10101'
        )
        self.clown = Employee.objects.create(
            first_name='Fun', last_name='Clown', role='clown', national_id='20202'
        )

    def test_default_pricing_values(self):
        work_day = WorkDay.objects.create(
            location=self.location,
            date='2026-08-12',
            created_by=self.user
        )
        self.assertFalse(work_day.dynamic_pricing_enabled)
        self.assertEqual(work_day.photographer_unit_price, Decimal('45.00'))
        self.assertEqual(work_day.clown_unit_price, Decimal('50.00'))

        resolved = work_day.get_resolved_unit_prices(photo_count=20)
        self.assertEqual(resolved['tier'], 'normal')
        self.assertEqual(resolved['photographer_unit_price'], Decimal('45.00'))
        self.assertEqual(resolved['clown_unit_price'], Decimal('50.00'))

    def test_dynamic_pricing_tiers(self):
        work_day = WorkDay.objects.create(
            location=self.location,
            date='2026-08-13',
            created_by=self.user,
            dynamic_pricing_enabled=True,
            low_photo_threshold=40,
            high_photo_threshold=80,
            low_photographer_price=Decimal('40.00'),
            low_clown_price=Decimal('45.00'),
            photographer_unit_price=Decimal('45.00'),
            clown_unit_price=Decimal('50.00'),
            high_photographer_price=Decimal('50.00'),
            high_clown_price=Decimal('55.00'),
        )

        # Boundary test 1: 39 photos (< 40) -> Low Volume
        res_low = work_day.get_resolved_unit_prices(photo_count=39)
        self.assertEqual(res_low['tier'], 'low')
        self.assertEqual(res_low['photographer_unit_price'], Decimal('40.00'))
        self.assertEqual(res_low['clown_unit_price'], Decimal('45.00'))

        # Boundary test 2: 40 photos (== 40) -> Normal Volume
        res_norm_40 = work_day.get_resolved_unit_prices(photo_count=40)
        self.assertEqual(res_norm_40['tier'], 'normal')
        self.assertEqual(res_norm_40['photographer_unit_price'], Decimal('45.00'))
        self.assertEqual(res_norm_40['clown_unit_price'], Decimal('50.00'))

        # Boundary test 3: 80 photos (== 80) -> Normal Volume
        res_norm_80 = work_day.get_resolved_unit_prices(photo_count=80)
        self.assertEqual(res_norm_80['tier'], 'normal')
        self.assertEqual(res_norm_80['photographer_unit_price'], Decimal('45.00'))
        self.assertEqual(res_norm_80['clown_unit_price'], Decimal('50.00'))

        # Boundary test 4: 81 photos (> 80) -> High Volume
        res_high = work_day.get_resolved_unit_prices(photo_count=81)
        self.assertEqual(res_high['tier'], 'high')
        self.assertEqual(res_high['photographer_unit_price'], Decimal('50.00'))
        self.assertEqual(res_high['clown_unit_price'], Decimal('55.00'))

    def test_manual_override(self):
        work_day = WorkDay.objects.create(
            location=self.location,
            date='2026-08-14',
            created_by=self.user,
            dynamic_pricing_enabled=True,
            is_manually_overridden=True,
            override_photographer_price=Decimal('60.00'),
            override_clown_price=Decimal('65.00'),
        )

        res = work_day.get_resolved_unit_prices(photo_count=100)
        self.assertEqual(res['tier'], 'override')
        self.assertTrue(res['is_overridden'])
        self.assertEqual(res['photographer_unit_price'], Decimal('60.00'))
        self.assertEqual(res['clown_unit_price'], Decimal('65.00'))
