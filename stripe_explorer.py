#!/usr/bin/env python3
"""
Stripe Sandbox Explorer

This script helps explore what's available in your Stripe sandbox environment.
Set your Stripe test API key as an environment variable or pass it directly.
"""

import os
import sys
import json
from typing import Dict, Any
import requests


class StripeExplorer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('STRIPE_API_KEY')
        if not self.api_key:
            raise ValueError("Please provide STRIPE_API_KEY environment variable or pass it directly")
        
        if not self.api_key.startswith('sk_test_'):
            print("⚠️  Warning: This doesn't appear to be a test key. Make sure you're using a test environment key.")
        
        self.base_url = "https://api.stripe.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def make_request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
        """Make a request to the Stripe API"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=data)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, data=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error making request to {endpoint}: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            return {}

    def explore_account(self):
        """Get account information"""
        print("\n🏢 Account Information:")
        print("=" * 50)
        
        account = self.make_request("account")
        if account:
            print(f"Account ID: {account.get('id', 'N/A')}")
            print(f"Business Name: {account.get('business_profile', {}).get('name', 'N/A')}")
            print(f"Country: {account.get('country', 'N/A')}")
            print(f"Default Currency: {account.get('default_currency', 'N/A')}")
            print(f"Email: {account.get('email', 'N/A')}")
            print(f"Charges Enabled: {account.get('charges_enabled', 'N/A')}")
            print(f"Details Submitted: {account.get('details_submitted', 'N/A')}")

    def explore_products(self):
        """List available products"""
        print("\n📦 Products:")
        print("=" * 50)
        
        products = self.make_request("products", data={"limit": 10})
        if products and products.get('data'):
            for product in products['data']:
                print(f"ID: {product['id']}")
                print(f"Name: {product.get('name', 'N/A')}")
                print(f"Description: {product.get('description', 'N/A')}")
                print(f"Active: {product.get('active', 'N/A')}")
                print(f"Type: {product.get('type', 'N/A')}")
                print("-" * 30)
        else:
            print("No products found")

    def explore_prices(self):
        """List available prices"""
        print("\n💰 Prices:")
        print("=" * 50)
        
        prices = self.make_request("prices", data={"limit": 10})
        if prices and prices.get('data'):
            for price in prices['data']:
                print(f"ID: {price['id']}")
                print(f"Product: {price.get('product', 'N/A')}")
                print(f"Unit Amount: {price.get('unit_amount', 'N/A')}")
                print(f"Currency: {price.get('currency', 'N/A')}")
                print(f"Type: {price.get('type', 'N/A')}")
                print(f"Recurring: {price.get('recurring', {})}")
                print(f"Active: {price.get('active', 'N/A')}")
                print("-" * 30)
        else:
            print("No prices found")

    def explore_customers(self):
        """List available customers"""
        print("\n👥 Customers:")
        print("=" * 50)
        
        customers = self.make_request("customers", data={"limit": 10})
        if customers and customers.get('data'):
            for customer in customers['data']:
                print(f"ID: {customer['id']}")
                print(f"Email: {customer.get('email', 'N/A')}")
                print(f"Name: {customer.get('name', 'N/A')}")
                print(f"Created: {customer.get('created', 'N/A')}")
                print("-" * 30)
        else:
            print("No customers found")

    def explore_subscriptions(self):
        """List available subscriptions"""
        print("\n🔄 Subscriptions:")
        print("=" * 50)
        
        subscriptions = self.make_request("subscriptions", data={"limit": 10})
        if subscriptions and subscriptions.get('data'):
            for subscription in subscriptions['data']:
                print(f"ID: {subscription['id']}")
                print(f"Customer: {subscription.get('customer', 'N/A')}")
                print(f"Status: {subscription.get('status', 'N/A')}")
                print(f"Current Period Start: {subscription.get('current_period_start', 'N/A')}")
                print(f"Current Period End: {subscription.get('current_period_end', 'N/A')}")
                print(f"Items: {len(subscription.get('items', {}).get('data', []))}")
                print("-" * 30)
        else:
            print("No subscriptions found")

    def create_test_product_and_price(self):
        """Create a test product and price for LiteLLM usage"""
        print("\n🧪 Creating Test Product and Price:")
        print("=" * 50)
        
        # Create a product
        product_data = {
            "name": "LiteLLM API Usage",
            "description": "Usage-based billing for LiteLLM API calls",
            "type": "service"
        }
        
        product = self.make_request("products", method="POST", data=product_data)
        if not product:
            return
        
        print(f"✅ Created Product: {product['id']}")
        
        # Create a usage-based price
        price_data = {
            "product": product['id'],
            "unit_amount": 100,  # $1.00 per unit (in cents)
            "currency": "usd",
            "recurring[interval]": "month",
            "recurring[usage_type]": "metered",
            "billing_scheme": "per_unit"
        }
        
        price = self.make_request("prices", method="POST", data=price_data)
        if price:
            print(f"✅ Created Price: {price['id']}")
            print(f"Unit Amount: ${price['unit_amount'] / 100:.2f}")
            print(f"Usage Type: {price.get('recurring', {}).get('usage_type', 'N/A')}")
            
            print(f"\n🔧 For your .env file:")
            print(f"STRIPE_PRICE_ID={price['id']}")
        
        return product, price

    def create_test_customer(self):
        """Create a test customer"""
        print("\n👤 Creating Test Customer:")
        print("=" * 50)
        
        customer_data = {
            "email": "test-litellm@example.com",
            "name": "LiteLLM Test Customer",
            "description": "Test customer for LiteLLM integration"
        }
        
        customer = self.make_request("customers", method="POST", data=customer_data)
        if customer:
            print(f"✅ Created Customer: {customer['id']}")
            print(f"Email: {customer['email']}")
            print(f"Name: {customer['name']}")
        
        return customer

    def run_exploration(self):
        """Run the complete exploration"""
        print("🔍 Stripe Sandbox Explorer")
        print("=" * 50)
        print(f"Using API Key: {self.api_key[:12]}...")
        
        try:
            self.explore_account()
            self.explore_products()
            self.explore_prices()
            self.explore_customers()
            self.explore_subscriptions()
            
            print("\n" + "=" * 50)
            create_test = input("Would you like to create test resources for LiteLLM? (y/n): ").strip().lower()
            
            if create_test == 'y':
                self.create_test_product_and_price()
                self.create_test_customer()
                
        except KeyboardInterrupt:
            print("\n\n👋 Exploration cancelled by user")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    # Check if API key is provided as command line argument
    api_key = None
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    
    try:
        explorer = StripeExplorer(api_key)
        explorer.run_exploration()
    except ValueError as e:
        print(f"❌ {e}")
        print("\nUsage:")
        print("1. Set STRIPE_API_KEY environment variable")
        print("2. Or run: python stripe_explorer.py sk_test_your_key_here")
        sys.exit(1)