#!/usr/bin/env python3
"""
Simple Stripe API checker using only standard library
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
import base64
from typing import Dict, Any


def make_stripe_request(api_key: str, endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """Make a request to Stripe API using only standard library"""
    url = f"https://api.stripe.com/v1/{endpoint}"
    
    # Prepare headers
    auth_string = f"{api_key}:"
    auth_bytes = auth_string.encode('ascii')
    auth_base64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        'Authorization': f'Basic {auth_base64}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'LiteLLM-Stripe-Explorer/1.0'
    }
    
    try:
        if method == "GET" and data:
            # Add query parameters for GET requests
            query_string = urllib.parse.urlencode(data)
            url += f"?{query_string}"
            
        request = urllib.request.Request(url, headers=headers)
        
        if method == "POST" and data:
            post_data = urllib.parse.urlencode(data).encode('utf-8')
            request.data = post_data
            
        with urllib.request.urlopen(request) as response:
            response_data = response.read().decode('utf-8')
            return json.loads(response_data)
            
    except urllib.error.HTTPError as e:
        error_data = e.read().decode('utf-8')
        print(f"ERROR: HTTP Error {e.code}: {e.reason}")
        try:
            error_json = json.loads(error_data)
            print(f"Error details: {error_json.get('error', {}).get('message', 'Unknown error')}")
        except:
            print(f"Raw error: {error_data}")
        return {}
    except urllib.error.URLError as e:
        print(f"ERROR: URL Error: {e.reason}")
        return {}
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return {}


def check_stripe_key(api_key: str):
    """Check if the Stripe key is valid by making a simple API call"""
    print(f"Testing Stripe API key: {api_key[:12]}...")
    
    if not api_key.startswith('sk_test_'):
        print("Warning: This doesn't appear to be a test key!")
    
    # Test with account endpoint
    account = make_stripe_request(api_key, "account")
    
    if account:
        print("SUCCESS: API key is valid!")
        print(f"Account ID: {account.get('id', 'N/A')}")
        print(f"Business Name: {account.get('business_profile', {}).get('name', 'Not set')}")
        print(f"Country: {account.get('country', 'N/A')}")
        print(f"Default Currency: {account.get('default_currency', 'N/A')}")
        print(f"Charges Enabled: {account.get('charges_enabled', 'N/A')}")
        return True
    else:
        print("ERROR: API key appears to be invalid")
        return False


def list_products(api_key: str):
    """List existing products"""
    print("\nExisting Products:")
    print("-" * 40)
    
    products = make_stripe_request(api_key, "products", data={"limit": 10})
    
    if products and products.get('data'):
        for product in products['data']:
            print(f"ID: {product['id']}")
            print(f"Name: {product.get('name', 'N/A')}")
            print(f"Active: {product.get('active', 'N/A')}")
            print(f"Type: {product.get('type', 'N/A')}")
            print()
    else:
        print("No products found")


def list_prices(api_key: str):
    """List existing prices"""
    print("\nExisting Prices:")
    print("-" * 40)
    
    prices = make_stripe_request(api_key, "prices", data={"limit": 10})
    
    if prices and prices.get('data'):
        for price in prices['data']:
            print(f"ID: {price['id']}")
            print(f"Product: {price.get('product', 'N/A')}")
            if price.get('unit_amount'):
                amount = price['unit_amount'] / 100
                currency = price.get('currency', 'usd').upper()
                print(f"Unit Amount: {amount:.2f} {currency}")
            print(f"Type: {price.get('type', 'N/A')}")
            if price.get('recurring'):
                recurring = price['recurring']
                print(f"Recurring: {recurring.get('interval', 'N/A')} ({recurring.get('usage_type', 'N/A')})")
            print()
    else:
        print("No prices found")


def create_litellm_resources(api_key: str):
    """Create basic resources for LiteLLM integration"""
    print("\nCreating LiteLLM Resources:")
    print("-" * 40)
    
    # Create product
    product_data = {
        "name": "LiteLLM API Usage",
        "description": "Token usage for LiteLLM API calls", 
        "type": "service"
    }
    
    product = make_stripe_request(api_key, "products", method="POST", data=product_data)
    
    if not product:
        print("ERROR: Failed to create product")
        return
        
    print(f"SUCCESS: Created product: {product['id']}")
    
    # Create metered price (per token)
    price_data = {
        "product": product['id'],
        "unit_amount": 1,  # 1 cent per token
        "currency": "usd",
        "recurring[interval]": "month",
        "recurring[usage_type]": "metered",
        "billing_scheme": "per_unit"
    }
    
    price = make_stripe_request(api_key, "prices", method="POST", data=price_data)
    
    if price:
        print(f"SUCCESS: Created price: {price['id']}")
        print(f"Unit amount: $0.01 per token")
        print(f"Usage type: metered")
        
        print(f"\nAdd this to your environment:")
        print(f"export STRIPE_PRICE_ID={price['id']}")
        print(f"export STRIPE_API_KEY={api_key}")
        
        return product, price
    else:
        print("ERROR: Failed to create price")
        return product, None


def main():
    """Main function"""
    print("Simple Stripe Sandbox Checker")
    print("=" * 40)
    
    # Check for API key
    api_key = os.getenv('STRIPE_API_KEY')
    
    if not api_key:
        api_key = input("Enter your Stripe test API key (sk_test_...): ").strip()
        
    if not api_key:
        print("ERROR: No API key provided")
        return
    
    # Validate key
    if not check_stripe_key(api_key):
        return
    
    # List existing resources
    list_products(api_key)
    list_prices(api_key)
    
    # Ask if user wants to create resources
    print("\n" + "=" * 40)
    create = input("Create LiteLLM test resources? (y/n): ").strip().lower()
    
    if create == 'y':
        create_litellm_resources(api_key)
    
    print("\nDone!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nERROR: Unexpected error: {e}")