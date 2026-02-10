import React from 'react';

function TemplateSelector({ templates, selectedTemplate, onSelectTemplate }) {
  
  const templateDescriptions = {
    'new_customer': 'Welcome first-time customers and thank them for choosing SPATULA.',
    'winback_60': 'Re-engage customers who haven\'t ordered in 60+ days with a warm welcome back.',
    'gift_card': 'Thank customers who purchased gift cards and share the love of SPATULA.'
  };

  return (
    <div className="template-selector-container">
      <div className="template-header">
        <h2>Choose Email Template</h2>
        <p>Select the type of email you want to send to your selected customers</p>
      </div>

      <div className="templates-grid">
        {templates.map((template) => (
          <div
            key={template.id}
            className={`template-card ${selectedTemplate === template.id ? 'selected' : ''}`}
            onClick={() => onSelectTemplate(template.id)}
          >
            <div className="template-card-header">
              <div className="template-radio">
                <input
                  type="radio"
                  name="template"
                  checked={selectedTemplate === template.id}
                  onChange={() => onSelectTemplate(template.id)}
                />
              </div>
              <h3>{template.name}</h3>
            </div>
            
            <div className="template-card-body">
              <p className="template-description">
                {templateDescriptions[template.id] || 'Email template'}
              </p>
              <div className="template-subject">
                <strong>Subject:</strong> {template.subject}
              </div>
            </div>

            {selectedTemplate === template.id && (
              <div className="template-selected-indicator">
                ✓ Selected
              </div>
            )}
          </div>
        ))}
      </div>

      {templates.length === 0 && (
        <div className="no-templates">
          No email templates available. Please contact support.
        </div>
      )}
    </div>
  );
}

export default TemplateSelector;
