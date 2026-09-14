from unittest.mock import patch

from django.test import TestCase

from .coordinates import Coordinates, get_coordinates, get_coordinates_for_addresses
from .distance import calculate_distance
from .models import Geocache

ADDRESS = 'Москва, Тверская улица, 1'


def yandex_answer(lon, lat):
    """Ответ геокодера в том виде, в каком его отдаёт Яндекс."""
    return {
        'response': {
            'GeoObjectCollection': {
                'featureMember': [
                    {'GeoObject': {'Point': {'pos': f'{lon} {lat}'}}},
                ],
            },
        },
    }


class GeocacheTests(TestCase):

    @patch('geocoder.coordinates.requests.get')
    def test_known_address_does_not_reach_api(self, requests_get):
        Geocache.objects.create(address=ADDRESS, lat=55.76, lon=37.61)

        coordinates = get_coordinates(ADDRESS)

        self.assertEqual(coordinates, (55.76, 37.61))
        requests_get.assert_not_called()

    @patch('geocoder.coordinates.requests.get')
    def test_new_address_is_asked_once_and_saved(self, requests_get):
        requests_get.return_value.json.return_value = yandex_answer(37.61, 55.76)
        requests_get.return_value.raise_for_status.return_value = None

        first = get_coordinates(ADDRESS)
        second = get_coordinates(ADDRESS)

        self.assertEqual(first, (55.76, 37.61))
        self.assertEqual(second, first)
        self.assertEqual(requests_get.call_count, 1)
        self.assertEqual(Geocache.objects.filter(address=ADDRESS).count(), 1)

    @patch('geocoder.coordinates.requests.get')
    def test_unknown_address_is_not_cached(self, requests_get):
        requests_get.return_value.json.return_value = {
            'response': {'GeoObjectCollection': {'featureMember': []}},
        }
        requests_get.return_value.raise_for_status.return_value = None

        coordinates = get_coordinates('улица, которой нет')

        # Пустой ответ мог прийти и от сбоя сети. Запомнив его, мы оставили бы
        # адрес без координат навсегда, поэтому в кэш он не попадает.
        self.assertIsNone(coordinates)
        self.assertFalse(Geocache.objects.exists())

    @patch('geocoder.coordinates.requests.get')
    def test_repeated_address_costs_one_request(self, requests_get):
        requests_get.return_value.json.return_value = yandex_answer(37.61, 55.76)
        requests_get.return_value.raise_for_status.return_value = None

        coordinates_by_address = get_coordinates_for_addresses([ADDRESS, ADDRESS])

        self.assertEqual(coordinates_by_address, {ADDRESS: (55.76, 37.61)})
        self.assertEqual(requests_get.call_count, 1)

    @patch('geocoder.coordinates.requests.get')
    def test_empty_address_is_not_asked_at_all(self, requests_get):
        coordinates_by_address = get_coordinates_for_addresses([''])

        self.assertEqual(coordinates_by_address, {'': None})
        requests_get.assert_not_called()


class DistanceTests(TestCase):
    """Расстояния сверены с геометрией и с известными расстояниями по карте."""

    def test_same_point_is_zero(self):
        self.assertEqual(calculate_distance(Coordinates(55.75, 37.61), Coordinates(55.75, 37.61)), 0)

    def test_one_degree_of_latitude(self):
        # Меридиан — большой круг, поэтому градус широты везде одинаков:
        # 2 * pi * 6371 / 360 = 111,2 км.
        self.assertEqual(calculate_distance(Coordinates(0, 0), Coordinates(1, 0)), 111.2)
        self.assertEqual(calculate_distance(Coordinates(55, 37), Coordinates(56, 37)), 111.2)

    def test_one_degree_of_longitude_shrinks_to_the_north(self):
        # На широте Москвы параллель короче экватора в cos(55,75°) раз:
        # 111,2 * 0,5624 = 62,6 км.
        self.assertEqual(calculate_distance(Coordinates(55.75, 37), Coordinates(55.75, 38)), 62.6)

    def test_known_distances_from_the_map(self):
        kremlin = Coordinates(55.7520, 37.6175)
        palace_square = Coordinates(59.9390, 30.3158)
        sheremetyevo = Coordinates(55.9726, 37.4146)

        # Москва — Петербург по прямой ~634 км, Кремль — Шереметьево ~28 км.
        self.assertAlmostEqual(calculate_distance(kremlin, palace_square), 634, delta=2)
        self.assertAlmostEqual(calculate_distance(kremlin, sheremetyevo), 28, delta=1)

    def test_distance_does_not_depend_on_direction(self):
        kremlin = Coordinates(55.7520, 37.6175)
        sheremetyevo = Coordinates(55.9726, 37.4146)

        self.assertEqual(
            calculate_distance(kremlin, sheremetyevo),
            calculate_distance(sheremetyevo, kremlin),
        )
