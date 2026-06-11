from django.db import migrations


SAMPLE_CATEGORIES = [
    ("Laptop", "laptop"),
    ("Mobile", "mobile"),
    ("Quan ao", "clothing"),
    ("Dien tu", "electronics"),
    ("Product", "product"),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("app", "Category")
    for name, slug in SAMPLE_CATEGORIES:
        Category.objects.get_or_create(slug=slug, defaults={"name": name})


def unseed_categories(apps, schema_editor):
    Category = apps.get_model("app", "Category")
    Category.objects.filter(slug__in=[slug for _, slug in SAMPLE_CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
