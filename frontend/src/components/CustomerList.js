import React from 'react';

function CustomerList({
  customers,
  selectedCustomers,
  onSelectCustomer,
  onSelectAll,
  filters,
  onFilterChange,
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
}) {
  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getDaysSinceLastOrder = (dateString) => {
    if (!dateString) return null;
    const lastOrder = new Date(dateString);
    const today = new Date();
    const diffTime = Math.abs(today - lastOrder);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  // Always merge into existing filters (prevents wiping winback fields)
  const setFiltersPartial = (patch) => {
    onFilterChange({ ...filters, ...patch });
  };

  const handleFilterChange = (key, value) => {
    setFiltersPartial({ [key]: value });
  };

  const toggleSortOrder = () => {
    onSortOrderChange(sortOrder === 'asc' ? 'desc' : 'asc');
  };

  return (
    <div className="customer-list-container">
      <div className="filters-section">
        <h2>Filter & Sort Customers</h2>

        <div className="filters-grid">
          <div className="filter-group">
            <label>Search</label>
            <input
              type="text"
              placeholder="Search by name or email..."
              value={filters.search || ''}
              onChange={(e) => handleFilterChange('search', e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>Minimum Orders</label>
            <input
              type="number"
              placeholder="e.g., 5"
              value={filters.orderCount || ''}
              onChange={(e) => handleFilterChange('orderCount', e.target.value)}
              min="0"
            />
          </div>

          <div className="filter-group">
            <label>Maximum Orders</label>
            <input
              type="number"
              placeholder="e.g., 50"
              value={filters.maxOrders || ''}
              onChange={(e) => handleFilterChange('maxOrders', e.target.value)}
              min="0"
            />
          </div>

          <div className="filter-group">
            <label>Inactive Since (days)</label>
            <input
              type="number"
              placeholder="e.g., 30"
              value={filters.lastOrderDays || ''}
              onChange={(e) => handleFilterChange('lastOrderDays', e.target.value)}
              min="0"
            />
          </div>

          <div className="filter-group">
            <label>Min. Total Spent ($)</label>
            <input
              type="number"
              placeholder="e.g., 100"
              value={filters.minSpent || ''}
              onChange={(e) => handleFilterChange('minSpent', e.target.value)}
              min="0"
              step="0.01"
            />
          </div>

          <div className="filter-group">
            <label>Max. Total Spent ($)</label>
            <input
              type="number"
              placeholder="e.g., 1000"
              value={filters.maxSpent || ''}
              onChange={(e) => handleFilterChange('maxSpent', e.target.value)}
              min="0"
              step="0.01"
            />
          </div>

          <div className="filter-group">
            <label>Sort By</label>
            <div className="sort-controls">
              <select value={sortBy} onChange={(e) => onSortByChange(e.target.value)}>
                <option value="last_order_date">Last Order Date</option>
                <option value="order_count">Number of Orders</option>
                <option value="total_spent">Total Spent</option>
                <option value="customer_since">Customer Since</option>
                <option value="name">Name</option>
              </select>
              <button
                className="sort-order-btn"
                onClick={toggleSortOrder}
                title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
                type="button"
              >
                {sortOrder === 'asc' ? '↑' : '↓'}
              </button>
            </div>
          </div>

          <div className="filter-group checkbox-filter">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={!!filters.winback}
                onChange={(e) => handleFilterChange('winback', e.target.checked)}
              />
              <span>🔁 Winback customers (gap ≥ N days)</span>
            </label>

            <div style={{ marginTop: 8 }}>
              <label>
                Min gap days:
                <input
                  type="number"
                  min="1"
                  value={filters.winbackDays ?? 60}
                  disabled={!filters.winback}
                  onChange={(e) =>
                    handleFilterChange(
                      'winbackDays',
                      e.target.value === '' ? '' : Number(e.target.value)
                    )
                  }
                  style={{ marginLeft: 8, width: 90 }}
                />
              </label>
            </div>

            <small style={{ display: 'block', marginTop: 6, opacity: 0.8 }}>
              Customers whose most recent order happened at least N days after their previous order.
            </small>

            <label className="checkbox-label" style={{ marginTop: 10 }}>
              <input
                type="checkbox"
                checked={!!filters.purchasedGiftCard}
                onChange={(e) => handleFilterChange('purchasedGiftCard', e.target.checked)}
              />
              <span>🎁 Gift Card Purchasers Only</span>
            </label>

            <small className="filter-note">
              {filters.purchasedGiftCard && '⚠️ May take longer to load'}
            </small>
          </div>
        </div>

        <div className="quick-filters">
          <button
            className="quick-filter-btn"
            type="button"
            onClick={() =>
              setFiltersPartial({
                search: '',
                orderCount: '1',
                maxOrders: '1',
                lastOrderDays: '',
                minSpent: '',
                maxSpent: '',
                purchasedGiftCard: false,
                winback: false,
                winbackDays: filters.winbackDays ?? 60,
              })
            }
          >
            🆕 New Customers (1 order)
          </button>

          <button
            className="quick-filter-btn"
            type="button"
            onClick={() =>
              setFiltersPartial({
                winback: true,
                winbackDays: 60,
                purchasedGiftCard: false,
              })
            }
          >
            🔁 Winback (gap ≥ 60 days)
          </button>

          <button
            className="quick-filter-btn"
            type="button"
            onClick={() =>
              setFiltersPartial({
                purchasedGiftCard: true,
                winback: false,
              })
            }
          >
            🎁 Gift Card Purchasers
          </button>

          <button
            className="quick-filter-btn"
            type="button"
            onClick={() =>
              setFiltersPartial({
                orderCount: '5',
                minSpent: '500',
                purchasedGiftCard: false,
                winback: false,
              })
            }
          >
            ⭐ VIP Customers (5+ orders, $500+)
          </button>

          <button
            className="quick-filter-btn"
            type="button"
            onClick={() =>
              setFiltersPartial({
                orderCount: '10',
                purchasedGiftCard: false,
                winback: false,
              })
            }
          >
            💎 Loyalists (10+ orders)
          </button>

          <button
            className="quick-filter-btn"
            type="button"
            onClick={() =>
              setFiltersPartial({
                lastOrderDays: '90',
                purchasedGiftCard: false,
                winback: false,
              })
            }
          >
            ⚠️ At Risk (90+ days inactive)
          </button>

          <button
            className="quick-filter-btn"
            type="button"
            onClick={() =>
              onFilterChange({
                // reset to your defaults (IMPORTANT: include winback defaults too)
                search: '',
                orderCount: '',
                maxOrders: '',
                lastOrderDays: '',
                minSpent: '',
                maxSpent: '',
                purchasedGiftCard: false,
                winback: false,
                winbackDays: 60,
              })
            }
          >
            ✖️ Clear All Filters
          </button>
        </div>
      </div>

      <div className="customers-table-container">
        <div className="table-header">
          <h3>
            Customers ({customers.length}
            {customers.length > 0 && customers.length < 1000 && ' matching filters'})
          </h3>
          <button className="select-all-btn" onClick={onSelectAll} type="button">
            {selectedCustomers.length === customers.length && customers.length > 0
              ? 'Deselect All'
              : 'Select All'}
          </button>
        </div>

        {customers.length === 0 ? (
          <div className="no-results">
            No customers match your filters. Try adjusting your search criteria.
          </div>
        ) : (
          <table className="customers-table">
            <thead>
              <tr>
                <th className="checkbox-col">
                  <input
                    type="checkbox"
                    checked={selectedCustomers.length === customers.length && customers.length > 0}
                    onChange={onSelectAll}
                  />
                </th>
                <th>Name</th>
                <th>Email</th>
                <th>Orders</th>
                <th>Total Spent</th>
                <th>Last Order</th>
                <th>Customer Since</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => {
                const daysSince = getDaysSinceLastOrder(customer.last_order_date);

                return (
                  <tr
                    key={customer.id}
                    className={selectedCustomers.includes(customer.id) ? 'selected' : ''}
                  >
                    <td className="checkbox-col">
                      <input
                        type="checkbox"
                        checked={selectedCustomers.includes(customer.id)}
                        onChange={() => onSelectCustomer(customer.id)}
                      />
                    </td>
                    <td className="customer-name">
                      {customer.first_name} {customer.last_name}
                    </td>
                    <td className="customer-email">{customer.email}</td>
                    <td className="order-count">
                      <span className="badge">{customer.order_count}</span>
                    </td>
                    <td className="total-spent">
                      ${customer.total_spent?.toFixed(2) || '0.00'}
                    </td>
                    <td>
                      <div className="date-cell">
                        {formatDate(customer.last_order_date)}
                        {daysSince && (
                          <span className={`days-badge ${daysSince > 90 ? 'warning' : ''}`}>
                            {daysSince} days ago
                          </span>
                        )}
                      </div>
                    </td>
                    <td>{formatDate(customer.customer_since)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default CustomerList;
