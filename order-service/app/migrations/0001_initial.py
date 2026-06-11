from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
	initial = True

	dependencies = []

	operations = [
		migrations.CreateModel(
			name='Order',
			fields=[
				('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('user_id', models.IntegerField()),
				('total_price', models.DecimalField(decimal_places=2, max_digits=12)),
				('status', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('shipped', 'Shipped'), ('canceled', 'Canceled')], default='pending', max_length=20)),
				('created_at', models.DateTimeField(auto_now_add=True)),
				('updated_at', models.DateTimeField(auto_now=True)),
			],
			options={
				'indexes': [
					models.Index(fields=['user_id'], name='order_user_id_idx'),
					models.Index(fields=['status'], name='order_status_idx'),
				],
			},
		),
		migrations.CreateModel(
			name='OrderItem',
			fields=[
				('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('product_id', models.IntegerField()),
				('quantity', models.PositiveIntegerField(default=1)),
				('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='app.order')),
			],
			options={
				'indexes': [
					models.Index(fields=['order'], name='order_item_order_idx'),
					models.Index(fields=['product_id'], name='order_item_product_idx'),
				],
			},
		),
	]
