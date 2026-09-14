"""Кто и откуда повезёт заказ.

Здесь живёт ответ на вопрос «какой ресторан может приготовить этот заказ и
как далеко он от клиента». Вьюхе остаётся только отдать результат в шаблон.
"""

from collections import defaultdict, namedtuple

from geocoder.coordinates import get_coordinates_for_addresses
from geocoder.distance import calculate_distance

from .models import RestaurantMenuItem

RestaurantOption = namedtuple('RestaurantOption', ['restaurant', 'distance'])
OrderDelivery = namedtuple('OrderDelivery', ['order', 'client_coordinates', 'restaurants'])


def plan_deliveries(orders):
    """Список `OrderDelivery` — по одному на каждый заказ, в том же порядке.

    Все меню и все координаты собираются заранее, одним разом на весь список
    заказов: иначе каждая новая строчка в таблице заказов стоила бы отдельных
    запросов в базу и к геокодеру.
    """
    menus = fetch_menus()
    coordinates_by_address = get_coordinates_for_addresses([
        *(order.address for order in orders),
        *(restaurant.address for restaurant, _ in menus),
    ])
    return [
        OrderDelivery(
            order=order,
            client_coordinates=coordinates_by_address[order.address],
            restaurants=find_restaurants(order, menus, coordinates_by_address),
        )
        for order in orders
    ]


def fetch_menus():
    """Меню всех ресторанов: [(ресторан, {id товара, ...}), ...].

    В меню попадает только то, что есть в продаже.
    """
    products_by_restaurant = defaultdict(set)
    restaurants_by_id = {}
    menu_items = (
        RestaurantMenuItem.objects
        .available()
        .select_related('restaurant')
        .only('product', 'restaurant__id', 'restaurant__name', 'restaurant__address')
    )
    for menu_item in menu_items:
        products_by_restaurant[menu_item.restaurant_id].add(menu_item.product_id)
        restaurants_by_id[menu_item.restaurant_id] = menu_item.restaurant

    return [
        (restaurants_by_id[restaurant_id], product_ids)
        for restaurant_id, product_ids in products_by_restaurant.items()
    ]


def find_restaurants(order, menus, coordinates_by_address):
    """Рестораны, которым по силам весь заказ, от ближнего к дальнему.

    Ближе — значит меньше расстояние по прямой до адреса клиента. Рестораны с
    неизвестным расстоянием уезжают в конец списка: сортировать их не по чему,
    но и прятать от менеджера нельзя.

    У пустого заказа ресторанов нет: готовить нечего, и предлагать некого.
    """
    client_coordinates = coordinates_by_address[order.address]
    ordered_products = {item.product_id for item in order.items.all()}

    options = [
        RestaurantOption(
            restaurant=restaurant,
            distance=get_distance(client_coordinates, coordinates_by_address[restaurant.address]),
        )
        for restaurant, available_products in menus
        if ordered_products and ordered_products <= available_products
    ]
    return sorted(options, key=lambda option: (option.distance is None, option.distance))


def get_distance(first_coordinates, second_coordinates):
    """Расстояние между точками или None, если какую-то из них не нашли."""
    if first_coordinates is None or second_coordinates is None:
        return None
    return calculate_distance(first_coordinates, second_coordinates)
