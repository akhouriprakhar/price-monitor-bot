import sqlite3
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name='products.db'):
        """Initializes the database connection and creates tables if they don't exist."""
        self.db_name = db_name
        self.conn = None
        try:
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.create_tables()
            logger.info(f"Database '{self.db_name}' connected successfully.")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def create_tables(self):
        """Creates the necessary database tables."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                initial_price REAL,
                last_checked_price REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, url)
            )
            """)
            self.conn.commit()
            logger.info("Table 'products' created or already exists.")
        except sqlite3.Error as e:
            logger.error(f"Failed to create tables: {e}")

    def add_product(self, user_id, url, title, price):
        """Adds a new product to the database for tracking."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO products (user_id, url, title, initial_price, last_checked_price)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, url) DO UPDATE SET
            last_checked_price=excluded.last_checked_price
            """, (user_id, url, title, price, price))
            self.conn.commit()
            logger.info(f"Product added/updated for user {user_id}: {title}")
        except sqlite3.Error as e:
            logger.error(f"Failed to add product for user {user_id}: {e}")

    def get_user_products(self, user_id):
        """Retrieves all products tracked by a specific user."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, title, initial_price, last_checked_price, url FROM products WHERE user_id = ?", (user_id,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Failed to get products for user {user_id}: {e}")
            return []

    def get_all_products(self):
        """Retrieves all products from the database for price checking."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, user_id, url, title, last_checked_price FROM products")
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Failed to get all products: {e}")
            return []

    def update_product_price(self, product_id, new_price):
        """Updates the last checked price of a product."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE products SET last_checked_price = ? WHERE id = ?", (new_price, product_id))
            self.conn.commit()
            logger.info(f"Updated price for product ID {product_id} to {new_price}.")
        except sqlite3.Error as e:
            logger.error(f"Failed to update price for product ID {product_id}: {e}")

    def delete_product(self, user_id, product_id):
        """Deletes a product from a user's tracking list."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, user_id))
            self.conn.commit()
            logger.info(f"Deleted product ID {product_id} for user {user_id}.")
        except sqlite3.Error as e:
            logger.error(f"Failed to delete product ID {product_id} for user {user_id}: {e}")

    def __del__(self):
        """Closes the database connection when the object is destroyed."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")