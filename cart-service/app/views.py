import json

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Cart, CartItem


def _parse_json(request):
	try:
		return json.loads(request.body or '{}'), None
	except json.JSONDecodeError:
		return None, JsonResponse({'error': 'Invalid JSON body.'}, status=400)


def _serialize_item(item):
	return {'id': item.id, 'product_id': item.product_id, 'quantity': item.quantity}


def _serialize_cart(cart):
	items = list(cart.items.all())
	return {
		'id': cart.id,
		'user_id': cart.user_id,
		'items': [_serialize_item(item) for item in items],
	}


@method_decorator(csrf_exempt, name='dispatch')
class HealthView(View):
	def get(self, request):
		return JsonResponse({'status': 'ok', 'service': 'cart-service'})


@method_decorator(csrf_exempt, name='dispatch')
class CartView(View):
	def get(self, request):
		user_id = request.GET.get('user_id')
		queryset = Cart.objects.prefetch_related('items').order_by('-id')
		if user_id:
			queryset = queryset.filter(user_id=user_id)
		return JsonResponse({'count': queryset.count(), 'data': [_serialize_cart(cart) for cart in queryset]})

	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		user_id = payload.get('user_id')
		if not user_id:
			return JsonResponse({'error': 'user_id is required.'}, status=400)

		cart, _ = Cart.objects.get_or_create(user_id=user_id)
		return JsonResponse({'message': 'Cart ready.', 'cart': _serialize_cart(cart)}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class CartItemView(View):
	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		cart_id = payload.get('cart')
		product_id = payload.get('product_id')
		quantity = payload.get('quantity', 1)

		if not cart_id or not product_id:
			return JsonResponse({'error': 'cart and product_id are required.'}, status=400)

		try:
			quantity = int(quantity)
		except (TypeError, ValueError):
			return JsonResponse({'error': 'quantity must be integer.'}, status=400)

		if quantity <= 0:
			return JsonResponse({'error': 'quantity must be > 0.'}, status=400)

		cart = Cart.objects.filter(id=cart_id).first()
		if cart is None:
			return JsonResponse({'error': 'cart not found.'}, status=404)

		item, created = CartItem.objects.get_or_create(
			cart=cart,
			product_id=product_id,
			defaults={'quantity': quantity},
		)
		if not created:
			item.quantity += quantity
			item.save(update_fields=['quantity'])

		return JsonResponse({'message': 'Item added to cart.', 'item': _serialize_item(item)}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class CartItemDetailView(View):
	def put(self, request, item_id):
		payload, error = _parse_json(request)
		if error:
			return error

		item = CartItem.objects.filter(id=item_id).first()
		if item is None:
			return JsonResponse({'error': 'cart item not found.'}, status=404)

		try:
			quantity = int(payload.get('quantity'))
		except (TypeError, ValueError):
			return JsonResponse({'error': 'quantity must be integer.'}, status=400)

		if quantity <= 0:
			return JsonResponse({'error': 'quantity must be > 0.'}, status=400)

		item.quantity = quantity
		item.save(update_fields=['quantity'])
		return JsonResponse({'message': 'Cart item updated.', 'item': _serialize_item(item)})

	def delete(self, request, item_id):
		item = CartItem.objects.filter(id=item_id).first()
		if item is None:
			return JsonResponse({'error': 'cart item not found.'}, status=404)

		item.delete()
		return JsonResponse({'message': 'Cart item removed.'})
