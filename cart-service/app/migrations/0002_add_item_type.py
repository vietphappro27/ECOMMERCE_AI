from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='item_type',
            field=models.CharField(db_index=True, default='product', max_length=50),
        ),
    ]
