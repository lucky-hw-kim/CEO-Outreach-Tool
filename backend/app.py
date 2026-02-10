from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
import base64
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure CORS - Allow requests from frontend
CORS(
    app,
    resources={r"/api/*": {"origins": [
        "http://localhost:3000",
        "https://ceo-outreach-tool.onrender.com",
        "https://ceo-outreach-frontend.onrender.com"
    ]}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = app.make_response("")
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response


# Configuration
SHOPIFY_API_KEY = os.environ.get('SHOPIFY_API_KEY')
SHOPIFY_PASSWORD = os.environ.get('SHOPIFY_PASSWORD')
SHOPIFY_STORE_URL = os.environ.get('SHOPIFY_STORE_URL')
GMAIL_CREDENTIALS = os.environ.get('GMAIL_CREDENTIALS')

import time
from functools import wraps

# Cache configuration
CACHE_TTL = 43200  # Cache for 12 hours (43200 seconds)
customer_cache = {
    'data': None,
    'timestamp': None
}

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

# Email templates
EMAIL_TEMPLATES = {
    'comeback': {
        'name': 'Come Back to Us',
        'subject': 'We Miss You, {first_name}!',
        'body': '''Hi {first_name},

We noticed it's been a while since your last order with us. We'd love to have you back!

As a valued customer, we wanted to reach out personally and let you know we're here if you need anything.

Best regards,
[Your Company]'''
    },
    'thankyou': {
        'name': 'Thank You',
        'subject': 'Thank You for Being With Us, {first_name}!',
        'body': '''Hi {first_name},

We wanted to take a moment to thank you for being a loyal customer since {customer_since}.

Your support means everything to us, and we're grateful to have you as part of our community.

Best regards,
[Your Company]'''
    },
    'special_offer': {
        'name': 'Special Offer',
        'subject': 'Exclusive Offer Just for You, {first_name}!',
        'body': '''Hi {first_name},

As one of our valued customers, we wanted to share an exclusive offer with you.

[Include your special offer details here]

This is our way of saying thank you for your continued support.

Best regards,
[Your Company]'''
    },
    'feedback': {
        'name': 'Request Feedback',
        'subject': 'We\'d Love Your Feedback, {first_name}',
        'body': '''Hi {first_name},

Your opinion matters to us! We'd love to hear about your experience with our products.

Could you take a moment to share your thoughts? Your feedback helps us serve you better.

Best regards,
[Your Company]'''
    }
}

@app.route('/api/customers', methods=['GET'])
def get_customers():
    cached_data = None
    """Fetch customers from Shopify with marketing-focused filters"""
    try:
        # Get filter parameters from query string
        search = request.args.get('search', '')
        min_orders = request.args.get('min_orders', None)
        max_orders = request.args.get('max_orders', None)
        min_spent = request.args.get('min_spent', None)
        max_spent = request.args.get('max_spent', None)
        days_since_order = request.args.get('days_since_order', None)
        sort_by = request.args.get('sort_by', 'last_order_date')
        sort_order = request.args.get('sort_order', 'desc')
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        
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
                'days_since_order': days_since_order
            }
        })
    
    except Exception as e:
        print(f"Error fetching customers: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def fetch_all_customers_from_shopify():
    """Fetch all customers from Shopify with pagination"""
    all_customers = []
    url = 'customers.json?limit=250'
    page_count = 0
    
    print(f"Starting to fetch customers from Shopify...")
    
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
    """Create Gmail drafts for selected customers"""
    data = request.json
    template_id = data.get('template_id')
    customers = data.get('customers', [])
    boss_email = data.get('boss_email')
    
    if not boss_email:
        return jsonify({'error': 'Boss email is required', 'success': False}), 400
    
    if template_id not in EMAIL_TEMPLATES:
        return jsonify({'error': 'Template not found', 'success': False}), 404
    
    try:
        # Load Gmail credentials
        creds = None
        if GMAIL_CREDENTIALS:
            creds_data = json.loads(GMAIL_CREDENTIALS)
            creds = Credentials.from_authorized_user_info(creds_data)
        
        if not creds or not creds.valid:
            return jsonify({
                'error': 'Gmail authentication required. Please authenticate first.',
                'success': False,
                'auth_required': True
            }), 401
        
        service = build('gmail', 'v1', credentials=creds)
        template = EMAIL_TEMPLATES[template_id]
        
        created_drafts = []
        errors = []
        
        for customer in customers:
            try:
                # Format customer since date
                customer_since = 'N/A'
                if customer.get('customer_since'):
                    try:
                        date_obj = datetime.fromisoformat(customer['customer_since'].replace('Z', '+00:00'))
                        customer_since = date_obj.strftime('%B %Y')
                    except:
                        pass
                
                # Create personalized email
                subject = template['subject'].format(
                    first_name=customer.get('first_name', 'Valued Customer')
                )
                body = template['body'].format(
                    first_name=customer.get('first_name', 'Valued Customer'),
                    customer_since=customer_since
                )
                
                # Create MIME message
                message = MIMEText(body)
                message['to'] = customer.get('email')
                message['subject'] = subject
                
                # Encode message
                raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
                
                # Create draft
                draft = service.users().drafts().create(
                    userId='me',
                    body={'message': {'raw': raw_message}}
                ).execute()
                
                created_drafts.append({
                    'customer': customer.get('email'),
                    'draft_id': draft['id']
                })
                
            except HttpError as error:
                errors.append({
                    'customer': customer.get('email'),
                    'error': str(error)
                })
        
        return jsonify({
            'success': True,
            'created': len(created_drafts),
            'drafts': created_drafts,
            'errors': errors
        })
    
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

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
