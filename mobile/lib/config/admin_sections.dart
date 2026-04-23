import 'package:flutter/material.dart';

import '../config/api_config.dart';
import '../l10n/generated/app_localizations.dart';

/// Defines how a single row in a generic admin list screen should render
/// for a given endpoint.
///
/// Each column maps to a JSON key on the record (`Map<String, dynamic>`).
/// Values are converted to strings via `toString()` unless a custom
/// `format` is supplied.
class AdminColumn {
  final String key;
  final String Function(dynamic value, Map<String, dynamic> row)? format;

  const AdminColumn(this.key, {this.format});

  String render(Map<String, dynamic> row) {
    final v = row[key];
    if (format != null) return format!(v, row);
    if (v == null) return '—';
    return v.toString();
  }
}

/// Declarative description of an admin section (employees, invoices, …).
///
/// Drives:
/// * nav entries in [AdminShell]
/// * generic list-screen title + endpoint + search placeholder
/// * row layout (title / subtitle / trailing)
class AdminSection {
  final String key;
  final String title;
  final IconData icon;
  final String endpoint;
  final String? searchHint;
  final AdminColumn title_;
  final AdminColumn? subtitle;
  final AdminColumn? trailing;
  final bool readOnly;
  final String group;

  const AdminSection({
    required this.key,
    required this.title,
    required this.icon,
    required this.endpoint,
    required this.title_,
    required this.group,
    this.subtitle,
    this.trailing,
    this.searchHint,
    this.readOnly = true,
  });
}

String _money(dynamic v, Map<String, dynamic> _) {
  if (v == null) return '—';
  final d = double.tryParse(v.toString());
  if (d == null) return v.toString();
  final sign = d < 0 ? '-' : '';
  final abs = d.abs();
  final intPart = abs.truncate();
  final frac = abs - intPart;
  final intStr = intPart
      .toString()
      .replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
  final fracStr = frac > 0 ? frac.toStringAsFixed(2).substring(1) : '';
  return '$sign$intStr$fracStr';
}

String _status(dynamic v, Map<String, dynamic> _) =>
    (v ?? '').toString().toUpperCase();

/// All admin sections, grouped for nav display.
const List<AdminSection> kAdminSections = [
  // ── Operations ───────────────────────────────────────────────
  AdminSection(
    key: 'approvals',
    title: 'Approvals',
    icon: Icons.task_alt,
    endpoint: '', // handled by dedicated screen
    title_: AdminColumn('id'),
    group: 'Operations',
  ),
  AdminSection(
    key: 'notifications',
    title: 'Notifications',
    icon: Icons.notifications_outlined,
    endpoint: ApiConfig.adminNotifications,
    title_: AdminColumn('title'),
    subtitle: AdminColumn('message'),
    group: 'Operations',
  ),
  AdminSection(
    key: 'audit_logs',
    title: 'Audit log',
    icon: Icons.history,
    endpoint: ApiConfig.adminAuditLogs,
    title_: AdminColumn('action'),
    subtitle: AdminColumn('description'),
    group: 'Operations',
  ),

  // ── HR ───────────────────────────────────────────────────────
  AdminSection(
    key: 'employees',
    title: 'Employees',
    icon: Icons.badge_outlined,
    endpoint: ApiConfig.adminEmployees,
    title_: AdminColumn('first_name', format: _fullName),
    subtitle: AdminColumn('job_title'),
    trailing: AdminColumn('employment_status', format: _status),
    searchHint: 'Name, email, employee ID',
    group: 'HR',
  ),
  AdminSection(
    key: 'departments',
    title: 'Departments',
    icon: Icons.apartment_outlined,
    endpoint: ApiConfig.adminDepartments,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('code'),
    group: 'HR',
  ),
  AdminSection(
    key: 'branches',
    title: 'Branches',
    icon: Icons.store_mall_directory_outlined,
    endpoint: ApiConfig.adminBranches,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('city'),
    group: 'HR',
  ),
  AdminSection(
    key: 'attendance',
    title: 'Attendance',
    icon: Icons.access_time,
    endpoint: ApiConfig.adminAttendance,
    title_: AdminColumn('employee_name'),
    subtitle: AdminColumn('date'),
    trailing: AdminColumn('hours_worked'),
    group: 'HR',
  ),
  AdminSection(
    key: 'leave_requests',
    title: 'Leave requests',
    icon: Icons.beach_access_outlined,
    endpoint: ApiConfig.adminLeaveRequests,
    title_: AdminColumn('employee_name'),
    subtitle: AdminColumn('leave_type_name'),
    trailing: AdminColumn('status', format: _status),
    group: 'HR',
  ),
  AdminSection(
    key: 'payroll',
    title: 'Payroll',
    icon: Icons.payments_outlined,
    endpoint: ApiConfig.adminPayroll,
    title_: AdminColumn('employee_name'),
    subtitle: AdminColumn('period_end'),
    trailing: AdminColumn('net_salary', format: _money),
    group: 'HR',
  ),

  // ── Finance ──────────────────────────────────────────────────
  AdminSection(
    key: 'customers',
    title: 'Customers',
    icon: Icons.people_outline,
    endpoint: ApiConfig.adminCustomers,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('email'),
    trailing: AdminColumn('current_balance', format: _money),
    searchHint: 'Name, email, phone',
    group: 'Finance',
  ),
  AdminSection(
    key: 'invoices',
    title: 'Invoices',
    icon: Icons.description_outlined,
    endpoint: ApiConfig.adminInvoices,
    title_: AdminColumn('invoice_number'),
    subtitle: AdminColumn('customer_name'),
    trailing: AdminColumn('balance_due', format: _money),
    searchHint: 'Invoice number',
    group: 'Finance',
  ),
  AdminSection(
    key: 'payments',
    title: 'Payments',
    icon: Icons.account_balance_outlined,
    endpoint: ApiConfig.adminPayments,
    title_: AdminColumn('payment_number'),
    subtitle: AdminColumn('customer_name'),
    trailing: AdminColumn('amount', format: _money),
    group: 'Finance',
  ),
  AdminSection(
    key: 'expenses',
    title: 'Expenses',
    icon: Icons.receipt_long_outlined,
    endpoint: ApiConfig.adminExpenses,
    title_: AdminColumn('expense_number'),
    subtitle: AdminColumn('category_name'),
    trailing: AdminColumn('total_amount', format: _money),
    group: 'Finance',
  ),
  AdminSection(
    key: 'accounts',
    title: 'Chart of accounts',
    icon: Icons.account_tree_outlined,
    endpoint: ApiConfig.adminAccounts,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('code'),
    trailing: AdminColumn('current_balance', format: _money),
    group: 'Finance',
  ),
  AdminSection(
    key: 'tax_rates',
    title: 'Tax rates',
    icon: Icons.percent_outlined,
    endpoint: ApiConfig.adminTaxRates,
    title_: AdminColumn('name'),
    trailing: AdminColumn('rate'),
    group: 'Finance',
  ),

  // ── Suppliers ────────────────────────────────────────────────
  AdminSection(
    key: 'suppliers',
    title: 'Suppliers',
    icon: Icons.local_shipping_outlined,
    endpoint: ApiConfig.adminSuppliers,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('email'),
    trailing: AdminColumn('current_balance', format: _money),
    group: 'Suppliers',
  ),
  AdminSection(
    key: 'purchase_orders',
    title: 'Purchase orders',
    icon: Icons.shopping_cart_outlined,
    endpoint: ApiConfig.adminPurchaseOrders,
    title_: AdminColumn('po_number'),
    subtitle: AdminColumn('supplier_name'),
    trailing: AdminColumn('total_amount', format: _money),
    group: 'Suppliers',
  ),
  AdminSection(
    key: 'supplier_invoices',
    title: 'Supplier invoices',
    icon: Icons.receipt_outlined,
    endpoint: ApiConfig.adminSupplierInvoices,
    title_: AdminColumn('invoice_number'),
    subtitle: AdminColumn('supplier_name'),
    trailing: AdminColumn('balance_due', format: _money),
    group: 'Suppliers',
  ),
  AdminSection(
    key: 'supplier_payments',
    title: 'Supplier payments',
    icon: Icons.outbox_outlined,
    endpoint: ApiConfig.adminSupplierPayments,
    title_: AdminColumn('payment_number'),
    subtitle: AdminColumn('supplier_name'),
    trailing: AdminColumn('amount', format: _money),
    group: 'Suppliers',
  ),

  // ── Inventory ────────────────────────────────────────────────
  AdminSection(
    key: 'products',
    title: 'Products',
    icon: Icons.inventory_2_outlined,
    endpoint: ApiConfig.adminProducts,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('sku'),
    trailing: AdminColumn('selling_price', format: _money),
    group: 'Inventory',
  ),
  AdminSection(
    key: 'warehouses',
    title: 'Warehouses',
    icon: Icons.warehouse_outlined,
    endpoint: ApiConfig.adminWarehouses,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('city'),
    group: 'Inventory',
  ),
  AdminSection(
    key: 'stock_items',
    title: 'Stock on hand',
    icon: Icons.shelves,
    endpoint: ApiConfig.adminStockItems,
    title_: AdminColumn('product_name'),
    subtitle: AdminColumn('warehouse_name'),
    trailing: AdminColumn('on_hand'),
    group: 'Inventory',
  ),
  AdminSection(
    key: 'stock_movements',
    title: 'Stock movements',
    icon: Icons.swap_horiz,
    endpoint: ApiConfig.adminStockMovements,
    title_: AdminColumn('product_name'),
    subtitle: AdminColumn('movement_type'),
    trailing: AdminColumn('quantity'),
    group: 'Inventory',
  ),
  AdminSection(
    key: 'goods_receipts',
    title: 'Goods receipts',
    icon: Icons.move_to_inbox_outlined,
    endpoint: ApiConfig.adminGoodsReceipts,
    title_: AdminColumn('grn_number'),
    subtitle: AdminColumn('supplier_name'),
    trailing: AdminColumn('status', format: _status),
    group: 'Inventory',
  ),
  AdminSection(
    key: 'stock_adjustments',
    title: 'Stock adjustments',
    icon: Icons.tune,
    endpoint: ApiConfig.adminStockAdjustments,
    title_: AdminColumn('adjustment_number'),
    subtitle: AdminColumn('warehouse_name'),
    trailing: AdminColumn('status', format: _status),
    group: 'Inventory',
  ),

  // ── POS ──────────────────────────────────────────────────────
  AdminSection(
    key: 'pos_terminals',
    title: 'POS terminals',
    icon: Icons.point_of_sale_outlined,
    endpoint: ApiConfig.adminPosTerminals,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('code'),
    group: 'POS',
  ),
  AdminSection(
    key: 'pos_sessions',
    title: 'POS sessions',
    icon: Icons.meeting_room_outlined,
    endpoint: ApiConfig.adminPosSessions,
    title_: AdminColumn('session_number'),
    subtitle: AdminColumn('opened_by_name'),
    trailing: AdminColumn('total_sales', format: _money),
    group: 'POS',
  ),
  AdminSection(
    key: 'pos_orders',
    title: 'POS orders',
    icon: Icons.receipt_outlined,
    endpoint: ApiConfig.adminPosOrders,
    title_: AdminColumn('order_number'),
    subtitle: AdminColumn('customer_name'),
    trailing: AdminColumn('total_amount', format: _money),
    group: 'POS',
  ),

  // ── CRM & Services ───────────────────────────────────────────
  AdminSection(
    key: 'leads',
    title: 'Leads',
    icon: Icons.person_add_alt_outlined,
    endpoint: ApiConfig.adminLeads,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('email'),
    trailing: AdminColumn('status', format: _status),
    group: 'CRM',
  ),
  AdminSection(
    key: 'tasks',
    title: 'Tasks',
    icon: Icons.check_box_outlined,
    endpoint: ApiConfig.adminTasks,
    title_: AdminColumn('title'),
    subtitle: AdminColumn('assignee_name'),
    trailing: AdminColumn('status', format: _status),
    group: 'CRM',
  ),
  AdminSection(
    key: 'campaigns',
    title: 'Campaigns',
    icon: Icons.campaign_outlined,
    endpoint: ApiConfig.adminCampaigns,
    title_: AdminColumn('name'),
    subtitle: AdminColumn('status'),
    group: 'CRM',
  ),
  AdminSection(
    key: 'quotes',
    title: 'Quotes',
    icon: Icons.request_quote_outlined,
    endpoint: ApiConfig.adminQuotes,
    title_: AdminColumn('quote_number'),
    subtitle: AdminColumn('customer_name'),
    trailing: AdminColumn('total_amount', format: _money),
    group: 'CRM',
  ),
];

String _fullName(dynamic _, Map<String, dynamic> row) {
  final first = (row['first_name'] ?? '').toString();
  final last = (row['last_name'] ?? '').toString();
  final name = '$first $last'.trim();
  return name.isEmpty ? (row['name'] ?? '—').toString() : name;
}

AdminSection? findSection(String key) {
  for (final s in kAdminSections) {
    if (s.key == key) return s;
  }
  return null;
}

Map<String, List<AdminSection>> groupSections() {
  final out = <String, List<AdminSection>>{};
  for (final s in kAdminSections) {
    out.putIfAbsent(s.group, () => []).add(s);
  }
  return out;
}

/// Returns the localized display name for a [AdminSection.group] key,
/// or the raw English group name when no translation/context is available.
String localizedGroupLabel(BuildContext context, String group) {
  final l10n = AppLocalizations.of(context);
  if (l10n == null) return group;
  switch (group) {
    case 'Operations':
      return l10n.groupOperations;
    case 'HR':
      return l10n.groupHr;
    case 'Finance':
      return l10n.groupFinance;
    case 'Suppliers':
      return l10n.groupSuppliers;
    case 'Inventory':
      return l10n.groupInventory;
    case 'CRM':
      return l10n.groupCrm;
    case 'POS':
      return l10n.groupPos;
  }
  return group;
}
