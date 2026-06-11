from django.contrib import admin
from .models import Book, Category, Cosmetic, Electronic, Fashion, Food, Furniture, Product, Sport, Toy, Vehicle


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'price', 'stock')
    search_fields = ('name',)
    list_filter = ('category',)


@admin.register(Furniture)
class FurnitureAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'material', 'dimesions')
    search_fields = ('product__name', 'material')


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'author', 'publisher', 'isbn')
    search_fields = ('product__name', 'author', 'isbn')


@admin.register(Electronic)
class ElectronicAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'brand', 'warranty')
    search_fields = ('product__name', 'brand')


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'origin', 'expiry_date')
    search_fields = ('product__name', 'origin')


@admin.register(Cosmetic)
class CosmeticAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'brand', 'skin_type')
    search_fields = ('product__name', 'brand', 'skin_type')


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'type', 'weight')
    search_fields = ('product__name', 'type')


@admin.register(Fashion)
class FashionAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'size', 'color')
    search_fields = ('product__name', 'size', 'color')


@admin.register(Toy)
class ToyAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'age_group', 'material')
    search_fields = ('product__name', 'age_group', 'material')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'brand', 'engine_type')
    search_fields = ('product__name', 'brand', 'engine_type')
