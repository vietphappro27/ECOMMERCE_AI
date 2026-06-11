from django.db import models


class Cart(models.Model):
	user_id = models.IntegerField(db_index=True)


class CartItem(models.Model):
	cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
	product_id = models.IntegerField(db_index=True)
	quantity = models.PositiveIntegerField(default=1)
