import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';

import 'config/theme.dart';
import 'config/routes.dart';
import 'providers/auth_provider.dart';
import 'providers/locale_provider.dart';
import 'providers/theme_provider.dart';

import 'screens/auth/login_screen.dart';
import 'screens/auth/change_password_screen.dart';
import 'screens/dashboard/dashboard_screen.dart';
import 'screens/attendance/attendance_list_screen.dart';
import 'screens/attendance/qr_scanner_screen.dart';
import 'screens/leaves/leave_list_screen.dart';
import 'screens/leaves/leave_form_screen.dart';
import 'screens/payslips/payslip_list_screen.dart';
import 'screens/payslips/payslip_detail_screen.dart';
import 'screens/tasks/task_list_screen.dart';
import 'screens/tasks/task_detail_screen.dart';
import 'screens/profile/profile_screen.dart';
import 'screens/pos/terminal_select_screen.dart';
import 'screens/pos/pos_main_screen.dart';
import 'screens/pos/payment_screen.dart';
import 'screens/pos/receipt_screen.dart';
import 'screens/pos/order_history_screen.dart';
import 'screens/pos/pos_stats_screen.dart';
import 'screens/notifications/notification_screen.dart';

class ERPApp extends StatefulWidget {
  const ERPApp({super.key});

  @override
  State<ERPApp> createState() => _ERPAppState();
}

class _ERPAppState extends State<ERPApp> {
  @override
  void initState() {
    super.initState();
    // Check auth state on app start
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AuthProvider>().checkAuth();
    });
  }

  @override
  Widget build(BuildContext context) {
    final localeProvider = context.watch<LocaleProvider>();
    final themeProvider = context.watch<ThemeProvider>();
    final authProvider = context.watch<AuthProvider>();

    return MaterialApp(
      title: 'ERP Portal',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: themeProvider.themeMode,
      locale: localeProvider.locale,
      supportedLocales: LocaleProvider.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: authProvider.isLoggedIn
          ? const DashboardScreen()
          : const LoginScreen(),
      routes: {
        AppRoutes.login: (_) => const LoginScreen(),
        AppRoutes.dashboard: (_) => const DashboardScreen(),
        AppRoutes.attendance: (_) => const AttendanceListScreen(),
        AppRoutes.qrScanner: (_) => const QRScannerScreen(),
        AppRoutes.leaves: (_) => const LeaveListScreen(),
        AppRoutes.leaveForm: (_) => const LeaveFormScreen(),
        AppRoutes.payslips: (_) => const PayslipListScreen(),
        AppRoutes.tasks: (_) => const TaskListScreen(),
        AppRoutes.profile: (_) => const ProfileScreen(),
        AppRoutes.changePassword: (_) => const ChangePasswordScreen(),
        AppRoutes.posTerminals: (_) => const TerminalSelectScreen(),
        AppRoutes.posMain: (_) => const POSMainScreen(),
        AppRoutes.posOrderHistory: (_) => const OrderHistoryScreen(),
        AppRoutes.posStats: (_) => const POSStatsScreen(),
        AppRoutes.notifications: (_) => const NotificationScreen(),
      },
      onGenerateRoute: (settings) {
        // Handle routes with arguments
        if (settings.name == AppRoutes.payslipDetail) {
          final id = settings.arguments as int;
          return MaterialPageRoute(
            builder: (_) => PayslipDetailScreen(payslipId: id),
          );
        }
        if (settings.name == AppRoutes.taskDetail) {
          final id = settings.arguments as int;
          return MaterialPageRoute(
            builder: (_) => TaskDetailScreen(taskId: id),
          );
        }
        if (settings.name == AppRoutes.posPayment) {
          final args = settings.arguments as Map<String, dynamic>;
          return MaterialPageRoute(
            builder: (_) => PaymentScreen(
              orderId: args['order_id'],
              totalAmount: args['total_amount'],
            ),
          );
        }
        if (settings.name == AppRoutes.posReceipt) {
          final orderId = settings.arguments as int;
          return MaterialPageRoute(
            builder: (_) => ReceiptScreen(orderId: orderId),
          );
        }
        return null;
      },
    );
  }
}
