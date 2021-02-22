The database will have the following structure:

* TABLES: 
- products
    - product_id: UNIQUE, PRIMARY, TEXT
    - last_price: NUMBER
    - current_price: NUMBER
    - title: TEXT
    - merchant: TEXT
    - url: TEXT
    - subcategory_id: NUMBER
    - brand_id: NUMBER

- categories
    - category_id: UNIQUE, PRIMARY, NUMBER
    - name: TEXT
    - url: TEXT

- subcategories
    - subcategory_id: UNIQUE, PRIMARY, NUMBER
    - category_id: NUMBER
    - name: TEXT
    - url: TEXT

- brands
    - brand_id: UNIQUE, PRIMARY, NUMBER
    - name: TEXT
    - url: TEXT