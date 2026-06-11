import json
import os
from decimal import Decimal

import httpx
from django.db import transaction
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Address, Order, OrderItem


PAYMENT_SERVICE_URL = os.getenv('PAYMENT_SERVICE_URL', 'http://payment-service:8007').rstrip('/')
SHIP_SERVICE_URL = os.getenv('SHIP_SERVICE_URL', 'http://ship-service:8008').rstrip('/')


def _parse_json(request):
	try:
		return json.loads(request.body or "{}"), None
	except json.JSONDecodeError:
		return None, JsonResponse({'error': 'Invalid JSON body.'}, status=400)


def _clean_str(value):
	return str(value or '').strip()


def _normalize_address_payload(payload):
	raw = payload.get('address') or payload.get('shipping_address') or payload.get('shippingAddress')
	if isinstance(raw, dict):
		return raw
	if isinstance(raw, str) and raw.strip():
		return {'line1': raw.strip()}
	return None


def _build_address(address_payload):
	if not isinstance(address_payload, dict):
		return None, 'address is required.'

	line1 = _clean_str(address_payload.get('line1') or address_payload.get('street') or address_payload.get('address'))
	if not line1:
		return None, 'address.line1 is required.'

	address = Address.objects.create(
		full_name=_clean_str(address_payload.get('full_name') or address_payload.get('name')),
		phone=_clean_str(address_payload.get('phone')),
		line1=line1,
		line2=_clean_str(address_payload.get('line2')),
		ward=_clean_str(address_payload.get('ward')),
		district=_clean_str(address_payload.get('district')),
		city=_clean_str(address_payload.get('city')),
		province=_clean_str(address_payload.get('province')),
		country=_clean_str(address_payload.get('country') or 'Vietnam'),
		postal_code=_clean_str(address_payload.get('postal_code') or address_payload.get('postalCode')),
	)
	return address, None


def _serialize_address(address):
	if not address:
		return None
	return {
		'id': address.id,
		'full_name': address.full_name,
		'phone': address.phone,
		'line1': address.line1,
		'line2': address.line2,
		'ward': address.ward,
		'district': address.district,
		'city': address.city,
		'province': address.province,
		'country': address.country,
		'postal_code': address.postal_code,
	}


def _serialize_order(order):
	return {
		'id': order.id,
		'user_id': order.user_id,
		'total_price': str(order.total_price),
		'status': order.status,
		'address': _serialize_address(getattr(order, 'address', None)),
		'created_at': order.created_at.isoformat(),
		'updated_at': order.updated_at.isoformat(),
		'items': [
			{
				'product_id': item.product_id,
				'quantity': item.quantity,
			}
			for item in order.items.all()
		],
	}


def _process_payment(order_id, address_payload, status='paid'):
	payload = {
		'order_id': order_id,
		'status': status,
		'address': address_payload,
	}
	with httpx.Client(timeout=10.0) as client:
		response = client.post(f'{PAYMENT_SERVICE_URL}/payments/', json=payload)
		response.raise_for_status()
		data = response.json()
	payment = data.get('payment') or {}
	return {'status': str(payment.get('status') or '').lower(), 'data': data}


def _create_shipment(order_id, address_payload):
	payload = {
		'order_id': order_id,
		'address': address_payload,
	}
	with httpx.Client(timeout=10.0) as client:
		response = client.post(f'{SHIP_SERVICE_URL}/shipments/', json=payload)
		response.raise_for_status()
		data = response.json()
	return data


@method_decorator(csrf_exempt, name='dispatch')
class HealthView(View):
	def get(self, request):
		return JsonResponse({'status': 'ok', 'service': 'order-service'})


@method_decorator(csrf_exempt, name='dispatch')
class OrderListCreateView(View):
	def get(self, request):
		user_id = request.GET.get('user_id') or request.GET.get('customer_id')
		queryset = Order.objects.select_related('address').prefetch_related('items').order_by('-created_at')
		if user_id:
			queryset = queryset.filter(user_id=user_id)
		return JsonResponse({'orders': [_serialize_order(order) for order in queryset]})

	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		user_id = payload.get('user_id')
		items = payload.get('items') or []
		address_payload = _normalize_address_payload(payload)
		payment_status = str(payload.get('payment_status') or 'paid').strip().lower()

		if not user_id:
			return JsonResponse({'error': 'user_id is required.'}, status=400)
		if not isinstance(items, list) or not items:
			return JsonResponse({'error': 'items must be a non-empty list.'}, status=400)
		if not address_payload:
			return JsonResponse({'error': 'address is required.'}, status=400)
		if payment_status not in {'pending', 'paid', 'failed'}:
			return JsonResponse({'error': 'payment_status must be pending, paid or failed.'}, status=400)

		parsed_items = []
		total = Decimal('0')
		for item in items:
			try:
				product_id = int(item.get('product_id'))
				quantity = int(item.get('quantity', 1))
				unit_price = Decimal(str(item.get('unit_price', 0)))
			except Exception:
				return JsonResponse({'error': 'Invalid item payload.'}, status=400)

			if quantity <= 0:
				return JsonResponse({'error': 'quantity must be > 0.'}, status=400)

			parsed_items.append(
				{
					'product_id': product_id,
					'quantity': quantity,
				}
			)
			total += unit_price * quantity

		with transaction.atomic():
			address, address_error = _build_address(address_payload)
			if address_error:
				return JsonResponse({'error': address_error}, status=400)

			order = Order.objects.create(
				user_id=user_id,
				total_price=total,
				address=address,
			)
			OrderItem.objects.bulk_create(
				[
					OrderItem(
						order=order,
						product_id=item['product_id'],
						quantity=item['quantity'],
					)
					for item in parsed_items
				]
			)

		payment_result = None
		shipment_result = None

		try:
			payment_result = _process_payment(order.id, _serialize_address(order.address), payment_status)
		except Exception as ex:
			order.status = Order.STATUS_CANCELED
			order.save(update_fields=['status', 'updated_at'])
			return JsonResponse({'error': f'Payment service failed: {ex}', 'order': _serialize_order(order)}, status=502)

		if payment_result.get('status') == 'paid':
			try:
				shipment_result = _create_shipment(order.id, _serialize_address(order.address))
				order.status = Order.STATUS_SHIPPED
			except Exception as ex:
				order.status = Order.STATUS_CONFIRMED
				order.save(update_fields=['status', 'updated_at'])
				return JsonResponse(
					{
						'error': f'Shipping service failed: {ex}',
						'payment': payment_result.get('data'),
						'order': _serialize_order(order),
					},
					status=502,
				)
		else:
			order.status = Order.STATUS_CONFIRMED if payment_result.get('status') == 'pending' else Order.STATUS_CANCELED

		order.save(update_fields=['status', 'updated_at'])

		return JsonResponse(
			{
				'message': 'Order created successfully.',
				'order': _serialize_order(order),
				'payment': payment_result.get('data') if payment_result else None,
				'shipment': shipment_result,
			},
			status=201,
		)


@method_decorator(csrf_exempt, name='dispatch')
class OrderDetailView(View):
	def get(self, request, order_id):
		try:
			order = Order.objects.select_related('address').prefetch_related('items').get(id=order_id)
		except Order.DoesNotExist:
			return JsonResponse({'error': 'Order not found.'}, status=404)
		return JsonResponse(_serialize_order(order))
