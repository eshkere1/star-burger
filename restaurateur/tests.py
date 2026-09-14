from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from foodcartapp.models import Order, OrderItem, Product, Restaurant, RestaurantMenuItem
from geocoder.models import Geocache

CLIENT_ADDRESS = 'Москва, Тверская улица, 1'
RESTAURANT_ADDRESS = 'Москва, Тверская улица, 10'


class ManagerPagesTests(TestCase):
    """Кабинет менеджера открывается и показывает заказ целиком."""

    def setUp(self):
        # Геокодер из тестов не дозвонится никуда, координаты берутся из кэша.
        geocoder_request = patch('geocoder.coordinates.fetch_coordinates', return_value=None)
        geocoder_request.start()
        self.addCleanup(geocoder_request.stop)

        Geocache.objects.create(address=CLIENT_ADDRESS, lat=55.757, lon=37.611)
        Geocache.objects.create(address=RESTAURANT_ADDRESS, lat=55.762, lon=37.606)

        self.manager = User.objects.create_user('manager', password='manager', is_staff=True)
        self.client.force_login(self.manager)

        self.burger = Product.objects.create(name='Бургер', price=Decimal('250.00'), image='burger.jpg')
        self.restaurant = Restaurant.objects.create(name='Ближний', address=RESTAURANT_ADDRESS)
        RestaurantMenuItem.objects.create(restaurant=self.restaurant, product=self.burger)

        self.order = Order.objects.create(
            firstname='Иван',
            lastname='Иванов',
            phonenumber='+79001234567',
            address=CLIENT_ADDRESS,
        )
        OrderItem.objects.create(order=self.order, product=self.burger, quantity=2)

    def test_orders_page_shows_order_with_restaurant(self):
        response = self.client.get(reverse('restaurateur:view_orders'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Иван Иванов')
        self.assertContains(response, self.restaurant.name)
        self.assertContains(response, '500')  # сумма заказа: 2 бургера по 250

    def test_order_page_shows_items(self):
        response = self.client.get(reverse('restaurateur:view_order', args=[self.order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.burger.name)
        # Координаты клиента, взятые из кэша; формат — как его покажет шаблон.
        self.assertContains(response, floatformat(55.757, 4))

    def test_order_can_be_edited(self):
        response = self.client.post(
            reverse('restaurateur:edit_order', args=[self.order.id]),
            data={
                'status': Order.Status.COOKING,
                'payment_method': Order.PaymentMethod.ELECTRONIC,
                'firstname': 'Пётр',
                'lastname': 'Иванов',
                'phonenumber': '+79001234567',
                'address': CLIENT_ADDRESS,
                'comment': 'позвонить за 10 минут',
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '1',
                'items-MIN_NUM_FORMS': '0',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-id': str(self.order.items.get().id),
                'items-0-order': str(self.order.id),
                'items-0-product': str(self.burger.id),
                'items-0-quantity': '3',
            },
        )

        self.assertRedirects(response, reverse('restaurateur:view_order', args=[self.order.id]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.firstname, 'Пётр')
        self.assertEqual(self.order.status, Order.Status.COOKING)
        self.assertEqual(self.order.items.get().quantity, 3)

    def test_wrong_phonenumber_is_not_saved(self):
        response = self.client.post(
            reverse('restaurateur:edit_order', args=[self.order.id]),
            data={
                'status': Order.Status.NEW,
                'payment_method': Order.PaymentMethod.CASH,
                'firstname': 'Иван',
                'lastname': 'Иванов',
                'phonenumber': '+7999',
                'address': CLIENT_ADDRESS,
                'comment': '',
                'items-TOTAL_FORMS': '0',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '0',
                'items-MAX_NUM_FORMS': '1000',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'phonenumber', 'Введен некорректный номер телефона')

    def test_menu_page_shows_availability(self):
        response = self.client.get(reverse('restaurateur:ProductsView'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.burger.name)
        self.assertContains(response, self.restaurant.name)

    def test_restaurants_page_opens(self):
        response = self.client.get(reverse('restaurateur:RestaurantView'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.restaurant.name)

    def test_login_page_opens(self):
        self.client.logout()

        response = self.client.get(reverse('restaurateur:login'))

        self.assertEqual(response.status_code, 200)

    def test_done_orders_are_hidden_and_empty_list_says_so(self):
        response = self.client.get(reverse('restaurateur:view_orders'))
        self.assertContains(response, 'Иван Иванов')

        Order.objects.update(status=Order.Status.DONE)

        response = self.client.get(reverse('restaurateur:view_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заказов пока нет')
        self.assertNotContains(response, 'Иван Иванов')

    def test_forgotten_item_can_be_added_with_catalogue_price(self):
        fries = Product.objects.create(name='Картошка фри', price=Decimal('150.00'))
        existing_item = self.order.items.get()

        response = self.client.post(
            reverse('restaurateur:edit_order', args=[self.order.id]),
            data={
                'status': Order.Status.NEW,
                'payment_method': Order.PaymentMethod.CASH,
                'firstname': 'Иван',
                'lastname': 'Иванов',
                'phonenumber': '+79001234567',
                'address': CLIENT_ADDRESS,
                'comment': '',
                'items-TOTAL_FORMS': '2',
                'items-INITIAL_FORMS': '1',
                'items-MIN_NUM_FORMS': '0',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-id': str(existing_item.id),
                'items-0-order': str(self.order.id),
                'items-0-product': str(self.burger.id),
                'items-0-quantity': str(existing_item.quantity),
                'items-1-id': '',
                'items-1-order': str(self.order.id),
                'items-1-product': str(fries.id),
                'items-1-quantity': '2',
            },
        )

        self.assertRedirects(response, reverse('restaurateur:view_order', args=[self.order.id]))
        added_item = self.order.items.get(product=fries)
        self.assertEqual(added_item.price, Decimal('150.00'))

    def test_stranger_is_sent_to_login(self):
        self.client.logout()

        response = self.client.get(reverse('restaurateur:view_orders'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('restaurateur:login'), response['Location'])


class OrdersPageQueriesTests(TestCase):
    """Страница заказов не должна лезть в базу за каждым заказом отдельно."""

    def setUp(self):
        Geocache.objects.create(address=CLIENT_ADDRESS, lat=55.757, lon=37.611)
        Geocache.objects.create(address=RESTAURANT_ADDRESS, lat=55.762, lon=37.606)

        self.manager = User.objects.create_user('manager', password='manager', is_staff=True)
        self.client.force_login(self.manager)

        self.burger = Product.objects.create(name='Бургер', price=Decimal('250.00'))
        restaurant = Restaurant.objects.create(name='Ближний', address=RESTAURANT_ADDRESS)
        RestaurantMenuItem.objects.create(restaurant=restaurant, product=self.burger)

    def create_orders(self, count):
        for number in range(count):
            order = Order.objects.create(
                firstname=f'Клиент {number}',
                lastname='Иванов',
                phonenumber='+79001234567',
                address=CLIENT_ADDRESS,
            )
            OrderItem.objects.create(order=order, product=self.burger, quantity=1)

    def count_queries_on_orders_page(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('restaurateur:view_orders'))
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_query_count_does_not_grow_with_orders(self):
        self.create_orders(1)
        queries_for_one_order = self.count_queries_on_orders_page()

        self.create_orders(9)
        queries_for_ten_orders = self.count_queries_on_orders_page()

        self.assertEqual(queries_for_ten_orders, queries_for_one_order)
