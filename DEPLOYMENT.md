# Quick Start: Deploy to Render

This guide will get your CEO Outreach Tool deployed to Render in under 30 minutes.

## Prerequisites Checklist

- [ ] GitHub account
- [ ] Render account (free tier works)
- [ ] Shopify store with admin access
- [ ] Google account with Gmail

## Step 1: Get Your Shopify Credentials (5 minutes)

1. Log into your Shopify Admin
2. Go to **Settings** → **Apps and sales channels** → **Develop apps**
3. Click **Create an app** (name it "CEO Outreach Tool")
4. Click **Configure Admin API scopes**
5. Enable these scopes:
   - `read_customers`
   - `read_orders`
6. Click **Save**
7. Click **Install app** at the top
8. Click **Reveal token once** and copy your Admin API access token
9. Copy your API key from the app details page

You now have:
- ✅ API Key
- ✅ Admin API access token  
- ✅ Store URL (e.g., `your-store.myshopify.com`)

## Step 2: Set Up Gmail OAuth (10 minutes)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Click **Enable APIs and Services**
4. Search for "Gmail API" and enable it
5. Go to **Credentials** in the sidebar
6. Click **Create Credentials** → **OAuth client ID**
7. If prompted, configure the consent screen:
   - User type: External
   - Add your email as a test user
8. Application type: **Desktop app**
9. Name it "CEO Outreach Tool"
10. Click **Create** and download the JSON file

Now get your credentials:

```bash
# Install required packages
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client

# Place your downloaded credentials.json in the project root
# Run the setup script
python setup_gmail_oauth.py
```

Follow the browser prompts to authenticate. Copy the output `GMAIL_CREDENTIALS` value.

## Step 3: Push to GitHub (2 minutes)

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Step 4: Deploy on Render (10 minutes)

### Backend Deployment

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **New +** → **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `ceo-outreach-backend`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add Environment Variables:
   ```
   SHOPIFY_API_KEY=your_api_key_here
   SHOPIFY_PASSWORD=your_admin_api_token_here
   SHOPIFY_STORE_URL=your-store.myshopify.com
   GMAIL_CREDENTIALS=your_gmail_credentials_json_here
   PYTHON_VERSION=3.11.0
   ```
6. Click **Create Web Service**
7. Wait for deployment (3-5 minutes)
8. Copy your backend URL (e.g., `https://ceo-outreach-backend.onrender.com`)

### Frontend Deployment

1. Click **New +** → **Static Site**
2. Connect the same GitHub repository
3. Configure:
   - **Name**: `ceo-outreach-frontend`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `build`
4. Add Environment Variable:
   ```
   REACT_APP_API_URL=https://ceo-outreach-backend.onrender.com
   ```
   (Use your actual backend URL from step 7 above)
5. Click **Create Static Site**
6. Wait for deployment (3-5 minutes)

## Step 5: Test Your Application

1. Visit your frontend URL (e.g., `https://ceo-outreach-frontend.onrender.com`)
2. You should see the CEO Outreach Tool interface
3. Test the functionality:
   - Customer list should load from Shopify
   - Filters and sorting should work
   - Select customers and choose a template
   - Enter a Gmail address and create drafts

## Troubleshooting

### "Failed to load customers"
- Check Shopify credentials in Render environment variables
- Verify API scopes are enabled in Shopify app
- Check backend logs in Render dashboard

### "Gmail authentication required"
- Verify GMAIL_CREDENTIALS is correctly set
- Try re-running the OAuth setup script
- Check that Gmail API is enabled in Google Cloud Console

### "CORS errors" in browser console
- Ensure REACT_APP_API_URL is set correctly in frontend
- Verify backend is running and accessible
- Check that backend has `flask-cors` installed

### Backend won't start
- Check Python version is set to 3.11.0
- Verify all dependencies in requirements.txt
- Review build logs in Render dashboard

## Maintenance

### Updating the App
```bash
git add .
git commit -m "Your changes"
git push
```

Render will automatically redeploy on push!

### Rotating Credentials
1. Generate new credentials in Shopify/Google Cloud
2. Update environment variables in Render dashboard
3. Restart services

### Adding Email Templates
1. Edit `backend/app.py`
2. Add new template to `EMAIL_TEMPLATES` dictionary
3. Commit and push changes
4. Render will auto-deploy

## Cost Estimate

- **Render Free Tier**: $0/month
  - Backend: Free (sleeps after inactivity)
  - Frontend: Free
  - Limited to 750 hours/month
  
- **Render Starter**: $7/month per service
  - Always-on backend
  - Faster performance
  - No sleep timeout

- **Shopify API**: Free (included with your plan)
- **Gmail API**: Free (up to reasonable limits)

## Support Resources

- [Render Documentation](https://render.com/docs)
- [Shopify Admin API](https://shopify.dev/api/admin)
- [Gmail API Documentation](https://developers.google.com/gmail/api)

## Next Steps

Now that your app is deployed:

1. ✅ Share the URL with your boss
2. ✅ Add it to your bookmarks
3. ✅ Test with a few customers first
4. ✅ Customize email templates for your business
5. ✅ Set up monitoring/alerts in Render dashboard

Congratulations! Your CEO Outreach Tool is live! 🎉
