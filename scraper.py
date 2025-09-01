import requests
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger(__name__)

class ProductScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Connection': 'keep-alive',
            'DNT': '1'
        }

    def get_product_info(self, url):
        """Fetches product information (title and price) from a given URL."""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
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
        """Extracts the product title using a list of potential selectors."""
        title_selectors = [
            '#productTitle', '.B_NuCI', '.pdp-title', '.product-title', 
            'h1', 'span[data-ui="product-title"]'
        ]
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        return "Product Title Not Found"

    def _extract_price(self, soup):
        """Extracts and cleans the product price using a list of potential selectors."""
        price_selectors = [
            '.a-price-whole', '._30jeq3', '.pdp-price', '.product-price', 
            '.a-offscreen', 'span.price', 'span[data-testid="price"]'
        ]
        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                cleaned_price = re.sub(r'[^\d.]', '', price_text)
                if cleaned_price:
                    try:
                        return float(cleaned_price)
                    except ValueError:
                        continue
        return None
