from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import requests
import traceback
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from email.mime.text import MIMEText
import base64
import json


# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure CORS - Allow requests from frontend
CORS(app, 
     origins=[
         'http://localhost:3000',
         'http://localhost:5001', 
         'https://ceo-outreach-tool.onrender.com',
         'https://ceo-outreach-frontend.onrender.com'
     ],
     supports_credentials=False,
     allow_headers=['Content-Type'],
     methods=['GET', 'POST', 'OPTIONS']
)

# Configuration
SHOPIFY_API_KEY = os.environ.get('SHOPIFY_API_KEY')
SHOPIFY_PASSWORD = os.environ.get('SHOPIFY_PASSWORD')
SHOPIFY_STORE_URL = os.environ.get('SHOPIFY_STORE_URL')
GMAIL_CREDENTIALS = os.environ.get('GMAIL_CREDENTIALS')

GIFT_CARD_PRODUCT_ID = 7033261424832
GIFT_CARD_VARIANT_IDS = [
    41369759252672, 41369759285440, 41369759318208,
    42311665844416, 42311665877184, 42311665909952,
    46402146631872, 46402146664640, 43257806815424,
    42359567843520, 42359567810752, 42359683907776,
    43739294466240
]

import time
from functools import wraps

# Cache configuration
CACHE_TTL = 43200  # Cache for 12 hours (43200 seconds)
customer_cache = {
    'data': None,
    'timestamp': None
}
gift_card_customer_cache = {
    'customer_ids': None,
    'timestamp': None
}
winback_gap_cache = {
    "data": None,       # dict: {customer_id: gap_days}
    "timestamp": None
}
WINBACK_CACHE_TTL = 43200  # 12h


@app.route('/api/debug/ping', methods=['GET'])
def debug_ping():
    print("DEBUG PING HIT", flush=True)
    return jsonify({
        "ok": True,
        "has_gmail_creds": bool(os.environ.get("GMAIL_CREDENTIALS") or os.environ.get("GMAIL_CREDENTIALS_B64")),
    })

def get_cached_gift_card_customers():
    if gift_card_customer_cache['customer_ids'] and (time.time() - gift_card_customer_cache['timestamp'] < CACHE_TTL):
        return gift_card_customer_cache['customer_ids']
    return None

def cache_gift_card_customers(customer_ids):
    gift_card_customer_cache['customer_ids'] = customer_ids
    gift_card_customer_cache['timestamp'] = time.time()

def is_cache_valid():
    """Check if cache is still valid"""
    if customer_cache['data'] is None or customer_cache['timestamp'] is None:
        return False
    
    age = time.time() - customer_cache['timestamp']
    return age < CACHE_TTL

def get_cached_customers():
    """Get customers from cache if valid"""
    if is_cache_valid():
        print(f"Returning cached data (age: {int(time.time() - customer_cache['timestamp'])}s)")
        return customer_cache['data']
    return None

def cache_customers(data):
    """Store customers in cache"""
    customer_cache['data'] = data
    customer_cache['timestamp'] = time.time()
    print(f"Cached {len(data)} customers")


def get_winback_gaps():
    """
    Returns dict {customer_id: gap_days} where gap_days is the number of days
    between the customer's most recent order and the order before it.
    Only includes customers with >= 2 orders.
    """
    if winback_gap_cache["data"] and winback_gap_cache["timestamp"]:
        if time.time() - winback_gap_cache["timestamp"] < WINBACK_CACHE_TTL:
            return winback_gap_cache["data"]

    print("Computing winback gaps from Shopify orders...", flush=True)

    gaps = {}
    # We only need customer + created_at, so keep fields small
    endpoint = "orders.json?status=any&limit=250&fields=customer,created_at"
    url = endpoint

    # For each customer, track latest + second latest order dates
    latest = {}   # {customer_id: datetime}
    second = {}   # {customer_id: datetime}

    while url:
        response = shopify_request_with_retry(url)
        data = response.json()
        orders = data.get("orders", [])

        for order in orders:
            cust = order.get("customer")
            if not cust or not cust.get("id"):
                continue
            cid = cust["id"]

            created_at = order.get("created_at")
            if not created_at:
                continue
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                continue

            # Update top-2 most recent
            cur_latest = latest.get(cid)
            if cur_latest is None or dt > cur_latest:
                # shift latest -> second
                if cur_latest is not None:
                    second[cid] = cur_latest
                latest[cid] = dt
            else:
                cur_second = second.get(cid)
                if cur_second is None or dt > cur_second:
                    second[cid] = dt

        # pagination
        link_header = response.headers.get("Link", "")
        url = None
        if 'rel="next"' in link_header:
            import re
            match = re.search(r'<https://[^>]+/admin/api/[^>]+/orders\.json\?([^>]+)>; rel="next"', link_header)
            if match:
                url = f"orders.json?{match.group(1)}"
                time.sleep(0.5)

    # Build gaps
    for cid in latest:
        if cid in second:
            gap = (latest[cid] - second[cid]).days
            gaps[cid] = gap

    winback_gap_cache["data"] = gaps
    winback_gap_cache["timestamp"] = time.time()

    print(f"Winback gaps computed for {len(gaps)} customers", flush=True)
    return gaps

# Shopify API helpers
def get_shopify_headers():
    """Get headers for Shopify API requests"""
    return {
        'X-Shopify-Access-Token': SHOPIFY_PASSWORD,
        'Content-Type': 'application/json'
    }

def shopify_request_with_retry(endpoint, max_retries=5):
    """Make a request to Shopify API with retry logic for rate limits"""
    url = f"https://{SHOPIFY_STORE_URL}/admin/api/2024-01/{endpoint}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=get_shopify_headers())
            
            # Handle rate limiting (429 Too Many Requests)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2))
                sleep_time = min(retry_after, 2 ** attempt)  # Exponential backoff, max based on retry-after
                print(f"Rate limited (429). Sleeping for {sleep_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(sleep_time)
                continue
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            sleep_time = 2 ** attempt  # Exponential backoff
            print(f"Request failed: {e}. Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
    
    raise Exception("Max retries exceeded")

def shopify_request(endpoint):
    """Make a request to Shopify API (simple wrapper for backward compatibility)"""
    response = shopify_request_with_retry(endpoint)
    return response.json()

def get_customers_who_purchased_gift_card():
    """Fetch customer IDs who purchased gift cards using Orders API"""
    cached_ids = get_cached_gift_card_customers()
    if cached_ids:
        print(f"Using cached {len(cached_ids)} gift card customers")
        return cached_ids

    print("Fetching gift card purchasers from Shopify orders...")
    customer_ids = set()
    url = f"orders.json?limit=250&status=any&fields=customer,line_items"
    
    while url:
        response = shopify_request_with_retry(url)
        data = response.json()
        orders = data.get('orders', [])

        for order in orders:
            customer = order.get('customer')
            if not customer:
                continue
            customer_id = customer.get('id')
            for item in order.get('line_items', []):
                if item.get('product_id') == GIFT_CARD_PRODUCT_ID or item.get('variant_id') in GIFT_CARD_VARIANT_IDS:
                    customer_ids.add(customer_id)
                    break

        # Pagination
        link_header = response.headers.get('Link', '')
        url = None
        if 'rel="next"' in link_header:
            import re
            next_match = re.search(r'<https://[^>]+/admin/api/[^>]+/orders\.json\?([^>]+)>; rel="next"', link_header)
            if next_match:
                url = f"orders.json?{next_match.group(1)}"
                time.sleep(0.5)

    print(f"Found {len(customer_ids)} gift card customers")
    cache_gift_card_customers(customer_ids)
    return customer_ids


# Email templates
EMAIL_TEMPLATES = {
    'new_customer': {
        'name': 'New Customers',
        'subject': 'Thank You for Choosing SPATULA',
        'body': '''Hi {first_name},

I wanted to thank you personally for giving SPATULA a try. It means a lot to us to have you here.

We started SPATULA to make mealtime easier and a lot more delicious for busy people who still care about good food. If you have a moment, I would love to hear what made you choose us. Your feedback really helps us make SPATULA even better.

If there is ever anything we can do from our side to make your experience even better, please don't hesitate to let us know.

Thank you for welcoming us into your kitchen!'''
    },
    'winback_60': {
        'name': 'Winback Customers - 60 days',
        'subject': 'Welcome Back to SPATULA',
        'body': '''Hi {first_name},

I wanted to reach out and say thank you for your recent order. It is great to have you back with us!

At SPATULA, we are always working to make mealtime easier and more delicious, and it means a lot when customers return after some time away. If you have a moment, I would love to hear what brought you back. Your feedback really helps us make SPATULA even better.

If there is ever anything we can do from our side to make your experience even better, please don't hesitate to let us know.

Thanks again for having us back in your kitchen!'''
    },
    'gift_card': {
        'name': 'Gifting Customers - Gift Card',
        'subject': 'Thank You for Gifting SPATULA',
        'body': '''Hi {first_name},

I wanted to personally thank you for choosing to gift SPATULA. It truly means a lot to us that you thought of us for such a special gesture.

We started SPATULA to make mealtime easier—and a lot more delicious—for busy people who still care about good food. That's why we're always so touched when someone chooses to share it with someone else.

If you have a moment, I'd love to hear what inspired the gift—what was the occasion, and what made you choose us? Your story helps us understand what moments we're a part of and how we can make them even better.

As always, if there's anything we can do to improve your experience (or theirs), don't hesitate to reach out.'''
    }
}

@app.route('/api/customers', methods=['GET'])
def get_customers():
    """Fetch customers from Shopify with marketing-focused filters"""
    try:
        # Get filter parameters from query string
        search = request.args.get('search', '')
        min_orders = request.args.get('min_orders', None)
        max_orders = request.args.get('max_orders', None)
        min_spent = request.args.get('min_spent', None)
        max_spent = request.args.get('max_spent', None)
        days_since_order = request.args.get('days_since_order', None)
        purchased_gift_card = request.args.get('purchased_gift_card', 'false').lower() == 'true'
        sort_by = request.args.get('sort_by', 'last_order_date')
        sort_order = request.args.get('sort_order', 'desc')
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        winback = request.args.get('winback', 'false').lower() == 'true'
        winback_days = int(request.args.get('winback_days', 60))

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_data = get_cached_customers()
            if cached_data is not None:
                all_customers = cached_data
                print(f"Using {len(all_customers)} customers from cache")
            else:
                # Fetch from Shopify
                all_customers = fetch_all_customers_from_shopify()
                cache_customers(all_customers)
        else:
            print("Force refresh requested, bypassing cache")
            all_customers = fetch_all_customers_from_shopify()
            cache_customers(all_customers)
        
        # Now filter the customers
        customer_data = []
        current_date = datetime.now()
        
        for customer in all_customers:
            # Get customer data
            order_count = customer.get('orders_count', 0)
            total_spent = float(customer.get('total_spent', 0))
            email = customer.get('email', '')
            created_at = customer.get('created_at')
            last_order_date = customer.get('updated_at')
            customer_id = customer.get('id')
            
            # Skip if no email (can't do outreach)
            if not email:
                continue
            
            # Apply search filter
            if search:
                search_lower = search.lower()
                first_name = (customer.get('first_name') or '').lower()
                last_name = (customer.get('last_name') or '').lower()
                email_lower = (email or '').lower()
                
                if not (
                    (first_name.find(search_lower) >= 0) or
                    (last_name.find(search_lower) >= 0) or
                    (email_lower.find(search_lower) >= 0)
                ):
                    continue
            
            # Filter: Minimum orders
            if min_orders and order_count < int(min_orders):
                continue
            
            # Filter: Maximum orders
            if max_orders and order_count > int(max_orders):
                continue
            
            # Filter: Minimum spent
            if min_spent and total_spent < float(min_spent):
                continue
            
            # Filter: Maximum spent
            if max_spent and total_spent > float(max_spent):
                continue
            
            # Calculate days since last order
            days_since_last_order = None
            if last_order_date:
                try:
                    last_order_dt = datetime.fromisoformat(last_order_date.replace('Z', '+00:00'))
                    days_since_last_order = (current_date - last_order_dt.replace(tzinfo=None)).days
                except:
                    pass
            
            # Filter: Days since last order
            if days_since_order:
                if days_since_last_order is None or days_since_last_order < int(days_since_order):
                    continue
            
            # Filter: Gift card purchasers
            # NOTE: This is an expensive operation as it requires checking each customer's orders
            # Only run if the filter is explicitly enabled
            if purchased_gift_card:
                gift_card_customer_ids = get_customers_who_purchased_gift_card()
                if customer_id not in gift_card_customer_ids:
                    continue
            if winback:
                gaps = get_winback_gaps()
                gap_days = gaps.get(customer_id)  # None if <2 orders
                if gap_days is None or gap_days < winback_days:
                    continue
            
            customer_info = {
                'id': customer.get('id'),
                'email': email,
                'first_name': customer.get('first_name', ''),
                'last_name': customer.get('last_name', ''),
                'order_count': order_count,
                'last_order_date': last_order_date,
                'customer_since': created_at,
                'total_spent': total_spent,
                'days_since_last_order': days_since_last_order
            }
            customer_data.append(customer_info)
        
        # Sort results
        if sort_by == 'order_count':
            customer_data.sort(key=lambda x: x['order_count'], reverse=(sort_order == 'desc'))
        elif sort_by == 'total_spent':
            customer_data.sort(key=lambda x: x['total_spent'], reverse=(sort_order == 'desc'))
        elif sort_by == 'last_order_date':
            customer_data.sort(
                key=lambda x: x['last_order_date'] if x['last_order_date'] else '', 
                reverse=(sort_order == 'desc')
            )
        elif sort_by == 'customer_since':
            customer_data.sort(
                key=lambda x: x['customer_since'] if x['customer_since'] else '', 
                reverse=(sort_order == 'desc')
            )
        elif sort_by == 'name':
            customer_data.sort(
                key=lambda x: ((x.get('first_name') or '') + (x.get('last_name') or '')).lower(),
                reverse=(sort_order == 'desc')
            )
        
        print(f"Returning {len(customer_data)} customers after filters")
        
        # Calculate cache info
        cache_age = None
        if customer_cache['timestamp']:
            cache_age = int(time.time() - customer_cache['timestamp'])
        
        return jsonify({
            'customers': customer_data, 
            'success': True,
            'count': len(customer_data),
            'total_customers': len(all_customers),
            'cache_age': cache_age,
            'cache_ttl': CACHE_TTL,
            'from_cache': not force_refresh and cached_data is not None,
            'filters_applied': {
                'search': search,
                'min_orders': min_orders,
                'max_orders': max_orders,
                'min_spent': min_spent,
                'max_spent': max_spent,
                'days_since_order': days_since_order,
                'purchased_gift_card': purchased_gift_card
            }
        })
    
    except Exception as e:
        print(f"Error fetching customers: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def fetch_all_customers_from_shopify():
    """Fetch all customers from Shopify with pagination - ONLY customers with at least 1 order"""
    all_customers = []
    url = 'customers.json?limit=250'
    page_count = 0
    
    print(f"Starting to fetch customers from Shopify (only those with orders)...")
    
    while url:
        page_count += 1
        print(f"Fetching page {page_count}...")
        
        # Use retry logic for rate limiting
        response = shopify_request_with_retry(url)
        
        data = response.json()
        customers = data.get('customers', [])
        
        # Only add customers with at least 1 order to save resources
        customers_with_orders = [c for c in customers if c.get('orders_count', 0) > 0]
        all_customers.extend(customers_with_orders)
        
        print(f"Page {page_count}: Found {len(customers)} customers, {len(customers_with_orders)} with orders. Total so far: {len(all_customers)}")
        
        # Check for next page in Link header
        link_header = response.headers.get('Link', '')
        url = None
        
        if 'rel="next"' in link_header:
            # Extract next page URL from Link header
            import re
            next_match = re.search(r'<https://[^>]+/admin/api/[^>]+/customers\.json\?([^>]+)>; rel="next"', link_header)
            if next_match:
                url = f'customers.json?{next_match.group(1)}'
                # Add small delay between pages to be respectful to API
                time.sleep(0.5)
    
    print(f"Finished fetching. Total customers with orders: {len(all_customers)}")
    return all_customers

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get all available email templates"""
    templates = [
        {'id': key, 'name': value['name'], 'subject': value['subject']}
        for key, value in EMAIL_TEMPLATES.items()
    ]
    return jsonify({'templates': templates, 'success': True})

@app.route('/api/preview-template', methods=['POST'])
def preview_template():
    """Preview email template with customer data"""
    data = request.json
    template_id = data.get('template_id')
    customer = data.get('customer')
    
    if template_id not in EMAIL_TEMPLATES:
        return jsonify({'error': 'Template not found', 'success': False}), 404
    
    template = EMAIL_TEMPLATES[template_id]
    
    # Format customer since date
    customer_since = 'N/A'
    if customer.get('customer_since'):
        try:
            date_obj = datetime.fromisoformat(customer['customer_since'].replace('Z', '+00:00'))
            customer_since = date_obj.strftime('%B %Y')
        except:
            pass
    
    # Replace variables
    subject = template['subject'].format(
        first_name=customer.get('first_name', 'Valued Customer')
    )
    body = template['body'].format(
        first_name=customer.get('first_name', 'Valued Customer'),
        customer_since=customer_since
    )
    
    return jsonify({
        'subject': subject,
        'body': body,
        'success': True
    })


@app.route('/api/create-drafts', methods=['POST'])
def create_drafts():
    """
    Create Gmail drafts for selected customers.

    Expects JSON payload:
    {
      "template_id": "new_customer" | "winback_60" | ...,
      "customers": [{ "email": "...", "first_name": "...", "customer_since": "..." }, ...],
      "boss_email": "hello@spatulafoods.com"   # informational/required by your UI
    }
    """
    print("CREATE-DRAFTS HIT", flush=True)

    # ---- Parse JSON safely (avoid None issues) ----
    data = request.get_json(silent=True) or {}
    print("payload keys:", list(data.keys()), flush=True)

    template_id = data.get('template_id')
    customers = data.get('customers') or []
    boss_email = data.get('boss_email')

    if not boss_email:
        return jsonify({'success': False, 'error': 'Sender email is required'}), 400

    if not template_id or template_id not in EMAIL_TEMPLATES:
        return jsonify({'success': False, 'error': 'Template not found'}), 404

    if not isinstance(customers, list) or len(customers) == 0:
        return jsonify({'success': False, 'error': 'No customers provided'}), 400

    # ---- Load credentials (prefer base64 on Render) ----
    try:
        creds_json = os.environ.get("GMAIL_CREDENTIALS")

        if not creds_json:
            b64 = os.environ.get("GMAIL_CREDENTIALS_B64")
            if b64:
                creds_json = base64.b64decode(b64).decode("utf-8")

        if not creds_json:
            return jsonify({
                'success': False,
                'error': 'Gmail authentication required (missing credentials env var).',
                'auth_required': True
            }), 401

        creds_data = json.loads(creds_json)
        creds = Credentials.from_authorized_user_info(creds_data)

    except Exception as e:
        print("CREDENTIAL LOAD ERROR:", str(e), flush=True)
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Invalid Gmail credentials config: {str(e)}',
            'auth_required': True
        }), 500

    # ---- Refresh if expired ----
    try:
        if creds and getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
            creds.refresh(Request())
            print("Refreshed Gmail token OK", flush=True)
    except Exception as e:
        print("TOKEN REFRESH ERROR:", str(e), flush=True)
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Failed to refresh Gmail token: {str(e)}',
            'auth_required': True
        }), 401

    # ---- Validate creds ----
    if not creds or not creds.valid:
        return jsonify({
            'success': False,
            'error': 'Gmail authentication required.',
            'auth_required': True,
            'debug': {
                'expired': getattr(creds, 'expired', None),
                'has_refresh_token': bool(getattr(creds, 'refresh_token', None)),
                'token_uri': getattr(creds, 'token_uri', None),
                'scopes': getattr(creds, 'scopes', None),
            }
        }), 401

    # ---- Build Gmail service ----
    try:
        service = build('gmail', 'v1', credentials=creds)
    except Exception as e:
        print("GMAIL SERVICE BUILD ERROR:", str(e), flush=True)
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

    template = EMAIL_TEMPLATES[template_id]
    created_drafts = []
    errors = []

    # ---- Create drafts ----
    for customer in customers:
        try:
            to_email = (customer or {}).get("email")
            if not to_email:
                errors.append({'customer': None, 'error': 'Missing customer email'})
                continue

            # Format customer_since if present
            customer_since_str = 'N/A'
            cs = (customer or {}).get('customer_since')
            if cs:
                try:
                    date_obj = datetime.fromisoformat(cs.replace('Z', '+00:00'))
                    customer_since_str = date_obj.strftime('%B %Y')
                except Exception:
                    customer_since_str = 'N/A'

            first_name = (customer or {}).get('first_name') or 'Valued Customer'

            subject = template['subject'].format(first_name=first_name)
            body = template['body'].format(first_name=first_name, customer_since=customer_since_str)

            message = MIMEText(body)
            message['to'] = to_email
            message['subject'] = subject

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            draft = service.users().drafts().create(
                userId='me',
                body={'message': {'raw': raw_message}}
            ).execute()

            created_drafts.append({'customer': to_email, 'draft_id': draft.get('id')})

        except HttpError as he:
            # Gmail API-specific error
            errors.append({'customer': (customer or {}).get("email"), 'error': str(he)})
        except Exception as e:
            errors.append({'customer': (customer or {}).get("email"), 'error': str(e)})

    return jsonify({
        'success': True,
        'created': len(created_drafts),
        'drafts': created_drafts,
        'errors': errors
    }), 200


@app.route('/api/auth/gmail', methods=['GET'])
def gmail_auth():
    """Initiate Gmail OAuth flow"""
    # This would redirect to Google's OAuth page
    # Implementation depends on your OAuth setup
    return jsonify({
        'message': 'Please configure Gmail OAuth',
        'success': False
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'success': True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
