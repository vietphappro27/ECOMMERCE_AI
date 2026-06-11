import json

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Address, Payment


def _parse_json(request):
	try:
		return json.loads(request.body or '{}'), None
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


def _serialize_payment(payment):
	return {
		'id': payment.id,
		'order_id': payment.order_id,
		'status': payment.status,
		'address': _serialize_address(getattr(payment, 'address', None)),
	}


@method_decorator(csrf_exempt, name='dispatch')
class HealthView(View):
	def get(self, request):
		return JsonResponse({'status': 'ok', 'service': 'payment-service'})


@method_decorator(csrf_exempt, name='dispatch')
class PaymentView(View):
	def get(self, request):
		order_id = request.GET.get('order_id')
		if not order_id:
			return JsonResponse({'error': 'order_id is required.'}, status=400)

		try:
			payment = Payment.objects.get(order_id=order_id)
		except Payment.DoesNotExist:
			return JsonResponse({'error': 'Payment not found.'}, status=404)

		return JsonResponse(_serialize_payment(payment))

	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		order_id = payload.get('order_id')
		status_value = (payload.get('status') or Payment.STATUS_PENDING).strip().lower()
		address_payload = _normalize_address_payload(payload)

		if not order_id:
			return JsonResponse({'error': 'order_id is required.'}, status=400)
		if status_value not in {Payment.STATUS_PENDING, Payment.STATUS_PAID, Payment.STATUS_FAILED}:
			return JsonResponse({'error': 'status is invalid.'}, status=400)
		if not address_payload:
			return JsonResponse({'error': 'address is required.'}, status=400)

		address, address_error = _build_address(address_payload)
		if address_error:
			return JsonResponse({'error': address_error}, status=400)

		payment, _ = Payment.objects.get_or_create(
			order_id=order_id,
			defaults={
				'status': status_value,
				'address': address,
			},
		)

		payment.status = status_value
		payment.address = address
		payment.save(update_fields=['status', 'address'])

		return JsonResponse(
			{
				'message': 'Payment saved.',
				'payment': _serialize_payment(payment),
			},
			status=201,
		)
