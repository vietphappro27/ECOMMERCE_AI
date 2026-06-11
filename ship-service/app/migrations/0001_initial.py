from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
	initial = True

	dependencies = []

	operations = [
		migrations.CreateModel(
			name='Shipment',
			fields=[
				('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('order_id', models.IntegerField(unique=True)),
				('status', models.CharField(choices=[('created', 'Created'), ('shipping', 'Shipping'), ('delivered', 'Delivered'), ('failed', 'Failed')], default='created', max_length=20)),
				('address', models.TextField()),
			],
			options={
				'indexes': [
					models.Index(fields=['order_id'], name='shipment_order_id_idx'),
					models.Index(fields=['status'], name='shipment_status_idx'),
				],
			},
		),
	]
