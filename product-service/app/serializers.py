from rest_framework import serializers
from .models import (
    Book,
    Category,
    Cosmetic,
    Electronic,
    Fashion,
    Food,
    Furniture,
    Product,
    Sport,
    Toy,
    Vehicle,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class FurnitureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Furniture
        fields = ['material', 'dimesions']


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ['author', 'publisher', 'isbn']

class ElectronicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Electronic
        fields = ['brand', 'warranty']


class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = ['expiry_date', 'origin']


class CosmeticSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cosmetic
        fields = ['brand', 'skin_type']


class SportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sport
        fields = ['type', 'weight']


class FashionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fashion
        fields = ['size', 'color']


class ToySerializer(serializers.ModelSerializer):
    class Meta:
        model = Toy
        fields = ['age_group', 'material']


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['brand', 'engine_type']


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source='category.name', read_only=True)
    details = serializers.JSONField(write_only=True, required=False)
    product_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'price',
            'stock',
            'image',
            'category',
            'category_name',
            'details',
            'product_details',
        ]

    DETAIL_SERIALIZER_BY_CATEGORY = {
        'furniture': (Furniture, FurnitureSerializer),
        'book': (Book, BookSerializer),
        'electronic': (Electronic, ElectronicSerializer),
        'food': (Food, FoodSerializer),
        'cosmetic': (Cosmetic, CosmeticSerializer),
        'sport': (Sport, SportSerializer),
        'fashion': (Fashion, FashionSerializer),
        'toy': (Toy, ToySerializer),
        'vehicle': (Vehicle, VehicleSerializer),
    }

    def _category_key(self, category_name):
        return (category_name or '').strip().lower()

    def _get_detail_binding(self, category_name):
        key = self._category_key(category_name)
        return self.DETAIL_SERIALIZER_BY_CATEGORY.get(key)

    def _upsert_detail_model(self, product, details_payload):
        binding = self._get_detail_binding(product.category.name)
        if not binding:
            return
        model_cls, serializer_cls = binding
        detail_instance = model_cls.objects.filter(product=product).first()
        serializer = serializer_cls(instance=detail_instance, data=details_payload or {}, partial=bool(detail_instance))
        serializer.is_valid(raise_exception=True)
        if detail_instance is None:
            serializer.save(product=product)
            return

        detail = serializer.save()
        if detail.product_id != product.id:
            detail.product = product
            detail.save(update_fields=['product'])

    def get_product_details(self, obj):
        binding = self._get_detail_binding(obj.category.name)
        if not binding:
            return None
        model_cls, serializer_cls = binding
        detail_instance = model_cls.objects.filter(product=obj).first()
        if not detail_instance:
            return None
        return serializer_cls(detail_instance).data

    def create(self, validated_data):
        details_payload = validated_data.pop('details', None)
        product = Product.objects.create(**validated_data)
        if details_payload is not None:
            self._upsert_detail_model(product, details_payload)
        return product

    def update(self, instance, validated_data):
        details_payload = validated_data.pop('details', None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if details_payload is not None:
            self._upsert_detail_model(instance, details_payload)
        return instance
