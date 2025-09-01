import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name='products.db'):
        """Initializes the database connection and creates/updates tables."""
        # Use Railway's persistent volume if it exists, otherwise use local file
        db_path = '/data/products.db' if os.path.exists('/data') else db_name
        self.db_name = db_path
        self.conn = None
        try:
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.create_tables()
            self._update_schema()  # Ensure schema is up-to-date
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def create_tables(self):
        """Creates the database table if it doesn't exist."""
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
        except sqlite3.Error as e:
            logger.error(f"Failed to create tables: {e}")

    def _update_schema(self):
        """Adds new columns to the table for new features, ensuring backward compatibility."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(products)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'target_price' not in columns:
                cursor.execute("ALTER TABLE products ADD COLUMN target_price REAL")
                self.conn.commit()
                logger.info("Database schema updated with 'target_price' column.")
        except sqlite3.Error as e:
            logger.error(f"Failed to update schema: {e}")

    def add_product(self, user_id, url, title, price):
        """Adds a new product and returns its ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO products (user_id, url, title, initial_price, last_checked_price)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, url) DO UPDATE SET
            last_checked_price=excluded.last_checked_price, title=excluded.title
            """, (user_id, url, title, price, price))
            self.conn.commit()
            # Get the ID of the inserted or updated row
            cursor.execute("SELECT id FROM products WHERE user_id = ? AND url = ?", (user_id, url))
            product_id = cursor.fetchone()[0]
            return product_id
        except sqlite3.Error as e:
            logger.error(f"Failed to add product for user {user_id}: {e}")
            return None

    def get_user_products(self, user_id):
        """Retrieves all products for a user, including target price."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, title, initial_price, last_checked_price, url, target_price FROM products WHERE user_id = ?", (user_id,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Failed to get products for user {user_id}: {e}")
            return []
            
    def get_all_products(self):
        """Retrieves all products for the scheduler, including target price."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, user_id, url, title, last_checked_price, target_price FROM products")
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Failed to get all products: {e}")
            return []

    def set_target_price(self, product_id, user_id, target_price):
        """Sets or updates the target price for a product."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE products SET target_price = ? WHERE id = ? AND user_id = ?", (target_price, product_id, user_id))
            self.conn.commit()
            return cursor.rowcount > 0 # Returns True if a row was updated
        except sqlite3.Error as e:
            logger.error(f"Failed to set target price for product {product_id}: {e}")
            return False

    def update_product_price(self, product_id, new_price):
        """Updates the last checked price of a product."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE products SET last_checked_price = ? WHERE id = ?", (new_price, product_id))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to update price for product ID {product_id}: {e}")

    def delete_product(self, user_id, product_id):
        """Deletes a product from a user's tracking list."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, user_id))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to delete product ID {product_id} for user {user_id}: {e}")

    def __del__(self):
        """Closes the database connection when the object is destroyed."""
        if self.conn:
            self.conn.close()

