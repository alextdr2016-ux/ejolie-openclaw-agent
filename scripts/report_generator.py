"""
Report Generator for ejolie.ro
Creates formatted reports from API data
"""

from ejolie_api import EjolieAPI
from datetime import datetime
from typing import Dict, List
import json


class ReportGenerator:
    """Generate business reports from ejolie.ro data"""

    def __init__(self):
        self.api = EjolieAPI()

    def sales_report(self, start_date: str, end_date: str) -> str:
        """
        Generate sales report for a period

        Args:
            start_date: Format 'DD-MM-YYYY'
            end_date: Format 'DD-MM-YYYY'

        Returns:
            Formatted report string
        """
        orders = self.api.get_orders(start_date, end_date)

        if isinstance(orders, dict) and orders.get('eroare'):
            return f"❌ Eroare la obținerea comenzilor: {orders.get('mesaj')}"

        # Calculate metrics
        total_orders = len(orders)
        total_revenue = 0
        products_sold = {}

        for order_id, order in orders.items():
            if not isinstance(order, dict):
                continue

            # Add to revenue
            total_revenue += float(order.get('total_comanda', 0))

            # Count products
            products = order.get('produse', {})
            for prod_id, product in products.items():
                if isinstance(product, dict):
                    name = product.get('nume', 'Unknown')
                    qty = float(product.get('cantitate', 0))

                    if name in products_sold:
                        products_sold[name] += qty
                    else:
                        products_sold[name] = qty

        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

        # Format report
        report = f"""
📊 **RAPORT VÂNZĂRI**
Perioadă: {start_date} - {end_date}

💰 **Rezumat Financiar:**
- Total vânzări: {total_revenue:.2f} RON
- Număr comenzi: {total_orders}
- Valoare medie comandă: {avg_order_value:.2f} RON

📦 **Produse vândute:**
- Total articole: {sum(products_sold.values()):.0f} bucăți
- Produse distincte: {len(products_sold)}

🔝 **Top 5 Produse:**
"""

        # Add top products
        top_products = sorted(products_sold.items(),
                              key=lambda x: x[1], reverse=True)[:5]
        for i, (name, qty) in enumerate(top_products, 1):
            report += f"{i}. {name}: {qty:.0f} buc\n"

        return report.strip()

    def profit_analysis(self, start_date: str, end_date: str) -> str:
        """
        Generate profit margins analysis

        Args:
            start_date: Format 'DD-MM-YYYY'
            end_date: Format 'DD-MM-YYYY'

        Returns:
            Formatted profit report
        """
        orders = self.api.get_orders(start_date, end_date)
        all_products = self.api.get_products()

        if isinstance(orders, dict) and orders.get('eroare'):
            return f"❌ Eroare: {orders.get('mesaj')}"

        # Build product price lookup
        product_prices = {}
        for prod_id, product in all_products.items():
            if isinstance(product, dict):
                product_prices[prod_id] = {
                    'pret_lista': float(product.get('pret', 0)),
                    'pret_vanzare': float(product.get('pret_discount', 0)) or float(product.get('pret', 0)),
                    'nume': product.get('nume', 'Unknown')
                }

        # Calculate profits
        product_profits = {}
        total_profit = 0
        total_cost = 0
        total_revenue = 0

        for order_id, order in orders.items():
            if not isinstance(order, dict):
                continue

            products = order.get('produse', {})
            for prod_id, product in products.items():
                if not isinstance(product, dict):
                    continue

                item_id = product.get('id_produs')
                if not item_id or item_id not in product_prices:
                    continue

                qty = float(product.get('cantitate', 0))
                sell_price = float(product.get('pret_unitar', 0))
                cost_price = product_prices[item_id]['pret_lista']

                profit_per_unit = sell_price - cost_price
                total_item_profit = profit_per_unit * qty

                total_profit += total_item_profit
                total_cost += cost_price * qty
                total_revenue += sell_price * qty

                name = product.get('nume', 'Unknown')
                if name not in product_profits:
                    product_profits[name] = {
                        'profit': 0,
                        'units': 0,
                        'revenue': 0
                    }

                product_profits[name]['profit'] += total_item_profit
                product_profits[name]['units'] += qty
                product_profits[name]['revenue'] += sell_price * qty

        # Calculate margin
        profit_margin = (total_profit / total_revenue *
                         100) if total_revenue > 0 else 0

        # Format report
        report = f"""
💰 **ANALIZĂ PROFIT MARGINS**
Perioadă: {start_date} - {end_date}

📈 **Rezumat:**
- Total venituri: {total_revenue:.2f} RON
- Total costuri: {total_cost:.2f} RON
- Profit net: {total_profit:.2f} RON
- Marjă profit: {profit_margin:.1f}%

🏆 **Top 5 Produse după Profit:**
"""

        # Add top profitable products
        top_profit = sorted(product_profits.items(),
                            key=lambda x: x[1]['profit'], reverse=True)[:5]
        for i, (name, data) in enumerate(top_profit, 1):
            margin = (data['profit'] / data['revenue'] *
                      100) if data['revenue'] > 0 else 0
            report += f"{i}. {name}\n"
            report += f"   Profit: {data['profit']:.2f} RON | Marjă: {margin:.1f}% | Unități: {data['units']:.0f}\n"

        return report.strip()

    def stock_alert(self, threshold: int = 5) -> str:
        """
        Generate low stock alert

        Args:
            threshold: Stock level to trigger alert

        Returns:
            Formatted stock report
        """
        low_stock = self.api.get_low_stock_products(threshold)

        if not low_stock:
            return f"✅ Toate produsele au stoc suficient (peste {threshold} bucăți)"

        report = f"""
⚠️ **ALERTĂ STOC SCĂZUT**
Produse sub {threshold} bucăți:

"""

        # Sort by stock level
        low_stock.sort(key=lambda x: int(x.get('stoc_fizic', 0)))

        for product in low_stock[:20]:  # Limit to 20 items
            name = product.get('nume', 'Unknown')
            stock = product.get('stoc_fizic', 0)
            code = product.get('cod_produs', 'N/A')

            report += f"• {name}\n"
            report += f"  Cod: {code} | Stoc: {stock} buc\n\n"

        if len(low_stock) > 20:
            report += f"\n... și încă {len(low_stock) - 20} produse"

        return report.strip()

    def pending_orders(self) -> str:
        """Get pending orders report"""
        # Status 1 = "Comanda noua"
        pending = self.api.get_orders(
            start_date='01-01-2024',  # Far back date
            end_date=datetime.now().strftime('%d-%m-%Y'),
            status_id=1
        )

        if isinstance(pending, dict) and pending.get('eroare'):
            return f"❌ Eroare: {pending.get('mesaj')}"

        if not pending or len(pending) == 0:
            return "✅ Nu există comenzi pendinte!"

        report = f"""
📋 **COMENZI PENDINTE**
Total: {len(pending)} comenzi noi

"""

        for order_id, order in list(pending.items())[:10]:  # Limit to 10
            if not isinstance(order, dict):
                continue

            client = order.get('client', {}).get('nume', 'Unknown')
            total = order.get('total_comanda', 0)
            date = order.get('data', 'N/A')

            report += f"• Comanda #{order_id}\n"
            report += f"  Client: {client} | Total: {total} RON | Data: {date}\n\n"

        if len(pending) > 10:
            report += f"\n... și încă {len(pending) - 10} comenzi"

        return report.strip()


if __name__ == "__main__":
    # Test reports
    generator = ReportGenerator()

    print("Testing Sales Report...")
    print(generator.sales_report('01-02-2024', '29-02-2024'))

    print("\n" + "="*50 + "\n")

    print("Testing Stock Alert...")
    print(generator.stock_alert())
