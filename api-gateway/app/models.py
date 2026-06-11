from django.db import models


class ApiRequestLog(models.Model):
	service_name = models.CharField(max_length=50)
	method = models.CharField(max_length=10)
	path = models.CharField(max_length=255)
	status_code = models.IntegerField()
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"{self.method} {self.path} -> {self.service_name} ({self.status_code})"


class CustomerRating(models.Model):
	customer_id = models.IntegerField(db_index=True)
	item_type = models.CharField(max_length=50, default='product')
	item_id = models.IntegerField(db_index=True)
	score = models.PositiveSmallIntegerField()
	review = models.TextField(blank=True, default='')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=['customer_id', 'item_type', 'item_id'],
				name='uniq_customer_item_rating',
			),
		]

	def __str__(self) -> str:
		return f"rating c={self.customer_id} {self.item_type}:{self.item_id}={self.score}"
