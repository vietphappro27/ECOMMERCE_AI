import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db.models import Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import ApiRequestLog, CustomerRating


_recommend_cache: dict[int, dict] = {}
_recommend_cache_ttl = timedelta(minutes=5)


def _parse_json_body(request):
	try:
		return json.loads(request.body or "{}"), None
	except json.JSONDecodeError:
		return None, JsonResponse({"error": "Invalid JSON body."}, status=400)


def _build_target_url(base_url, path, query_string=""):
	target = f"{base_url.rstrip('/')}{path}"
	if query_string:
		target = f"{target}?{query_string}"
	return target


def _json_response_from_raw(raw_body, status_code):
	text = raw_body.decode("utf-8", errors="ignore")
	try:
		payload = json.loads(text) if text else {}
	except json.JSONDecodeError:
		payload = {"message": text}
	return JsonResponse(payload, status=status_code)


def _log_proxy_call(service_name, request, status_code):
	try:
		ApiRequestLog.objects.create(
			service_name=service_name,
			method=request.method,
			path=request.path,
			status_code=status_code,
		)
	except Exception:
		pass


def _proxy_request(request, service_name, service_base_url, service_path, timeout=20):
	target_url = _build_target_url(
		service_base_url,
		service_path,
		request.META.get("QUERY_STRING", ""),
	)

	headers = {"Accept": "application/json"}
	if request.content_type:
		headers["Content-Type"] = request.content_type

	data = request.body if request.method in {"POST", "PUT", "PATCH"} else None
	outbound = urllib.request.Request(
		url=target_url,
		data=data if data else None,
		method=request.method,
		headers=headers,
	)

	try:
		with urllib.request.urlopen(outbound, timeout=timeout) as response:
			raw_body = response.read()
			status_code = response.getcode()
			content_type = response.headers.get("Content-Type", "application/json")
	except urllib.error.HTTPError as exc:
		raw_body = exc.read()
		status_code = exc.code
		content_type = exc.headers.get("Content-Type", "application/json")
	except urllib.error.URLError as exc:
		status_code = 502
		# include exception details to aid debugging (connection refused, name resolution, timeout...)
		raw_body = json.dumps(
			{
				"error": f"Cannot connect to {service_name} service.",
				"details": str(exc),
			}
		).encode("utf-8")
		content_type = "application/json"

	_log_proxy_call(service_name, request, status_code)
	return HttpResponse(raw_body, status=status_code, content_type=content_type)


def _call_login_service(role, username, password):
	normalized_role = (role or "").strip().upper()
	if normalized_role == "CUSTOMER":
		service_name = "customer"
		base_url = settings.CUSTOMER_SERVICE_URL
		path = "/customer/login/"
		id_key = "customer_id"
		dashboard_url = "/ui/customer/"
	elif normalized_role == "STAFF":
		service_name = "staff"
		base_url = settings.STAFF_SERVICE_URL
		path = "/staff/login/"
		id_key = "staff_id"
		dashboard_url = "/ui/staff/"
	else:
		return {
			"ok": False,
			"status": 400,
			"data": {"error": "role must be CUSTOMER or STAFF."},
			"id_key": None,
			"dashboard_url": "/",
		}

	payload = json.dumps({"username": username, "password": password}).encode("utf-8")
	outbound = urllib.request.Request(
		url=_build_target_url(base_url, path),
		data=payload,
		method="POST",
		headers={"Content-Type": "application/json", "Accept": "application/json"},
	)

	try:
		with urllib.request.urlopen(outbound, timeout=20) as response:
			raw_body = response.read()
			status_code = response.getcode()
	except urllib.error.HTTPError as exc:
		raw_body = exc.read()
		status_code = exc.code
	except urllib.error.URLError:
		return {
			"ok": False,
			"status": 502,
			"data": {"error": f"Cannot connect to {service_name} service."},
			"id_key": id_key,
			"dashboard_url": dashboard_url,
		}

	try:
		data = json.loads(raw_body.decode("utf-8") or "{}")
	except json.JSONDecodeError:
		data = {"message": raw_body.decode("utf-8", errors="ignore")}

	if not isinstance(data, dict):
		data = {"message": str(data)}

	return {
		"ok": status_code < 400,
		"status": status_code,
		"data": data,
		"id_key": id_key,
		"dashboard_url": dashboard_url,
	}


def _call_register_service(role, username, password, full_name):
	normalized_role = (role or "").strip().upper()
	if normalized_role == "CUSTOMER":
		service_name = "customer"
		base_url = settings.CUSTOMER_SERVICE_URL
		path = "/customer/register/"
	elif normalized_role == "STAFF":
		service_name = "staff"
		base_url = settings.STAFF_SERVICE_URL
		path = "/staff/register/"
	else:
		return {
			"ok": False,
			"status": 400,
			"data": {"error": "role must be CUSTOMER or STAFF."},
		}

	payload = json.dumps(
		{
			"username": username,
			"password": password,
			"full_name": full_name,
		}
	).encode("utf-8")
	outbound = urllib.request.Request(
		url=_build_target_url(base_url, path),
		data=payload,
		method="POST",
		headers={"Content-Type": "application/json", "Accept": "application/json"},
	)

	try:
		with urllib.request.urlopen(outbound, timeout=20) as response:
			raw_body = response.read()
			status_code = response.getcode()
	except urllib.error.HTTPError as exc:
		raw_body = exc.read()
		status_code = exc.code
	except urllib.error.URLError:
		return {
			"ok": False,
			"status": 502,
			"data": {"error": f"Cannot connect to {service_name} service."},
		}

	try:
		data = json.loads(raw_body.decode("utf-8") or "{}")
	except json.JSONDecodeError:
		data = {"message": raw_body.decode("utf-8", errors="ignore")}

	if not isinstance(data, dict):
		data = {"message": str(data)}

	return {
		"ok": status_code < 400,
		"status": status_code,
		"data": data,
	}


def _save_login_session(request, login_payload, id_key, fallback_role):
	request.session["is_authenticated"] = True
	request.session["role"] = (login_payload.get("role") or fallback_role).upper()
	request.session["username"] = login_payload.get("username", "")
	request.session["full_name"] = login_payload.get("full_name", "")
	# user-service currently returns `user_id` for both CUSTOMER and STAFF logins.
	# Keep role-specific key support for backward compatibility.
	resolved_user_id = login_payload.get(id_key)
	if resolved_user_id in (None, "", 0, "0"):
		resolved_user_id = login_payload.get("user_id")
	if resolved_user_id in (None, "", 0, "0"):
		user_obj = login_payload.get("user") if isinstance(login_payload.get("user"), dict) else {}
		resolved_user_id = user_obj.get("id")
	request.session["user_id"] = resolved_user_id


def _resolve_customer_id(request, candidate):
	value = candidate
	if value in (None, "", 0, "0"):
		value = request.session.get("user_id")
	try:
		value = int(value)
	except Exception:
		return None
	return value if value > 0 else None


def _clean_str(value):
	return str(value or '').strip()


def _normalize_address_payload(payload):
	raw = payload.get('shipping_address') or payload.get('address') or payload.get('shippingAddress')
	if isinstance(raw, dict):
		return {
			'full_name': _clean_str(raw.get('full_name') or raw.get('name')),
			'phone': _clean_str(raw.get('phone')),
			'line1': _clean_str(raw.get('line1') or raw.get('street') or raw.get('address')),
			'line2': _clean_str(raw.get('line2')),
			'ward': _clean_str(raw.get('ward')),
			'district': _clean_str(raw.get('district')),
			'city': _clean_str(raw.get('city')),
			'province': _clean_str(raw.get('province')),
			'country': _clean_str(raw.get('country') or 'Vietnam'),
			'postal_code': _clean_str(raw.get('postal_code') or raw.get('postalCode')),
		}
	if isinstance(raw, str) and raw.strip():
		return {'line1': raw.strip()}
	return None


def _has_role(request, role):
	return request.session.get("is_authenticated") and request.session.get("role") == role


PRODUCT_CATEGORY_SCHEMAS = {
	"furniture": [
		{"name": "material", "label": "Material", "attribute_type": "text", "is_required": True},
		{"name": "dimesions", "label": "Dimensions", "attribute_type": "text", "is_required": True},
	],
	"book": [
		{"name": "author", "label": "Author", "attribute_type": "text", "is_required": True},
		{"name": "publisher", "label": "Publisher", "attribute_type": "text", "is_required": True},
		{"name": "isbn", "label": "ISBN", "attribute_type": "text", "is_required": True},
	],
	"electronic": [
		{"name": "brand", "label": "Brand", "attribute_type": "text", "is_required": True},
		{"name": "warranty", "label": "Warranty", "attribute_type": "text", "is_required": True},
	],
	"food": [
		{"name": "expiry_date", "label": "Expiry Date", "attribute_type": "text", "is_required": True},
		{"name": "origin", "label": "Origin", "attribute_type": "text", "is_required": True},
	],
	"cosmetic": [
		{"name": "brand", "label": "Brand", "attribute_type": "text", "is_required": True},
		{"name": "skin_type", "label": "Skin Type", "attribute_type": "text", "is_required": True},
	],
	"sport": [
		{"name": "type", "label": "Sport Type", "attribute_type": "text", "is_required": True},
		{"name": "weight", "label": "Weight", "attribute_type": "text", "is_required": True},
	],
	"fashion": [
		{"name": "size", "label": "Size", "attribute_type": "text", "is_required": True},
		{"name": "color", "label": "Color", "attribute_type": "text", "is_required": True},
	],
	"toy": [
		{"name": "age_group", "label": "Age Group", "attribute_type": "text", "is_required": True},
		{"name": "material", "label": "Material", "attribute_type": "text", "is_required": True},
	],
	"vehicle": [
		{"name": "brand", "label": "Brand", "attribute_type": "text", "is_required": True},
		{"name": "engine_type", "label": "Engine Type", "attribute_type": "text", "is_required": True},
	],
}


def _request_json(service_name, service_base_url, service_path, method='GET', payload=None, timeout=20):
	target_url = _build_target_url(service_base_url, service_path)
	headers = {'Accept': 'application/json'}
	body = None
	if payload is not None:
		headers['Content-Type'] = 'application/json'
		body = json.dumps(payload).encode('utf-8')

	outbound = urllib.request.Request(
		url=target_url,
		data=body,
		method=method,
		headers=headers,
	)

	try:
		with urllib.request.urlopen(outbound, timeout=timeout) as response:
			raw_body = response.read()
			status_code = response.getcode()
	except urllib.error.HTTPError as exc:
		raw_body = exc.read()
		status_code = exc.code
	except urllib.error.URLError as exc:
		return 502, {'error': f'Cannot connect to {service_name} service.', 'details': str(exc)}

	try:
		data = json.loads(raw_body.decode('utf-8') or '{}')
	except json.JSONDecodeError:
		data = {'message': raw_body.decode('utf-8', errors='ignore')}

	if not isinstance(data, dict):
		data = {'data': data}

	return status_code, data


def _emit_behavior(user_id, product_id, action):
	payload = {
		'user_id': int(user_id),
		'product_id': int(product_id),
		'action': str(action or '').strip().lower(),
	}

	user_status, user_payload = _request_json(
		'user',
		settings.USER_SERVICE_URL,
		'/behaviors/',
		method='POST',
		payload=payload,
	)

	ai_status, ai_payload = _request_json(
		'ai',
		settings.AI_SERVICE_URL,
		'/behaviors',
		method='POST',
		payload=payload,
	)

	return {
		'user': {'status': user_status, 'payload': user_payload},
		'ai': {'status': ai_status, 'payload': ai_payload},
	}


def _normalize_category_key(value):
	if value is None:
		return ''
	return str(value).strip().lower()


def _map_product_rows(payload):
	if not isinstance(payload, dict):
		return []
	if isinstance(payload.get('data'), list):
		return payload['data']
	if isinstance(payload.get('results'), list):
		return payload['results']
	if isinstance(payload.get('items'), list):
		return payload['items']
	return []


def _product_index_by_id(limit=500):
	status_code, payload = _request_json('product', settings.PRODUCT_SERVICE_URL, f'/products/?limit={limit}', method='GET')
	if status_code >= 400:
		return {}

	products = _map_product_rows(payload)
	out = {}
	for row in products:
		try:
			pid = int(row.get('id'))
		except Exception:
			continue
		out[pid] = row
	return out


def _ensure_cart_for_user(user_id):
	status_code, payload = _request_json('cart', settings.CART_SERVICE_URL, f'/carts/?user_id={int(user_id)}', method='GET')
	if status_code >= 400:
		return None, status_code, payload

	rows = payload.get('data') if isinstance(payload, dict) else []
	if isinstance(rows, list) and rows:
		return rows[0], 200, payload

	create_status, create_payload = _request_json(
		'cart',
		settings.CART_SERVICE_URL,
		'/carts/',
		method='POST',
		payload={'user_id': int(user_id)},
	)
	if create_status >= 400:
		return None, create_status, create_payload

	cart = create_payload.get('cart') if isinstance(create_payload, dict) else None
	if not isinstance(cart, dict):
		return None, 502, {'error': 'cart-service response is invalid.'}
	return cart, 201, create_payload


def _build_cart_response(cart):
	items = cart.get('items') if isinstance(cart, dict) else []
	if not isinstance(items, list):
		items = []

	product_index = _product_index_by_id()
	normalized_items = []
	total = 0.0

	for item in items:
		try:
			product_id = int(item.get('product_id'))
			quantity = int(item.get('quantity') or 0)
		except Exception:
			continue

		product = product_index.get(product_id, {})
		if not product:
			continue
		price = float(product.get('price') or 0.0)
		line_total = price * max(0, quantity)
		total += line_total

		normalized_items.append(
			{
				'id': item.get('id'),
				'item_id': product_id,
				'product_id': product_id,
				'name': product.get('name') or f'Product #{product_id}',
				'item_type': (product.get('category_name') or 'product'),
				'price': price,
				'image': product.get('image') or '',
				'quantity': quantity,
				'line_total': line_total,
			}
		)

	return {
		'cart_id': cart.get('id'),
		'customer_id': cart.get('user_id'),
		'items': normalized_items,
		'items_count': sum(int(x.get('quantity') or 0) for x in normalized_items),
		'total': round(total, 2),
	}


def _derive_payment_and_shipping_status(order_id):
	payment_status = 'unknown'
	shipping_status = 'unknown'

	p_status, p_payload = _request_json('payment', settings.PAYMENT_SERVICE_URL, f'/payments/?order_id={int(order_id)}', method='GET')
	if p_status < 400 and isinstance(p_payload, dict):
		payment_status = str(p_payload.get('status') or 'unknown')

	s_status, s_payload = _request_json('ship', settings.SHIP_SERVICE_URL, f'/shipments/?order_id={int(order_id)}', method='GET')
	if s_status < 400 and isinstance(s_payload, dict):
		shipping_status = str(s_payload.get('status') or 'unknown')

	return payment_status, shipping_status


def _list_categories():
	status_code, payload = _request_json('product', settings.PRODUCT_SERVICE_URL, '/categories/', method='GET')
	if status_code >= 400:
		return []

	if isinstance(payload.get('results'), list):
		return payload.get('results', [])
	if isinstance(payload.get('data'), list):
		return payload.get('data', [])
	if isinstance(payload, dict) and isinstance(payload.get('id'), int):
		return [payload]
	if isinstance(payload.get('items'), list):
		return payload.get('items', [])
	return payload if isinstance(payload, list) else []


def _resolve_or_create_category_id(category_input):
	if category_input is None:
		return None, 'category is required.'

	categories = _list_categories()
	if str(category_input).isdigit():
		category_id = int(category_input)
		if any(int(category.get('id', -1)) == category_id for category in categories):
			return category_id, None
		return None, 'category does not exist.'

	category_name = str(category_input).strip()
	if not category_name:
		return None, 'category is required.'

	for category in categories:
		name = str(category.get('name', '')).strip().lower()
		if name == category_name.lower() and category.get('id') is not None:
			return int(category['id']), None

	return None, 'category does not exist.'


def _build_product_payload(raw_payload, partial=False):
	payload = {}

	name = raw_payload.get('name')
	if name is not None and str(name).strip():
		payload['name'] = str(name).strip()
	elif not partial:
		return None, 'name is required.'

	if 'price' in raw_payload and raw_payload.get('price') not in (None, ''):
		payload['price'] = raw_payload.get('price')
	elif not partial:
		payload['price'] = 0

	if 'stock' in raw_payload and raw_payload.get('stock') not in (None, ''):
		payload['stock'] = raw_payload.get('stock')
	elif not partial:
		payload['stock'] = 0

	image = raw_payload.get('image')
	if image is not None:
		payload['image'] = str(image).strip()

	category_input = raw_payload.get('category')
	if category_input is None:
		category_input = raw_payload.get('item_type')

	if category_input is not None:
		category_id, category_error = _resolve_or_create_category_id(category_input)
		if category_error:
			return None, category_error
		payload['category'] = category_id
	elif not partial:
		return None, 'category is required.'

	details = raw_payload.get('details')
	if details is None:
		details = raw_payload.get('attributes')
	if isinstance(details, dict):
		payload['details'] = details

	return payload, None


class LoginPageView(View):
	def get(self, request):
		if _has_role(request, "CUSTOMER"):
			return redirect("/ui/customer/")
		if _has_role(request, "STAFF"):
			return redirect("/ui/staff/")
		info = ""
		if request.GET.get("info") == "registered":
			info = "Register successful. Please login."
		return render(
			request,
			"app/login.html",
			{"error": "", "info": info, "role": "CUSTOMER"},
		)


@method_decorator(csrf_exempt, name="dispatch")
class RegisterPageView(View):
	def get(self, request):
		if _has_role(request, "CUSTOMER"):
			return redirect("/ui/customer/")
		if _has_role(request, "STAFF"):
			return redirect("/ui/staff/")
		return render(
			request,
			"app/register.html",
			{"error": "", "role": "CUSTOMER", "username": "", "full_name": ""},
		)

	def post(self, request):
		username = (request.POST.get("username") or "").strip()
		password = request.POST.get("password") or ""
		full_name = (request.POST.get("full_name") or "").strip()
		role = (request.POST.get("role") or "").strip().upper()

		if not username or not password or not full_name:
			return render(
				request,
				"app/register.html",
				{
					"error": "username, password and full_name are required.",
					"role": role or "CUSTOMER",
					"username": username,
					"full_name": full_name,
				},
			)

		register_result = _call_register_service(role, username, password, full_name)
		if not register_result["ok"]:
			error_message = register_result["data"].get("error", "Register failed.")
			return render(
				request,
				"app/register.html",
				{
					"error": error_message,
					"role": role or "CUSTOMER",
					"username": username,
					"full_name": full_name,
				},
			)

		return redirect("/?info=registered")


@method_decorator(csrf_exempt, name="dispatch")
class UiLoginView(View):
	def post(self, request):
		username = (request.POST.get("username") or "").strip()
		password = request.POST.get("password") or ""
		role = (request.POST.get("role") or "").strip().upper()

		if not username or not password:
			return render(
				request,
				"app/login.html",
				{
					"error": "username and password are required.",
					"info": "",
					"role": role or "CUSTOMER",
				},
			)

		login_result = _call_login_service(role, username, password)
		if not login_result["ok"]:
			error_message = login_result["data"].get("error", "Login failed.")
			return render(
				request,
				"app/login.html",
				{"error": error_message, "info": "", "role": role or "CUSTOMER"},
			)

		_save_login_session(
			request,
			login_result["data"],
			login_result["id_key"],
			role,
		)
		return redirect(login_result["dashboard_url"])


class LogoutView(View):
	def get(self, request):
		request.session.flush()
		return redirect("/")


class CustomerDashboardView(View):
	def get(self, request):
		if not _has_role(request, "CUSTOMER"):
			return redirect("/")
		return render(
			request,
			"app/customer_dashboard.html",
			{
				"username": request.session.get("username"),
				"full_name": request.session.get("full_name"),
				"user_id": request.session.get("user_id"),
			},
		)


class CustomerCartPageView(View):
	def get(self, request):
		if not _has_role(request, "CUSTOMER"):
			return redirect("/")
		return render(
			request,
			"app/customer_cart.html",
			{
				"username": request.session.get("username"),
				"full_name": request.session.get("full_name"),
				"user_id": request.session.get("user_id"),
			},
		)


class ProductDetailPageView(View):
	def get(self, request, product_id):
		if not _has_role(request, "CUSTOMER"):
			return redirect("/")
		return render(
			request,
			"app/product_detail.html",
			{
				"username": request.session.get("username"),
				"full_name": request.session.get("full_name"),
				"user_id": request.session.get("user_id"),
				"product_id": product_id,
			},
		)


class CustomerOrderPageView(View):
	def get(self, request):
		if not _has_role(request, "CUSTOMER"):
			return redirect("/")
		return render(
			request,
			"app/customer_order.html",
			{
				"username": request.session.get("username"),
				"full_name": request.session.get("full_name"),
				"user_id": request.session.get("user_id"),
			},
		)


class StaffDashboardView(View):
	def get(self, request):
		if not _has_role(request, "STAFF"):
			return redirect("/")
		return render(
			request,
			"app/staff_dashboard.html",
			{
				"username": request.session.get("username"),
				"full_name": request.session.get("full_name"),
				"user_id": request.session.get("user_id"),
			},
		)


@method_decorator(csrf_exempt, name="dispatch")
class ApiRoleRegisterView(View):
	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		username = (body.get("username") or "").strip()
		password = body.get("password") or ""
		full_name = (body.get("full_name") or "").strip()
		role = (body.get("role") or "").strip().upper()

		if not username or not password or not full_name:
			return JsonResponse(
				{"error": "username, password and full_name are required."},
				status=400,
			)

		register_result = _call_register_service(role, username, password, full_name)
		return JsonResponse(register_result["data"], status=register_result["status"])


@method_decorator(csrf_exempt, name="dispatch")
class ApiRoleLoginView(View):
	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		username = (body.get("username") or "").strip()
		password = body.get("password") or ""
		role = (body.get("role") or "").strip().upper()

		if not username or not password:
			return JsonResponse({"error": "username and password are required."}, status=400)

		login_result = _call_login_service(role, username, password)
		if not login_result["ok"]:
			return JsonResponse(login_result["data"], status=login_result["status"])

		_save_login_session(
			request,
			login_result["data"],
			login_result["id_key"],
			role,
		)

		response_payload = dict(login_result["data"])
		response_payload["dashboard_url"] = login_result["dashboard_url"]
		return JsonResponse(response_payload)


@method_decorator(csrf_exempt, name="dispatch")
class CustomerRegisterProxyView(View):
	def post(self, request):
		return _proxy_request(request, "customer", settings.CUSTOMER_SERVICE_URL, "/customer/register/")


@method_decorator(csrf_exempt, name="dispatch")
class CustomerLoginProxyView(View):
	def post(self, request):
		return _proxy_request(request, "customer", settings.CUSTOMER_SERVICE_URL, "/customer/login/")


@method_decorator(csrf_exempt, name="dispatch")
class CustomerCartProxyView(View):
	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		customer_id = _resolve_customer_id(request, body.get('customer_id') or body.get('user_id'))
		if not customer_id:
			return JsonResponse({'error': 'customer_id is required.'}, status=400)

		cart, status_code, payload = _ensure_cart_for_user(customer_id)
		if status_code >= 400 or cart is None:
			return JsonResponse(payload, status=status_code)

		return JsonResponse(_build_cart_response(cart), status=201)

	def get(self, request):
		customer_id = _resolve_customer_id(request, request.GET.get('customer_id') or request.GET.get('user_id'))
		if not customer_id:
			return JsonResponse({'error': 'customer_id is required.'}, status=400)

		cart, status_code, payload = _ensure_cart_for_user(customer_id)
		if status_code >= 400 or cart is None:
			return JsonResponse(payload, status=status_code)

		return JsonResponse(_build_cart_response(cart), status=200)


@method_decorator(csrf_exempt, name="dispatch")
class CustomerCartItemProxyView(View):
	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		customer_id = _resolve_customer_id(request, body.get('customer_id') or body.get('user_id'))
		product_id = body.get('product_id')
		quantity = body.get('quantity', 1)

		if not customer_id or not product_id:
			return JsonResponse({'error': 'customer_id and product_id are required.'}, status=400)

		try:
			quantity = int(quantity)
		except Exception:
			return JsonResponse({'error': 'quantity must be integer.'}, status=400)

		if quantity <= 0:
			return JsonResponse({'error': 'quantity must be > 0.'}, status=400)

		cart, status_code, payload = _ensure_cart_for_user(customer_id)
		if status_code >= 400 or cart is None:
			return JsonResponse(payload, status=status_code)

		add_status, add_payload = _request_json(
			'cart',
			settings.CART_SERVICE_URL,
			'/cart-items/',
			method='POST',
			payload={
				'cart': int(cart.get('id')),
				'product_id': int(product_id),
				'quantity': quantity,
			},
		)
		if add_status >= 400:
			return JsonResponse(add_payload, status=add_status)

		_ = _emit_behavior(customer_id, product_id, 'add_to_cart')

		updated_cart_status, updated_cart_payload = _request_json(
			'cart',
			settings.CART_SERVICE_URL,
			f"/carts/?user_id={int(customer_id)}",
			method='GET',
		)
		if updated_cart_status >= 400:
			return JsonResponse(add_payload, status=201)

		rows = updated_cart_payload.get('data') if isinstance(updated_cart_payload, dict) else []
		if not isinstance(rows, list) or not rows:
			return JsonResponse(add_payload, status=201)

		return JsonResponse(_build_cart_response(rows[0]), status=201)

	def put(self, request, cart_item_id):
		body, error = _parse_json_body(request)
		if error:
			return error

		quantity = body.get('quantity')
		try:
			quantity = int(quantity)
		except Exception:
			return JsonResponse({'error': 'quantity must be integer.'}, status=400)

		if quantity <= 0:
			return JsonResponse({'error': 'quantity must be > 0.'}, status=400)

		status_code, payload = _request_json(
			'cart',
			settings.CART_SERVICE_URL,
			f'/cart-items/{int(cart_item_id)}/',
			method='PUT',
			payload={'quantity': quantity},
		)
		return JsonResponse(payload, status=status_code)

	def delete(self, request, cart_item_id):
		return _proxy_request(
			request,
			'cart',
			settings.CART_SERVICE_URL,
			f'/cart-items/{int(cart_item_id)}/',
		)


@method_decorator(csrf_exempt, name="dispatch")
class CustomerSearchProxyView(View):
	def get(self, request):
		keyword = (request.GET.get('q') or '').strip()
		customer_id = _resolve_customer_id(request, request.GET.get('customer_id') or request.GET.get('user_id'))
		matched_product_ids = []

		if customer_id and keyword:
			needle = keyword.lower()
			for product_id, product in _product_index_by_id().items():
				text = ' '.join(
					str(product.get(key) or '')
					for key in ('name', 'description', 'category_name', 'item_type')
				).lower()
				if needle and needle in text:
					matched_product_ids.append(product_id)
				if len(matched_product_ids) >= 3:
					break

			for product_id in matched_product_ids:
				_ = _emit_behavior(customer_id, product_id, 'search')

		return JsonResponse({'ok': True, 'query': keyword, 'tracked_product_ids': matched_product_ids})


@method_decorator(csrf_exempt, name="dispatch")
class CustomerRatingProxyView(View):
	def get(self, request):
		customer_id = _resolve_customer_id(request, request.GET.get('customer_id') or request.GET.get('user_id'))
		item_type = str(request.GET.get('item_type') or 'product').strip().lower()
		item_id = request.GET.get('item_id')

		if not item_id:
			return JsonResponse({'error': 'item_id is required.'}, status=400)

		try:
			item_id = int(item_id)
		except Exception:
			return JsonResponse({'error': 'item_id must be integer.'}, status=400)

		if item_id <= 0:
			return JsonResponse({'error': 'item_id must be > 0.'}, status=400)

		qs = CustomerRating.objects.filter(item_type=item_type, item_id=item_id)
		agg = qs.aggregate(average_score=Avg('score'))
		my_score = 0
		if customer_id:
			mine = qs.filter(customer_id=int(customer_id)).first()
			if mine is not None:
				my_score = int(mine.score)

		return JsonResponse(
			{
				'average_score': round(float(agg.get('average_score') or 0.0), 2),
				'votes': int(qs.count()),
				'my_score': my_score,
			}
		)

	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		customer_id = _resolve_customer_id(request, body.get('customer_id') or body.get('user_id'))
		if not customer_id:
			return JsonResponse({'error': 'customer_id is required.'}, status=400)

		item_type = str(body.get('item_type') or 'product').strip().lower()
		item_id = body.get('item_id') or body.get('product_id')
		score = body.get('score')
		if score in (None, ''):
			score = body.get('rating')
		review = str(body.get('review') or body.get('comment') or '').strip()

		if not item_id:
			return JsonResponse({'error': 'item_id is required.'}, status=400)

		try:
			item_id = int(item_id)
			score = int(score)
		except Exception:
			return JsonResponse({'error': 'item_id and score must be integers.'}, status=400)

		if item_id <= 0:
			return JsonResponse({'error': 'item_id must be > 0.'}, status=400)
		if score < 1 or score > 5:
			return JsonResponse({'error': 'score must be in range 1..5.'}, status=400)

		CustomerRating.objects.update_or_create(
			customer_id=int(customer_id),
			item_type=item_type,
			item_id=int(item_id),
			defaults={'score': score, 'review': review},
		)

		_ = _emit_behavior(customer_id, item_id, 'rating')

		return JsonResponse({'message': 'Rating saved.', 'customer_id': customer_id}, status=201)


@method_decorator(csrf_exempt, name="dispatch")
class CustomerActivityProxyView(View):
	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		customer_id = _resolve_customer_id(request, body.get('customer_id') or body.get('user_id'))
		product_id = body.get('item_id') or body.get('product_id')
		action = str(body.get('action') or '').strip().lower()

		if not customer_id:
			return JsonResponse({'error': 'customer_id is required.'}, status=400)

		mapped_action = 'view'
		if action in {'add_to_cart', 'add-cart', 'addcart'}:
			mapped_action = 'add_to_cart'
		elif action in {'click', 'click_product'}:
			mapped_action = 'click'

		if not product_id:
			return JsonResponse({'message': 'Activity saved without product context.'}, status=201)

		result = _emit_behavior(customer_id, product_id, mapped_action)
		return JsonResponse(result.get('user', {}).get('payload', {}), status=result.get('user', {}).get('status', 502))


@method_decorator(csrf_exempt, name="dispatch")
class OrderProxyView(View):
	def get(self, request):
		customer_id = request.GET.get('customer_id') or request.GET.get('user_id')
		query = f"/orders/?user_id={int(customer_id)}" if customer_id else '/orders/'
		status_code, payload = _request_json('order', settings.ORDER_SERVICE_URL, query, method='GET')
		if status_code >= 400:
			return JsonResponse(payload, status=status_code)

		orders = payload.get('orders') if isinstance(payload, dict) else []
		if not isinstance(orders, list):
			orders = []

		product_index = _product_index_by_id()
		normalized = []
		for order in orders:
			order_id = order.get('id')
			if not order_id:
				continue
			payment_status, shipping_status = _derive_payment_and_shipping_status(order_id)
			items = []
			for item in order.get('items') or []:
				try:
					product_id = int(item.get('product_id') or item.get('item_id') or 0)
				except Exception:
					product_id = 0
				product = product_index.get(product_id, {})
				unit_price = float(item.get('unit_price') or item.get('price') or product.get('price') or 0)
				items.append(
					{
						**item,
						'product_id': product_id,
						'name': item.get('name') or item.get('product_name') or product.get('name') or f'Product #{product_id}',
						'product_name': item.get('product_name') or product.get('name') or f'Product #{product_id}',
						'price': unit_price,
						'unit_price': unit_price,
						'category_name': product.get('category_name') or item.get('category_name') or '',
						'image': product.get('image') or item.get('image') or '',
					}
				)
			normalized.append(
				{
					'id': order_id,
					'user_id': order.get('user_id'),
					'total_amount': order.get('total_price'),
					'status': order.get('status'),
					'payment_status': payment_status,
					'shipping_status': shipping_status,
					'created_at': order.get('created_at'),
					'items': items,
				}
			)

		return JsonResponse({'orders': normalized}, status=200)

	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		customer_id = body.get('customer_id') or body.get('user_id')
		items = body.get('items') or []
		address_payload = _normalize_address_payload(body)
		payment_status = str(body.get('payment_status') or '').strip().lower()
		payment_method = str(body.get('payment_method') or '').strip().lower()

		if not customer_id:
			return JsonResponse({'error': 'customer_id is required.'}, status=400)
		if not isinstance(items, list) or not items:
			return JsonResponse({'error': 'items must be a non-empty list.'}, status=400)
		if not address_payload or not address_payload.get('line1'):
			return JsonResponse({'error': 'shipping_address.line1 is required.'}, status=400)

		if not payment_status:
			payment_status = 'pending' if payment_method == 'cod' else 'paid'

		order_payload = {
			'user_id': int(customer_id),
			'address': address_payload,
			'payment_status': payment_status,
			'items': [
				{
					'product_id': int(item.get('product_id') or item.get('item_id') or 0),
					'quantity': int(item.get('quantity') or 1),
					'unit_price': float(item.get('unit_price') or item.get('price') or 0),
				}
				for item in items
			],
		}

		order_payload['items'] = [
			x for x in order_payload['items']
			if x['product_id'] > 0 and x['quantity'] > 0 and x['unit_price'] > 0
		]
		if not order_payload['items']:
			return JsonResponse({'error': 'No valid order items with price.'}, status=400)

		status_code, payload = _request_json(
			'order',
			settings.ORDER_SERVICE_URL,
			'/orders/',
			method='POST',
			payload=order_payload,
		)

		if status_code < 400:
			for item in order_payload.get('items', []):
				product_id = item.get('product_id')
				if product_id:
					_ = _emit_behavior(customer_id, product_id, 'buy')
		return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class OrderDetailProxyView(View):
	def get(self, request, order_id):
		return _proxy_request(
			request,
			"order",
			settings.ORDER_SERVICE_URL,
			f"/orders/{order_id}/",
		)


@method_decorator(csrf_exempt, name="dispatch")
class AIRecommendationProxyView(View):
	def get(self, request, customer_id):
		limit = request.GET.get('limit') or '8'
		try:
			limit_int = max(1, min(int(limit), 50))
		except Exception:
			limit_int = 8

		now = datetime.now(timezone.utc)
		cached = _recommend_cache.get(int(customer_id))
		if cached:
			cached_at = cached.get('cached_at')
			if isinstance(cached_at, datetime) and now - cached_at <= _recommend_cache_ttl:
				return JsonResponse(cached.get('payload', {}), status=200)

		status_code, payload = _request_json(
			'ai',
			settings.AI_SERVICE_URL,
			f"/ai/recommendations/{int(customer_id)}/?limit={limit_int}",
			method='GET',
			timeout=45,
		)

		if status_code < 400 and isinstance(payload, dict):
			_recommend_cache[int(customer_id)] = {
				'cached_at': now,
				'payload': payload,
			}

		return JsonResponse(payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class AIChatProxyView(View):
	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		question = str(body.get('question') or body.get('message') or '').strip()
		if not question:
			return JsonResponse({'error': 'question is required.'}, status=400)

		payload = dict(body)
		payload['question'] = question
		payload.pop('message', None)
		status_code, response_payload = _request_json(
			'ai',
			settings.AI_SERVICE_URL,
			'/ai/chat/',
			method='POST',
			payload=payload,
			timeout=90,
		)
		return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class StaffRegisterProxyView(View):
	def post(self, request):
		return _proxy_request(request, "staff", settings.STAFF_SERVICE_URL, "/staff/register/")


@method_decorator(csrf_exempt, name="dispatch")
class StaffLoginProxyView(View):
	def post(self, request):
		return _proxy_request(request, "staff", settings.STAFF_SERVICE_URL, "/staff/login/")


@method_decorator(csrf_exempt, name="dispatch")
class StaffItemProxyView(View):
	def get(self, request):
		return _proxy_request(request, 'product', settings.PRODUCT_SERVICE_URL, '/products/')

	def post(self, request):
		body, error = _parse_json_body(request)
		if error:
			return error

		product_payload, payload_error = _build_product_payload(body, partial=False)
		if payload_error:
			return JsonResponse({'error': payload_error}, status=400)

		status_code, response_payload = _request_json(
			'product',
			settings.PRODUCT_SERVICE_URL,
			'/products/',
			method='POST',
			payload=product_payload,
		)
		return JsonResponse(response_payload, status=status_code)


@method_decorator(csrf_exempt, name="dispatch")
class StaffItemAttributesProxyView(View):
	def get(self, request):
		category_input = request.GET.get('category')
		if not category_input:
			return JsonResponse({'attributes': [], 'message': 'category query parameter is required.'}, status=200)

		category_key = _normalize_category_key(category_input)
		if category_key.isdigit():
			categories = _list_categories()
			matched = next((item for item in categories if int(item.get('id', -1)) == int(category_key)), None)
			if matched:
				category_key = _normalize_category_key(matched.get('name'))

		attributes = PRODUCT_CATEGORY_SCHEMAS.get(category_key, [])
		return JsonResponse({'category': category_input, 'attributes': attributes})


@method_decorator(csrf_exempt, name="dispatch")
class StaffItemDetailProxyView(View):
	def get(self, request, item_id):
		return _proxy_request(
			request,
			'product',
			settings.PRODUCT_SERVICE_URL,
			f'/products/{item_id}/',
		)

	def put(self, request, item_id):
		body, error = _parse_json_body(request)
		if error:
			return error

		product_payload, payload_error = _build_product_payload(body, partial=False)
		if payload_error:
			return JsonResponse({'error': payload_error}, status=400)

		status_code, response_payload = _request_json(
			'product',
			settings.PRODUCT_SERVICE_URL,
			f'/products/{item_id}/',
			method='PUT',
			payload=product_payload,
		)
		return JsonResponse(response_payload, status=status_code)

	def patch(self, request, item_id):
		body, error = _parse_json_body(request)
		if error:
			return error

		product_payload, payload_error = _build_product_payload(body, partial=True)
		if payload_error:
			return JsonResponse({'error': payload_error}, status=400)

		if not product_payload:
			return JsonResponse({'error': 'No valid fields to update.'}, status=400)

		status_code, response_payload = _request_json(
			'product',
			settings.PRODUCT_SERVICE_URL,
			f'/products/{item_id}/',
			method='PATCH',
			payload=product_payload,
		)
		return JsonResponse(response_payload, status=status_code)

	def delete(self, request, item_id):
		return _proxy_request(
			request,
			'product',
			settings.PRODUCT_SERVICE_URL,
			f'/products/{item_id}/',
		)


@method_decorator(csrf_exempt, name="dispatch")
class ProductProxyView(View):
	def get(self, request, product_id=None):
		if product_id is None:
			path = "/products/"
		else:
			path = f"/products/{product_id}/"
		return _proxy_request(request, "product", settings.PRODUCT_SERVICE_URL, path)


@method_decorator(csrf_exempt, name="dispatch")
class ProductCategoryProxyView(View):
	def get(self, request):
		return _proxy_request(request, "product", settings.PRODUCT_SERVICE_URL, "/categories/")
