from django import forms

from foodcartapp.models import Order, OrderItem

BOOTSTRAP_INPUT = {'class': 'form-control'}


class LoginForm(forms.Form):
    username = forms.CharField(
        label='Логин', max_length=75, required=True,
        widget=forms.TextInput(attrs={
            **BOOTSTRAP_INPUT,
            'placeholder': 'Укажите имя пользователя',
        })
    )
    password = forms.CharField(
        label='Пароль', max_length=75, required=True,
        widget=forms.PasswordInput(attrs={
            **BOOTSTRAP_INPUT,
            'placeholder': 'Введите пароль',
        })
    )


class OrderForm(forms.ModelForm):
    """Карточка заказа в кабинете менеджера.

    Телефон здесь не проверяется: валидатор висит на поле модели и работает
    и в этой форме, и в API, и в админке.
    """

    class Meta:
        model = Order
        fields = ['status', 'payment_method', 'firstname', 'lastname', 'phonenumber', 'address', 'comment']
        widgets = {
            'status': forms.Select(attrs=BOOTSTRAP_INPUT),
            'payment_method': forms.Select(attrs=BOOTSTRAP_INPUT),
            'firstname': forms.TextInput(attrs=BOOTSTRAP_INPUT),
            'lastname': forms.TextInput(attrs=BOOTSTRAP_INPUT),
            'phonenumber': forms.TextInput(attrs=BOOTSTRAP_INPUT),
            'address': forms.TextInput(attrs=BOOTSTRAP_INPUT),
            'comment': forms.Textarea(attrs={**BOOTSTRAP_INPUT, 'rows': 3}),
        }


# Цены в формсете нет намеренно: новая позиция возьмёт её из товара сама,
# а у старых менеджер не должен случайно переписать цену покупки.
# Одна пустая строчка — чтобы менеджер мог добавить забытый товар по телефону.
OrderItemFormSet = forms.inlineformset_factory(
    Order,
    OrderItem,
    fields=['product', 'quantity'],
    extra=1,
    can_delete=True,
    widgets={
        'product': forms.Select(attrs=BOOTSTRAP_INPUT),
        'quantity': forms.NumberInput(attrs={**BOOTSTRAP_INPUT, 'min': 1}),
    },
)
