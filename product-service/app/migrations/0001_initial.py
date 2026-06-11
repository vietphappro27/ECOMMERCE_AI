# Generated manually for stable schema versioning
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='app.category')),
            ],
            options={
                'verbose_name_plural': 'categories',
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=512)),
                ('slug', models.SlugField(max_length=512, unique=True)),
                ('description', models.TextField(blank=True)),
                ('base_price', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='products', to='app.category')),
            ],
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sku', models.CharField(max_length=128, unique=True)),
                ('name', models.CharField(blank=True, max_length=512)),
                ('attributes', models.JSONField(blank=True, default=dict)),
                ('price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('stock', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variants', to='app.product')),
            ],
        ),
        migrations.AddIndex(
            model_name='category',
            index=models.Index(fields=['slug'], name='app_categor_slug_0ace88_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['slug'], name='app_product_slug_10a1ae_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['category'], name='app_product_categor_516f88_idx'),
        ),
        migrations.AddIndex(
            model_name='productvariant',
            index=models.Index(fields=['sku'], name='app_product_sku_bec5e7_idx'),
        ),
        migrations.AddIndex(
            model_name='productvariant',
            index=models.Index(fields=['product'], name='app_product_product_d6975d_idx'),
        ),
    ]
