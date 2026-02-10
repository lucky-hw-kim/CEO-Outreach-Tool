# CEO Customer Outreach Tool

A powerful tool for managing customer outreach campaigns with Shopify integration and Gmail draft creation.

## Features

- ✅ **Shopify Integration**: Automatically fetch customer data including order history
- ✅ **Advanced Filtering**: Filter customers by order count, last order date, and customer since date
- ✅ **Smart Sorting**: Sort by multiple criteria with ascending/descending options
- ✅ **Email Templates**: Pre-built templates for different outreach scenarios
- ✅ **Personalization**: Automatic first-name personalization for each email
- ✅ **Gmail Integration**: Create drafts directly in your boss's Gmail account
- ✅ **Preview System**: Review all emails before sending
- ✅ **Batch Processing**: Handle multiple customers at once

## Project Structure

```
ceo-outreach-tool/
├── backend/
│   ├── app.py                 # Flask backend with API endpoints
│   ├── requirements.txt       # Python dependencies
│   └── .env.example          # Environment variables template
├── frontend/
│   ├── src/
│   │   ├── App.js            # Main application component
│   │   ├── components/       # React components
│   │   │   ├── CustomerList.js
│   │   │   ├── TemplateSelector.js
│   │   │   └── EmailPreview.js
│   │   ├── services/
│   │   │   └── api.js        # API service layer
│   │   └── styles/
│   │       └── App.css       # Application styles
│   ├── public/
│   │   └── index.html
│   └── package.json
└── render.yaml               # Render deployment configuration
```

## Prerequisites

1. **Shopify Store Access**
   - Shopify store URL
   - Admin API access token
   - API key and password

2. **Google Cloud Project**
   - Gmail API enabled
   - OAuth 2.0 credentials configured
   - Authorized redirect URIs set up

3. **Render Account**
   - Free or paid account on render.com

## Setup Instructions

### 1. Shopify API Setup

1. Go to your Shopify Admin panel
2. Navigate to **Settings > Apps and sales channels > Develop apps**
3. Click **Create an app** (or use existing one)
4. Under **Configuration**, enable:
   - `read_customers`
   - `read_orders`
5. Install the app and copy:
   - API Key
   - Admin API access token
   - Store URL (format: `your-store.myshopify.com`)

### 2. Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **Gmail API**
4. Go to **Credentials** and create OAuth 2.0 Client ID
5. Set authorized redirect URIs:
   ```
   http://localhost:5000/oauth2callback
   https://your-app.onrender.com/oauth2callback
   ```
6. Download the credentials JSON file

#### Gmail OAuth Flow

To get the `GMAIL_CREDENTIALS` for the `.env` file:

1. Run this Python script locally:

```python
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ['https://www.googleapis.com/auth/gmail.compose']

def get_credentials():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json',  # Your downloaded credentials file
        SCOPES
    )
    creds = flow.run_local_server(port=0)
    
    # Save credentials
    creds_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    
    print("Add this to your .env file:")
    print(f"GMAIL_CREDENTIALS='{json.dumps(creds_data)}'")

if __name__ == '__main__':
    get_credentials()
```

2. Run: `pip install google-auth-oauthlib`
3. Run: `python get_credentials.py`
4. Follow the browser authentication flow
5. Copy the output to your `.env` file

### 3. Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd ceo-outreach-tool
   ```

2. **Backend Setup**
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env and add your credentials
   pip install -r requirements.txt
   python app.py
   ```

3. **Frontend Setup** (in new terminal)
   ```bash
   cd frontend
   npm install
   npm start
   ```

4. Visit `http://localhost:3000`

### 4. Deploy to Render

#### Option A: Using Render Dashboard

1. Push your code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click **New +** > **Blueprint**
4. Connect your GitHub repository
5. Render will detect the `render.yaml` file
6. Add environment variables in the Render dashboard:
   - `SHOPIFY_API_KEY`
   - `SHOPIFY_PASSWORD`
   - `SHOPIFY_STORE_URL`
   - `GMAIL_CREDENTIALS`
7. Deploy!

#### Option B: Manual Deployment

**Backend Service:**
1. New Web Service
2. Connect repository
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. Add environment variables

**Frontend Service:**
1. New Static Site
2. Connect repository
3. Build Command: `cd frontend && npm install && npm run build`
4. Publish Directory: `frontend/build`
5. Add environment variable:
   - `REACT_APP_API_URL`: Your backend URL

## Usage Guide

### Step 1: Select Customers

1. **Filter customers** by:
   - Search by name or email
   - Minimum number of orders
   - Days since last order

2. **Sort customers** by:
   - Last order date
   - Number of orders
   - Customer since date
   - Name

3. **Select customers** using:
   - Individual checkboxes
   - "Select All" button
   - Quick filter presets (30+ days, 90+ days inactive)

### Step 2: Choose Email Template

Select from pre-built templates:
- **Come Back to Us**: Re-engage inactive customers
- **Thank You**: Show appreciation to loyal customers
- **Special Offer**: Share exclusive deals
- **Request Feedback**: Gather customer opinions

### Step 3: Preview & Send

1. **Enter boss's Gmail address** (required)
2. **Preview each email** with personalization
3. **Review all recipients**
4. **Click "Create Gmail Drafts"**

The drafts will appear in the specified Gmail account's Drafts folder, where your boss can review, edit, and send them individually.

## Email Template Variables

Templates support these variables:
- `{first_name}`: Customer's first name
- `{customer_since}`: Formatted date (e.g., "January 2024")

## Customizing Email Templates

Edit the `EMAIL_TEMPLATES` dictionary in `backend/app.py`:

```python
EMAIL_TEMPLATES = {
    'your_template_id': {
        'name': 'Template Display Name',
        'subject': 'Email Subject with {first_name}',
        'body': '''Email body with {first_name} and {customer_since}'''
    }
}
```

## API Endpoints

- `GET /api/customers` - Fetch all customers with order data
- `GET /api/templates` - Get available email templates
- `POST /api/preview-template` - Preview template with customer data
- `POST /api/create-drafts` - Create Gmail drafts
- `GET /health` - Health check endpoint

## Troubleshooting

### Shopify Issues
- **Error: Invalid credentials**: Double-check API key and password
- **Error: Permission denied**: Ensure app has `read_customers` and `read_orders` scopes

### Gmail Issues
- **Error: Gmail authentication required**: Re-run OAuth flow and update credentials
- **Error: Quota exceeded**: Gmail API has rate limits; wait and retry

### Deployment Issues
- **Build fails**: Check that all environment variables are set
- **CORS errors**: Ensure backend URL is correctly configured in frontend
- **App crashes**: Check Render logs for specific error messages

## Security Notes

- Never commit `.env` files or credentials to Git
- Use Render's environment variables for sensitive data
- Regularly rotate API keys and tokens
- Use HTTPS in production (Render provides this automatically)

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Render logs for error messages
3. Verify all environment variables are set correctly
4. Ensure Shopify and Gmail APIs are properly configured

## License

This project is for internal use. Modify as needed for your organization.

## Future Enhancements

Potential features to add:
- [ ] Schedule emails for specific dates/times
- [ ] Track email open rates and responses
- [ ] A/B testing for email templates
- [ ] Customer segmentation by products purchased
- [ ] Export customer lists to CSV
- [ ] Multi-language support
- [ ] Analytics dashboard
- [ ] Custom template editor in UI
