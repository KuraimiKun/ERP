import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// ---------------------------------------------------------------------------
// Semantic colours (success, warning, info, danger, muted text)
// exposed via ThemeExtension so they adapt to light / dark automatically.
// Usage:  AppTheme.semantics(context).success
// ---------------------------------------------------------------------------

class AppSemanticColors extends ThemeExtension<AppSemanticColors> {
  final Color success;
  final Color successContainer;
  final Color onSuccessContainer;
  final Color warning;
  final Color warningContainer;
  final Color onWarningContainer;
  final Color info;
  final Color infoContainer;
  final Color onInfoContainer;
  final Color danger;
  final Color dangerContainer;
  final Color onDangerContainer;
  final Color textMuted;

  const AppSemanticColors({
    required this.success,
    required this.successContainer,
    required this.onSuccessContainer,
    required this.warning,
    required this.warningContainer,
    required this.onWarningContainer,
    required this.info,
    required this.infoContainer,
    required this.onInfoContainer,
    required this.danger,
    required this.dangerContainer,
    required this.onDangerContainer,
    required this.textMuted,
  });

  // Light-mode palette
  static const light = AppSemanticColors(
    success: Color(0xFF1B7D3A),
    successContainer: Color(0xFFD4EDDA),
    onSuccessContainer: Color(0xFF0A3D1A),
    warning: Color(0xFFC77700),
    warningContainer: Color(0xFFFFF3CD),
    onWarningContainer: Color(0xFF3D2E00),
    info: Color(0xFF2563A0),
    infoContainer: Color(0xFFD1ECF1),
    onInfoContainer: Color(0xFF0A2D45),
    danger: Color(0xFFBA1A1A),
    dangerContainer: Color(0xFFFDDEDE),
    onDangerContainer: Color(0xFF410002),
    textMuted: Color(0xFF6B7280),
  );

  // Dark-mode palette
  static const dark = AppSemanticColors(
    success: Color(0xFF6DD58C),
    successContainer: Color(0xFF1B3D2A),
    onSuccessContainer: Color(0xFFD4EDDA),
    warning: Color(0xFFFFB955),
    warningContainer: Color(0xFF3D2E00),
    onWarningContainer: Color(0xFFFFF3CD),
    info: Color(0xFF7CB8E4),
    infoContainer: Color(0xFF0A2D45),
    onInfoContainer: Color(0xFFD1ECF1),
    danger: Color(0xFFFFB4AB),
    dangerContainer: Color(0xFF3D0A0A),
    onDangerContainer: Color(0xFFFDDEDE),
    textMuted: Color(0xFF9CA3AF),
  );

  @override
  AppSemanticColors copyWith({
    Color? success,
    Color? successContainer,
    Color? onSuccessContainer,
    Color? warning,
    Color? warningContainer,
    Color? onWarningContainer,
    Color? info,
    Color? infoContainer,
    Color? onInfoContainer,
    Color? danger,
    Color? dangerContainer,
    Color? onDangerContainer,
    Color? textMuted,
  }) {
    return AppSemanticColors(
      success: success ?? this.success,
      successContainer: successContainer ?? this.successContainer,
      onSuccessContainer: onSuccessContainer ?? this.onSuccessContainer,
      warning: warning ?? this.warning,
      warningContainer: warningContainer ?? this.warningContainer,
      onWarningContainer: onWarningContainer ?? this.onWarningContainer,
      info: info ?? this.info,
      infoContainer: infoContainer ?? this.infoContainer,
      onInfoContainer: onInfoContainer ?? this.onInfoContainer,
      danger: danger ?? this.danger,
      dangerContainer: dangerContainer ?? this.dangerContainer,
      onDangerContainer: onDangerContainer ?? this.onDangerContainer,
      textMuted: textMuted ?? this.textMuted,
    );
  }

  @override
  AppSemanticColors lerp(AppSemanticColors? other, double t) {
    if (other is! AppSemanticColors) return this;
    return AppSemanticColors(
      success: Color.lerp(success, other.success, t)!,
      successContainer: Color.lerp(successContainer, other.successContainer, t)!,
      onSuccessContainer: Color.lerp(onSuccessContainer, other.onSuccessContainer, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningContainer: Color.lerp(warningContainer, other.warningContainer, t)!,
      onWarningContainer: Color.lerp(onWarningContainer, other.onWarningContainer, t)!,
      info: Color.lerp(info, other.info, t)!,
      infoContainer: Color.lerp(infoContainer, other.infoContainer, t)!,
      onInfoContainer: Color.lerp(onInfoContainer, other.onInfoContainer, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
      dangerContainer: Color.lerp(dangerContainer, other.dangerContainer, t)!,
      onDangerContainer: Color.lerp(onDangerContainer, other.onDangerContainer, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
    );
  }
}

// ---------------------------------------------------------------------------
// Main theme configuration
// ---------------------------------------------------------------------------

class AppTheme {
  AppTheme._();

  // ── Navy brand colours ──────────────────────────────────────────────────
  static const Color navy = Color(0xFF0F2644);
  static const Color navyLight = Color(0xFF1A3A5C);
  static const Color navyDark = Color(0xFF081A32);

  // ── Shortcut to access semantic colours from any widget ─────────────
  static AppSemanticColors semantics(BuildContext context) {
    return Theme.of(context).extension<AppSemanticColors>()!;
  }

  // ====================================================================
  // LIGHT THEME
  // ====================================================================
  static ThemeData get lightTheme {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: navy,
      brightness: Brightness.light,
      primary: navy,
      onPrimary: Colors.white,
      primaryContainer: const Color(0xFFD4E3F5),
      secondary: const Color(0xFF1A6B5A),
      secondaryContainer: const Color(0xFFC8EDE5),
      tertiary: const Color(0xFF5C548A),
      tertiaryContainer: const Color(0xFFE4DFFF),
      error: const Color(0xFFBA1A1A),
      errorContainer: const Color(0xFFFDDEDE),
      surface: const Color(0xFFF8F9FC),
      onSurface: const Color(0xFF1A1C1E),
      surfaceContainerLowest: Colors.white,
      surfaceContainerLow: const Color(0xFFF1F3F6),
      surfaceContainer: const Color(0xFFECEEF1),
      surfaceContainerHigh: const Color(0xFFE6E8EB),
      outline: const Color(0xFF73777F),
      outlineVariant: const Color(0xFFC3C7CF),
    );

    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      colorScheme: colorScheme,
      scaffoldBackgroundColor: colorScheme.surface,
      extensions: const [AppSemanticColors.light],
      appBarTheme: AppBarTheme(
        backgroundColor: navy,
        foregroundColor: Colors.white,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        titleTextStyle: GoogleFonts.tajawal(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: colorScheme.outlineVariant.withOpacity(0.5)),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: navy,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 48),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: GoogleFonts.tajawal(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: navy,
          side: const BorderSide(color: navy),
          minimumSize: const Size(double.infinity, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: navy, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.error),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      textTheme: GoogleFonts.tajawalTextTheme(base.textTheme),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: navy,
        foregroundColor: Colors.white,
        elevation: 2,
      ),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: Colors.white,
        selectedItemColor: navy,
        unselectedItemColor: colorScheme.onSurfaceVariant,
      ),
      dividerTheme: DividerThemeData(
        color: colorScheme.outlineVariant,
        thickness: 1,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: colorScheme.surfaceContainerLow,
        selectedColor: navy.withOpacity(0.12),
        labelStyle: GoogleFonts.tajawal(fontSize: 13),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        side: BorderSide.none,
      ),
      drawerTheme: DrawerThemeData(
        backgroundColor: colorScheme.surface,
      ),
      dialogTheme: DialogThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      listTileTheme: const ListTileThemeData(
        contentPadding: EdgeInsets.symmetric(horizontal: 16),
      ),
    );
  }

  // ====================================================================
  // DARK THEME
  // ====================================================================
  static ThemeData get darkTheme {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: navy,
      brightness: Brightness.dark,
      primary: const Color(0xFFA8C8E8),
      onPrimary: const Color(0xFF08243E),
      primaryContainer: const Color(0xFF1A3A5C),
      onPrimaryContainer: const Color(0xFFD4E3F5),
      secondary: const Color(0xFF8CD5C2),
      secondaryContainer: const Color(0xFF0F4D40),
      tertiary: const Color(0xFFC9C0F0),
      tertiaryContainer: const Color(0xFF443D6E),
      error: const Color(0xFFFFB4AB),
      errorContainer: const Color(0xFF93000A),
      surface: const Color(0xFF111318),
      onSurface: const Color(0xFFE2E2E6),
      surfaceContainerLowest: const Color(0xFF0C0E13),
      surfaceContainerLow: const Color(0xFF1A1C21),
      surfaceContainer: const Color(0xFF1D2024),
      surfaceContainerHigh: const Color(0xFF282A2F),
      surfaceContainerHighest: const Color(0xFF33353A),
      outline: const Color(0xFF8D9199),
      outlineVariant: const Color(0xFF43474E),
    );

    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      colorScheme: colorScheme,
      scaffoldBackgroundColor: colorScheme.surface,
      extensions: const [AppSemanticColors.dark],
      appBarTheme: AppBarTheme(
        backgroundColor: colorScheme.surfaceContainer,
        foregroundColor: colorScheme.onSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        titleTextStyle: GoogleFonts.tajawal(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: colorScheme.onSurface,
        ),
      ),
      cardTheme: CardThemeData(
        color: colorScheme.surfaceContainer,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: colorScheme.outlineVariant.withOpacity(0.4)),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: colorScheme.primary,
          foregroundColor: colorScheme.onPrimary,
          minimumSize: const Size(double.infinity, 48),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          textStyle: GoogleFonts.tajawal(
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: colorScheme.primary,
          side: BorderSide(color: colorScheme.primary),
          minimumSize: const Size(double.infinity, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colorScheme.surfaceContainerHigh,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: colorScheme.error),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      textTheme: GoogleFonts.tajawalTextTheme(base.textTheme).apply(
        bodyColor: colorScheme.onSurface,
        displayColor: colorScheme.onSurface,
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: colorScheme.primaryContainer,
        foregroundColor: colorScheme.onPrimaryContainer,
        elevation: 2,
      ),
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: colorScheme.surfaceContainer,
        selectedItemColor: colorScheme.primary,
        unselectedItemColor: colorScheme.onSurfaceVariant,
      ),
      dividerTheme: DividerThemeData(
        color: colorScheme.outlineVariant,
        thickness: 1,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: colorScheme.surfaceContainerHigh,
        selectedColor: colorScheme.primary.withOpacity(0.15),
        labelStyle: GoogleFonts.tajawal(fontSize: 13),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        side: BorderSide.none,
      ),
      drawerTheme: DrawerThemeData(
        backgroundColor: colorScheme.surfaceContainer,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: colorScheme.surfaceContainerHigh,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      listTileTheme: const ListTileThemeData(
        contentPadding: EdgeInsets.symmetric(horizontal: 16),
      ),
    );
  }
}
