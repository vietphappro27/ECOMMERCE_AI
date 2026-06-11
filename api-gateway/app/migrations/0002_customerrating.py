from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('customer_id', models.IntegerField(db_index=True)),
                ('item_type', models.CharField(default='product', max_length=50)),
                ('item_id', models.IntegerField(db_index=True)),
                ('score', models.PositiveSmallIntegerField()),
                ('review', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name='customerrating',
            constraint=models.UniqueConstraint(fields=('customer_id', 'item_type', 'item_id'), name='uniq_customer_item_rating'),
        ),
    ]
