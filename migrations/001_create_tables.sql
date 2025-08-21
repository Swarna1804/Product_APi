-- migrations/001_create_tables.sql

CREATE TABLE brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    year_founded INTEGER,
    street TEXT,
    city TEXT,
    state TEXT,
    postal_code TEXT,
    country TEXT
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    productId TEXT NOT NULL UNIQUE,
    productName TEXT NOT NULL,
    brand_id INTEGER NOT NULL,
    category TEXT,
    description TEXT,
    price REAL,
    currency TEXT,
    discountPercentage REAL,
    stockQuantity INTEGER,
    warehouseLocation TEXT,
    sku TEXT,
    processor TEXT,
    memory TEXT,
    storageCapacity TEXT,
    displaySize TEXT,
    isAvailable BOOLEAN,
    releaseDate TEXT,
    lastUpdated TEXT,
    averageRating REAL,
    ratingCount INTEGER,
    warrantyDurationMonths INTEGER,
    weight_kg REAL,
    FOREIGN KEY (brand_id) REFERENCES brands(id)
);
