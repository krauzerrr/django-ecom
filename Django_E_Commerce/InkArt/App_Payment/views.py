from django.shortcuts import render, HttpResponseRedirect, redirect
from django.urls import reverse
from App_Order.models import Cart,Order
from App_Payment.models import BillingAddress
from App_Payment.forms import BillingForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages

#paymentAPI
import requests
from sslcommerz_python.payment import SSLCSession
from decimal import Decimal
import socket
from django.views.decorators.csrf import csrf_exempt
# Create your views here.

@login_required
def checkout(request):
    saved_address = BillingAddress.objects.get_or_create(user=request.user)
    saved_address = saved_address[0]
    form = BillingForm(instance=saved_address)
    if request.method == 'POST':
        form = BillingForm(request.POST, instance=saved_address)
        if form.is_valid():
            form.save()
            form = BillingForm(instance=saved_address)
            messages.success(request, "Address Updated Successfully!")

    order_qs = Order.objects.filter(user=request.user,ordered=False)
    order_items = order_qs[0].orderitems.all()
    order_total = order_qs[0].get_totals()

    return render(request, 'App_Payment/checkout.html', context={'form':form,'order_items':order_items,'order_total':order_total,'saved_address':saved_address})

@login_required
def payment(request):
    saved_address = BillingAddress.objects.get_or_create(user=request.user)
    saved_address = saved_address[0]
    if not saved_address.is_fully_filled():
        messages.info(request, 'Please complete shipping address!')
        return redirect("App_Payment:checkout")

    if not request.user.profile.is_fully_filled():
        messages.info(request,"Please complete your profile details!")
        return redirect("App_Login:profile")

    store_id = 'inkar5fc5fb93efbd9'
    API_Key = 'inkar5fc5fb93efbd9@ssl'
    mypayment = SSLCSession(sslc_is_sandbox=True, sslc_store_id=store_id, sslc_store_pass=API_Key)

    status_url = request.build_absolute_uri(reverse("App_Payment:complete"))
    #print(status_url)
    mypayment.set_urls(success_url=status_url, fail_url=status_url, cancel_url=status_url, ipn_url=status_url)

    order_qs = Order.objects.filter(user=request.user, ordered=False)
    order_items = order_qs[0].orderitems.all()
    order_item_count = order_qs[0].orderitems.count()
    order_total = order_qs[0].get_totals()
    mypayment.set_product_integration(total_amount=Decimal(order_total), currency='USD', product_category='Mixed', product_name='order_items', num_of_item=order_item_count, shipping_method='Courier', product_profile='None')

    current_user = request.user
    mypayment.set_customer_info(name=current_user.profile.full_name, email=current_user.email, address1=current_user.profile.address_1, address2=current_user.profile.address_1, city=current_user.profile.city, postcode=current_user.profile.zipcode, country=current_user.profile.country, phone=current_user.profile.phone)

    mypayment.set_shipping_info(shipping_to=current_user.profile.full_name, address=saved_address.address, city=saved_address.city, postcode=saved_address.zipcode, country=saved_address.country)

    response_data = mypayment.init_payment()

    return redirect(response_data['GatewayPageURL'])

@csrf_exempt
def complete(request):
    if request.method == 'POST' or request.method == 'post':
        payment_data = request.POST
        status = payment_data['status']

        if status == 'VALID':
            val_id = payment_data['val_id']
            tran_id = payment_data['tran_id']
            messages.success(request, "Your Payment Completed Successfully!")
            return HttpResponseRedirect(reverse("App_Payment:purchase",kwargs={'val_id':val_id,'tran_id':tran_id}))
        elif status == 'FAILED':
            messages.danger(request, "Your Payment Failed! Try Again!")

    return render(request, "App_Payment/complete.html", context={})

@login_required
def purchase(request, val_id, tran_id):
    order_qs=Order.objects.filter(user=request.user, ordered=False)
    order = order_qs[0]
    orderId = tran_id
    order.ordered=True
    order.orderId = orderId
    order.paymentId = val_id
    order.save()
    cart_items = Cart.objects.filter(user=request.user, purchased=False)
    for item in cart_items:
        item.purchased=True
        item.save()
    return HttpResponseRedirect(reverse('App_Shop:home'))

@login_required
def order_view(request):
    try:
        orders = Order.objects.filter(user=request.user, ordered=True)
        context = {'orders':orders}
    except:
        messages.warning(request,"You do not have an active order!")
        return redirect("App_Shop:home")
    return render(request, "App_Payment/order.html", context)