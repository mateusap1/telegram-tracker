The database will have the following structure:

* TABLES: 
- products
    - product_id: TEXT
    - last_price: NUMBER
    - current_price: NUMBER
    - url: TEXT
    - subcategory_id: NUMBER

- categories
    - name: TEXT
    - url: TEXT

- subcategories
    - category_id: NUMBER
    - name: TEXT
    - url: TEXT

- brands
    - brand_name: TEXT
    - product_id: TEXT