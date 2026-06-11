from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
	initial = True

	dependencies = []

	operations = [
		migrations.CreateModel(
			name='Payment',
			fields=[
				('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('order_id', models.IntegerField(unique=True)),
				('status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')], default='pending', max_length=20)),
				('address', models.TextField()),
			],
			options={
				'indexes': [
					models.Index(fields=['order_id'], name='payment_order_id_idx'),
					models.Index(fields=['status'], name='payment_status_idx'),
				],
			},
		),
	]
