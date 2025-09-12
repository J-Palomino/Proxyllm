#!/usr/bin/env python3
"""
Create simple usage-based Stripe pricing for LiteLLM
Using standard subscription items approach instead of new meters
"""

import json
import urllib.request
import urllib.parse
import base64
import sys
import os


def make_stripe_request(api_key, endpoint, method="GET", data=None):
    """Make a request to Stripe API"""
    url = f"https://api.stripe.com/v1/{endpoint}"
    
    auth_string = f"{api_key}:"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_base64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    try:
        if method == "GET" and data:
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
            print(f"Error: {error_json.get('error', {}).get('message', 'Unknown')}")
        except:
            print(f"Raw error: {error_data}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def get_stripe_key():
    """Get Stripe API key from .env file"""
    env_file = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('STRIPE_SECRET='):
                        key = line.split('=', 1)[1].strip('"\'')
                        return key
        except Exception as e:
            print(f"Could not read .env file: {e}")
    return None


def create_usage_based_product_and_price(api_key):
    """Create a simple usage-based product and price"""
    print("Creating Usage-Based LiteLLM Product")
    print("=" * 40)
    
    # 1. Create product
    print("1. Creating product...")
    product_data = {
        "name": "LiteLLM Token Usage",
        "description": "Pay-as-you-go token usage for LiteLLM API",
        "type": "service"
    }
    
    product = make_stripe_request(api_key, "products", method="POST", data=product_data)
    if not product:
        return None, None
    
    print(f"SUCCESS: Product created - {product['id']}")
    
    # 2. Create usage-based price (old-style that still works)
    print("2. Creating usage-based price...")
    
    # Try creating a simple per-unit price without the new meter requirement
    price_data = {
        "product": product['id'],
        "unit_amount": 1,  # $0.01 per unit
        "currency": "usd", 
        "billing_scheme": "per_unit"
    }
    
    price = make_stripe_request(api_key, "prices", method="POST", data=price_data)
    
    if price:
        print(f"SUCCESS: Price created - {price['id']}")
        print(f"Unit amount: $0.01 per token")
        return product, price
    else:
        print("FAILED: Could not create usage price")
        return product, None


def create_test_customer_and_usage(api_key, price_id):
    """Create a test customer and demonstrate usage recording"""
    print(f"\n3. Creating test customer...")
    
    customer_data = {
        "email": "litellm-test@example.com",
        "name": "LiteLLM Test Customer",
        "description": "Test customer for LiteLLM token billing"
    }
    
    customer = make_stripe_request(api_key, "customers", method="POST", data=customer_data)
    if not customer:
        print("FAILED: Could not create customer")
        return None
    
    print(f"SUCCESS: Customer created - {customer['id']}")
    
    # Create a subscription with the usage-based price
    print(f"4. Creating subscription with usage-based pricing...")
    
    subscription_data = {
        "customer": customer['id'],
        "items[0][price]": price_id,
        "billing_cycle_anchor": "now"
    }
    
    subscription = make_stripe_request(api_key, "subscriptions", method="POST", data=subscription_data)
    
    if subscription:
        print(f"SUCCESS: Subscription created - {subscription['id']}")
        
        # Get the subscription item ID for usage records
        items = subscription.get('items', {}).get('data', [])
        if items:
            subscription_item_id = items[0]['id']
            print(f"Subscription Item ID: {subscription_item_id}")
            
            # This is what LiteLLM will use for creating usage records
            print(f"\nFor LiteLLM integration, you'll use:")
            print(f"STRIPE_SUBSCRIPTION_ITEM_ID={subscription_item_id}")
            
            return customer, subscription, subscription_item_id
    
    print("FAILED: Could not create subscription")
    return customer, None, None


def show_usage_record_example(api_key, subscription_item_id):
    """Show how to create usage records"""
    print(f"\n" + "="*50)
    print("USAGE RECORD EXAMPLE")
    print("="*50)
    
    print(f"To record 100 tokens used:")
    print(f"POST to: https://api.stripe.com/v1/subscription_items/{subscription_item_id}/usage_records")
    print(f"Data: {{")
    print(f"  'quantity': 100,")
    print(f"  'timestamp': <unix_timestamp>,")
    print(f"  'action': 'increment'")
    print(f"}}")
    
    # Create a test usage record
    print(f"\n5. Creating test usage record (100 tokens)...")
    
    usage_data = {
        "quantity": 100,
        "action": "increment"
    }
    
    usage_record = make_stripe_request(
        api_key, 
        f"subscription_items/{subscription_item_id}/usage_records", 
        method="POST", 
        data=usage_data
    )
    
    if usage_record:
        print(f"SUCCESS: Usage record created - {usage_record['id']}")
        print(f"Quantity: {usage_record.get('quantity')} tokens")
    else:
        print("FAILED: Could not create usage record")


def show_litellm_configuration(api_key, product, price, customer, subscription_item_id):
    """Show how to configure LiteLLM"""
    print(f"\n" + "="*60)
    print("LITELLM CONFIGURATION")
    print("="*60)
    
    print(f"\nCreated Resources:")
    print(f"  Product: {product['id']} - {product['name']}")
    print(f"  Price: {price['id']} - $0.01 per token")
    print(f"  Test Customer: {customer['id']} - {customer['email']}")
    print(f"  Subscription Item: {subscription_item_id}")
    
    print(f"\nEnvironment Variables for LiteLLM:")
    print(f"STRIPE_API_KEY={api_key}")
    print(f"STRIPE_PRICE_ID={price['id']}")
    print(f"STRIPE_SUBSCRIPTION_ITEM_ID={subscription_item_id}")
    print(f"STRIPE_CHARGE_BY=end_user_id")
    
    print(f"\nConfig.yaml:")
    print(f"litellm_settings:")
    print(f"  success_callback: ['stripe']")
    
    print(f"\nTest command:")
    print(f"python -c \"")
    print(f"import litellm")
    print(f"litellm.success_callback = ['stripe']")
    print(f"response = litellm.completion(")
    print(f"    model='gpt-3.5-turbo',")
    print(f"    messages=[{{'role': 'user', 'content': 'Hello!'}}],")
    print(f"    user='{customer['id']}'")
    print(f")")
    print(f"\"")


def main():
    """Main function"""
    print("LiteLLM Simple Usage-Based Stripe Setup")
    print("=" * 45)
    
    api_key = get_stripe_key()
    if not api_key:
        print("ERROR: No STRIPE_SECRET found in .env file")
        return
    
    print(f"Using API key: {api_key[:15]}...")
    
    # Create product and price
    product, price = create_usage_based_product_and_price(api_key)
    if not product or not price:
        print("Failed to create basic resources")
        return
    
    # Create test customer and subscription
    result = create_test_customer_and_usage(api_key, price['id'])
    if not result or len(result) != 3:
        print("Failed to create customer/subscription")
        return
    
    customer, subscription, subscription_item_id = result
    if not subscription_item_id:
        print("Failed to get subscription item ID")
        return
    
    # Show usage record example
    show_usage_record_example(api_key, subscription_item_id)
    
    # Show configuration
    show_litellm_configuration(api_key, product, price, customer, subscription_item_id)
    
    print(f"\nSetup complete! Check your Stripe dashboard.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nERROR: Unexpected error: {e}")