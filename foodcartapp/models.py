from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Prefetch, Sum
from django.utils import timezone

from .validators import validate_phonenumber


class Restaurant(models.Model):
    name = models.CharField(
        'название',
        max_length=50,
        db_index=True,
    )
    address = models.CharField(
        'адрес',
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        'контактный телефон',
        max_length=20,
        blank=True,
    )

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    name = models.CharField(
        'название',
        max_length=50,
    )

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        available_products = (
            RestaurantMenuItem.objects
            .available()
            .values_list('product')
        )
        return self.filter(pk__in=available_products)


class Product(models.Model):
    name = models.CharField(
        'название',
        max_length=50,
        db_index=True,
    )
    category = models.ForeignKey(
        ProductCategory,
        verbose_name='категория',
        related_name='products',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    image = models.ImageField(
        'картинка'
    )
    special_status = models.BooleanField(
        'спец.предложение',
        default=False,
        db_index=True,
    )
    description = models.CharField(
        'описание',
        max_length=200,
        blank=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'
        ordering = ['name']

    def __str__(self):
        return self.name


class RestaurantMenuItemQuerySet(models.QuerySet):
    def available(self):
        return self.filter(availability=True)


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        related_name='menu_items',
        verbose_name='ресторан',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        related_name='menu_items',
        verbose_name='продукт',
        on_delete=models.CASCADE,
    )
    availability = models.BooleanField(
        'в продаже',
        default=True,
        db_index=True,
    )

    objects = RestaurantMenuItemQuerySet.as_manager()

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]

    def __str__(self):
        return f'{self.restaurant.name} - {self.product.name}'


class OrderQuerySet(models.QuerySet):
    def with_total_price(self):
        return self.annotate(
            total_price=Sum(F('items__price') * F('items__quantity'))
        )

    def with_items(self):
        """Состав заказа — одним запросом на все заказы, вместе с товарами."""
        order_items = (
            OrderItem.objects
            .with_cost()
            .select_related('product')
            .only('order_id', 'price', 'quantity', 'product__id', 'product__name')
        )
        return self.prefetch_related(Prefetch('items', queryset=order_items))

    def unprocessed(self):
        return self.exclude(status=Order.Status.DONE)


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        COOKING = 'cooking', 'Готовится'
        DELIVERING = 'delivering', 'Доставляется'
        DONE = 'done', 'Выполнен'

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Наличными'
        ELECTRONIC = 'electronic', 'Электронно'

    status = models.CharField(
        'статус',
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    payment_method = models.CharField(
        'способ оплаты',
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        db_index=True,
    )
    firstname = models.CharField(
        'имя',
        max_length=50,
    )
    lastname = models.CharField(
        'фамилия',
        max_length=50,
    )
    phonenumber = models.CharField(
        'телефон',
        max_length=20,
        validators=[validate_phonenumber],
    )
    address = models.CharField(
        'адрес',
        max_length=100,
    )
    comment = models.TextField(
        'комментарий менеджера',
        blank=True,
    )
    registered_at = models.DateTimeField(
        'дата создания',
        auto_now_add=True,
        db_index=True,
    )
    status_changed_at = models.DateTimeField(
        'дата изменения статуса',
        default=timezone.now,
        db_index=True,
    )

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'
        ordering = ['-registered_at']

    def __str__(self):
        return f'{self.firstname} {self.lastname}'

    def save(self, *args, **kwargs):
        if self.pk and self.status != self._get_stored_status():
            self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)

    def _get_stored_status(self):
        """Статус, который лежит в базе прямо сейчас, до сохранения.

        Нужен, чтобы отличить смену статуса от правки имени или адреса:
        дату изменения статуса двигает только первая.
        """
        return (
            Order.objects
            .filter(pk=self.pk)
            .values_list('status', flat=True)
            .first()
        )


class OrderItemQuerySet(models.QuerySet):
    def with_cost(self):
        return self.annotate(cost=F('price') * F('quantity'))


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name='items',
        verbose_name='заказ',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        related_name='order_items',
        verbose_name='товар',
        # Заказ — документ, а не корзина: снять товар с продажи можно, а
        # переписать историю нельзя. PROTECT не даст удалить товар, который
        # кто-то уже купил, и потерять вместе с ним позиции старых заказов.
        on_delete=models.PROTECT,
    )
    quantity = models.PositiveSmallIntegerField(
        'количество',
        validators=[MinValueValidator(1)],
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    objects = OrderItemQuerySet.as_manager()

    class Meta:
        verbose_name = 'позиция заказа'
        verbose_name_plural = 'позиции заказа'

    def __str__(self):
        return f'{self.product} {self.quantity}'

    def save(self, *args, **kwargs):
        # Цена позиции — снимок цены товара на момент заказа. Подорожает
        # бургер — старые заказы останутся с той ценой, по которой их купили.
        if self.price is None:
            self.price = self.product.price
        super().save(*args, **kwargs)
