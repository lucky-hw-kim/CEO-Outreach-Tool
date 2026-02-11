import React, { useState, useEffect } from 'react';
import './styles/App.css';
import CustomerList from './components/CustomerList';
import TemplateSelector from './components/TemplateSelector';
import EmailPreview from './components/EmailPreview';
import * as api from './services/api';


const SENDER_EMAIL = "hello@spatulafoods.com";
function App() {
  const [customers, setCustomers] = useState([]);
  const [filteredCustomers, setFilteredCustomers] = useState([]);
  const [selectedCustomers, setSelectedCustomers] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [step, setStep] = useState('select'); // 'select', 'template', 'preview'
  const [filters, setFilters] = useState({
    orderCount: '',
    maxOrders: '',
    lastOrderDays: '',
    minSpent: '',
    maxSpent: '',
    search: '',
    winback: false,
    winbackDays: 60,
    purchasedGiftCard: false
  });
  const [sortBy, setSortBy] = useState('last_order_date');
  const [sortOrder, setSortOrder] = useState('desc');
  const [successMessage, setSuccessMessage] = useState('');
  const [cacheInfo, setCacheInfo] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  // Debounce filter changes to avoid too many API calls
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      loadData();
    }, 500); // Wait 500ms after user stops typing
    
    return () => clearTimeout(timeoutId);
  }, [filters, sortBy, sortOrder]);

  const loadData = async (forceRefresh = false) => {
  try {
    setLoading(true);

    const apiFilters = {
      refresh: forceRefresh ? 'true' : 'false',
      search: filters.search || undefined,
      min_orders: filters.orderCount || undefined,
      max_orders: filters.maxOrders || undefined,
      min_spent: filters.minSpent || undefined,
      max_spent: filters.maxSpent || undefined,
      days_since_order: filters.lastOrderDays || undefined,
      purchased_gift_card: filters.purchasedGiftCard || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
    };

    // ✅ ADD THESE TWO LINES HERE
    if (filters.winback) apiFilters.winback = 'true';
    if (filters.winbackDays) apiFilters.winback_days = filters.winbackDays;

    const customersResponse = await api.getCustomers(apiFilters);

    if (customersResponse.cache_info) {
      setCacheInfo(customersResponse.cache_info);
    }

    setCustomers(customersResponse.customers || customersResponse);

    if (templates.length === 0) {
      const templatesData = await api.getTemplates();
      setTemplates(templatesData);
    }

    setError(null);
  } catch (err) {
    setError('Failed to load data: ' + err.message);
  } finally {
    setLoading(false);
  }
};

  const handleRefresh = () => {
    loadData(true); // Force refresh from Shopify
  };

  const handleCustomerSelect = (customerId) => {
    setSelectedCustomers(prev => {
      if (prev.includes(customerId)) {
        return prev.filter(id => id !== customerId);
      } else {
        return [...prev, customerId];
      }
    });
  };

  const handleSelectAll = () => {
    if (selectedCustomers.length === filteredCustomers.length) {
      setSelectedCustomers([]);
    } else {
      setSelectedCustomers(filteredCustomers.map(c => c.id));
    }
  };

  const handleNextStep = () => {
    if (step === 'select' && selectedCustomers.length > 0) {
      setStep('template');
    } else if (step === 'template' && selectedTemplate) {
      setStep('preview');
    }
  };

  const handleBackStep = () => {
    if (step === 'template') {
      setStep('select');
    } else if (step === 'preview') {
      setStep('template');
    }
  };

const handleCreateDrafts = async () => {
  try {
    setLoading(true);

    const selectedCustomerData = customers.filter(c =>
      selectedCustomers.includes(c.id)
    );

    const result = await api.createDrafts({
      template_id: selectedTemplate,
      customers: selectedCustomerData,
      boss_email: SENDER_EMAIL
    });

    setSuccessMessage(`Successfully created ${result.created} draft emails in Gmail!`);

    setTimeout(() => {
      setSelectedCustomers([]);
      setSelectedTemplate(null);
      setStep('select');
      setSuccessMessage('');
    }, 3000);
  } catch (err) {
    setError('Failed to create drafts: ' + err.message);
  } finally {
    setLoading(false);
  }
};


  if (loading && customers.length === 0) {
    return (
      <div className="app">
        <div className="loading">
          <div className="loading-spinner"></div>
          <p>Fetching all customers from Shopify...</p>
          <small>This may take a moment for large customer lists</small>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div>
            <h1>CEO Customer Outreach Tool</h1>
          </div>
          {cacheInfo && (
            <div className="cache-info">
              {cacheInfo.from_cache ? (
                <>
                  <span className="cache-status">Using cached data</span>
                  <span className="cache-age">
                    {cacheInfo.cache_age < 60 
                      ? `${cacheInfo.cache_age}s ago` 
                      : `${Math.floor(cacheInfo.cache_age / 60)}m ago`}
                  </span>
                </>
              ) : (
                <span className="cache-status fresh">✨ Fresh data from Shopify</span>
              )}
              <button className="refresh-btn" onClick={handleRefresh} disabled={loading}>
                🔄 Refresh
              </button>
            </div>
          )}
        </div>
      </header>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {successMessage && (
        <div className="success-message">
          {successMessage}
        </div>
      )}

      <div className="step-indicator">
        <div className={`step ${step === 'select' ? 'active' : ''}`}>
          1. Select Customers
        </div>
        <div className={`step ${step === 'template' ? 'active' : ''}`}>
          2. Choose Template
        </div>
        <div className={`step ${step === 'preview' ? 'active' : ''}`}>
          3. Preview & Send
        </div>
      </div>

      <div className="app-content">
        {step === 'select' && (
          <CustomerList
            customers={filteredCustomers}
            selectedCustomers={selectedCustomers}
            onSelectCustomer={handleCustomerSelect}
            onSelectAll={handleSelectAll}
            filters={filters}
            onFilterChange={setFilters}
            sortBy={sortBy}
            onSortByChange={setSortBy}
            sortOrder={sortOrder}
            onSortOrderChange={setSortOrder}
          />
        )}

        {step === 'template' && (
          <TemplateSelector
            templates={templates}
            selectedTemplate={selectedTemplate}
            onSelectTemplate={setSelectedTemplate}
          />
        )}
        {step === 'preview' && (
          <EmailPreview
            template={templates.find(t => t.id === selectedTemplate)}
            customers={customers.filter(c => selectedCustomers.includes(c.id))}
          />
        )}
      </div>

      <div className="action-bar">
        {step !== 'select' && (
          <button className="btn btn-secondary" onClick={handleBackStep}>
            ← Back
          </button>
        )}
        
        <div className="action-info">
          {selectedCustomers.length} customer{selectedCustomers.length !== 1 ? 's' : ''} selected
        </div>

        {step === 'select' && (
          <button 
            className="btn btn-primary"
            onClick={handleNextStep}
            disabled={selectedCustomers.length === 0}
          >
            Continue to Templates →
          </button>
        )}

        {step === 'template' && (
          <button 
            className="btn btn-primary"
            onClick={handleNextStep}
            disabled={!selectedTemplate}
          >
            Preview Emails →
          </button>
        )}

        {step === 'preview' && (
          <button
            className="btn btn-primary"
            onClick={handleCreateDrafts}
            disabled={loading}   // optional: disable while loading
          >
            Create Gmail Drafts ✉️
          </button>
        )}
      </div>
    </div>
  );
}

export default App;
