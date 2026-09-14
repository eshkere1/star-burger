from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View

from foodcartapp.logistics import plan_deliveries
from foodcartapp.models import Order, Product, Restaurant, RestaurantMenuItem
from geocoder.coordinates import get_coordinates

from .forms import LoginForm, OrderForm, OrderItemFormSet


def is_manager(user):
    return user.is_staff  # FIXME replace with specific permission


manager_required = user_passes_test(is_manager, login_url='restaurateur:login')


class LoginView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'login.html', context={
            'form': LoginForm(),
        })

    def post(self, request):
        form = LoginForm(request.POST)

        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user:
                login(request, user)
                if user.is_staff:  # FIXME replace with specific permission
                    return redirect('restaurateur:RestaurantView')
                return redirect('start_page')

        return render(request, 'login.html', context={
            'form': form,
            'ivalid': True,
        })


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('restaurateur:login')


@manager_required
def view_products(request):
    restaurants = list(Restaurant.objects.only('id', 'name'))
    products = list(
        Product.objects
        .select_related('category')
        .only('id', 'name', 'price', 'image', 'category__id', 'category__name')
        .prefetch_related(
            Prefetch(
                'menu_items',
                queryset=RestaurantMenuItem.objects.only('product', 'restaurant_id', 'availability'),
            )
        )
    )

    products_with_restaurant_availability = []
    for product in products:
        availability = {item.restaurant_id: item.availability for item in product.menu_items.all()}
        ordered_availability = [availability.get(restaurant.id, False) for restaurant in restaurants]

        products_with_restaurant_availability.append(
            (product, ordered_availability)
        )

    return render(request, template_name='products_list.html', context={
        'products_with_restaurant_availability': products_with_restaurant_availability,
        'restaurants': restaurants,
    })


@manager_required
def view_restaurants(request):
    return render(request, template_name='restaurants_list.html', context={
        'restaurants': Restaurant.objects.all(),
    })


@manager_required
def view_orders(request):
    orders = list(
        Order.objects
        .unprocessed()
        .with_total_price()
        .with_items()
        .defer('comment')
    )

    return render(request, template_name='order_items.html', context={
        'deliveries': plan_deliveries(orders),
    })


@manager_required
def view_order(request, order_id):
    order = get_object_or_404(
        Order.objects.with_total_price().with_items(),
        pk=order_id,
    )

    return render(request, template_name='order_detail.html', context={
        'order': order,
        'client_coordinates': get_coordinates(order.address),
    })


@manager_required
def edit_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        items_formset = OrderItemFormSet(request.POST, instance=order)

        if form.is_valid() and items_formset.is_valid():
            with transaction.atomic():
                form.save()
                # Цену новых позиций подставит сам OrderItem, при сохранении.
                items_formset.save()

            return redirect('restaurateur:view_order', order_id=order.id)
    else:
        form = OrderForm(instance=order)
        items_formset = OrderItemFormSet(instance=order)

    return render(request, template_name='order_form.html', context={
        'order': order,
        'form': form,
        'items_formset': items_formset,
    })
