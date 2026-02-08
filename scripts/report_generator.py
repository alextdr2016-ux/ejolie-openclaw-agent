"""
Report generator using ejolie.ro Extended API
"""

from typing import Dict, List
from ejolie_api import EjolieAPI


class ReportGenerator:
    def __init__(self):
        self.api = EjolieAPI()

    def sales_report(self, start_date: str, end_date: str, status_id: int = None) -> str:
        """
        Generate sales report for a date range

        Args:
            start_date: Format 'DD-MM-YYYY'
            end_date: Format 'DD-MM-YYYY'
            status_id: Optional status filter (14=INCASATA, 9=RETURNATA, etc.)
        """
        orders = self.api.get_orders(start_date, end_date, status_id=status_id)

        if orders.get('eroare') == 1:
            return f"❌ Eroare la obținerea comenzilor: {orders.get('mesaj')}"

        if not orders:
            return f"📊 Nicio comandă găsită în perioada {start_date} - {end_date}"

        # Calculate statistics
        total_sales = 0
        total_orders = len(orders)
        products_sold = {}
        total_items = 0

        for order_id, order in orders.items():
            # Get order total from produse
            if 'produse' in order:
                # produse is a dict of products, not a list
                for product_id, product in order['produse'].items():
                    # Calculate product total
                    # cantitate is string!
                    quantity = float(product.get('cantitate', 0))
                    price = float(product.get('pret_unitar', 0))
                    product_total = quantity * price
                    total_sales += product_total
                    total_items += quantity

                    # Track products sold (nume already includes size)
                    product_name = product.get('nume', 'Unknown')
                    products_sold[product_name] = products_sold.get(
                        product_name, 0) + quantity

        avg_order = total_sales / total_orders if total_orders > 0 else 0

        # Get top 5 products
        top_products = sorted(products_sold.items(),
                              key=lambda x: x[1], reverse=True)[:5]

        # Build report
        status_filter = ""
        if status_id:
            status_names = {14: "INCASATA", 9: "RETURNATA",
                            38: "REFUZATA", 37: "SCHIMB"}
            status_filter = f"\nFiltru status: {status_names.get(status_id, str(status_id))}"

        report = f"""📊 **RAPORT VÂNZĂRI**
Perioadă: {start_date} - {end_date}{status_filter}

💰 **Rezumat Financiar:**
- Total vânzări: {total_sales:.2f} RON
- Număr comenzi: {total_orders}
- Valoare medie comandă: {avg_order:.2f} RON

📦 **Produse vândute:**
- Total articole: {total_items:.0f} bucăți
- Produse distincte: {len(products_sold)}

🔝 **Top 5 Produse:**
"""

        for i, (product, qty) in enumerate(top_products, 1):
            report += f"{i}. {product}: {qty:.0f} buc\n"

        return report

    def profit_analysis(self, start_date: str, end_date: str) -> str:
        """Generate profit analysis report"""
        orders = self.api.get_orders(start_date, end_date)

        if orders.get('eroare') == 1:
            return f"❌ Eroare: {orders.get('mesaj')}"

        return f"💰 Profit analysis for {start_date} to {end_date}\n(To be implemented)"

    def stock_alert(self, threshold: int = 5) -> str:
        """Generate low stock alert"""
        stock_data = self.api.get_low_stock(threshold)

        if stock_data.get('eroare') == 1:
            return f"❌ Eroare: {stock_data.get('mesaj')}"

        return f"📦 Low stock items (threshold: {threshold})\n(To be implemented)"

    def pending_orders(self) -> str:
        """Generate pending orders report"""
        # Get orders with pending status
        return "🛒 Pending orders report\n(To be implemented)"
