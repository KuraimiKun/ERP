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
  /// **'your@email.com'**
  String get emailHint;

  /// Password input hint
  ///
  /// In en, this message translates to:
  /// **'••••••••••'**
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

  /// Admin portal brand label
  ///
  /// In en, this message translates to:
  /// **'Admin Portal'**
  String get adminPortal;

  /// Open drawer with all admin sections
  ///
  /// In en, this message translates to:
  /// **'All sections'**
  String get allSections;

  /// Approvals nav label
  ///
  /// In en, this message translates to:
  /// **'Approvals'**
  String get approvals;

  /// Reports nav label
  ///
  /// In en, this message translates to:
  /// **'Reports'**
  String get reports;

  /// Refresh action
  ///
  /// In en, this message translates to:
  /// **'Refresh'**
  String get refresh;

  /// Empty search results
  ///
  /// In en, this message translates to:
  /// **'No results'**
  String get noResults;

  /// Record id footer label
  ///
  /// In en, this message translates to:
  /// **'Record ID'**
  String get recordId;

  /// Details section header
  ///
  /// In en, this message translates to:
  /// **'Details'**
  String get details;

  /// Items section header
  ///
  /// In en, this message translates to:
  /// **'Items'**
  String get items;

  /// Toast shown after copying a field value
  ///
  /// In en, this message translates to:
  /// **'Copied \"{name}\"'**
  String copied(String name);

  /// Approve action
  ///
  /// In en, this message translates to:
  /// **'Approve'**
  String get approve;

  /// Reject action
  ///
  /// In en, this message translates to:
  /// **'Reject'**
  String get reject;

  /// Dialog title for reject reason
  ///
  /// In en, this message translates to:
  /// **'Rejection reason'**
  String get rejectionReason;

  /// Empty approvals queue
  ///
  /// In en, this message translates to:
  /// **'Nothing to approve'**
  String get nothingToApprove;

  /// Theme selector label
  ///
  /// In en, this message translates to:
  /// **'Theme'**
  String get theme;

  /// Follow system theme
  ///
  /// In en, this message translates to:
  /// **'System'**
  String get systemTheme;

  /// English language name
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get english;

  /// Arabic language name
  ///
  /// In en, this message translates to:
  /// **'العربية'**
  String get arabic;

  /// Indonesian language name
  ///
  /// In en, this message translates to:
  /// **'Bahasa Indonesia'**
  String get indonesian;

  /// No description provided for @groupOperations.
  ///
  /// In en, this message translates to:
  /// **'Operations'**
  String get groupOperations;

  /// No description provided for @groupHr.
  ///
  /// In en, this message translates to:
  /// **'HR'**
  String get groupHr;

  /// No description provided for @groupFinance.
  ///
  /// In en, this message translates to:
  /// **'Finance'**
  String get groupFinance;

  /// No description provided for @groupSuppliers.
  ///
  /// In en, this message translates to:
  /// **'Suppliers'**
  String get groupSuppliers;

  /// No description provided for @groupInventory.
  ///
  /// In en, this message translates to:
  /// **'Inventory'**
  String get groupInventory;

  /// No description provided for @groupCrm.
  ///
  /// In en, this message translates to:
  /// **'CRM'**
  String get groupCrm;

  /// No description provided for @groupPos.
  ///
  /// In en, this message translates to:
  /// **'POS'**
  String get groupPos;

  /// No description provided for @reportTrialBalance.
  ///
  /// In en, this message translates to:
  /// **'Trial Balance'**
  String get reportTrialBalance;

  /// No description provided for @reportProfitLoss.
  ///
  /// In en, this message translates to:
  /// **'P & L'**
  String get reportProfitLoss;

  /// No description provided for @reportBalanceSheet.
  ///
  /// In en, this message translates to:
  /// **'Balance Sheet'**
  String get reportBalanceSheet;

  /// No description provided for @reportCashFlow.
  ///
  /// In en, this message translates to:
  /// **'Cash Flow'**
  String get reportCashFlow;

  /// No description provided for @reportSalesSummary.
  ///
  /// In en, this message translates to:
  /// **'Sales Summary'**
  String get reportSalesSummary;

  /// No description provided for @reportTopProducts.
  ///
  /// In en, this message translates to:
  /// **'Top Products'**
  String get reportTopProducts;

  /// No description provided for @reportTopCustomers.
  ///
  /// In en, this message translates to:
  /// **'Top Customers'**
  String get reportTopCustomers;

  /// No description provided for @reportArAging.
  ///
  /// In en, this message translates to:
  /// **'AR Aging'**
  String get reportArAging;

  /// No description provided for @reportApAging.
  ///
  /// In en, this message translates to:
  /// **'AP Aging'**
  String get reportApAging;

  /// No description provided for @approvalsLeaves.
  ///
  /// In en, this message translates to:
  /// **'Leaves'**
  String get approvalsLeaves;

  /// No description provided for @approvalsExpenses.
  ///
  /// In en, this message translates to:
  /// **'Expenses'**
  String get approvalsExpenses;

  /// No description provided for @approvalsTasks.
  ///
  /// In en, this message translates to:
  /// **'Tasks'**
  String get approvalsTasks;

  /// No description provided for @today.
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get today;

  /// No description provided for @pendingApprovalsTitle.
  ///
  /// In en, this message translates to:
  /// **'Pending approvals'**
  String get pendingApprovalsTitle;

  /// No description provided for @alertsOperations.
  ///
  /// In en, this message translates to:
  /// **'Alerts & operations'**
  String get alertsOperations;

  /// Section heading for n-day performance KPIs
  ///
  /// In en, this message translates to:
  /// **'{days}-day performance'**
  String periodPerformance(int days);

  /// No description provided for @recentActivity.
  ///
  /// In en, this message translates to:
  /// **'Recent activity'**
  String get recentActivity;

  /// No description provided for @unableToLoadDashboard.
  ///
  /// In en, this message translates to:
  /// **'Unable to load dashboard'**
  String get unableToLoadDashboard;

  /// No description provided for @goodMorning.
  ///
  /// In en, this message translates to:
  /// **'Good morning'**
  String get goodMorning;

  /// No description provided for @goodAfternoon.
  ///
  /// In en, this message translates to:
  /// **'Good afternoon'**
  String get goodAfternoon;

  /// No description provided for @goodEvening.
  ///
  /// In en, this message translates to:
  /// **'Good evening'**
  String get goodEvening;

  /// No description provided for @kpiTodayRevenue.
  ///
  /// In en, this message translates to:
  /// **'Today revenue'**
  String get kpiTodayRevenue;

  /// No description provided for @kpiCashInHand.
  ///
  /// In en, this message translates to:
  /// **'Cash in hand'**
  String get kpiCashInHand;

  /// No description provided for @kpiThisMonthRevenue.
  ///
  /// In en, this message translates to:
  /// **'This month revenue'**
  String get kpiThisMonthRevenue;

  /// No description provided for @kpiThisMonthExpenses.
  ///
  /// In en, this message translates to:
  /// **'This month expenses'**
  String get kpiThisMonthExpenses;

  /// No description provided for @kpiPurchaseOrders.
  ///
  /// In en, this message translates to:
  /// **'Purchase orders'**
  String get kpiPurchaseOrders;

  /// No description provided for @kpiOverdueInvoices.
  ///
  /// In en, this message translates to:
  /// **'Overdue invoices'**
  String get kpiOverdueInvoices;

  /// No description provided for @kpiLowStockItems.
  ///
  /// In en, this message translates to:
  /// **'Low stock items'**
  String get kpiLowStockItems;

  /// No description provided for @kpiOpenPosSessions.
  ///
  /// In en, this message translates to:
  /// **'Open POS sessions'**
  String get kpiOpenPosSessions;

  /// No description provided for @kpiRevenue.
  ///
  /// In en, this message translates to:
  /// **'Revenue'**
  String get kpiRevenue;

  /// No description provided for @kpiExpenses.
  ///
  /// In en, this message translates to:
  /// **'Expenses'**
  String get kpiExpenses;

  /// No description provided for @kpiNet.
  ///
  /// In en, this message translates to:
  /// **'Net'**
  String get kpiNet;

  /// No description provided for @kpiPaymentsReceived.
  ///
  /// In en, this message translates to:
  /// **'Payments received'**
  String get kpiPaymentsReceived;

  /// No description provided for @kpiInvoicesIssued.
  ///
  /// In en, this message translates to:
  /// **'Invoices issued'**
  String get kpiInvoicesIssued;

  /// No description provided for @kpiNewCustomers.
  ///
  /// In en, this message translates to:
  /// **'New customers'**
  String get kpiNewCustomers;

  /// No description provided for @kpiNewLeads.
  ///
  /// In en, this message translates to:
  /// **'New leads'**
  String get kpiNewLeads;

  /// No description provided for @approvalsPos.
  ///
  /// In en, this message translates to:
  /// **'POs'**
  String get approvalsPos;

  /// No description provided for @approvalsQuotes.
  ///
  /// In en, this message translates to:
  /// **'Quotes'**
  String get approvalsQuotes;

  /// No description provided for @approvalsSupplierInvoices.
  ///
  /// In en, this message translates to:
  /// **'Supplier invoices'**
  String get approvalsSupplierInvoices;

  /// No description provided for @noItems.
  ///
  /// In en, this message translates to:
  /// **'No items'**
  String get noItems;

  /// No description provided for @showAll.
  ///
  /// In en, this message translates to:
  /// **'Show all'**
  String get showAll;

  /// No description provided for @showUnreadOnly.
  ///
  /// In en, this message translates to:
  /// **'Show unread'**
  String get showUnreadOnly;

  /// No description provided for @company.
  ///
  /// In en, this message translates to:
  /// **'Company'**
  String get company;

  /// No description provided for @nameField.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get nameField;

  /// No description provided for @arabicName.
  ///
  /// In en, this message translates to:
  /// **'Arabic name'**
  String get arabicName;

  /// No description provided for @aiEnabled.
  ///
  /// In en, this message translates to:
  /// **'AI enabled'**
  String get aiEnabled;

  /// No description provided for @employeeProfile.
  ///
  /// In en, this message translates to:
  /// **'Employee profile'**
  String get employeeProfile;

  /// No description provided for @jobTitle.
  ///
  /// In en, this message translates to:
  /// **'Job title'**
  String get jobTitle;

  /// No description provided for @role.
  ///
  /// In en, this message translates to:
  /// **'Role'**
  String get role;

  /// No description provided for @requiredField.
  ///
  /// In en, this message translates to:
  /// **'Required'**
  String get requiredField;

  /// No description provided for @passwordTooShort.
  ///
  /// In en, this message translates to:
  /// **'At least 8 characters'**
  String get passwordTooShort;

  /// No description provided for @passwordsDoNotMatch.
  ///
  /// In en, this message translates to:
  /// **'Passwords differ'**
  String get passwordsDoNotMatch;

  /// No description provided for @updatePassword.
  ///
  /// In en, this message translates to:
  /// **'Update password'**
  String get updatePassword;

  /// No description provided for @welcomeBack.
  ///
  /// In en, this message translates to:
  /// **'Welcome back'**
  String get welcomeBack;

  /// No description provided for @signInToContinue.
  ///
  /// In en, this message translates to:
  /// **'Sign in to continue to Intara Group'**
  String get signInToContinue;

  /// No description provided for @signIn.
  ///
  /// In en, this message translates to:
  /// **'Sign In'**
  String get signIn;

  /// No description provided for @enterYourEmail.
  ///
  /// In en, this message translates to:
  /// **'Enter your email'**
  String get enterYourEmail;

  /// No description provided for @enterYourPassword.
  ///
  /// In en, this message translates to:
  /// **'Enter your password'**
  String get enterYourPassword;

  /// No description provided for @termsAndPrivacy.
  ///
  /// In en, this message translates to:
  /// **'By signing in you agree to the Terms & Privacy Policy.'**
  String get termsAndPrivacy;

  /// No description provided for @kuraimiTagline.
  ///
  /// In en, this message translates to:
  /// **'Your workplace, in one app.'**
  String get kuraimiTagline;
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
