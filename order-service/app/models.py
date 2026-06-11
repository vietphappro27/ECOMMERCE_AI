from django.db import models


class Address(models.Model):
	full_name = models.CharField(max_length=255, blank=True, default='')
	phone = models.CharField(max_length=30, blank=True, default='')
	line1 = models.CharField(max_length=255)
	line2 = models.CharField(max_length=255, blank=True, default='')
	ward = models.CharField(max_length=100, blank=True, default='')
	district = models.CharField(max_length=100, blank=True, default='')
	city = models.CharField(max_length=100, blank=True, default='')
	province = models.CharField(max_length=100, blank=True, default='')
	country = models.CharField(max_length=100, blank=True, default='Vietnam')
	postal_code = models.CharField(max_length=20, blank=True, default='')


class Order(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_CONFIRMED = 'confirmed'
	STATUS_SHIPPED = 'shipped'
	STATUS_CANCELED = 'canceled'

	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_CONFIRMED, 'Confirmed'),
		(STATUS_SHIPPED, 'Shipped'),
		(STATUS_CANCELED, 'Canceled'),
	]

	user_id = models.IntegerField()
	total_price = models.DecimalField(max_digits=12, decimal_places=2)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	address = models.ForeignKey(Address, related_name='orders', on_delete=models.PROTECT, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		indexes = [
			models.Index(fields=['user_id']),
			models.Index(fields=['status']),
		]


class OrderItem(models.Model):
	order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
	product_id = models.IntegerField()
	quantity = models.PositiveIntegerField(default=1)

	class Meta:
		indexes = [
			models.Index(fields=['order']),
			models.Index(fields=['product_id']),
		]
