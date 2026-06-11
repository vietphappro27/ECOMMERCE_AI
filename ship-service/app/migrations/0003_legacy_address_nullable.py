from django.db import migrations


class Migration(migrations.Migration):
	dependencies = [
		('app', '0002_add_address'),
	]

	operations = [
		migrations.RunSQL(
			sql="ALTER TABLE app_shipment ALTER COLUMN address DROP NOT NULL;",
			reverse_sql="ALTER TABLE app_shipment ALTER COLUMN address SET NOT NULL;",
		),
	]
