from django.db import models


class User(models.Model):
	full_name = models.CharField(max_length=255)
	email = models.EmailField(unique=True)
	password = models.CharField(max_length=255)

	def __str__(self):
		return self.email


class Role(models.Model):
	name = models.CharField(max_length=100, unique=True)

	def __str__(self):
		return self.name


class UserRole(models.Model):
	user = models.ForeignKey(User, related_name='user_roles', on_delete=models.CASCADE)
	role = models.ForeignKey(Role, related_name='role_users', on_delete=models.CASCADE)

	class Meta:
		unique_together = ('user', 'role')


class UserBehavior(models.Model):
	ACTION_VIEW = 'view'
	ACTION_CLICK = 'click'
	ACTION_ADD_TO_CART = 'add_to_cart'
	ACTION_BUY = 'buy'
	ACTION_RATING = 'rating'
	ACTION_SEARCH = 'search'

	ACTION_CHOICES = [
		(ACTION_VIEW, 'View'),
		(ACTION_CLICK, 'Click'),
		(ACTION_ADD_TO_CART, 'Add To Cart'),
		(ACTION_BUY, 'Buy'),
		(ACTION_RATING, 'Rating'),
		(ACTION_SEARCH, 'Search'),
	]

	user_id = models.IntegerField(db_index=True)
	product_id = models.IntegerField(db_index=True)
	action = models.CharField(max_length=20, choices=ACTION_CHOICES)
	timestamp = models.DateTimeField(auto_now_add=True)
