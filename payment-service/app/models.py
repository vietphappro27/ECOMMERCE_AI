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


class Payment(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_PAID = 'paid'
	STATUS_FAILED = 'failed'

	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_PAID, 'Paid'),
		(STATUS_FAILED, 'Failed'),
	]

	order_id = models.IntegerField(unique=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	address = models.ForeignKey(Address, related_name='payments', on_delete=models.PROTECT, null=True, blank=True)

	class Meta:
		indexes = [models.Index(fields=['order_id']), models.Index(fields=['status'])]
