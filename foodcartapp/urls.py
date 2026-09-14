from django.urls import path

from .views import OrderView, banners_list_api, product_list_api

app_name = 'foodcartapp'

urlpatterns = [
    path('products/', product_list_api, name='product_list'),
    path('banners/', banners_list_api, name='banners_list'),
    path('order/', OrderView.as_view(), name='order'),
]
