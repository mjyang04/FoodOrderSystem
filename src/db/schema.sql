-- Food Order System Database Schema
-- Run: mysql -u root -p food_order_system < src/db/schema.sql

CREATE DATABASE IF NOT EXISTS food_order_system;
USE food_order_system;

-- Users table with password hashing
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(64) NOT NULL,
    role ENUM('customer', 'admin') DEFAULT 'customer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Restaurants
CREATE TABLE IF NOT EXISTS restaurants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    cuisine_type VARCHAR(50) NOT NULL
);

-- Food items (linked to restaurants)
CREATE TABLE IF NOT EXISTS foods (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    description TEXT,
    preferences TEXT COMMENT 'Pipe-separated preferences, e.g., Mild|Medium|Spicy',
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);

-- Delivery riders
CREATE TABLE IF NOT EXISTS riders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL
);

-- Orders
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    restaurant_name VARCHAR(100),
    status ENUM('Pending', 'Confirmed', 'Preparing', 'Delivering', 'Delivered', 'Cancelled') DEFAULT 'Pending',
    total_price DECIMAL(10, 2) DEFAULT 0,
    discount_pct DOUBLE DEFAULT 0,
    delivery_type VARCHAR(50),
    delivery_fee DECIMAL(10, 2) DEFAULT 0,
    payment_method VARCHAR(50),
    rider_name VARCHAR(100),
    rider_phone VARCHAR(20),
    rating DOUBLE DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Order line items
CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    food_name VARCHAR(100) NOT NULL,
    food_price DECIMAL(10, 2) NOT NULL,
    food_description TEXT,
    quantity INT NOT NULL,
    preference VARCHAR(100) DEFAULT '',
    special_instruction TEXT DEFAULT '',
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- ============================================================
-- Seed Data
-- ============================================================

-- Default admin user (password: admin123, will be re-hashed by application)
-- Note: Use the application's register function for proper password hashing.
-- This is just placeholder data.

-- Restaurants
INSERT IGNORE INTO restaurants (id, name, cuisine_type) VALUES
    (1, 'Sichuan Delight', 'Sichuan'),
    (2, 'Chengdu Flavors', 'Sichuan'),
    (3, 'Cantonese Kitchen', 'Cantonese'),
    (4, 'Guangzhou Garden', 'Cantonese'),
    (5, 'La Dolce Vita', 'Italian'),
    (6, 'Roma Ristorante', 'Italian'),
    (7, 'Le Petit Bistro', 'French'),
    (8, 'Chez Paris', 'French'),
    (9, 'Lebanese Delights', 'Lebanese'),
    (10, 'Moroccan Feast', 'Moroccan'),
    (11, 'Texas Tacos', 'TexMex'),
    (12, 'Traditional Mexican', 'TraditionalMexican'),
    (13, 'Sushi House', 'Sushi'),
    (14, 'Ramen World', 'Ramen');

-- Food items
INSERT IGNORE INTO foods (restaurant_id, name, price, description, preferences) VALUES
    -- Sichuan Delight
    (1, 'Kung Pao Chicken', 12.00, 'Spicy stir-fried chicken with peanuts', 'Mild|Medium|Extra Spicy'),
    (1, 'Mapo Tofu', 8.00, 'Spicy tofu with minced meat', 'Mild|Medium|Extra Spicy'),
    (1, 'Hot Pot', 15.00, 'Spicy hot pot with meat and vegetables', 'Mild|Medium|Extra Spicy'),
    (1, 'Dan Dan Noodles', 8.00, 'Spicy noodles with minced meat', 'Mild|Medium|Extra Spicy'),
    (1, 'Sichuan Beef Noodles', 10.00, 'Spicy beef noodles', 'Mild|Medium|Extra Spicy'),
    -- Chengdu Flavors
    (2, 'Chongqing Spicy Chicken', 12.00, 'Spicy chicken with chili peppers', 'Mild|Medium|Extra Spicy'),
    (2, 'Spicy Pork Belly', 14.00, 'Pork belly with Sichuan spices', ''),
    (2, 'Boiled Fish', 16.00, 'Boiled fish with spicy broth', 'Mild|Medium|Extra Spicy'),
    (2, 'Spicy Crayfish', 18.00, 'Crayfish cooked with Sichuan spices', ''),
    (2, 'Sichuan Dumplings', 9.00, 'Spicy dumplings with sauce', ''),
    -- Cantonese Kitchen
    (3, 'Dim Sum', 10.00, 'Variety of small Cantonese dishes', ''),
    (3, 'Roast Duck', 20.00, 'Crispy roast duck', 'Half|Whole'),
    (3, 'Wonton Noodle Soup', 8.00, 'Noodle soup with wontons', ''),
    (3, 'BBQ Pork Buns', 3.00, 'Steamed buns with BBQ pork', ''),
    (3, 'Egg Tarts', 2.00, 'Baked egg custard tarts', ''),
    -- Guangzhou Garden
    (4, 'Steamed Fish', 15.00, 'Steamed fish with soy sauce', ''),
    (4, 'Char Siu', 12.00, 'Barbecue pork', ''),
    (4, 'Fried Rice', 8.00, 'Fried rice with egg and vegetables', ''),
    (4, 'Spring Rolls', 5.00, 'Deep-fried spring rolls', ''),
    (4, 'Cantonese Chicken', 14.00, 'Chicken with soy sauce', ''),
    -- La Dolce Vita
    (5, 'Pasta', 10.00, 'Italian pasta with tomato sauce', 'Spaghetti|Penne|Fusilli'),
    (5, 'Pizza', 15.00, 'Cheese and tomato pizza', 'Small|Medium|Large'),
    (5, 'Tiramisu', 5.00, 'Italian coffee-flavored dessert', ''),
    (5, 'Risotto', 12.00, 'Italian rice dish', ''),
    (5, 'Lasagna', 12.00, 'Italian pasta dish', ''),
    -- Roma Ristorante
    (6, 'Fettuccine Alfredo', 14.00, 'Pasta with creamy sauce', ''),
    (6, 'Margherita Pizza', 16.00, 'Pizza with tomatoes, mozzarella, and basil', 'Small|Medium|Large'),
    (6, 'Cannoli', 7.00, 'Pastry with sweet filling', ''),
    (6, 'Gnocchi', 13.00, 'Potato dumplings with sauce', ''),
    (6, 'Gelato', 5.00, 'Italian ice cream', 'Vanilla|Chocolate|Strawberry|Pistachio'),
    -- Le Petit Bistro
    (7, 'Steak', 25.00, 'Grilled beef steak', 'Rare|Medium Rare|Medium|Well Done'),
    (7, 'Croissant', 3.00, 'Buttery croissant', ''),
    (7, 'Ratatouille', 8.00, 'Vegetable stew', ''),
    (7, 'Macarons', 2.00, 'Colorful French cookies', 'Vanilla|Chocolate|Raspberry|Pistachio'),
    (7, 'Baguette', 2.00, 'Long French bread', ''),
    -- Chez Paris
    (8, 'Bouillabaisse', 18.00, 'Traditional fish stew', ''),
    (8, 'Coq au Vin', 20.00, 'Chicken braised with wine', ''),
    (8, 'Crepes', 6.00, 'Thin pancakes with various fillings', 'Sweet|Savory'),
    (8, 'French Onion Soup', 8.00, 'Onion soup with cheese', ''),
    (8, 'Eclairs', 4.00, 'Pastry with cream filling', 'Chocolate|Vanilla|Coffee'),
    -- Lebanese Delights
    (9, 'Shawarma', 10.00, 'Marinated meat wrapped in pita', 'Chicken|Beef|Lamb'),
    (9, 'Tabbouleh', 8.00, 'Parsley and bulgur salad', ''),
    (9, 'Falafel', 6.00, 'Deep-fried chickpea balls', ''),
    (9, 'Hummus', 5.00, 'Chickpea dip with tahini', ''),
    (9, 'Baba Ghanoush', 7.00, 'Smoky eggplant dip', ''),
    -- Moroccan Feast
    (10, 'Tagine', 15.00, 'Slow-cooked meat and vegetable stew', 'Chicken|Lamb|Vegetable'),
    (10, 'Couscous', 10.00, 'Steamed semolina with vegetables', ''),
    (10, 'Harira', 8.00, 'Tangy tomato soup with lentils', ''),
    (10, 'Briouats', 6.00, 'Stuffed pastry triangles', ''),
    (10, 'Zaalouk', 7.00, 'Spicy eggplant and tomato dip', ''),
    -- Texas Tacos
    (11, 'Taco', 3.00, 'Soft corn tortilla with fillings', 'Beef|Chicken|Fish'),
    (11, 'Nachos', 8.00, 'Tortilla chips with cheese and toppings', ''),
    (11, 'Quesadilla', 6.00, 'Grilled tortilla with cheese', ''),
    (11, 'Enchiladas', 10.00, 'Stuffed tortillas with chili sauce', 'Red Sauce|Green Sauce'),
    (11, 'Chili Con Carne', 12.00, 'Spicy meat stew', 'Mild|Medium|Hot'),
    -- Traditional Mexican
    (12, 'Tamale', 5.00, 'Steamed corn dough with fillings', 'Pork|Chicken|Cheese'),
    (12, 'Churro', 3.00, 'Fried dough pastry with sugar', ''),
    (12, 'Elote', 4.00, 'Grilled corn on the cob', ''),
    (12, 'Guacamole', 6.00, 'Avocado dip', ''),
    (12, 'Posole', 8.00, 'Hominy soup with pork', ''),
    -- Sushi House
    (13, 'Nigiri', 12.00, 'Sushi with fish on top of rice', 'Tuna|Salmon|Shrimp'),
    (13, 'Maki', 10.00, 'Rice and fish rolled in seaweed', ''),
    (13, 'Sashimi', 14.00, 'Sliced raw fish', 'Tuna|Salmon|Mixed'),
    (13, 'Tempura', 9.00, 'Battered and fried vegetables or seafood', ''),
    (13, 'Miso Soup', 4.00, 'Soybean paste soup with tofu', ''),
    -- Ramen World
    (14, 'Tonkotsu Ramen', 12.00, 'Pork bone broth ramen', 'Regular|Extra Rich'),
    (14, 'Shoyu Ramen', 10.00, 'Soy sauce ramen', ''),
    (14, 'Miso Ramen', 11.00, 'Miso-based ramen', ''),
    (14, 'Chashu Ramen', 14.00, 'Ramen with braised pork belly', ''),
    (14, 'Spicy Ramen', 13.00, 'Spicy flavored ramen', 'Mild|Medium|Extreme');

-- Riders
INSERT IGNORE INTO riders (name, phone) VALUES
    ('John Doe', '123-456-7890'),
    ('Jane Smith', '987-654-3210'),
    ('Bob Brown', '555-123-4567'),
    ('Alice Green', '444-987-6543'),
    ('Charlie Black', '222-333-4444'),
    ('Emily White', '333-555-6666'),
    ('Michael Johnson', '111-222-3333'),
    ('Jessica Davis', '444-555-7777'),
    ('David Wilson', '888-999-0000'),
    ('Sarah Martinez', '666-777-8888');
