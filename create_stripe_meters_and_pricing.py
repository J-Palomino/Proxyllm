#!/usr/bin/env python3
"""
Create Stripe meters and metered billing for LiteLLM integration
Updated for Stripe's new meter-based billing system (2025 API)
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
    
    # Use latest API version that supports meters
    auth_string = f"{api_key}:"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_base64}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Stripe-Version': '2024-11-20.basil'  # Use a version that supports meters
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
            print(f"Error details: {error_json.get('error', {}).get('message', 'Unknown error')}")
        except:
            print(f"Raw error: {error_data}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def get_stripe_key():
    """Get Stripe API key from various sources"""
    # Check .env file first
    env_file = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('STRIPE_SECRET='):
                        key = line.split('=', 1)[1].strip('"\'')
                        print(f"Using API key from .env file (STRIPE_SECRET)")
                        return key
        except Exception as e:
            print(f"Could not read .env file: {e}")
    
    # Check environment variables
    for env_var in ['STRIPE_SECRET', 'STRIPE_API_KEY']:
        api_key = os.getenv(env_var)
        if api_key:
            print(f"Using API key from {env_var}")
            return api_key
    
    # Check command line
    if len(sys.argv) > 1:
        return sys.argv[1]
    
    return None


def create_meter(api_key, meter_name, display_name, event_name):
    """Create a meter for tracking usage"""
    print(f"Creating meter: {meter_name}...")
    
    meter_data = {
        "display_name": display_name,
        "event_name": event_name,
        "customer_mapping[event_payload_key]": "customer_id",
        "default_aggregation[formula]": "sum"
    }
    
    meter = make_stripe_request(api_key, "billing/meters", method="POST", data=meter_data)
    
    if meter:
        print(f"SUCCESS: Created meter {meter['id']}")
        print(f"  Display Name: {meter.get('display_name')}")
        print(f"  Event Name: {meter.get('event_name')}")
        return meter
    else:
        print(f"FAILED: Could not create meter {meter_name}")
        return None


def create_litellm_resources_with_meters(api_key):
    """Create LiteLLM resources using the new meter-based system"""
    print("Creating LiteLLM Meter-Based Billing Resources")
    print("=" * 50)
    
    # 1. Create meter for token usage
    meter = create_meter(
        api_key, 
        "litellm_tokens", 
        "LiteLLM Token Usage",
        "litellm_token_usage"
    )
    
    if not meter:
        print("Cannot proceed without meter")
        return None, None, []
    
    # 2. Create a product for LiteLLM API usage
    print(f"\nCreating LiteLLM API Usage product...")
    product_data = {
        "name": "LiteLLM API Usage",
        "description": "Token-based usage billing for LiteLLM API calls",
        "type": "service"
    }
    
    product = make_stripe_request(api_key, "products", method="POST", data=product_data)
    if not product:
        print("FAILED: Could not create product")
        return meter, None, []
    
    print(f"SUCCESS: Created product {product['id']}")
    
    # 3. Create metered prices using the meter
    prices_to_create = [
        {
            "name": "Per Token ($0.01)",
            "unit_amount": 100,  # $1.00 per 100 tokens = $0.01 per token
            "description": "$0.01 per token used"
        },
        {
            "name": "Per Token ($0.001)", 
            "unit_amount": 100,  # Will set transform_quantity to divide by 100
            "description": "$0.001 per token used"
        }
    ]
    
    created_prices = []
    
    for i, price_config in enumerate(prices_to_create, 1):
        print(f"\nCreating metered price: {price_config['name']}...")
        
        price_data = {
            "product": product['id'],
            "currency": "usd",
            "recurring[interval]": "month",
            "recurring[meter]": meter['id'],
            "recurring[usage_type]": "metered",
            "billing_scheme": "per_unit",
            "nickname": price_config['name'],
            "unit_amount": price_config['unit_amount']
        }
        
        # For the second price, add a transform to make it cheaper
        if i == 2:
            price_data["transform_quantity[divide_by]"] = "100"
            price_data["transform_quantity[round]"] = "up"
        
        price = make_stripe_request(api_key, "prices", method="POST", data=price_data)
        if price:
            print(f"SUCCESS: Created price {price['id']}")
            print(f"  Nickname: {price_config['name']}")
            print(f"  Unit Amount: ${price_config['unit_amount']/100:.2f}")
            created_prices.append(price)
        else:
            print(f"FAILED: Could not create price {price_config['name']}")
    
    return meter, product, created_prices


def show_meter_configuration(api_key, meter, product, prices):
    """Show how to configure the meter-based billing"""
    if not meter or not prices:
        print("ERROR: Missing meter or prices")
        return
    
    print(f"\n{'='*60}")
    print("LITELLM STRIPE METER-BASED BILLING CONFIGURATION")
    print(f"{'='*60}")
    
    print(f"\nCreated Resources:")
    print(f"  Meter ID: {meter['id']}")
    print(f"  Meter Event Name: {meter['event_name']}")
    print(f"  Product ID: {product['id']}")
    
    print(f"\nAvailable Price IDs:")
    for price in prices:
        nickname = price.get('nickname', 'Unnamed')
        print(f"  {price['id']} - {nickname}")
    
    print(f"\n" + "="*40)
    print("CONFIGURATION FOR LITELLM")
    print("="*40)
    
    print(f"\n1. ENVIRONMENT VARIABLES:")
    print(f"   STRIPE_API_KEY={api_key}")
    print(f"   STRIPE_PRICE_ID={prices[0]['id']}")
    print(f"   STRIPE_METER_ID={meter['id']}")
    print(f"   STRIPE_METER_EVENT_NAME={meter['event_name']}")
    print(f"   STRIPE_CHARGE_BY=end_user_id")
    
    print(f"\n2. LITELLM CONFIG:")
    print(f"   litellm_settings:")
    print(f"     success_callback: ['stripe']")
    
    print(f"\n" + "="*40)
    print("IMPORTANT: METER EVENT REPORTING")
    print("="*40)
    print(f"The Stripe integration will need to report meter events.")
    print(f"Event name: {meter['event_name']}")
    print(f"This requires sending usage data to Stripe's meter endpoint.")
    
    print(f"\nExample meter event payload:")
    print(f'{{')
    print(f'  "event_name": "{meter["event_name"]}",')
    print(f'  "payload": {{')
    print(f'    "customer_id": "cus_customer123",')
    print(f'    "value": 150')
    print(f'  }},')
    print(f'  "timestamp": "2024-01-01T00:00:00Z"')
    print(f'}}')


def main():
    """Main function"""
    print("LiteLLM Stripe Meter-Based Billing Setup")
    print("Updated for Stripe's 2025 meter system")
    print("=" * 50)
    
    api_key = get_stripe_key()
    
    if not api_key:
        print("ERROR: No Stripe API key found!")
        return
    
    if not api_key.startswith('sk_test_'):
        print("WARNING: Not using a test key!")
    
    print(f"Using API key: {api_key[:15]}...")
    
    # Create resources
    meter, product, prices = create_litellm_resources_with_meters(api_key)
    
    if meter and product and prices:
        show_meter_configuration(api_key, meter, product, prices)
    else:
        print("\nSetup incomplete - some resources failed to create")
    
    print(f"\nSetup complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nERROR: Unexpected error: {e}")