import json

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Address, Shipment


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


def _serialize_shipment(shipment):
	return {
		'id': shipment.id,
		'order_id': shipment.order_id,
		'address': _serialize_address(getattr(shipment, 'address', None)),
		'status': shipment.status,
	}


@method_decorator(csrf_exempt, name='dispatch')
class HealthView(View):
	def get(self, request):
		return JsonResponse({'status': 'ok', 'service': 'ship-service'})


@method_decorator(csrf_exempt, name='dispatch')
class ShipmentView(View):
	def get(self, request):
		order_id = request.GET.get('order_id')
		if not order_id:
			return JsonResponse({'error': 'order_id is required.'}, status=400)

		try:
			shipment = Shipment.objects.get(order_id=order_id)
		except Shipment.DoesNotExist:
			return JsonResponse({'error': 'Shipment not found.'}, status=404)

		return JsonResponse(_serialize_shipment(shipment))

	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		order_id = payload.get('order_id')
		address_payload = _normalize_address_payload(payload)

		if not order_id:
			return JsonResponse({'error': 'order_id is required.'}, status=400)
		if not address_payload:
			return JsonResponse({'error': 'address is required.'}, status=400)

		address, address_error = _build_address(address_payload)
		if address_error:
			return JsonResponse({'error': address_error}, status=400)

		shipment, created = Shipment.objects.get_or_create(
			order_id=order_id,
			defaults={
				'address': address,
				'status': Shipment.STATUS_CREATED,
			},
		)
		if not created:
			shipment.address = address
			shipment.save(update_fields=['address'])

		return JsonResponse(
			{
				'message': 'Shipment created successfully.',
				'shipment': _serialize_shipment(shipment),
			},
			status=201,
		)
