const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001';

export const getCustomers = async (filters = {}) => {
  // Build query string from filters
  const params = new URLSearchParams();
  
  if (filters.search) params.append('search', filters.search);
  if (filters.min_orders) params.append('min_orders', filters.min_orders);
  if (filters.max_orders) params.append('max_orders', filters.max_orders);
  if (filters.min_spent) params.append('min_spent', filters.min_spent);
  if (filters.max_spent) params.append('max_spent', filters.max_spent);
  if (filters.days_since_order) params.append('days_since_order', filters.days_since_order);
  if (filters.purchased_gift_card) params.append('purchased_gift_card', filters.purchased_gift_card);
  if (filters.sort_by) params.append('sort_by', filters.sort_by);
  if (filters.sort_order) params.append('sort_order', filters.sort_order);
  if (filters.refresh) params.append('refresh', filters.refresh);
  
  const queryString = params.toString();
  const url = `${API_BASE_URL}/api/customers${queryString ? '?' + queryString : ''}`;
  
  const response = await fetch(url);
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error || 'Failed to fetch customers');
  }
  
  // Return full response including cache info
  return {
    customers: data.customers,
    cache_info: {
      from_cache: data.from_cache,
      cache_age: data.cache_age,
      cache_ttl: data.cache_ttl,
      total_customers: data.total_customers
    }
  };
};

export const getTemplates = async () => {
  const response = await fetch(`${API_BASE_URL}/api/templates`);
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error || 'Failed to fetch templates');
  }
  
  return data.templates;
};

export const previewTemplate = async (templateId, customer) => {
  const response = await fetch(`${API_BASE_URL}/api/preview-template`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      template_id: templateId,
      customer: customer
    })
  });
  
  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error || 'Failed to preview template');
  }
  
  return data;
};

export async function createDrafts(payload) {
  const res = await fetch(`${API_BASE_URL}/api/create-drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  // safer parsing (see below)
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : null; }
  catch { throw new Error(`Non-JSON response (${res.status}): ${text.slice(0, 200)}`); }

  if (!res.ok) throw new Error(data?.error || `Request failed (${res.status})`);
  return data;
}
