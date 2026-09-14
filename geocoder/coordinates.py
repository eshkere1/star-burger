"""Координаты адресов: кэш в базе и запросы к геокодеру Яндекса.

Наружу торчат только `get_coordinates` и `get_coordinates_for_addresses` —
вьюхам не нужно знать ни про таблицу кэша, ни про HTTP-запросы.
"""

from collections import namedtuple

import requests
from django.conf import settings

from .models import Geocache

GEOCODER_URL = 'https://geocode-maps.yandex.ru/1.x'
GEOCODER_TIMEOUT_SECONDS = 5

Coordinates = namedtuple('Coordinates', ['lat', 'lon'])


def get_coordinates(address):
    """Координаты адреса или None, если геокодер их не знает."""
    return get_coordinates_for_addresses([address])[address]


def get_coordinates_for_addresses(addresses):
    """Координаты каждого адреса: {адрес: Coordinates или None}.

    Адрес спрашивается у Яндекса ровно один раз за всё время жизни проекта:
    ответ ложится в таблицу Geocache, и дальше HTTP-запроса не будет вовсе.
    Повторы внутри `addresses` тоже стоят одного запроса, а известные адреса
    достаются из базы одним запросом на всех.

    Неудача не кэшируется намеренно. Геокодер молчит не только на выдуманных
    адресах, но и на своём же таймауте, и на кончившемся лимите. Записав
    пустые координаты, мы запомнили бы сбой сети навсегда — адрес остался бы
    без координат до ручной чистки таблицы.
    """
    wanted_addresses = {address for address in addresses if address}
    coordinates_by_address = {
        geocache.address: Coordinates(geocache.lat, geocache.lon)
        for geocache in Geocache.objects.filter(address__in=wanted_addresses)
    }
    for address in wanted_addresses - coordinates_by_address.keys():
        coordinates_by_address[address] = fetch_and_remember_coordinates(address)

    return {address: coordinates_by_address.get(address) for address in addresses}


def fetch_and_remember_coordinates(address):
    """Спросить координаты у геокодера и положить удачный ответ в кэш."""
    coordinates = fetch_coordinates(address)
    if not coordinates:
        return None

    Geocache.objects.update_or_create(
        address=address,
        defaults={'lat': coordinates.lat, 'lon': coordinates.lon},
    )
    return coordinates


def fetch_coordinates(address):
    """Координаты адреса от геокодера Яндекса, в обход кэша.

    Возвращает None на любую неудачу: и когда адреса нет на свете, и когда
    геокодер не ответил. Различить их по ответу нельзя, а звонить наружу
    из шаблона всё равно нечем — вызывающему хватает «координат нет».
    """
    params = {
        'geocode': address,
        'apikey': settings.YANDEX_GEOCODER_API_KEY,
        'format': 'json',
    }
    try:
        response = requests.get(GEOCODER_URL, params=params, timeout=GEOCODER_TIMEOUT_SECONDS)
        response.raise_for_status()
        found_places = response.json()['response']['GeoObjectCollection']['featureMember']
    except (requests.exceptions.RequestException, KeyError, ValueError):
        return None

    if not found_places:
        return None

    most_relevant, *_ = found_places
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(' ')
    return Coordinates(float(lat), float(lon))
