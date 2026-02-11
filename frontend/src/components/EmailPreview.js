import React, { useState, useEffect } from 'react';
import * as api from '../services/api';

function EmailPreview({ template, customers, bossEmail, onBossEmailChange }) {
  const [previews, setPreviews] = useState([]);
  const [selectedPreview, setSelectedPreview] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPreviews();
  }, [template, customers]);

  const loadPreviews = async () => {
    if (!template || !customers || customers.length === 0) return;

    setLoading(true);
    const previewPromises = customers.map(customer =>
      api.previewTemplate(template.id, customer)
    );

    try {
      const results = await Promise.all(previewPromises);
      setPreviews(results);
    } catch (err) {
      console.error('Failed to load previews:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Generating email previews...</div>;
  }

  const currentCustomer = customers[selectedPreview];
  const currentPreview = previews[selectedPreview];

  return (
    <div className="email-preview-container">
      <div className="preview-header">
        <h2>Review Email Drafts</h2>
        <p>Preview personalized emails before sending to Gmail</p>
      </div>

      <div className="boss-email-section">
        <label>
          <strong>Sender Gmail Address:</strong>
          <span className="required">*</span>
        </label>
        <input
          type="email"
          placeholder="hello@spatulafoods.com"
          value={bossEmail}
          onChange={(e) => onBossEmailChange(e.target.value)}
          className="boss-email-input"
        />
        <small>Drafts will be created in this Gmail account</small>
      </div>

      <div className="preview-controls">
        <div className="customer-selector">
          <button
            onClick={() => setSelectedPreview(Math.max(0, selectedPreview - 1))}
            disabled={selectedPreview === 0}
            className="nav-btn"
          >
            ← Previous
          </button>
          
          <div className="customer-counter">
            Customer {selectedPreview + 1} of {customers.length}
          </div>

          <button
            onClick={() => setSelectedPreview(Math.min(customers.length - 1, selectedPreview + 1))}
            disabled={selectedPreview === customers.length - 1}
            className="nav-btn"
          >
            Next →
          </button>
        </div>
      </div>

      {currentCustomer && currentPreview && (
        <div className="email-preview-card">
          <div className="preview-meta">
            <div className="meta-row">
              <span className="meta-label">To:</span>
              <span className="meta-value">{currentCustomer.email}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Customer:</span>
              <span className="meta-value">
                {currentCustomer.first_name} {currentCustomer.last_name}
              </span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Template:</span>
              <span className="meta-value">{template.name}</span>
            </div>
          </div>

          <div className="email-content">
            <div className="email-subject">
              <strong>Subject:</strong> {currentPreview.subject}
            </div>
            <div className="email-body">
              {currentPreview.body.split('\n').map((line, index) => (
                <p key={index}>{line}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="preview-summary">
        <div className="summary-card">
          <h3>📧 Summary</h3>
          <ul>
            <li><strong>{customers.length}</strong> draft emails will be created</li>
            <li>Template: <strong>{template.name}</strong></li>
            <li>Each email is personalized with the customer's first name</li>
            <li>Drafts will appear in <strong>{bossEmail || 'the specified Gmail account'}</strong></li>
          </ul>
        </div>

        <div className="info-box">
          <strong>ℹ️ Note:</strong> After clicking "Create Gmail Drafts", all emails will be 
          created as drafts in Gmail. You can review, edit, and send them individually.
        </div>
      </div>

      <div className="customer-list-preview">
        <h3>All Recipients ({customers.length})</h3>
        <div className="recipient-tags">
          {customers.map((customer, index) => (
            <div
              key={customer.id}
              className={`recipient-tag ${index === selectedPreview ? 'active' : ''}`}
              onClick={() => setSelectedPreview(index)}
            >
              {customer.first_name} {customer.last_name}
              <br />
              <small>{customer.email}</small>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default EmailPreview;
