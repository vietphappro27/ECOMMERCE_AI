from django.db import migrations, models
import django.db.models.deletion


DEFAULT_CATEGORIES = [
    "Furniture",
    "Book",
    "Electronic",
    "Food",
    "Cosmetic",
    "Sport",
    "Fashion",
    "Toy",
    "Vehicle",
]


def seed_default_categories(apps, schema_editor):
    Category = apps.get_model("app", "Category")
    for name in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(name=name)


def unseed_default_categories(apps, schema_editor):
    Category = apps.get_model("app", "Category")
    Category.objects.filter(name__in=DEFAULT_CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0004_seed_more_categories"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CategoryAttribute",
        ),
        migrations.DeleteModel(
            name="ProductVariant",
        ),
        migrations.RemoveField(
            model_name="category",
            name="parent",
        ),
        migrations.RemoveField(
            model_name="category",
            name="slug",
        ),
        migrations.RemoveField(
            model_name="product",
            name="base_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="created_at",
        ),
        migrations.RemoveField(
            model_name="product",
            name="description",
        ),
        migrations.RemoveField(
            model_name="product",
            name="is_active",
        ),
        migrations.RemoveField(
            model_name="product",
            name="slug",
        ),
        migrations.RemoveField(
            model_name="product",
            name="updated_at",
        ),
        migrations.AlterField(
            model_name="category",
            name="name",
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name="product",
            name="category",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="products", to="app.category"),
        ),
        migrations.AlterField(
            model_name="product",
            name="name",
            field=models.CharField(max_length=255),
        ),
        migrations.AddField(
            model_name="product",
            name="price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="product",
            name="stock",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="Book",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("author", models.CharField(max_length=255)),
                ("publisher", models.CharField(max_length=255)),
                ("isbn", models.CharField(max_length=32)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="book", to="app.product")),
            ],
        ),
        migrations.CreateModel(
            name="Cosmetic",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("brand", models.CharField(max_length=255)),
                ("skin_type", models.CharField(max_length=255)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="cosmetic", to="app.product")),
            ],
        ),
        migrations.CreateModel(
            name="Electronic",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("brand", models.CharField(max_length=255)),
                ("warranty", models.CharField(max_length=255)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="electronic", to="app.product")),
            ],
        ),
        migrations.CreateModel(
            name="Fashion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("size", models.CharField(max_length=64)),
                ("color", models.CharField(max_length=64)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="fashion", to="app.product")),
            ],
        ),
        migrations.CreateModel(
            name="Food",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("expiry_date", models.DateField()),
                ("origin", models.CharField(max_length=255)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="food", to="app.product")),
            ],
        ),
        migrations.CreateModel(
            name="Furniture",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("material", models.CharField(max_length=255)),
                ("dimesions", models.CharField(max_length=255)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="furniture", to="app.product")),
            ],
        ),
        migrations.CreateModel(
            name="Sport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(max_length=255)),
                ("weight", models.CharField(max_length=255)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="sport", to="app.product")),
            ],
        ),
        migrations.CreateModel(
            name="Toy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("age_group", models.CharField(max_length=255)),
                ("material", models.CharField(max_length=255)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="toy", to="app.product")),
            ],
        ),
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("brand", models.CharField(max_length=255)),
                ("engine_type", models.CharField(max_length=255)),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="vehicle", to="app.product")),
            ],
        ),
        migrations.RunPython(seed_default_categories, unseed_default_categories),
    ]
