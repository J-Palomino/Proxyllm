#!/usr/bin/env python3
"""
Create metered billing resources for LiteLLM integration
Can be used with environment variables or passed API key
Similar to Slack/Lago setup patterns
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
    
    # Prepare headers
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
            print(f"Error details: {error_json.get('error', {}).get('message', 'Unknown error')}")
        except:
            print(f"Raw error: {error_data}")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def get_stripe_key():
    """Get Stripe API key from various sources (like Slack/Lago setup)"""
    # 1. Check command line argument
    if len(sys.argv) > 1:
        return sys.argv[1]
    
    # 2. Check environment variables (multiple possible names)
    possible_env_vars = [
        'STRIPE_API_KEY',
        'STRIPE_SECRET_KEY', 
        'STRIPE_SECRET',
        'STRIPE_SK'
    ]
    
    for env_var in possible_env_vars:
        api_key = os.getenv(env_var)
        if api_key:
            print(f"Using API key from {env_var}")
            return api_key
    
    # 3. Check .env file if present
    env_file = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        for env_var in possible_env_vars:
                            if line.startswith(f"{env_var}="):
                                key = line.split('=', 1)[1].strip('"\'')
                                print(f"Using API key from .env file ({env_var})")
                                return key
        except Exception as e:
            print(f"Could not read .env file: {e}")
    
    return None


def create_litellm_metered_resources(api_key):
    """Create LiteLLM metered billing resources"""
    print("Creating LiteLLM Metered Billing Resources")
    print("=" * 50)
    
    # Validate API key format
    if not api_key.startswith(('sk_test_', 'sk_live_')):
        print("WARNING: API key doesn't look like a valid Stripe secret key")
        return None, []
    
    if api_key.startswith('sk_live_'):
        print("WARNING: This appears to be a LIVE key - please use test keys for development!")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            return None, []
    
    # 1. Create a product for LiteLLM API usage
    print("1. Creating LiteLLM API Usage product...")
    product_data = {
        "name": "LiteLLM API Usage",
        "description": "Token-based usage billing for LiteLLM API calls",
        "type": "service"
    }
    
    product = make_stripe_request(api_key, "products", method="POST", data=product_data)
    if not product:
        print("FAILED: Could not create product")
        return None, []
    
    print(f"SUCCESS: Created product {product['id']}")
    
    # 2. Create different metered pricing tiers
    prices_to_create = [
        {
            "name": "Per Token (Basic)",
            "unit_amount": 1,  # $0.01 per token
            "description": "$0.01 per token used"
        },
        {
            "name": "Per 100 Tokens", 
            "unit_amount": 10,  # $0.10 per 100 tokens
            "description": "$0.001 per token ($0.10 per 100 tokens)"
        },
        {
            "name": "Per 1000 Tokens",
            "unit_amount": 100,  # $1.00 per 1000 tokens
            "description": "$0.001 per token ($1.00 per 1000 tokens)"
        }
    ]
    
    created_prices = []
    
    for i, price_config in enumerate(prices_to_create, 1):
        print(f"\n2.{i} Creating metered price: {price_config['name']}...")
        
        price_data = {
            "product": product['id'],
            "unit_amount": price_config['unit_amount'],
            "currency": "usd",
            "recurring[interval]": "month",
            "recurring[usage_type]": "metered",
            "billing_scheme": "per_unit",
            "nickname": price_config['name']
        }
        
        price = make_stripe_request(api_key, "prices", method="POST", data=price_data)
        if price:
            print(f"SUCCESS: Created price {price['id']}")
            print(f"  Amount: ${price_config['unit_amount']/100:.3f} USD per unit")
            print(f"  Description: {price_config['description']}")
            created_prices.append(price)
        else:
            print(f"FAILED: Could not create price {price_config['name']}")
    
    return product, created_prices


def show_configuration_options(api_key, product, prices):
    """Show configuration options for different setups"""
    if not prices:
        print("ERROR: No prices were created successfully")
        return
    
    print(f"\n{'='*60}")
    print("LITELLM STRIPE INTEGRATION CONFIGURATION")
    print(f"{'='*60}")
    
    print(f"\nCreated Resources:")
    print(f"  Product ID: {product['id']}")
    print(f"  Product Name: {product['name']}")
    
    print(f"\nAvailable Price IDs:")
    for price in prices:
        nickname = price.get('nickname', 'Unnamed')
        amount = price.get('unit_amount', 0) / 100
        print(f"  {price['id']} - {nickname} (${amount:.3f} per unit)")
    
    print(f"\n" + "="*30)
    print("CONFIGURATION OPTIONS")
    print("="*30)
    
    # Option 1: Environment Variables
    print(f"\n1. ENVIRONMENT VARIABLES (.env file):")
    print(f"   STRIPE_API_KEY={api_key}")
    print(f"   STRIPE_PRICE_ID={prices[0]['id']}")
    print(f"   STRIPE_CHARGE_BY=end_user_id")
    
    # Option 2: LiteLLM Config YAML
    print(f"\n2. LITELLM CONFIG.YAML:")
    print(f"   litellm_settings:")
    print(f"     success_callback: ['stripe']")
    
    # Option 3: UI Configuration (like Slack/Lago)
    print(f"\n3. UI CONFIGURATION (Admin Dashboard):")
    print(f"   Go to Settings > Logging & Observability")
    print(f"   Add Stripe Integration:")
    print(f"     - STRIPE_API_KEY: {api_key}")
    print(f"     - STRIPE_PRICE_ID: {prices[0]['id']}")
    print(f"     - STRIPE_CHARGE_BY: end_user_id (or user_id/team_id)")
    
    # Option 4: Python Code
    print(f"\n4. PYTHON CODE:")
    print(f"   import litellm")
    print(f"   litellm.success_callback = ['stripe']")
    print(f"   # Make sure environment variables are set")
    
    print(f"\n" + "="*30)
    print("NEXT STEPS")
    print("="*30)
    print(f"1. Choose one of the configuration methods above")
    print(f"2. Create customers and subscriptions in Stripe using the price IDs")
    print(f"3. Test with LiteLLM completion calls")
    print(f"4. Monitor usage records in your Stripe dashboard")
    
    print(f"\nTesting command:")
    print(f"python -c \"")
    print(f"import litellm")
    print(f"litellm.success_callback = ['stripe']") 
    print(f"response = litellm.completion(")
    print(f"    model='gpt-3.5-turbo',")
    print(f"    messages=[{{'role': 'user', 'content': 'Hello!'}}],")
    print(f"    user='test-customer-123'")
    print(f")")
    print(f"print(response)")
    print(f"\"")


def main():
    """Main function"""
    print("LiteLLM Stripe Metered Billing Setup")
    print("Similar to Slack/Lago integration setup")
    print("=" * 50)
    
    # Get API key from various sources
    api_key = get_stripe_key()
    
    if not api_key:
        print("ERROR: No Stripe API key found!")
        print("\nProvide API key via:")
        print("1. Command line: python script.py sk_test_...")
        print("2. Environment variable: STRIPE_API_KEY=sk_test_...")  
        print("3. .env file: STRIPE_API_KEY=sk_test_...")
        return
    
    print(f"Using API key: {api_key[:15]}...")
    
    # Create metered billing resources
    product, prices = create_litellm_metered_resources(api_key)
    
    if product and prices:
        show_configuration_options(api_key, product, prices)
    
    print(f"\nSetup complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nERROR: Unexpected error: {e}")