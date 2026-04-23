// Dashboard summary + KPI models for the admin-mobile portal.

class AdminDashboardSummary {
  final String todayRevenue;
  final String cashInHand;
  final int pendingLeaveApprovals;
  final int pendingExpenseApprovals;
  final int pendingPoApprovals;
  final int lowStockItems;
  final int openPosSessions;
  final String overdueInvoicesAmount;
  final String thisMonthRevenue;
  final String thisMonthExpenses;

  const AdminDashboardSummary({
    this.todayRevenue = '0',
    this.cashInHand = '0',
    this.pendingLeaveApprovals = 0,
    this.pendingExpenseApprovals = 0,
    this.pendingPoApprovals = 0,
    this.lowStockItems = 0,
    this.openPosSessions = 0,
    this.overdueInvoicesAmount = '0',
    this.thisMonthRevenue = '0',
    this.thisMonthExpenses = '0',
  });

  factory AdminDashboardSummary.fromJson(Map<String, dynamic> json) =>
      AdminDashboardSummary(
        todayRevenue: (json['today_revenue'] ?? '0').toString(),
        cashInHand: (json['cash_in_hand'] ?? '0').toString(),
        pendingLeaveApprovals: json['pending_leave_approvals'] ?? 0,
        pendingExpenseApprovals: json['pending_expense_approvals'] ?? 0,
        pendingPoApprovals: json['pending_po_approvals'] ?? 0,
        lowStockItems: json['low_stock_items'] ?? 0,
        openPosSessions: json['open_pos_sessions'] ?? 0,
        overdueInvoicesAmount: (json['overdue_invoices_amount'] ?? '0')
            .toString(),
        thisMonthRevenue: (json['this_month_revenue'] ?? '0').toString(),
        thisMonthExpenses: (json['this_month_expenses'] ?? '0').toString(),
      );
}

class AdminDashboardKpis {
  final int periodDays;
  final String revenue;
  final String expenses;
  final String net;
  final int newCustomers;
  final int newLeads;
  final int invoicesIssued;
  final String paymentsReceived;

  const AdminDashboardKpis({
    this.periodDays = 30,
    this.revenue = '0',
    this.expenses = '0',
    this.net = '0',
    this.newCustomers = 0,
    this.newLeads = 0,
    this.invoicesIssued = 0,
    this.paymentsReceived = '0',
  });

  factory AdminDashboardKpis.fromJson(Map<String, dynamic> json) =>
      AdminDashboardKpis(
        periodDays: json['period_days'] ?? 30,
        revenue: (json['revenue'] ?? '0').toString(),
        expenses: (json['expenses'] ?? '0').toString(),
        net: (json['net'] ?? '0').toString(),
        newCustomers: json['new_customers'] ?? 0,
        newLeads: json['new_leads'] ?? 0,
        invoicesIssued: json['invoices_issued'] ?? 0,
        paymentsReceived: (json['payments_received'] ?? '0').toString(),
      );
}

class AdminActivityEntry {
  final int id;
  final String action;
  final String actorName;
  final String description;
  final String createdAt;
  final String? contentType;

  const AdminActivityEntry({
    required this.id,
    required this.action,
    required this.actorName,
    required this.description,
    required this.createdAt,
    this.contentType,
  });

  factory AdminActivityEntry.fromJson(Map<String, dynamic> json) {
    // AuditLogMobileSerializer shape may vary — be defensive.
    final user = json['user'];
    String actor = '';
    if (user is Map) {
      actor =
          (user['full_name'] ??
                  user['email'] ??
                  '${user['first_name'] ?? ''} ${user['last_name'] ?? ''}')
              .toString()
              .trim();
    } else if (user is String) {
      actor = user;
    }
    actor = actor.isEmpty ? 'System' : actor;

    return AdminActivityEntry(
      id: json['id'] ?? 0,
      action: (json['action'] ?? json['action_type'] ?? '').toString(),
      actorName: actor,
      description:
          (json['description'] ??
                  json['object_repr'] ??
                  json['change_message'] ??
                  '')
              .toString(),
      createdAt: (json['created_at'] ?? json['timestamp'] ?? '').toString(),
      contentType:
          json['content_type_label']?.toString() ??
          (json['content_type'] is Map
              ? json['content_type']['model']?.toString()
              : null),
    );
  }
}
