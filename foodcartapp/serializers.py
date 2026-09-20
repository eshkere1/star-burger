from django.db import transaction
from rest_framework import serializers

from .models import Order, OrderItem, Product


def fetch_products(order_fields):
    """Товары всех позиций заказа: {id: товар}, одним запросом на весь заказ.

    Заказ приходит сырым, ещё не проверенным, поэтому в позициях может
    лежать что угодно. Всё, что не похоже на id, здесь просто пропускается:
    ругаться на него — работа поля, а не этой функции.
    """
    if not hasattr(order_fields, 'get'):
        return {}

    items_fields = order_fields.get('products')
    if not isinstance(items_fields, list):
        return {}

    product_ids = {
        item_fields.get('product')
        for item_fields in items_fields
        if isinstance(item_fields, dict) and isinstance(item_fields.get('product'), int)
    }
    return Product.objects.in_bulk(product_ids)


class ProductByIdField(serializers.PrimaryKeyRelatedField):
    """Товар по его id, без отдельного запроса на каждую позицию заказа.

    DRF по умолчанию спрашивает у базы каждый товар отдельно, и заказ из
    десяти позиций стоит десяти запросов вместо одного. Готовый словарь
    товаров кладёт в контекст `OrderSerializer`; тексты ошибок остаются
    ровно теми же, что были у DRF.
    """

    def to_internal_value(self, data):
        products_by_id = self.context.get('products_by_id')
        if products_by_id is None:
            return super().to_internal_value(data)

        try:
            product_id = int(data)
        except (TypeError, ValueError):
            self.fail('incorrect_type', data_type=type(data).__name__)

        try:
            return products_by_id[product_id]
        except KeyError:
            self.fail('does_not_exist', pk_value=data)


class OrderItemSerializer(serializers.ModelSerializer):
    # `product` приходит как id, а поле само превращает его в товар и само же
    # ругается на несуществующий id — руками проверять нечего. Цена в заказ
    # приходит не от клиента, а из карточки товара.
    product = ProductByIdField(queryset=Product.objects.all())

    class Meta:
        model = OrderItem
        fields = ['product', 'quantity']


class OrderSerializer(serializers.ModelSerializer):
    products = OrderItemSerializer(many=True, write_only=True, allow_empty=False)
    # Способ оплаты необязателен: форма на сайте про него не спрашивает, и
    # заказ оттуда приходит без него. Такой заказ считается оплатой наличными
    # (значение по умолчанию у модели), а менеджер поправит его в кабинете,
    # когда перезвонит клиенту.

    class Meta:
        model = Order
        fields = ['firstname', 'lastname', 'phonenumber', 'address', 'products', 'payment_method']

    def to_internal_value(self, data):
        # Товары всего заказа — одним запросом, до того как DRF возьмётся
        # разбирать позиции по одной.
        self.context['products_by_id'] = fetch_products(data)
        return super().to_internal_value(data)

    def create(self, validated_data):
        items_fields = validated_data.pop('products')
        with transaction.atomic():
            order = Order.objects.create(**validated_data)
            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    product=item_fields['product'],
                    quantity=item_fields['quantity'],
                    # bulk_create не зовёт OrderItem.save, поэтому цену —
                    # снимок цены товара на момент заказа — ставим здесь сами.
                    price=item_fields['product'].price,
                )
                for item_fields in items_fields
            ])
        return order
