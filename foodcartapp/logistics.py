"""Кто и откуда повезёт заказ.

Здесь живёт ответ на вопрос «какой ресторан может приготовить этот заказ и
как далеко он от клиента». Вьюхе остаётся только отдать результат в шаблон.
"""

from collections import namedtuple

from geocoder.coordinates import get_coordinates_for_addresses
from geocoder.distance import calculate_distance

from .models import Restaurant

RestaurantOption = namedtuple('RestaurantOption', ['restaurant', 'distance'])
OrderDelivery = namedtuple('OrderDelivery', ['order', 'client_coordinates', 'restaurants'])


def plan_deliveries(orders):
    """Список `OrderDelivery` — по одному на каждый заказ, в том же порядке.

    Координаты всех адресов собираются заранее, одним разом на весь список:
    иначе каждая новая строчка в таблице заказов стоила бы отдельного похода
    к геокодеру.
    """
    coordinates_by_address = get_coordinates_for_addresses([
        *(order.address for order in orders),
        *Restaurant.objects.values_list('address', flat=True),
    ])
    return [
        OrderDelivery(
            order=order,
            client_coordinates=coordinates_by_address[order.address],
            restaurants=find_restaurants(order, coordinates_by_address),
        )
        for order in orders
    ]


def find_restaurants(order, coordinates_by_address):
    """Рестораны, которым по силам весь заказ, от ближнего к дальнему.

    Кто именно подходит, решает `Order.get_available_restaurants`. Здесь к
    ним добавляется расстояние: ближе — значит меньше по прямой до адреса
    клиента. Рестораны с неизвестным расстоянием уезжают в конец списка:
    сортировать их не по чему, но и прятать от менеджера нельзя.
    """
    client_coordinates = coordinates_by_address[order.address]

    options = [
        RestaurantOption(
            restaurant=restaurant,
            distance=get_distance(client_coordinates, coordinates_by_address.get(restaurant.address)),
        )
        for restaurant in order.get_available_restaurants()
    ]
    return sorted(options, key=lambda option: (option.distance is None, option.distance))


def get_distance(first_coordinates, second_coordinates):
    """Расстояние между точками или None, если какую-то из них не нашли."""
    if first_coordinates is None or second_coordinates is None:
        return None
    return calculate_distance(first_coordinates, second_coordinates)
