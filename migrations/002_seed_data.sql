-- migrations/002_seed_data.sql

INSERT INTO brands (name, year_founded, street, city, state, postal_code, country)
VALUES
("Innovatech", 2001, "123 Tech Park", "San Francisco", "CA", "94105", "USA"),
("Nexus", 1998, "456 Mobile Ave", "New York", "NY", "10001", "USA");

INSERT INTO products (
    productId, productName, brand_id, category, description, price, currency,
    discountPercentage, stockQuantity, warehouseLocation, sku, processor, memory,
    storageCapacity, displaySize, isAvailable, releaseDate, lastUpdated,
    averageRating, ratingCount, warrantyDurationMonths, weight_kg
) VALUES
(
 "SKU-LPTP-001", "Innovatech ProBook X1", 1, "Laptops",
 "A high-performance laptop for professionals...",
 1299.99, "USD", 5, 85, "Warehouse C, Sector 2", "INVT-PBX1-2025-512",
 "Innovatech Fusion Z1", "16GB DDR5", "512GB SSD", "14 inches", 1,
 "2025-01-20", "2024-08-01T10:00:00Z", 4.7, 312, 24, 1.4
),
(
 "SKU-MOBL-001", "Nexus Galaxy S10", 2, "Mobiles",
 "The Nexus Galaxy S10 offers a stunning display...",
 899.99, "USD", 10, 150, "Warehouse A, Sector 5", "NXS-GS10-2025-256",
 "Nexus Octa-Core 5", "8GB RAM", "256GB SSD", "6.5 inches", 1,
 "2025-03-10", "2024-08-01T10:00:00Z", 4.8, 1024, 12, 0.2
);
