import django.db.models.deletion
from django.db import migrations, models


CATEGORY_ATTRIBUTES = {
    "laptop": [
        {
            "name": "brand",
            "label": "Brand",
            "attribute_type": "text",
            "is_required": True,
            "order": 1,
        },
        {
            "name": "cpu",
            "label": "CPU",
            "attribute_type": "text",
            "is_required": True,
            "order": 2,
        },
        {
            "name": "ram_gb",
            "label": "RAM (GB)",
            "attribute_type": "number",
            "is_required": True,
            "order": 3,
            "min_value": 2,
        },
        {
            "name": "storage_gb",
            "label": "Storage (GB)",
            "attribute_type": "number",
            "is_required": True,
            "order": 4,
            "min_value": 32,
        },
    ],
    "mobile": [
        {
            "name": "brand",
            "label": "Brand",
            "attribute_type": "text",
            "is_required": True,
            "order": 1,
        },
        {
            "name": "screen_size",
            "label": "Screen Size (inch)",
            "attribute_type": "decimal",
            "is_required": True,
            "order": 2,
            "min_value": 4.0,
        },
        {
            "name": "battery_mah",
            "label": "Battery (mAh)",
            "attribute_type": "number",
            "is_required": True,
            "order": 3,
            "min_value": 1000,
        },
        {
            "name": "camera_specs",
            "label": "Camera",
            "attribute_type": "text",
            "is_required": False,
            "order": 4,
        },
    ],
    "clothing": [
        {
            "name": "brand",
            "label": "Brand",
            "attribute_type": "text",
            "is_required": False,
            "order": 1,
        },
        {
            "name": "size",
            "label": "Size",
            "attribute_type": "choice",
            "choices": "XS,S,M,L,XL,XXL",
            "is_required": True,
            "order": 2,
        },
        {
            "name": "color",
            "label": "Color",
            "attribute_type": "text",
            "is_required": True,
            "order": 3,
        },
        {
            "name": "material",
            "label": "Material",
            "attribute_type": "text",
            "is_required": False,
            "order": 4,
        },
    ],
    "electronics": [
        {
            "name": "brand",
            "label": "Brand",
            "attribute_type": "text",
            "is_required": True,
            "order": 1,
        },
        {
            "name": "model",
            "label": "Model",
            "attribute_type": "text",
            "is_required": True,
            "order": 2,
        },
        {
            "name": "warranty_months",
            "label": "Warranty (months)",
            "attribute_type": "number",
            "is_required": False,
            "order": 3,
            "min_value": 0,
        },
    ],
    "product": [
        {
            "name": "brand",
            "label": "Brand",
            "attribute_type": "text",
            "is_required": False,
            "order": 1,
        },
    ],
}


def seed_category_attributes(apps, schema_editor):
    Category = apps.get_model("app", "Category")
    CategoryAttribute = apps.get_model("app", "CategoryAttribute")

    for slug, attrs in CATEGORY_ATTRIBUTES.items():
        category = Category.objects.filter(slug=slug).first()
        if category is None:
            continue

        for attr in attrs:
            CategoryAttribute.objects.get_or_create(
                category=category,
                name=attr["name"],
                defaults={
                    "label": attr["label"],
                    "attribute_type": attr["attribute_type"],
                    "is_required": attr.get("is_required", False),
                    "choices": attr.get("choices", ""),
                    "order": attr.get("order", 0),
                    "min_value": attr.get("min_value"),
                    "max_value": attr.get("max_value"),
                },
            )


def unseed_category_attributes(apps, schema_editor):
    CategoryAttribute = apps.get_model("app", "CategoryAttribute")
    names = set()
    for attrs in CATEGORY_ATTRIBUTES.values():
        for attr in attrs:
            names.add(attr["name"])

    CategoryAttribute.objects.filter(name__in=list(names)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_seed_categories"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoryAttribute",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=128)),
                ("label", models.CharField(max_length=255)),
                (
                    "attribute_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("number", "Number"),
                            ("decimal", "Decimal (Float)"),
                            ("choice", "Dropdown/Choice"),
                            ("boolean", "Yes/No"),
                            ("textarea", "Long Text"),
                        ],
                        default="text",
                        max_length=20,
                    ),
                ),
                ("is_required", models.BooleanField(default=False)),
                (
                    "choices",
                    models.TextField(
                        blank=True,
                        help_text="For choice type: comma-separated values or JSON array",
                    ),
                ),
                ("order", models.IntegerField(default=0)),
                (
                    "min_value",
                    models.FloatField(
                        blank=True,
                        help_text="For number/decimal types",
                        null=True,
                    ),
                ),
                (
                    "max_value",
                    models.FloatField(
                        blank=True,
                        help_text="For number/decimal types",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attributes",
                        to="app.category",
                    ),
                ),
            ],
            options={
                "ordering": ["category", "order", "name"],
                "unique_together": {("category", "name")},
            },
        ),
        migrations.AddIndex(
            model_name="categoryattribute",
            index=models.Index(
                fields=["category", "order"],
                name="app_categor_categor_68356f_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="categoryattribute",
            index=models.Index(fields=["category"], name="app_categor_categor_5f9538_idx"),
        ),
        migrations.RunPython(seed_category_attributes, unseed_category_attributes),
    ]
