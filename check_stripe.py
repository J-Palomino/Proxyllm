#!/usr/bin/env python3
"""
Quick Stripe environment checker
Usage: python check_stripe.py your_stripe_key_here
"""

import sys
import json
import urllib.request
import urllib.parse
import base64


def check_stripe(api_key):
    """Check Stripe environment and list resources"""
    print(f"Checking Stripe with key: {api_key[:12]}...")
    
    # Basic auth setup
    auth_string = f"{api_key}:"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_base64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    def make_request(endpoint):
        try:
            url = f"https://api.stripe.com/v1/{endpoint}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Error with {endpoint}: {e}")
            return None
    
    # Check account
    print("\n=== ACCOUNT INFO ===")
    account = make_request("account")
    if account:
        print(f"Account ID: {account.get('id')}")
        print(f"Country: {account.get('country')}")
        print(f"Currency: {account.get('default_currency')}")
        print(f"Charges Enabled: {account.get('charges_enabled')}")
    
    # Check products
    print("\n=== PRODUCTS ===")
    products = make_request("products?limit=10")
    if products and products.get('data'):
        for p in products['data']:
            print(f"Product: {p['id']} - {p.get('name')} (active: {p.get('active')})")
    else:
        print("No products found")
    
    # Check prices  
    print("\n=== PRICES/BILLING MODELS ===")
    prices = make_request("prices?limit=10")
    if prices and prices.get('data'):
        for p in prices['data']:
            amount = p.get('unit_amount', 0) / 100 if p.get('unit_amount') else 0
            currency = p.get('currency', 'usd').upper()
            recurring = p.get('recurring', {})
            
            print(f"Price ID: {p['id']}")
            print(f"  Product: {p.get('product')}")
            print(f"  Amount: ${amount:.2f} {currency}")
            print(f"  Type: {p.get('type', 'N/A')}")
            
            if recurring:
                interval = recurring.get('interval', 'N/A')
                usage_type = recurring.get('usage_type', 'N/A')
                print(f"  Recurring: {interval} ({usage_type})")
            print()
    else:
        print("No prices found")
    
    # Check customers
    print("\n=== CUSTOMERS ===")
    customers = make_request("customers?limit=5")
    if customers and customers.get('data'):
        print(f"Found {len(customers['data'])} customers")
        for c in customers['data'][:3]:  # Show first 3
            print(f"Customer: {c['id']} - {c.get('email', 'No email')}")
    else:
        print("No customers found")
    
    # Check subscriptions
    print("\n=== SUBSCRIPTIONS ===")
    subs = make_request("subscriptions?limit=5")
    if subs and subs.get('data'):
        print(f"Found {len(subs['data'])} subscriptions")
        for s in subs['data'][:3]:  # Show first 3
            print(f"Subscription: {s['id']} - Status: {s.get('status')} - Customer: {s.get('customer')}")
    else:
        print("No subscriptions found")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_stripe.py sk_test_your_key_here")
        print("This will show what products, prices, and billing models are set up")
        sys.exit(1)
    
    api_key = sys.argv[1]
    if not api_key.startswith('sk_test_'):
        print("WARNING: This doesn't look like a test key!")
        
    check_stripe(api_key)