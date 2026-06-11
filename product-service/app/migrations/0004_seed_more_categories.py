from django.db import migrations


SAMPLE_CATEGORIES = [
    ("Giay dep", "footwear"),
    ("Phu kien", "accessories"),
    ("Sach", "books"),
    ("Do gia dung", "home-living"),
    ("Lam dep", "beauty"),
]


def seed_more_categories(apps, schema_editor):
    Category = apps.get_model("app", "Category")
    for name, slug in SAMPLE_CATEGORIES:
        Category.objects.get_or_create(slug=slug, defaults={"name": name})


def unseed_more_categories(apps, schema_editor):
    Category = apps.get_model("app", "Category")
    Category.objects.filter(slug__in=[slug for _, slug in SAMPLE_CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0003_category_attribute_schema"),
    ]

    operations = [
        migrations.RunPython(seed_more_categories, unseed_more_categories),
    ]
