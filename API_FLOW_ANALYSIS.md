# API Flow Analysis - Frontend to Backend Data Mismatch

## 🔴 VẤN ĐỀ CHÍNH

Frontend gửi dữ liệu **KHÔNG KHỚP** với Backend xử lý, dẫn đến **mất dữ liệu `item_type`**.

---

## 📤 BƯỚC 1: Frontend Gửi (customer_dashboard.html)

**Hàm:** `addToCart(type, id)`  
**URL:** `POST /api/customer/cart-items/`  
**Dữ liệu gửi:**

```json
{
    "customer_id": CUSTOMER_ID,
    "item_type": "fashion",        // ✅ Frontend gửi
    "product_id": 123,
    "quantity": 1
}
```

---

## ❌ BƯỚC 2: Gateway Nhận (api_gateway/app/views.py)

**View:** `CustomerCartItemProxyView.post()`  
**Dòng 857-860:**

```python
customer_id = _resolve_customer_id(request, body.get('customer_id') or body.get('user_id'))
product_id = body.get('product_id')
quantity = body.get('quantity', 1)

# ❌ KHÔNG LẤY item_type TỪ REQUEST BODY!
# item_type = body.get('item_type')  # <-- MISSING!
```

**Kết quả:**
- ✅ `customer_id` được lấy
- ✅ `product_id` được lấy  
- ✅ `quantity` được lấy
- ❌ **`item_type` BỊ BỎ QUA HOÀN TOÀN**

---

## 📥 BƯỚC 3: Gateway Gửi Đến Cart Service

**Dòng 877-882:**

```python
add_status, add_payload = _request_json(
    'cart',
    settings.CART_SERVICE_URL,
    '/cart-items/',
    method='POST',
    payload={
        'cart': int(cart.get('id')),
        'product_id': int(product_id),
        'quantity': quantity,
        # ❌ item_type KHÔNG ĐƯỢC GỬI
    },
)
```

**Dữ liệu gửi đến cart-service:**

```json
{
    "cart": 5,
    "product_id": 123,
    "quantity": 1
    // ❌ item_type KHÔNG CÓ
}
```

---

## 🗄️ BƯỚC 4: Cart Service Lưu (cart_service/app/views.py)

**CartItemView.post() - Dòng 68-93:**

```python
# Cart service chỉ nhận và lưu:
cart_id = payload.get('cart')
product_id = payload.get('product_id')
quantity = payload.get('quantity', 1)

# Lưu vào Database:
item, created = CartItem.objects.get_or_create(
    cart=cart,
    product_id=product_id,
    defaults={'quantity': quantity},
)
```

**Kết quả:** Item lưu **MÀ KHÔNG CÓ `item_type`**

---

## 📊 BƯỚC 5: Gateway Retrieve Cart (api_gateway/app/views.py)

**Hàm:** `_build_cart_response()` - Dòng 449-485

```python
product_index = _product_index_by_id()  # ⚠️ Load tất cả products!

for item in items:
    product_id = int(item.get('product_id'))
    quantity = int(item.get('quantity') or 0)
    
    product = product_index.get(product_id, {})
    price = float(product.get('price') or 0.0)
    
    normalized_items.append({
        'id': item.get('id'),
        'product_id': product_id,
        'item_type': (product.get('category_name') or 'product'),  # ⚠️ Phụ thuộc vào Product Service
        'price': price,
        'quantity': quantity,
        'line_total': line_total,
    })
```

**Vấn đề:**
1. `item_type` **phải query product service** để lấy `category_name`
2. Nếu **product service không trả `category_name`** → `item_type = 'product'` (mất dữ liệu)
3. **Performance**: Phải load ALL products mỗi lần build cart response

---

## 🐛 LỖI PHỤ KHÁC

### 1. Typo trong PRODUCT_CATEGORY_SCHEMAS (Dòng 287)

```python
"furniture": [
    {"name": "material", "label": "Material", ...},
    {"name": "dimesions", "label": "Dimensions", ...},  # ❌ "dimesions" không phải "dimensions"!
],
```

Nên sửa thành: `"dimensions"`

### 2. Hàm _build_product_payload Không Xử Lý item_type Đúng (Dòng 549-590)

```python
category_input = raw_payload.get('category')
if category_input is None:
    category_input = raw_payload.get('item_type')  # ⚠️ Fallback to item_type
```

Điều này tốt, nhưng:
- **Frontend gửi `item_type` add-to-cart** → Backend BỎ QUA
- **Backend chỉ dùng nó khi CREATE/UPDATE product** → Không phù hợp

---

## 📋 LUỒNG SỰ CỐ SO SÁNH

```
EXPECTED (Lý tưởng):
Frontend gửi: {customer_id, item_type, product_id, quantity}
    ↓
Gateway lấy: {customer_id, item_type, product_id, quantity}
    ↓
Cart Service lưu: {cart_id, product_id, quantity, item_type}
    ↓
Frontend retrieve: {product_id, quantity, item_type} ✅ Đúng dữ liệu

---

ACTUAL (Hiện tại):
Frontend gửi: {customer_id, item_type, product_id, quantity}
    ↓
Gateway lấy: {customer_id, ❌product_id, quantity}  [MISSING item_type]
    ↓
Cart Service lưu: {cart_id, product_id, quantity}  [NO item_type]
    ↓
Frontend retrieve: {product_id, quantity, category_from_product_service}
    ↓
Problem: Nếu product service DOWN hoặc không có category_name → mất dữ liệu
```

---

## 🔧 GIẢI PHÁP

### Fix 1: Gateway Lấy Và Lưu item_type

**File:** `api_gateway/app/views.py` - Line 857-860

```python
customer_id = _resolve_customer_id(request, body.get('customer_id') or body.get('user_id'))
product_id = body.get('product_id')
quantity = body.get('quantity', 1)
item_type = (body.get('item_type') or '').strip().lower()  # ✅ ADD THIS

if not customer_id or not product_id:
    return JsonResponse({'error': 'customer_id and product_id are required.'}, status=400)
```

### Fix 2: Gateway Gửi item_type Đến Cart Service

**File:** `api_gateway/app/views.py` - Line 877-882

```python
add_status, add_payload = _request_json(
    'cart',
    settings.CART_SERVICE_URL,
    '/cart-items/',
    method='POST',
    payload={
        'cart': int(cart.get('id')),
        'product_id': int(product_id),
        'quantity': quantity,
        'item_type': item_type,  # ✅ ADD THIS
    },
)
```

### Fix 3: Cart Service Lưu item_type

**File:** `cart_service/app/models.py`

```python
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_id = models.IntegerField()
    quantity = models.IntegerField(default=1)
    item_type = models.CharField(max_length=50, default='product')  # ✅ ADD THIS
```

**File:** `cart_service/app/views.py` - Line 68-80

```python
item_type = payload.get('item_type', 'product')

item, created = CartItem.objects.get_or_create(
    cart=cart,
    product_id=product_id,
    defaults={'quantity': quantity, 'item_type': item_type},  # ✅ ADD item_type
)
if not created:
    item.quantity += quantity
    item.item_type = item_type  # ✅ UPDATE if exists
    item.save(update_fields=['quantity', 'item_type'])
```

### Fix 4: Typo "dimesions" → "dimensions"

**File:** `api_gateway/app/views.py` - Line 287

```python
"furniture": [
    {"name": "material", "label": "Material", "attribute_type": "text", "is_required": True},
    {"name": "dimensions", "label": "Dimensions", "attribute_type": "text", "is_required": True},  # ✅ Fixed
],
```

---

## ✅ EXPECTED RESULT SAU KHI FIX

```json
Frontend → Gateway → Cart Service → Database:

Request:  {customer_id: 1, item_type: "fashion", product_id: 123, quantity: 1}
Saved:    {cart: 5, product_id: 123, quantity: 1, item_type: "fashion"}
Response: {product_id: 123, quantity: 1, item_type: "fashion"}

✅ Dữ liệu KHỚP từ đầu đến cuối!
```

---

## 📝 SUMMARY

| Layer | Issue | Impact |
|-------|-------|--------|
| **Frontend** | Gửi `item_type` đúng | ✅ Không vấn đề |
| **Gateway** | ❌ BỎ QUA `item_type` | ❌ Mất dữ liệu |
| **Cart Service** | Không lưu `item_type` | ❌ Không thể retrieve |
| **Response** | Phụ thuộc vào Product Service | ⚠️ Không tin cậy |
