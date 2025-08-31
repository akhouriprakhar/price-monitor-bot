import requests
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger(__name__)

class ProductScraper:
    def __init__(self):
        """Initializes the scraper with standard headers."""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Connection': 'keep-alive'
        }

    def get_product_info(self, url):
        """
        Fetches product information (title and price) from a given URL.
        Returns a dictionary with 'title' and 'price' or None on failure.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
            soup = BeautifulSoup(response.content, 'lxml')

            title = self._extract_title(soup)
            price = self._extract_price(soup)

            if title and price:
                logger.info(f"Successfully scraped '{title}' with price {price} from {url}")
                return {'title': title, 'price': price}
            else:
                logger.warning(f"Could not find title or price for URL: {url}")
                return None

        except requests.RequestException as e:
            logger.error(f"Request failed for URL {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"An error occurred during scraping of {url}: {e}")
            return None

    def _extract_title(self, soup):
        """Extracts the product title from the page soup."""
        # Try common tags and IDs for product titles
        title_selectors = ['#productTitle', 'h1.product-title', '.B_NuCI', '.pdp-title']
        for selector in title_selectors:
            title_element = soup.select_one(selector)
            if title_element:
                return title_element.get_text(strip=True)
        return "Product Title Not Found"

    def _extract_price(self, soup):
        """Extracts and cleans the product price from the page soup."""
        # Try common classes and IDs for prices
        price_selectors = [
            '.a-price-whole', '.a-offscreen', '._30jeq3',
            'span.price', '.product-price', '.pdp-price'
        ]
        for selector in price_selectors:
            price_element = soup.select_one(selector)
            if price_element:
                price_text = price_element.get_text(strip=True)
                # Clean the price string (remove symbols, commas)
                cleaned_price = re.sub(r'[^\d.]', '', price_text)
                if cleaned_price:
                    try:
                        return float(cleaned_price)
                    except ValueError:
                        continue # Try next selector if conversion fails
        return None