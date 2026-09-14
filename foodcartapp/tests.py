import json
from decimal import Decimal
from unittest.mock import patch

from django.db.models import ProtectedError
from django.test import TestCase

from geocoder.models import Geocache

from .logistics import plan_deliveries
from .models import Order, OrderItem, Product, Restaurant, RestaurantMenuItem

CLIENT_ADDRESS = 'Москва, Тверская улица, 1'
NEAR_ADDRESS = 'Москва, Тверская улица, 10'
FAR_ADDRESS = 'Москва, Ленинский проспект, 100'


def create_product(name, price='100.00'):
    return Product.objects.create(name=name, price=Decimal(price), image=f'{name}.jpg')


def create_order(products, address=CLIENT_ADDRESS):
    order = Order.objects.create(
        firstname='Иван',
        lastname='Иванов',
        phonenumber='+79001234567',
        address=address,
    )
    for product in products:
        OrderItem.objects.create(order=order, product=product, quantity=1)
    return order


class OrderItemTests(TestCase):

    def test_price_is_copied_from_product(self):
        burger = create_product('Бургер', '250.00')

        order = create_order([burger])

        self.assertEqual(order.items.get().price, Decimal('250.00'))

    def test_price_stays_after_product_gets_more_expensive(self):
        burger = create_product('Бургер', '250.00')
        order = create_order([burger])

        burger.price = Decimal('300.00')
        burger.save()

        self.assertEqual(order.items.get().price, Decimal('250.00'))

    def test_purchased_product_cannot_be_deleted(self):
        burger = create_product('Бургер', '250.00')
        create_order([burger])

        # Удалить товар — значит потерять позиции заказов, в которых он есть,
        # поэтому on_delete=PROTECT такого не позволит.
        with self.assertRaises(ProtectedError):
            burger.delete()


class OrderApiTests(TestCase):

    def post_order(self, **fields):
        """Заказ ровно в том виде, в каком его присылает форма на сайте."""
        return self.client.post(
            '/api/order/',
            data=json.dumps({
                'firstname': 'Иван',
                'lastname': 'Иванов',
                'phonenumber': '+79001234567',
                'address': CLIENT_ADDRESS,
                **fields,
            }),
            content_type='application/json',
        )

    def test_order_from_site_gets_prices_from_products(self):
        burger = create_product('Бургер', '250.00')

        response = self.post_order(products=[{'product': burger.id, 'quantity': 2}])

        self.assertEqual(response.status_code, 201)
        order_item = OrderItem.objects.get()
        self.assertEqual(order_item.price, Decimal('250.00'))
        self.assertEqual(order_item.quantity, 2)

    def test_order_from_site_comes_without_payment_method(self):
        burger = create_product('Бургер', '250.00')

        response = self.post_order(products=[{'product': burger.id, 'quantity': 1}])

        # Форма на сайте про оплату не спрашивает, поэтому заказ приходит без
        # неё и считается оплатой наличными, пока менеджер не решит иначе.
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.get().payment_method, Order.PaymentMethod.CASH)
        self.assertEqual(Order.objects.get().status, Order.Status.NEW)

    def test_payment_method_is_kept_when_given(self):
        burger = create_product('Бургер', '250.00')

        response = self.post_order(
            payment_method=Order.PaymentMethod.ELECTRONIC,
            products=[{'product': burger.id, 'quantity': 1}],
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.get().payment_method, Order.PaymentMethod.ELECTRONIC)

    def test_order_with_unknown_product_is_rejected(self):
        response = self.post_order(products=[{'product': 100500, 'quantity': 1}])

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_order_with_wrong_phonenumber_is_rejected(self):
        burger = create_product('Бургер', '250.00')

        response = self.post_order(
            phonenumber='+7999',
            products=[{'product': burger.id, 'quantity': 1}],
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('phonenumber', response.json())
        self.assertFalse(Order.objects.exists())

    def test_order_without_products_is_rejected(self):
        response = self.post_order(products=[])

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())


class ProductListApiTests(TestCase):

    def test_only_products_on_sale_are_listed(self):
        burger = create_product('Бургер', '250.00')
        forgotten = create_product('Забытый салат', '150.00')
        restaurant = Restaurant.objects.create(name='Ближний', address=NEAR_ADDRESS)
        RestaurantMenuItem.objects.create(restaurant=restaurant, product=burger)
        RestaurantMenuItem.objects.create(restaurant=restaurant, product=forgotten, availability=False)

        response = self.client.get('/api/products/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([product['name'] for product in response.json()], [burger.name])


class PlanDeliveriesTests(TestCase):

    def setUp(self):
        self.burger = create_product('Бургер')
        self.fries = create_product('Картошка')

        self.near_restaurant = self.create_restaurant('Ближний', NEAR_ADDRESS, [self.burger, self.fries])
        self.far_restaurant = self.create_restaurant('Дальний', FAR_ADDRESS, [self.burger, self.fries])
        self.burger_only_restaurant = self.create_restaurant('Только бургеры', NEAR_ADDRESS, [self.burger])

        # Геокодер из тестов не дозвонится никуда: всё, чего нет в кэше,
        # остаётся без координат.
        geocoder_request = patch('geocoder.coordinates.fetch_coordinates', return_value=None)
        geocoder_request.start()
        self.addCleanup(geocoder_request.stop)

        Geocache.objects.create(address=CLIENT_ADDRESS, lat=55.757, lon=37.611)
        Geocache.objects.create(address=NEAR_ADDRESS, lat=55.762, lon=37.606)
        Geocache.objects.create(address=FAR_ADDRESS, lat=55.680, lon=37.520)

    def create_restaurant(self, name, address, products, availability=True):
        restaurant = Restaurant.objects.create(name=name, address=address)
        for product in products:
            RestaurantMenuItem.objects.create(
                restaurant=restaurant,
                product=product,
                availability=availability,
            )
        return restaurant

    def plan_delivery(self, order):
        delivery, = plan_deliveries([order])
        return delivery

    def test_restaurant_without_whole_order_is_not_offered(self):
        order = create_order([self.burger, self.fries])

        delivery = self.plan_delivery(order)

        self.assertNotIn(
            self.burger_only_restaurant,
            [option.restaurant for option in delivery.restaurants],
        )

    def test_nearest_restaurant_goes_first(self):
        order = create_order([self.burger, self.fries])

        delivery = self.plan_delivery(order)

        self.assertEqual(
            [option.restaurant for option in delivery.restaurants],
            [self.near_restaurant, self.far_restaurant],
        )
        first, second = delivery.restaurants
        self.assertLess(first.distance, second.distance)

    def test_restaurant_with_unknown_address_goes_last(self):
        unknown = self.create_restaurant('Без координат', 'адрес, которого нет', [self.burger, self.fries])
        order = create_order([self.burger, self.fries])

        delivery = self.plan_delivery(order)

        last_option = delivery.restaurants[-1]
        self.assertEqual(last_option.restaurant, unknown)
        self.assertIsNone(last_option.distance)

    def test_product_out_of_stock_hides_restaurant(self):
        RestaurantMenuItem.objects.filter(restaurant=self.near_restaurant).update(availability=False)
        order = create_order([self.burger, self.fries])

        delivery = self.plan_delivery(order)

        self.assertEqual(
            [option.restaurant for option in delivery.restaurants],
            [self.far_restaurant],
        )

    def test_order_nobody_can_cook_has_no_restaurants(self):
        # Товар есть в каталоге, но ни в одном меню его нет.
        rings = create_product('Луковые кольца')
        order = create_order([self.burger, rings])

        delivery = self.plan_delivery(order)

        self.assertEqual(delivery.restaurants, [])

    def test_unknown_client_address_keeps_restaurants_without_distances(self):
        order = create_order([self.burger, self.fries], address='адрес, которого нет')

        delivery = self.plan_delivery(order)

        # Расстояние посчитать не от чего, но менеджеру всё равно нужно знать,
        # кто может приготовить заказ.
        self.assertIsNone(delivery.client_coordinates)
        self.assertEqual(
            [option.restaurant for option in delivery.restaurants],
            [self.near_restaurant, self.far_restaurant],
        )
        self.assertEqual([option.distance for option in delivery.restaurants], [None, None])

    def test_client_coordinates_come_from_cache(self):
        order = create_order([self.burger])

        delivery = self.plan_delivery(order)

        self.assertEqual(delivery.client_coordinates, (55.757, 37.611))
