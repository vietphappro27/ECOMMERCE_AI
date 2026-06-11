import json
import importlib

from django.http import JsonResponse
from django.db import transaction
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .neo4j_client import BehaviorEvent, neo4j_behavior_client
from .models import Role, User, UserBehavior, UserRole


def _parse_json(request):
	try:
		return json.loads(request.body or '{}'), None
	except json.JSONDecodeError:
		return None, JsonResponse({'error': 'Invalid JSON body.'}, status=400)
 

def _serialize_user(user):
	return {
		'id': user.id,
		'full_name': user.full_name,
		'email': user.email,
	}


def _serialize_behavior(item):
	return {
		'id': item.id,
		'user_id': item.user_id,
		'product_id': item.product_id,
		'action': item.action,
		'timestamp': item.timestamp.isoformat(),
	}


def _ensure_role_for_user(user, role_name):
	role, _ = Role.objects.get_or_create(name=role_name)
	UserRole.objects.get_or_create(user=user, role=role)


def _load_jwt_classes():
	try:
		tokens_module = importlib.import_module('rest_framework_simplejwt.tokens')
		return tokens_module.AccessToken, tokens_module.RefreshToken, tokens_module.UntypedToken
	except Exception:
		return None, None, None


def _extract_roles(user):
	return [pair.role.name for pair in user.user_roles.select_related('role').all()]


def _issue_tokens(user, roles):
	AccessToken, RefreshToken, _ = _load_jwt_classes()
	if AccessToken is None or RefreshToken is None:
		raise RuntimeError('JWT dependency is missing. Install djangorestframework-simplejwt.')

	refresh = RefreshToken()
	refresh['user_id'] = user.id
	refresh['email'] = user.email
	refresh['full_name'] = user.full_name
	refresh['roles'] = roles

	access = AccessToken()
	access['user_id'] = user.id
	access['email'] = user.email
	access['full_name'] = user.full_name
	access['roles'] = roles

	return {'access': str(access), 'refresh': str(refresh)}


def _parse_bearer_token(request):
	auth_header = (request.headers.get('Authorization') or '').strip()
	if not auth_header.lower().startswith('bearer '):
		return None
	return auth_header.split(' ', 1)[1].strip()


@method_decorator(csrf_exempt, name='dispatch')
class HealthView(View):
	def get(self, request):
		return JsonResponse({'status': 'ok', 'service': 'user-service'})


@method_decorator(csrf_exempt, name='dispatch')
class UserView(View):
	def get(self, request):
		users = User.objects.order_by('-id')
		return JsonResponse({'count': users.count(), 'data': [_serialize_user(user) for user in users]})

	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		full_name = (payload.get('full_name') or '').strip()
		email = (payload.get('email') or '').strip().lower()
		password = payload.get('password') or ''

		if not full_name or not email or not password:
			return JsonResponse({'error': 'full_name, email, password are required.'}, status=400)

		if User.objects.filter(email=email).exists():
			return JsonResponse({'error': 'email already exists.'}, status=400)

		user = User.objects.create(full_name=full_name, email=email, password=password)
		return JsonResponse({'message': 'User created.', 'user': _serialize_user(user)}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class RoleView(View):
	def get(self, request):
		roles = Role.objects.order_by('name')
		return JsonResponse({'count': roles.count(), 'data': [{'id': role.id, 'name': role.name} for role in roles]})

	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		name = (payload.get('name') or '').strip()
		if not name:
			return JsonResponse({'error': 'name is required.'}, status=400)

		role, created = Role.objects.get_or_create(name=name)
		return JsonResponse({'message': 'Role created.' if created else 'Role already exists.', 'id': role.id, 'name': role.name}, status=201 if created else 200)


@method_decorator(csrf_exempt, name='dispatch')
class UserRoleView(View):
	def get(self, request):
		pairs = UserRole.objects.select_related('user', 'role').order_by('-id')
		data = [
			{
				'id': pair.id,
				'user': pair.user_id,
				'role': pair.role_id,
				'user_email': pair.user.email,
				'role_name': pair.role.name,
			}
			for pair in pairs
		]
		return JsonResponse({'count': len(data), 'data': data})

	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		user_id = payload.get('user')
		role_id = payload.get('role')
		if not user_id or not role_id:
			return JsonResponse({'error': 'user and role are required.'}, status=400)

		user = User.objects.filter(id=user_id).first()
		role = Role.objects.filter(id=role_id).first()
		if user is None or role is None:
			return JsonResponse({'error': 'user or role not found.'}, status=404)

		user_role, created = UserRole.objects.get_or_create(user=user, role=role)
		return JsonResponse(
			{
				'message': 'User role assigned.' if created else 'User already has this role.',
				'id': user_role.id,
				'user': user_role.user_id,
				'role': user_role.role_id,
			},
			status=201 if created else 200,
		)


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(View):
	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		email = (payload.get('email') or '').strip().lower()
		password = payload.get('password') or ''

		if not email or not password:
			return JsonResponse({'error': 'email and password are required.'}, status=400)

		user = User.objects.filter(email=email, password=password).first()
		if user is None:
			return JsonResponse({'error': 'Invalid credentials.'}, status=401)

		roles = _extract_roles(user)
		tokens = _issue_tokens(user, roles)
		return JsonResponse({'message': 'Login successful.', 'user': _serialize_user(user), 'roles': roles, 'tokens': tokens})


@method_decorator(csrf_exempt, name='dispatch')
class RoleRegisterView(View):
	def post(self, request, role_name):
		payload, error = _parse_json(request)
		if error:
			return error

		full_name = (payload.get('full_name') or '').strip()
		email = (payload.get('email') or payload.get('username') or '').strip().lower()
		password = payload.get('password') or ''

		if not full_name or not email or not password:
			return JsonResponse({'error': 'full_name, email, password are required.'}, status=400)

		user = User.objects.filter(email=email).first()
		if user is None:
			user = User.objects.create(full_name=full_name, email=email, password=password)
		elif user.password != password:
			return JsonResponse({'error': 'email already exists with different password.'}, status=400)

		_ensure_role_for_user(user, role_name.upper())
		return JsonResponse({'message': f'{role_name} register successful.', 'user': _serialize_user(user)}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class RoleLoginView(View):
	def post(self, request, role_name):
		payload, error = _parse_json(request)
		if error:
			return error

		email = (payload.get('email') or payload.get('username') or '').strip().lower()
		password = payload.get('password') or ''

		if not email or not password:
			return JsonResponse({'error': 'email and password are required.'}, status=400)

		user = User.objects.filter(email=email, password=password).first()
		if user is None:
			return JsonResponse({'error': 'Invalid credentials.'}, status=401)

		required_role = role_name.upper()
		has_role = user.user_roles.select_related('role').filter(role__name=required_role).exists()
		if not has_role:
			return JsonResponse({'error': f'User does not have {required_role} role.'}, status=403)

		roles = _extract_roles(user)
		tokens = _issue_tokens(user, roles)

		return JsonResponse(
			{
				'message': f'{role_name} login successful.',
				'role': required_role,
				'user_id': user.id,
				'username': user.email,
				'full_name': user.full_name,
				'roles': roles,
				'tokens': tokens,
			},
		)


@method_decorator(csrf_exempt, name='dispatch')
class AuthVerifyView(View):
	def get(self, request):
		_, _, UntypedToken = _load_jwt_classes()
		if UntypedToken is None:
			return JsonResponse({'error': 'JWT dependency is missing.'}, status=500)

		token = _parse_bearer_token(request)
		if not token:
			return JsonResponse({'error': 'Missing bearer token.'}, status=401)

		try:
			claims = UntypedToken(token)
		except Exception:
			return JsonResponse({'error': 'Invalid token.'}, status=401)

		required_role = (request.headers.get('X-Required-Role') or '').strip().upper()
		roles = [str(role).upper() for role in (claims.get('roles') or [])]
		if required_role and required_role not in roles:
			return JsonResponse({'error': 'Forbidden role.'}, status=403)

		return JsonResponse({'ok': True, 'user_id': claims.get('user_id'), 'roles': roles})


@method_decorator(csrf_exempt, name='dispatch')
class UserBehaviorView(View):
	def get(self, request):
		user_id = request.GET.get('user_id')
		queryset = UserBehavior.objects.order_by('-timestamp')
		if user_id:
			queryset = queryset.filter(user_id=user_id)
		return JsonResponse({'count': queryset.count(), 'data': [_serialize_behavior(item) for item in queryset[:500]]})

	def post(self, request):
		payload, error = _parse_json(request)
		if error:
			return error

		user_id = payload.get('user_id')
		product_id = payload.get('product_id')
		action = (payload.get('action') or '').strip().lower()

		if not user_id or not product_id or not action:
			return JsonResponse({'error': 'user_id, product_id, action are required.'}, status=400)

		try:
			user_id_int = int(user_id)
			product_id_int = int(product_id)
		except (TypeError, ValueError):
			return JsonResponse({'error': 'user_id and product_id must be integers.'}, status=400)

		if action not in {UserBehavior.ACTION_VIEW, UserBehavior.ACTION_CLICK, UserBehavior.ACTION_ADD_TO_CART, UserBehavior.ACTION_BUY, UserBehavior.ACTION_RATING, UserBehavior.ACTION_SEARCH}:
			return JsonResponse({'error': 'action must be view, click, add_to_cart, buy, rating or search.'}, status=400)

		try:
			with transaction.atomic():
				item = UserBehavior.objects.create(user_id=user_id_int, product_id=product_id_int, action=action)
				neo4j_behavior_client.save_behavior(
					BehaviorEvent(
						user_id=user_id_int,
						product_id=product_id_int,
						action=action,
						event_time=item.timestamp.isoformat(),
					)
				)
		except Exception as ex:
			return JsonResponse({'error': f'Failed to save behavior to Neo4j: {str(ex)}'}, status=503)

		return JsonResponse({'message': 'Behavior saved.', 'data': _serialize_behavior(item)}, status=201)
