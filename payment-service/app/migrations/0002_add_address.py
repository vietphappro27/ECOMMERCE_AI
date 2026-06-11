from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
	dependencies = [
		('app', '0001_initial'),
	]

	operations = [
		migrations.CreateModel(
			name='Address',
			fields=[
				('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('full_name', models.CharField(blank=True, default='', max_length=255)),
				('phone', models.CharField(blank=True, default='', max_length=30)),
				('line1', models.CharField(max_length=255)),
				('line2', models.CharField(blank=True, default='', max_length=255)),
				('ward', models.CharField(blank=True, default='', max_length=100)),
				('district', models.CharField(blank=True, default='', max_length=100)),
				('city', models.CharField(blank=True, default='', max_length=100)),
				('province', models.CharField(blank=True, default='', max_length=100)),
				('country', models.CharField(blank=True, default='Vietnam', max_length=100)),
				('postal_code', models.CharField(blank=True, default='', max_length=20)),
			],
		),
		migrations.SeparateDatabaseAndState(
			database_operations=[],
			state_operations=[
				migrations.RemoveField(
					model_name='payment',
					name='address',
				),
			],
		),
		migrations.AddField(
			model_name='payment',
			name='address',
			field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='payments', to='app.address'),
		),
	]
