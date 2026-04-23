import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'app.dart';
import 'services/storage_service.dart';
import 'services/api_service.dart';
import 'services/auth_service.dart';
import 'providers/auth_provider.dart';
import 'providers/locale_provider.dart';
import 'providers/theme_provider.dart';
import 'providers/dashboard_provider.dart';
import 'providers/attendance_provider.dart';
import 'providers/leave_provider.dart';
import 'providers/payslip_provider.dart';
import 'providers/task_provider.dart';
import 'providers/profile_provider.dart';
import 'providers/notification_provider.dart';
import 'providers/pos_provider.dart';
import 'providers/admin_dashboard_provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final storage = StorageService();
  await storage.init();

  final apiService = ApiService(storage);
  final authService = AuthService(apiService, storage);

  runApp(
    MultiProvider(
      providers: [
        Provider<ApiService>.value(value: apiService),
        Provider<StorageService>.value(value: storage),
        ChangeNotifierProvider(create: (_) => LocaleProvider(storage)),
        ChangeNotifierProvider(create: (_) => ThemeProvider(storage)),
        ChangeNotifierProvider(
          create: (_) => AuthProvider(authService, storage),
        ),
        ChangeNotifierProvider(create: (_) => DashboardProvider(apiService)),
        ChangeNotifierProvider(create: (_) => AttendanceProvider(apiService)),
        ChangeNotifierProvider(create: (_) => LeaveProvider(apiService)),
        ChangeNotifierProvider(create: (_) => PayslipProvider(apiService)),
        ChangeNotifierProvider(create: (_) => TaskProvider(apiService)),
        ChangeNotifierProvider(
          create: (_) => ProfileProvider(apiService, storage),
        ),
        ChangeNotifierProvider(create: (_) => NotificationProvider(apiService)),
        ChangeNotifierProvider(create: (_) => POSProvider(apiService)),
        ChangeNotifierProvider(
          create: (_) => AdminDashboardProvider(apiService),
        ),
      ],
      child: const ERPApp(),
    ),
  );
}
