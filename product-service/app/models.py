from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.URLField(max_length=1000, blank=True, default='')
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Furniture(models.Model):
    material = models.CharField(max_length=255)
    dimesions = models.CharField(max_length=255)
    product = models.OneToOneField(Product, related_name='furniture', on_delete=models.CASCADE)


class Book(models.Model):
    author = models.CharField(max_length=255)
    publisher = models.CharField(max_length=255)
    isbn = models.CharField(max_length=32)
    product = models.OneToOneField(Product, related_name='book', on_delete=models.CASCADE)


class Electronic(models.Model):
    brand = models.CharField(max_length=255)
    warranty = models.CharField(max_length=255)
    product = models.OneToOneField(Product, related_name='electronic', on_delete=models.CASCADE)


class Food(models.Model):
    expiry_date = models.DateField()
    origin = models.CharField(max_length=255)
    product = models.OneToOneField(Product, related_name='food', on_delete=models.CASCADE)


class Cosmetic(models.Model):
    brand = models.CharField(max_length=255)
    skin_type = models.CharField(max_length=255)
    product = models.OneToOneField(Product, related_name='cosmetic', on_delete=models.CASCADE)


class Sport(models.Model):
    type = models.CharField(max_length=255)
    weight = models.CharField(max_length=255)
    product = models.OneToOneField(Product, related_name='sport', on_delete=models.CASCADE)


class Fashion(models.Model):
    size = models.CharField(max_length=64)
    color = models.CharField(max_length=64)
    product = models.OneToOneField(Product, related_name='fashion', on_delete=models.CASCADE)


class Toy(models.Model):
    age_group = models.CharField(max_length=255)
    material = models.CharField(max_length=255)
    product = models.OneToOneField(Product, related_name='toy', on_delete=models.CASCADE)


class Vehicle(models.Model):
    brand = models.CharField(max_length=255)
    engine_type = models.CharField(max_length=255)
    product = models.OneToOneField(Product, related_name='vehicle', on_delete=models.CASCADE)
