from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time
import json
import base64
import traceback
from datetime import datetime

import requests
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from email.mime.text import MIMEText

# -----------------------------
# Setup
# -----------------------------
load_dotenv()

app = Flask(__name__)

CORS(
    app,
    origins=[
        "http://localhost:3000",
        "http://localhost:5001",
        "https://ceo-outreach-tool.onrender.com",
        "https://ceo-outreach-frontend.onrender.com",
    ],
    supports_credentials=False,
    allow_headers=["Content-Type"],
    methods=["GET", "POST", "OPTIONS"],
)

SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY")  # not used, but kept
SHOPIFY_PASSWORD = os.environ.get("SHOPIFY_PASSWORD")
SHOPIFY_STORE_URL = os.environ.get("SHOPIFY_STORE_URL")
GMAIL_CREDENTIALS = os.environ.get("GMAIL_CREDENTIALS")  # optional; can use *_B64

# Gift card IDs
GIFT_CARD_PRODUCT_ID = 7033261424832
GIFT_CARD_VARIANT_IDS = [
    41369759252672, 41369759285440, 41369759318208,
    42311665844416, 42311665877184, 42311665909952,
    46402146631872, 46402146664640, 43257806815424,
    42359567843520, 42359567810752, 42359683907776,
    43739294466240,
]

# -----------------------------
# Caches
# -----------------------------
CACHE_TTL = 43200  # 12 hours

customer_cache = {"data": None, "timestamp": None}
gift_card_customer_cache = {"customer_ids": None, "timestamp": None}
order_stats_cache = {"data": None, "timestamp": None}  # {cid: {"last": dt, "prev": dt, "gap_days": int}}

# -----------------------------
# Shopify helpers
# -----------------------------
def _require_env():
    missing = []
    if not SHOPIFY_PASSWORD:
        missing.append("SHOPIFY_PASSWORD")
    if not SHOPIFY_STORE_URL:
        missing.append("SHOPIFY_STORE_URL")
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

def get_shopify_headers():
    return {
        "X-Shopify-Access-Token": SHOPIFY_PASSWORD,
        "Content-Type": "application/json",
    }

def shopify_request_with_retry(endpoint: str, max_retries: int = 5):
    """
    endpoint example: 'customers.json?limit=250'
    """
    _require_env()
    url = f"https://{SHOPIFY_STORE_URL}/admin/api/2024-01/{endpoint}"

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=get_shopify_headers(), timeout=30)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                sleep_time = min(retry_after, 2 ** attempt)
                print(f"Rate limited (429). Sleeping {sleep_time}s (attempt {attempt+1}/{max_retries})", flush=True)
                time.sleep(sleep_time)
                continue

            resp.raise_for_status()
            return resp

        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            sleep_time = 2 ** attempt
            print(f"Shopify request failed: {e}. Retrying in {sleep_time}s...", flush=True)
            time.sleep(sleep_time)

    raise RuntimeError("Max retries exceeded")

# -----------------------------
# Cache helpers
# -----------------------------
def is_cache_valid(cache_obj, ttl=CACHE_TTL):
    return cache_obj.get("data") is not None and cache_obj.get("timestamp") is not None and (time.time() - cache_obj["timestamp"] < ttl)

def get_cached_customers():
    if is_cache_valid(customer_cache, CACHE_TTL):
        print(f"Returning cached customers (age {int(time.time()-customer_cache['timestamp'])}s)", flush=True)
        return customer_cache["data"]
    return None

def cache_customers(data):
    customer_cache["data"] = data
    customer_cache["timestamp"] = time.time()
    print(f"Cached {len(data)} customers", flush=True)

def get_cached_gift_card_customers():
    if gift_card_customer_cache["customer_ids"] and gift_card_customer_cache["timestamp"] and (time.time() - gift_card_customer_cache["timestamp"] < CACHE_TTL):
        return gift_card_customer_cache["customer_ids"]
    return None

def cache_gift_card_customers(customer_ids):
    gift_card_customer_cache["customer_ids"] = customer_ids
    gift_card_customer_cache["timestamp"] = time.time()

# -----------------------------
# Shopify data fetchers
# -----------------------------
def fetch_all_customers_from_shopify():
    """
    Fetch all customers (only those with >=1 order, as you wanted).
    """
    all_customers = []
    url = "customers.json?limit=250"
    page_count = 0

    print("Starting to fetch customers from Shopify (only those with orders)...", flush=True)

    while url:
        page_count += 1
        print(f"Fetching customers page {page_count}...", flush=True)

        resp = shopify_request_with_retry(url)
        data = resp.json()
        customers = data.get("customers", [])

        customers_with_orders = [c for c in customers if (c.get("orders_count") or 0) > 0]
        all_customers.extend(customers_with_orders)

        print(
            f"Page {page_count}: {len(customers)} customers, {len(customers_with_orders)} with orders. Total so far: {len(all_customers)}",
            flush=True,
        )

        link_header = resp.headers.get("Link", "")
        url = None
        if 'rel="next"' in link_header:
            import re
            m = re.search(r'<https://[^>]+/admin/api/[^>]+/customers\.json\?([^>]+)>; rel="next"', link_header)
            if m:
                url = f"customers.json?{m.group(1)}"
                time.sleep(0.4)

    print(f"Finished fetching. Total customers with orders: {len(all_customers)}", flush=True)
    return all_customers

def get_customers_who_purchased_gift_card():
    cached = get_cached_gift_card_customers()
    if cached:
        print(f"Using cached {len(cached)} gift card customer IDs", flush=True)
        return cached

    print("Fetching gift card purchasers from Shopify orders...", flush=True)
    customer_ids = set()
    url = "orders.json?limit=250&status=any&fields=customer,line_items"

    while url:
        resp = shopify_request_with_retry(url)
        data = resp.json()
        orders = data.get("orders", [])

        for order in orders:
            cust = order.get("customer") or {}
            cid = cust.get("id")
            if not cid:
                continue

            for item in order.get("line_items", []):
                if item.get("product_id") == GIFT_CARD_PRODUCT_ID or item.get("variant_id") in GIFT_CARD_VARIANT_IDS:
                    customer_ids.add(cid)
                    break

        link_header = resp.headers.get("Link", "")
        url = None
        if 'rel="next"' in link_header:
            import re
            m = re.search(r'<https://[^>]+/admin/api/[^>]+/orders\.json\?([^>]+)>; rel="next"', link_header)
            if m:
                url = f"orders.json?{m.group(1)}"
                time.sleep(0.4)

    cache_gift_card_customers(customer_ids)
    print(f"Found {len(customer_ids)} gift card customers", flush=True)
    return customer_ids

def get_order_stats():
    """
    Computes TRUE last order date per customer and winback gap (last - prev).
    Returns dict {customer_id: {"last": dt, "prev": dt|None, "gap_days": int|None}}
    Cached for 12 hours.
    """
    if order_stats_cache["data"] and order_stats_cache["timestamp"] and (time.time() - order_stats_cache["timestamp"] < CACHE_TTL):
        return order_stats_cache["data"]

    print("Computing order stats from Shopify orders...", flush=True)

    stats = {}
    url = "orders.json?status=any&limit=250&order=created_at%20desc&fields=customer,created_at"

    while url:
        resp = shopify_request_with_retry(url)
        data = resp.json()
        orders = data.get("orders", [])

        for order in orders:
            cust = order.get("customer") or {}
            cid = cust.get("id")
            if not cid:
                continue

            created_at = order.get("created_at")
            if not created_at:
                continue

            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                continue

            if cid not in stats:
                stats[cid] = {"last": dt, "prev": None, "gap_days": None}
            else:
                if stats[cid]["prev"] is None:
                    stats[cid]["prev"] = dt
                    stats[cid]["gap_days"] = (stats[cid]["last"] - stats[cid]["prev"]).days

        link_header = resp.headers.get("Link", "")
        url = None
        if 'rel="next"' in link_header:
            import re
            m = re.search(r'<https://[^>]+/admin/api/[^>]+/orders\.json\?([^>]+)>; rel="next"', link_header)
            if m:
                url = f"orders.json?{m.group(1)}"
                time.sleep(0.25)

    order_stats_cache["data"] = stats
    order_stats_cache["timestamp"] = time.time()
    print(f"Order stats computed for {len(stats)} customers", flush=True)
    return stats

# -----------------------------
# Email templates
# -----------------------------
EMAIL_TEMPLATES = {
    "new_customer": {
        "name": "New Customers",
        "subject": "Thank You for Choosing SPATULA",
        "body": """Hi {first_name},

I wanted to thank you personally for giving SPATULA a try. It means a lot to us to have you here.

We started SPATULA to make mealtime easier and a lot more delicious for busy people who still care about good food. If you have a moment, I would love to hear what made you choose us. Your feedback really helps us make SPATULA even better.

If there is ever anything we can do from our side to make your experience even better, please don't hesitate to let us know.

Thank you for welcoming us into your kitchen!""",
    },
    "winback_60": {
        "name": "Winback Customers - 60 days",
        "subject": "Welcome Back to SPATULA",
        "body": """Hi {first_name},

I wanted to reach out and say thank you for your recent order. It is great to have you back with us!

At SPATULA, we are always working to make mealtime easier and more delicious, and it means a lot when customers return after some time away. If you have a moment, I would love to hear what brought you back. Your feedback really helps us make SPATULA even better.

If there is ever anything we can do from our side to make your experience even better, please don't hesitate to let us know.

Thanks again for having us back in your kitchen!""",
    },
    "gift_card": {
        "name": "Gifting Customers - Gift Card",
        "subject": "Thank You for Gifting SPATULA",
        "body": """Hi {first_name},

I wanted to personally thank you for choosing to gift SPATULA. It truly means a lot to us that you thought of us for such a special gesture.

We started SPATULA to make mealtime easier—and a lot more delicious—for busy people who still care about good food. That's why we're always so touched when someone chooses to share it with someone else.

If you have a moment, I'd love to hear what inspired the gift—what was the occasion, and what made you choose us? Your story helps us understand what moments we're a part of and how we can make them even better.

As always, if there's anything we can do to improve your experience (or theirs), don't hesitate to reach out.""",
    },
}

# -----------------------------
# Gmail drafts
# -----------------------------
def load_gmail_credentials_from_env():
    creds_json = os.environ.get("GMAIL_CREDENTIALS")
    if not creds_json:
        b64 = os.environ.get("GMAIL_CREDENTIALS_B64")
        if b64:
            creds_json = base64.b64decode(b64).decode("utf-8")

    if not creds_json:
        return None, "Missing GMAIL_CREDENTIALS or GMAIL_CREDENTIALS_B64"

    try:
        creds_data = json.loads(creds_json)
        creds = Credentials.from_authorized_user_info(creds_data)
    except Exception as e:
        return None, f"Invalid Gmail credentials JSON: {e}"

    # refresh if possible
    try:
        if getattr(creds, "expired", False) and getattr(creds, "refresh_token", None):
            creds.refresh(Request())
    except Exception as e:
        return None, f"Failed to refresh Gmail token: {e}"

    if not creds.valid:
        return None, "Gmail credentials are not valid (expired / missing refresh_token / wrong scopes)"
    return creds, None

# -----------------------------
# Routes
# -----------------------------
@app.route("/api/debug/ping", methods=["GET"])
def debug_ping():
    return jsonify(
        {
            "ok": True,
            "has_gmail_creds": bool(os.environ.get("GMAIL_CREDENTIALS") or os.environ.get("GMAIL_CREDENTIALS_B64")),
            "has_shopify_creds": bool(SHOPIFY_PASSWORD and SHOPIFY_STORE_URL),
        }
    )

@app.route("/api/customers", methods=["GET"])
def api_customers():
    """
    Filters:
      search, min_orders, max_orders, min_spent, max_spent, days_since_order,
      purchased_gift_card=true/false,
      winback=true/false, winback_days=int,
      sort_by=last_order_date|order_count|total_spent|customer_since|name,
      sort_order=asc|desc,
      refresh=true/false
    """
    try:
        search = request.args.get("search", "")
        min_orders = request.args.get("min_orders", None)
        max_orders = request.args.get("max_orders", None)
        min_spent = request.args.get("min_spent", None)
        max_spent = request.args.get("max_spent", None)
        days_since_order = request.args.get("days_since_order", None)

        purchased_gift_card = request.args.get("purchased_gift_card", "false").lower() == "true"
        winback = request.args.get("winback", "false").lower() == "true"
        try:
            winback_days = int(request.args.get("winback_days", 60))
        except Exception:
            winback_days = 60

        sort_by = request.args.get("sort_by", "last_order_date")
        sort_order = request.args.get("sort_order", "desc")
        force_refresh = request.args.get("refresh", "false").lower() == "true"

        cached_data = None
        if not force_refresh:
            cached_data = get_cached_customers()

        if cached_data is not None:
            all_customers = cached_data
            from_cache = True
        else:
            all_customers = fetch_all_customers_from_shopify()
            cache_customers(all_customers)
            from_cache = False

        # TRUE last order / gap stats (cached separately)
        order_stats = get_order_stats()

        gift_card_customer_ids = None
        if purchased_gift_card:
            gift_card_customer_ids = get_customers_who_purchased_gift_card()

        now = datetime.now()
        out = []

        for c in all_customers:
            cid = c.get("id")
            email = c.get("email") or ""
            if not cid or not email:
                continue

            order_count = c.get("orders_count") or 0
            total_spent = float(c.get("total_spent") or 0)
            created_at = c.get("created_at")

            # true last order
            stat = order_stats.get(cid) or {}
            last_dt = stat.get("last")  # tz-aware dt
            prev_dt = stat.get("prev")
            gap_days = stat.get("gap_days")

            last_order_date = last_dt.isoformat() if last_dt else None

            days_since_last_order = None
            if last_dt:
                # keep it simple & stable: compare naive -> naive
                try:
                    days_since_last_order = (now - last_dt.replace(tzinfo=None)).days
                except Exception:
                    days_since_last_order = None

            # search
            if search:
                q = search.lower()
                fn = (c.get("first_name") or "").lower()
                ln = (c.get("last_name") or "").lower()
                em = email.lower()
                if q not in fn and q not in ln and q not in em:
                    continue

            # min/max orders
            if min_orders and order_count < int(min_orders):
                continue
            if max_orders and order_count > int(max_orders):
                continue

            # min/max spent
            if min_spent and total_spent < float(min_spent):
                continue
            if max_spent and total_spent > float(max_spent):
                continue

            # inactive
            if days_since_order:
                min_days = int(days_since_order)
                if days_since_last_order is None or days_since_last_order < min_days:
                    continue

            # gift card filter
            if purchased_gift_card:
                if cid not in gift_card_customer_ids:
                    continue

            # winback filter
            if winback:
                if gap_days is None or gap_days < winback_days:
                    continue

            out.append(
                {
                    "id": cid,
                    "email": email,
                    "first_name": c.get("first_name", ""),
                    "last_name": c.get("last_name", ""),
                    "order_count": order_count,
                    "total_spent": total_spent,
                    "customer_since": created_at,
                    "last_order_date": last_order_date,
                    "days_since_last_order": days_since_last_order,
                    "winback_gap_days": gap_days,
                }
            )

        reverse = sort_order == "desc"
        if sort_by == "order_count":
            out.sort(key=lambda x: x.get("order_count") or 0, reverse=reverse)
        elif sort_by == "total_spent":
            out.sort(key=lambda x: x.get("total_spent") or 0, reverse=reverse)
        elif sort_by == "last_order_date":
            out.sort(key=lambda x: x.get("last_order_date") or "", reverse=reverse)
        elif sort_by == "customer_since":
            out.sort(key=lambda x: x.get("customer_since") or "", reverse=reverse)
        elif sort_by == "name":
            out.sort(key=lambda x: ((x.get("first_name") or "") + " " + (x.get("last_name") or "")).lower(), reverse=reverse)

        cache_age = int(time.time() - customer_cache["timestamp"]) if customer_cache["timestamp"] else None

        return jsonify(
            {
                "customers": out,
                "success": True,
                "count": len(out),
                "total_customers": len(all_customers),
                "cache_age": cache_age,
                "cache_ttl": CACHE_TTL,
                "from_cache": from_cache,
                "filters_applied": {
                    "search": search,
                    "min_orders": min_orders,
                    "max_orders": max_orders,
                    "min_spent": min_spent,
                    "max_spent": max_spent,
                    "days_since_order": days_since_order,
                    "purchased_gift_card": purchased_gift_card,
                    "winback": winback,
                    "winback_days": winback_days,
                },
            }
        )

    except Exception as e:
        print("Error in /api/customers:", str(e), flush=True)
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/templates", methods=["GET"])
def get_templates():
    templates = [{"id": k, "name": v["name"], "subject": v["subject"]} for k, v in EMAIL_TEMPLATES.items()]
    return jsonify({"templates": templates, "success": True})

@app.route("/api/preview-template", methods=["POST"])
def preview_template():
    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id")
    customer = data.get("customer") or {}

    if template_id not in EMAIL_TEMPLATES:
        return jsonify({"error": "Template not found", "success": False}), 404

    template = EMAIL_TEMPLATES[template_id]

    customer_since_str = "N/A"
    cs = customer.get("customer_since")
    if cs:
        try:
            dt = datetime.fromisoformat(cs.replace("Z", "+00:00"))
            customer_since_str = dt.strftime("%B %Y")
        except Exception:
            customer_since_str = "N/A"

    first_name = customer.get("first_name") or "Valued Customer"

    subject = template["subject"].format(first_name=first_name)
    body = template["body"].format(first_name=first_name, customer_since=customer_since_str)

    return jsonify({"subject": subject, "body": body, "success": True})

@app.route("/api/create-drafts", methods=["POST"])
def create_drafts():
    print("CREATE-DRAFTS HIT", flush=True)

    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id")
    customers = data.get("customers") or []
    boss_email = data.get("boss_email")

    if not boss_email:
        return jsonify({"success": False, "error": "Sender email is required"}), 400
    if not template_id or template_id not in EMAIL_TEMPLATES:
        return jsonify({"success": False, "error": "Template not found"}), 404
    if not isinstance(customers, list) or len(customers) == 0:
        return jsonify({"success": False, "error": "No customers provided"}), 400

    creds, err = load_gmail_credentials_from_env()
    if err:
        return jsonify({"success": False, "error": f"Gmail authentication required: {err}", "auth_required": True}), 401

    try:
        service = build("gmail", "v1", credentials=creds)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to build Gmail service: {e}"}), 500

    template = EMAIL_TEMPLATES[template_id]
    created_drafts = []
    errors = []

    for customer in customers:
        try:
            cust = customer or {}
            to_email = cust.get("email")
            if not to_email:
                errors.append({"customer": None, "error": "Missing customer email"})
                continue

            cs = cust.get("customer_since")
            customer_since_str = "N/A"
            if cs:
                try:
                    dt = datetime.fromisoformat(cs.replace("Z", "+00:00"))
                    customer_since_str = dt.strftime("%B %Y")
                except Exception:
                    customer_since_str = "N/A"

            first_name = cust.get("first_name") or "Valued Customer"
            subject = template["subject"].format(first_name=first_name)
            body = template["body"].format(first_name=first_name, customer_since=customer_since_str)

            msg = MIMEText(body)
            msg["to"] = to_email
            msg["subject"] = subject

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
            draft = (
                service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw}})
                .execute()
            )

            created_drafts.append({"customer": to_email, "draft_id": draft.get("id")})

        except HttpError as he:
            errors.append({"customer": (customer or {}).get("email"), "error": str(he)})
        except Exception as e:
            errors.append({"customer": (customer or {}).get("email"), "error": str(e)})

    return jsonify(
        {
            "success": True,
            "created": len(created_drafts),
            "drafts": created_drafts,
            "errors": errors,
        }
    ), 200

@app.route("/api/auth/gmail", methods=["GET"])
def gmail_auth():
    # You’re using env token loading; this endpoint can stay as a stub.
    return jsonify({"message": "Please configure Gmail OAuth / credentials env vars", "success": False}), 400

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "success": True})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
