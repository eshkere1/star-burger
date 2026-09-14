from django.db import transaction
from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        # `product` приходит как id, а ModelSerializer сам превращает его в
        # товар и сам же ругается на несуществующий id — руками проверять
        # нечего. Цена в заказ приходит не от клиента, а из карточки товара.
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

    def create(self, validated_data):
        items_fields = validated_data.pop('products')
        with transaction.atomic():
            order = Order.objects.create(**validated_data)
            for item_fields in items_fields:
                # Цену позиция возьмёт из товара сама, в OrderItem.save.
                OrderItem.objects.create(order=order, **item_fields)
        return order
