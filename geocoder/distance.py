"""Расстояние между двумя точками на земном шаре."""

from math import atan2, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371


def calculate_distance(first_coordinates, second_coordinates):
    """Расстояние по прямой между двумя `Coordinates`, в километрах."""
    lat1, lon1 = map(radians, first_coordinates)
    lat2, lon2 = map(radians, second_coordinates)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return round(EARTH_RADIUS_KM * c, 1)
