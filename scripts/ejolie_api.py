"""
Extended API Client for ejolie.ro
Handles all API communication and data processing
"""

import requests
import os
from dotenv import load_dotenv
from typing import Dict, List, Optional
from datetime import datetime

load_dotenv()


class EjolieAPI:
    """Client for Extended API integration"""

    def __init__(self):
        self.base_url = os.getenv('EJOLIE_API_URL', 'https://ejolie.ro/api/')
        self.api_key = os.getenv('EJOLIE_API_KEY')

        if not self.api_key:
            raise ValueError("EJOLIE_API_KEY not found in environment")

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request to API"""
        if params is None:
            params = {}

        params['apikey'] = self.api_key

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"eroare": 1, "mesaj": str(e)}

    def get_orders(self, start_date: str, end_date: str,
                   status_id: Optional[int] = None) -> Dict:
        """
        Get orders for a specific period

        Args:
            start_date: Format 'DD-MM-YYYY'
            end_date: Format 'DD-MM-YYYY'
            status_id: Optional order status filter

        Returns:
            Dict with orders data
        """
        params = {
            'comenzi': '',
            'data_start': start_date,
            'data_end': end_date,
            'limit': 2000
        }

        if status_id:
            params['idstatus'] = status_id

        return self._make_request('comenzi', params)

    def get_products(self, category: Optional[str] = None) -> Dict:
        """Get products list"""
        params = {'produse': ''}
        if category:
            params['categorie'] = category

        return self._make_request('produse', params)

    def get_low_stock_products(self, threshold: int = 5) -> List[Dict]:
        """Get products with low stock"""
        products = self.get_products()

        if isinstance(products, dict) and products.get('eroare'):
            return []

        low_stock = []
        for product in products.values():
            if isinstance(product, dict):
                stock = product.get('stoc_fizic', 0)
                if stock and int(stock) < threshold:
                    low_stock.append(product)

        return low_stock


if __name__ == "__main__":
    # Test the API
    api = EjolieAPI()

    # Test orders
    orders = api.get_orders('01-01-2024', '31-01-2024')
    print(
        f"Orders retrieved: {len(orders) if isinstance(orders, dict) else 0}")

    # Test low stock
    low_stock = api.get_low_stock_products()
    print(f"Low stock items: {len(low_stock)}")
