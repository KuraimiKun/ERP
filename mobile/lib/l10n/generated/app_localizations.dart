import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';
import 'app_localizations_id.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
    Locale('id'),
  ];

  /// Application name
  ///
  /// In en, this message translates to:
  /// **'ERP Portal'**
  String get appName;

  /// Login action
  ///
  /// In en, this message translates to:
  /// **'Login'**
  String get login;

  /// Logout action
  ///
  /// In en, this message translates to:
  /// **'Logout'**
  String get logout;

  /// Email label
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get email;

  /// Password label
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get password;

  /// Submit button
  ///
  /// In en, this message translates to:
  /// **'Submit'**
  String get submit;

  /// Cancel button
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// Save button
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// Delete action
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// Back navigation
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get back;

  /// Search label
  ///
  /// In en, this message translates to:
  /// **'Search'**
  String get search;

  /// Loading indicator
  ///
  /// In en, this message translates to:
  /// **'Loading...'**
  String get loading;

  /// Error label
  ///
  /// In en, this message translates to:
  /// **'Error'**
  String get error;

  /// Success label
  ///
  /// In en, this message translates to:
  /// **'Success'**
  String get success;

  /// Empty state message
  ///
  /// In en, this message translates to:
  /// **'No data available'**
  String get noData;

  /// Retry action
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// Confirm action
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// Yes option
  ///
  /// In en, this message translates to:
  /// **'Yes'**
  String get yes;

  /// No option
  ///
  /// In en, this message translates to:
  /// **'No'**
  String get no;

  /// OK button
  ///
  /// In en, this message translates to:
  /// **'OK'**
  String get ok;

  /// Close action
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;

  /// Login page title
  ///
  /// In en, this message translates to:
  /// **'Employee Portal'**
  String get loginTitle;

  /// Login page subtitle
  ///
  /// In en, this message translates to:
  /// **'Sign in to your account'**
  String get loginSubtitle;

  /// Email input hint
  ///
  /// In en, this message translates to:
  /// **'Enter your email'**
  String get emailHint;

  /// Password input hint
  ///
  /// In en, this message translates to:
  /// **'Enter your password'**
  String get passwordHint;

  /// Login button text
  ///
  /// In en, this message translates to:
  /// **'Sign In'**
  String get loginButton;

  /// Logout confirmation
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to logout?'**
  String get logoutConfirm;

  /// Login error message
  ///
  /// In en, this message translates to:
  /// **'Invalid email or password'**
  String get invalidCredentials;

  /// Dashboard title
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get dashboard;

  /// Today attendance card
  ///
  /// In en, this message translates to:
  /// **'Today\'s Attendance'**
  String get todayAttendance;

  /// Check in status
  ///
  /// In en, this message translates to:
  /// **'Checked In'**
  String get checkedIn;

  /// Check out status
  ///
  /// In en, this message translates to:
  /// **'Checked Out'**
  String get checkedOut;

  /// Not checked in status
  ///
  /// In en, this message translates to:
  /// **'Not Checked In'**
  String get notCheckedIn;

  /// Monthly stats header
  ///
  /// In en, this message translates to:
  /// **'This Month'**
  String get monthStats;

  /// Present count
  ///
  /// In en, this message translates to:
  /// **'Present'**
  String get present;

  /// Absent count
  ///
  /// In en, this message translates to:
  /// **'Absent'**
  String get absent;

  /// Late count
  ///
  /// In en, this message translates to:
  /// **'Late'**
  String get late;

  /// Pending leave count
  ///
  /// In en, this message translates to:
  /// **'Pending Leaves'**
  String get pendingLeaves;

  /// Pending task count
  ///
  /// In en, this message translates to:
  /// **'Pending Tasks'**
  String get pendingTasks;

  /// Recent payslips section
  ///
  /// In en, this message translates to:
  /// **'Recent Payslips'**
  String get recentPayslips;

  /// Attendance title
  ///
  /// In en, this message translates to:
  /// **'Attendance'**
  String get attendance;

  /// Attendance history title
  ///
  /// In en, this message translates to:
  /// **'Attendance History'**
  String get attendanceHistory;

  /// QR scan button
  ///
  /// In en, this message translates to:
  /// **'Scan QR Code'**
  String get scanQR;

  /// Check in action
  ///
  /// In en, this message translates to:
  /// **'Check In'**
  String get checkIn;

  /// Check out action
  ///
  /// In en, this message translates to:
  /// **'Check Out'**
  String get checkOut;

  /// Hours worked label
  ///
  /// In en, this message translates to:
  /// **'Hours Worked'**
  String get hoursWorked;

  /// Overtime label
  ///
  /// In en, this message translates to:
  /// **'Overtime'**
  String get overtime;

  /// Late minutes label
  ///
  /// In en, this message translates to:
  /// **'Late Minutes'**
  String get lateMinutes;

  /// Date label
  ///
  /// In en, this message translates to:
  /// **'Date'**
  String get date;

  /// Scan success message
  ///
  /// In en, this message translates to:
  /// **'Scan Successful'**
  String get scanSuccess;

  /// Check in success
  ///
  /// In en, this message translates to:
  /// **'You have been checked in successfully'**
  String get scanCheckIn;

  /// Check out success
  ///
  /// In en, this message translates to:
  /// **'You have been checked out successfully'**
  String get scanCheckOut;

  /// Leave requests title
  ///
  /// In en, this message translates to:
  /// **'Leave Requests'**
  String get leaveRequests;

  /// New leave button
  ///
  /// In en, this message translates to:
  /// **'New Leave Request'**
  String get newLeave;

  /// Leave type label
  ///
  /// In en, this message translates to:
  /// **'Leave Type'**
  String get leaveType;

  /// Start date label
  ///
  /// In en, this message translates to:
  /// **'Start Date'**
  String get startDate;

  /// End date label
  ///
  /// In en, this message translates to:
  /// **'End Date'**
  String get endDate;

  /// Reason label
  ///
  /// In en, this message translates to:
  /// **'Reason'**
  String get reason;

  /// Days requested label
  ///
  /// In en, this message translates to:
  /// **'Days Requested'**
  String get daysRequested;

  /// Leave balance title
  ///
  /// In en, this message translates to:
  /// **'Leave Balance'**
  String get leaveBalance;

  /// Remaining label
  ///
  /// In en, this message translates to:
  /// **'Remaining'**
  String get remaining;

  /// Pending status
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get pending;

  /// Approved status
  ///
  /// In en, this message translates to:
  /// **'Approved'**
  String get approved;

  /// Rejected status
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get rejected;

  /// Cancelled status
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get cancelled;

  /// Cancel leave action
  ///
  /// In en, this message translates to:
  /// **'Cancel Leave'**
  String get cancelLeave;

  /// Submit leave button
  ///
  /// In en, this message translates to:
  /// **'Submit Leave Request'**
  String get submitLeave;

  /// Payslips title
  ///
  /// In en, this message translates to:
  /// **'Payslips'**
  String get payslips;

  /// Payslip detail title
  ///
  /// In en, this message translates to:
  /// **'Payslip Detail'**
  String get payslipDetail;

  /// Period start label
  ///
  /// In en, this message translates to:
  /// **'Period Start'**
  String get periodStart;

  /// Period end label
  ///
  /// In en, this message translates to:
  /// **'Period End'**
  String get periodEnd;

  /// Basic salary label
  ///
  /// In en, this message translates to:
  /// **'Basic Salary'**
  String get basicSalary;

  /// Gross salary label
  ///
  /// In en, this message translates to:
  /// **'Gross Salary'**
  String get grossSalary;

  /// Total deductions label
  ///
  /// In en, this message translates to:
  /// **'Total Deductions'**
  String get totalDeductions;

  /// Net salary label
  ///
  /// In en, this message translates to:
  /// **'Net Salary'**
  String get netSalary;

  /// Earnings section
  ///
  /// In en, this message translates to:
  /// **'Earnings'**
  String get earnings;

  /// Deductions section
  ///
  /// In en, this message translates to:
  /// **'Deductions'**
  String get deductions;

  /// Payment date label
  ///
  /// In en, this message translates to:
  /// **'Payment Date'**
  String get paymentDate;

  /// Tasks title
  ///
  /// In en, this message translates to:
  /// **'Tasks'**
  String get tasks;

  /// Task detail title
  ///
  /// In en, this message translates to:
  /// **'Task Detail'**
  String get taskDetail;

  /// Priority label
  ///
  /// In en, this message translates to:
  /// **'Priority'**
  String get priority;

  /// Status label
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get status;

  /// Due date label
  ///
  /// In en, this message translates to:
  /// **'Due Date'**
  String get dueDate;

  /// Add comment action
  ///
  /// In en, this message translates to:
  /// **'Add Comment'**
  String get addComment;

  /// Comments section
  ///
  /// In en, this message translates to:
  /// **'Comments'**
  String get comments;

  /// Todo status
  ///
  /// In en, this message translates to:
  /// **'To Do'**
  String get todo;

  /// In progress status
  ///
  /// In en, this message translates to:
  /// **'In Progress'**
  String get inProgress;

  /// Completed status
  ///
  /// In en, this message translates to:
  /// **'Completed'**
  String get completed;

  /// On hold status
  ///
  /// In en, this message translates to:
  /// **'On Hold'**
  String get onHold;

  /// Low priority
  ///
  /// In en, this message translates to:
  /// **'Low'**
  String get low;

  /// Medium priority
  ///
  /// In en, this message translates to:
  /// **'Medium'**
  String get medium;

  /// High priority
  ///
  /// In en, this message translates to:
  /// **'High'**
  String get high;

  /// Urgent priority
  ///
  /// In en, this message translates to:
  /// **'Urgent'**
  String get urgent;

  /// Profile title
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profile;

  /// Edit profile action
  ///
  /// In en, this message translates to:
  /// **'Edit Profile'**
  String get editProfile;

  /// Personal info section
  ///
  /// In en, this message translates to:
  /// **'Personal Information'**
  String get personalInfo;

  /// Contact info section
  ///
  /// In en, this message translates to:
  /// **'Contact Information'**
  String get contactInfo;

  /// Employment info section
  ///
  /// In en, this message translates to:
  /// **'Employment Information'**
  String get employmentInfo;

  /// Phone label
  ///
  /// In en, this message translates to:
  /// **'Phone'**
  String get phone;

  /// Emergency contact label
  ///
  /// In en, this message translates to:
  /// **'Emergency Contact'**
  String get emergencyContact;

  /// Emergency phone label
  ///
  /// In en, this message translates to:
  /// **'Emergency Phone'**
  String get emergencyPhone;

  /// Address label
  ///
  /// In en, this message translates to:
  /// **'Address'**
  String get address;

  /// City label
  ///
  /// In en, this message translates to:
  /// **'City'**
  String get city;

  /// Country label
  ///
  /// In en, this message translates to:
  /// **'Country'**
  String get country;

  /// Change password title
  ///
  /// In en, this message translates to:
  /// **'Change Password'**
  String get changePassword;

  /// Current password label
  ///
  /// In en, this message translates to:
  /// **'Current Password'**
  String get currentPassword;

  /// New password label
  ///
  /// In en, this message translates to:
  /// **'New Password'**
  String get newPassword;

  /// Confirm password label
  ///
  /// In en, this message translates to:
  /// **'Confirm Password'**
  String get confirmPassword;

  /// Password changed message
  ///
  /// In en, this message translates to:
  /// **'Password changed successfully'**
  String get passwordChanged;

  /// POS title
  ///
  /// In en, this message translates to:
  /// **'Point of Sale'**
  String get pos;

  /// Terminal selection title
  ///
  /// In en, this message translates to:
  /// **'Select Terminal'**
  String get selectTerminal;

  /// Open session action
  ///
  /// In en, this message translates to:
  /// **'Open Session'**
  String get openSession;

  /// Close session action
  ///
  /// In en, this message translates to:
  /// **'Close Session'**
  String get closeSession;

  /// Opening balance label
  ///
  /// In en, this message translates to:
  /// **'Opening Balance'**
  String get openingBalance;

  /// Closing balance label
  ///
  /// In en, this message translates to:
  /// **'Closing Balance'**
  String get closingBalance;

  /// Expected cash label
  ///
  /// In en, this message translates to:
  /// **'Expected Cash'**
  String get expectedCash;

  /// Cash difference label
  ///
  /// In en, this message translates to:
  /// **'Cash Difference'**
  String get cashDifference;

  /// Products label
  ///
  /// In en, this message translates to:
  /// **'Products'**
  String get products;

  /// Categories label
  ///
  /// In en, this message translates to:
  /// **'Categories'**
  String get categories;

  /// Cart label
  ///
  /// In en, this message translates to:
  /// **'Cart'**
  String get cart;

  /// Subtotal label
  ///
  /// In en, this message translates to:
  /// **'Subtotal'**
  String get subtotal;

  /// Discount label
  ///
  /// In en, this message translates to:
  /// **'Discount'**
  String get discount;

  /// Tax label
  ///
  /// In en, this message translates to:
  /// **'Tax'**
  String get tax;

  /// Total label
  ///
  /// In en, this message translates to:
  /// **'Total'**
  String get total;

  /// Pay action
  ///
  /// In en, this message translates to:
  /// **'Pay'**
  String get pay;

  /// Receipt label
  ///
  /// In en, this message translates to:
  /// **'Receipt'**
  String get receipt;

  /// Order history title
  ///
  /// In en, this message translates to:
  /// **'Order History'**
  String get orderHistory;

  /// Add to cart action
  ///
  /// In en, this message translates to:
  /// **'Add to Cart'**
  String get addToCart;

  /// Checkout action
  ///
  /// In en, this message translates to:
  /// **'Checkout'**
  String get checkout;

  /// Payment method label
  ///
  /// In en, this message translates to:
  /// **'Payment Method'**
  String get paymentMethod;

  /// Amount tendered
  ///
  /// In en, this message translates to:
  /// **'Tendered'**
  String get tendered;

  /// Change amount
  ///
  /// In en, this message translates to:
  /// **'Change'**
  String get change;

  /// Order complete message
  ///
  /// In en, this message translates to:
  /// **'Order Complete'**
  String get orderComplete;

  /// Empty cart message
  ///
  /// In en, this message translates to:
  /// **'Your cart is empty'**
  String get emptyCart;

  /// Session closed message
  ///
  /// In en, this message translates to:
  /// **'Session Closed'**
  String get sessionClosed;

  /// Notifications title
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get notifications;

  /// Mark all read action
  ///
  /// In en, this message translates to:
  /// **'Mark All as Read'**
  String get markAllRead;

  /// No notifications message
  ///
  /// In en, this message translates to:
  /// **'No notifications'**
  String get noNotifications;

  /// POS stats title
  ///
  /// In en, this message translates to:
  /// **'My Performance'**
  String get myPerformance;

  /// Today period filter
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get periodToday;

  /// Week period filter
  ///
  /// In en, this message translates to:
  /// **'This Week'**
  String get periodWeek;

  /// Month period filter
  ///
  /// In en, this message translates to:
  /// **'This Month'**
  String get periodMonth;

  /// Total sales stat label
  ///
  /// In en, this message translates to:
  /// **'Total Sales'**
  String get totalSalesLabel;

  /// Total orders stat label
  ///
  /// In en, this message translates to:
  /// **'Orders'**
  String get totalOrdersLabel;

  /// Average order stat label
  ///
  /// In en, this message translates to:
  /// **'Avg Order'**
  String get avgOrderLabel;

  /// Items sold stat label
  ///
  /// In en, this message translates to:
  /// **'Items Sold'**
  String get itemsSoldLabel;

  /// Hourly sales chart title
  ///
  /// In en, this message translates to:
  /// **'Hourly Sales'**
  String get hourlySalesTitle;

  /// Payment breakdown section title
  ///
  /// In en, this message translates to:
  /// **'Payment Methods'**
  String get paymentBreakdown;

  /// Top products section title
  ///
  /// In en, this message translates to:
  /// **'Top Products'**
  String get topProducts;

  /// Recent sessions section title
  ///
  /// In en, this message translates to:
  /// **'Recent Sessions'**
  String get recentSessions;

  /// Appearance settings header
  ///
  /// In en, this message translates to:
  /// **'Appearance'**
  String get appearance;

  /// Dark mode toggle label
  ///
  /// In en, this message translates to:
  /// **'Dark Mode'**
  String get darkMode;

  /// Light mode label
  ///
  /// In en, this message translates to:
  /// **'Light Mode'**
  String get lightMode;

  /// System default theme label
  ///
  /// In en, this message translates to:
  /// **'System Default'**
  String get systemMode;

  /// View all action
  ///
  /// In en, this message translates to:
  /// **'View All'**
  String get viewAll;

  /// All filter option
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get all;

  /// Gender label
  ///
  /// In en, this message translates to:
  /// **'Gender'**
  String get gender;

  /// Date of birth label
  ///
  /// In en, this message translates to:
  /// **'Date of Birth'**
  String get dateOfBirth;

  /// Nationality label
  ///
  /// In en, this message translates to:
  /// **'Nationality'**
  String get nationality;

  /// Hire date label
  ///
  /// In en, this message translates to:
  /// **'Hire Date'**
  String get hireDate;

  /// Employment type label
  ///
  /// In en, this message translates to:
  /// **'Employment Type'**
  String get employmentType;

  /// Branch label
  ///
  /// In en, this message translates to:
  /// **'Branch'**
  String get branch;

  /// Employee ID label
  ///
  /// In en, this message translates to:
  /// **'Employee ID'**
  String get employeeId;

  /// Language selector label
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'en', 'id'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'en':
      return AppLocalizationsEn();
    case 'id':
      return AppLocalizationsId();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
