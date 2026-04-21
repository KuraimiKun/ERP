import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// ── Meridian design tokens ───────────────────────────────────────────────────

class MColors {
  // Light palette
  static const primary = Color(0xFF3730A3);
  static const primaryDeep = Color(0xFF2A2280);
  static const primarySoft = Color(0xFFEEF0FB);
  static const accent = Color(0xFF0891B2);
  static const accentSoft = Color(0xFFE0F4F8);
  static const bg = Color(0xFFF1F5F9);
  static const surface = Color(0xFFFFFFFF);
  static const surfaceAlt = Color(0xFFF8FAFC);
  static const border = Color(0xFFE2E8F0);
  static const borderSoft = Color(0xFFEEF2F6);
  static const text = Color(0xFF0F172A);
  static const textMid = Color(0xFF334155);
  static const textSub = Color(0xFF64748B);
  static const textFaint = Color(0xFF94A3B8);
  static const success = Color(0xFF059669);
  static const successSoft = Color(0xFFD1FAE5);
  static const warning = Color(0xFFD97706);
  static const warningSoft = Color(0xFFFEF3C7);
  static const error = Color(0xFFE11D48);
  static const errorSoft = Color(0xFFFEE2E2);
  static const info = Color(0xFF2563EB);
  static const infoSoft = Color(0xFFDBEAFE);
  static const purple = Color(0xFF7C3AED);
  static const purpleSoft = Color(0xFFEDE9FE);

  // Dark palette
  static const darkPrimary = Color(0xFF6366F1);
  static const darkPrimaryDeep = Color(0xFF4F46E5);
  static const darkPrimarySoft = Color(0xFF1E1B4B);
  static const darkAccent = Color(0xFF22D3EE);
  static const darkAccentSoft = Color(0xFF164E63);
  static const darkBg = Color(0xFF0B1220);
  static const darkSurface = Color(0xFF111827);
  static const darkSurfaceAlt = Color(0xFF1F2937);
  static const darkBorder = Color(0xFF1F2937);
  static const darkText = Color(0xFFF8FAFC);
  static const darkTextMid = Color(0xFFCBD5E1);
  static const darkTextSub = Color(0xFF94A3B8);
  static const darkTextFaint = Color(0xFF64748B);
  static const darkSuccess = Color(0xFF34D399);
  static const darkSuccessSoft = Color(0xFF064E3B);
  static const darkWarning = Color(0xFFFBBF24);
  static const darkWarningSoft = Color(0xFF78350F);
  static const darkError = Color(0xFFFB7185);
  static const darkErrorSoft = Color(0xFF7F1D1D);
  static const darkInfo = Color(0xFF60A5FA);
  static const darkInfoSoft = Color(0xFF1E3A8A);
  static const darkPurple = Color(0xFFA78BFA);
  static const darkPurpleSoft = Color(0xFF3B0764);
}

// ── Semantic colour extension ────────────────────────────────────────────────

class AppSemanticColors extends ThemeExtension<AppSemanticColors> {
  final Color success;
  final Color successContainer;
  final Color warning;
  final Color warningContainer;
  final Color info;
  final Color infoContainer;
  final Color danger;
  final Color dangerContainer;
  final Color purple;
  final Color purpleContainer;
  final Color accent;
  final Color accentContainer;
  final Color textMuted;
  final Color textSub;
  final Color textFaint;
  final Color border;
  final Color borderSoft;
  final Color surfaceAlt;

  const AppSemanticColors({
    required this.success,
    required this.successContainer,
    required this.warning,
    required this.warningContainer,
    required this.info,
    required this.infoContainer,
    required this.danger,
    required this.dangerContainer,
    required this.purple,
    required this.purpleContainer,
    required this.accent,
    required this.accentContainer,
    required this.textMuted,
    required this.textSub,
    required this.textFaint,
    required this.border,
    required this.borderSoft,
    required this.surfaceAlt,
  });

  static const light = AppSemanticColors(
    success: MColors.success,
    successContainer: MColors.successSoft,
    warning: MColors.warning,
    warningContainer: MColors.warningSoft,
    info: MColors.info,
    infoContainer: MColors.infoSoft,
    danger: MColors.error,
    dangerContainer: MColors.errorSoft,
    purple: MColors.purple,
    purpleContainer: MColors.purpleSoft,
    accent: MColors.accent,
    accentContainer: MColors.accentSoft,
    textMuted: MColors.textSub,
    textSub: MColors.textSub,
    textFaint: MColors.textFaint,
    border: MColors.border,
    borderSoft: MColors.borderSoft,
    surfaceAlt: MColors.surfaceAlt,
  );

  static const dark = AppSemanticColors(
    success: MColors.darkSuccess,
    successContainer: MColors.darkSuccessSoft,
    warning: MColors.darkWarning,
    warningContainer: MColors.darkWarningSoft,
    info: MColors.darkInfo,
    infoContainer: MColors.darkInfoSoft,
    danger: MColors.darkError,
    dangerContainer: MColors.darkErrorSoft,
    purple: MColors.darkPurple,
    purpleContainer: MColors.darkPurpleSoft,
    accent: MColors.darkAccent,
    accentContainer: MColors.darkAccentSoft,
    textMuted: MColors.darkTextSub,
    textSub: MColors.darkTextSub,
    textFaint: MColors.darkTextFaint,
    border: MColors.darkBorder,
    borderSoft: MColors.darkBorder,
    surfaceAlt: MColors.darkSurfaceAlt,
  );

  @override
  AppSemanticColors copyWith({
    Color? success, Color? successContainer,
    Color? warning, Color? warningContainer,
    Color? info, Color? infoContainer,
    Color? danger, Color? dangerContainer,
    Color? purple, Color? purpleContainer,
    Color? accent, Color? accentContainer,
    Color? textMuted, Color? textSub, Color? textFaint,
    Color? border, Color? borderSoft, Color? surfaceAlt,
  }) => AppSemanticColors(
    success: success ?? this.success,
    successContainer: successContainer ?? this.successContainer,
    warning: warning ?? this.warning,
    warningContainer: warningContainer ?? this.warningContainer,
    info: info ?? this.info,
    infoContainer: infoContainer ?? this.infoContainer,
    danger: danger ?? this.danger,
    dangerContainer: dangerContainer ?? this.dangerContainer,
    purple: purple ?? this.purple,
    purpleContainer: purpleContainer ?? this.purpleContainer,
    accent: accent ?? this.accent,
    accentContainer: accentContainer ?? this.accentContainer,
    textMuted: textMuted ?? this.textMuted,
    textSub: textSub ?? this.textSub,
    textFaint: textFaint ?? this.textFaint,
    border: border ?? this.border,
    borderSoft: borderSoft ?? this.borderSoft,
    surfaceAlt: surfaceAlt ?? this.surfaceAlt,
  );

  @override
  AppSemanticColors lerp(AppSemanticColors? other, double t) {
    if (other is! AppSemanticColors) return this;
    return AppSemanticColors(
      success: Color.lerp(success, other.success, t)!,
      successContainer: Color.lerp(successContainer, other.successContainer, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningContainer: Color.lerp(warningContainer, other.warningContainer, t)!,
      info: Color.lerp(info, other.info, t)!,
      infoContainer: Color.lerp(infoContainer, other.infoContainer, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
      dangerContainer: Color.lerp(dangerContainer, other.dangerContainer, t)!,
      purple: Color.lerp(purple, other.purple, t)!,
      purpleContainer: Color.lerp(purpleContainer, other.purpleContainer, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
      accentContainer: Color.lerp(accentContainer, other.accentContainer, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      textSub: Color.lerp(textSub, other.textSub, t)!,
      textFaint: Color.lerp(textFaint, other.textFaint, t)!,
      border: Color.lerp(border, other.border, t)!,
      borderSoft: Color.lerp(borderSoft, other.borderSoft, t)!,
      surfaceAlt: Color.lerp(surfaceAlt, other.surfaceAlt, t)!,
    );
  }
}

// ── App theme ────────────────────────────────────────────────────────────────

class AppTheme {
  AppTheme._();

  static AppSemanticColors semantics(BuildContext context) =>
      Theme.of(context).extension<AppSemanticColors>()!;

  static TextTheme _textTheme(TextTheme base) => GoogleFonts.interTextTheme(base);

  static ThemeData get lightTheme {
    const cs = ColorScheme(
      brightness: Brightness.light,
      primary: MColors.primary,
      onPrimary: Colors.white,
      primaryContainer: MColors.primarySoft,
      onPrimaryContainer: MColors.primaryDeep,
      secondary: MColors.accent,
      onSecondary: Colors.white,
      secondaryContainer: MColors.accentSoft,
      onSecondaryContainer: MColors.accent,
      tertiary: MColors.purple,
      onTertiary: Colors.white,
      tertiaryContainer: MColors.purpleSoft,
      onTertiaryContainer: MColors.purple,
      error: MColors.error,
      onError: Colors.white,
      errorContainer: MColors.errorSoft,
      onErrorContainer: MColors.error,
      surface: MColors.surface,
      onSurface: MColors.text,
      surfaceContainerLowest: MColors.surface,
      surfaceContainerLow: MColors.surfaceAlt,
      surfaceContainer: MColors.surfaceAlt,
      surfaceContainerHigh: MColors.bg,
      outline: MColors.border,
      outlineVariant: MColors.borderSoft,
      inverseSurface: MColors.text,
      onInverseSurface: MColors.surface,
    );

    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      colorScheme: cs,
      scaffoldBackgroundColor: MColors.bg,
      extensions: const [AppSemanticColors.light],
      textTheme: _textTheme(base.textTheme),
      appBarTheme: AppBarTheme(
        backgroundColor: MColors.surface,
        foregroundColor: MColors.text,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        titleTextStyle: GoogleFonts.inter(
          fontSize: 16, fontWeight: FontWeight.w700, color: MColors.text,
          letterSpacing: -0.3,
        ),
        iconTheme: const IconThemeData(color: MColors.text),
      ),
      cardTheme: CardThemeData(
        color: MColors.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: MColors.border, width: 0.5),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: MColors.primary,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 54),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: MColors.primary,
          side: const BorderSide(color: MColors.primary),
          minimumSize: const Size(double.infinity, 52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: MColors.surfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: MColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: MColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: MColors.primary, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: MColors.error),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        labelStyle: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: MColors.textSub),
        hintStyle: GoogleFonts.inter(fontSize: 14, color: MColors.textFaint),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: MColors.primary,
        foregroundColor: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: MColors.surface,
        selectedItemColor: MColors.primary,
        unselectedItemColor: MColors.textFaint,
        elevation: 0,
        type: BottomNavigationBarType.fixed,
      ),
      dividerTheme: const DividerThemeData(color: MColors.border, thickness: 0.5),
      chipTheme: ChipThemeData(
        backgroundColor: MColors.surfaceAlt,
        selectedColor: MColors.primarySoft,
        labelStyle: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        side: const BorderSide(color: MColors.border, width: 0.5),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      listTileTheme: const ListTileThemeData(
        contentPadding: EdgeInsets.symmetric(horizontal: 16),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: MColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        elevation: 0,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: MColors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        elevation: 0,
      ),
    );
  }

  static ThemeData get darkTheme {
    const cs = ColorScheme(
      brightness: Brightness.dark,
      primary: MColors.darkPrimary,
      onPrimary: Colors.white,
      primaryContainer: MColors.darkPrimarySoft,
      onPrimaryContainer: MColors.darkPrimary,
      secondary: MColors.darkAccent,
      onSecondary: MColors.darkBg,
      secondaryContainer: MColors.darkAccentSoft,
      onSecondaryContainer: MColors.darkAccent,
      tertiary: MColors.darkPurple,
      onTertiary: Colors.white,
      tertiaryContainer: MColors.darkPurpleSoft,
      onTertiaryContainer: MColors.darkPurple,
      error: MColors.darkError,
      onError: MColors.darkBg,
      errorContainer: MColors.darkErrorSoft,
      onErrorContainer: MColors.darkError,
      surface: MColors.darkSurface,
      onSurface: MColors.darkText,
      surfaceContainerLowest: MColors.darkBg,
      surfaceContainerLow: MColors.darkSurface,
      surfaceContainer: MColors.darkSurfaceAlt,
      surfaceContainerHigh: MColors.darkSurfaceAlt,
      outline: MColors.darkBorder,
      outlineVariant: MColors.darkBorder,
      inverseSurface: MColors.darkText,
      onInverseSurface: MColors.darkBg,
    );

    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      colorScheme: cs,
      scaffoldBackgroundColor: MColors.darkBg,
      extensions: const [AppSemanticColors.dark],
      textTheme: _textTheme(base.textTheme).apply(
        bodyColor: MColors.darkText,
        displayColor: MColors.darkText,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: MColors.darkSurface,
        foregroundColor: MColors.darkText,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        titleTextStyle: GoogleFonts.inter(
          fontSize: 16, fontWeight: FontWeight.w700, color: MColors.darkText,
          letterSpacing: -0.3,
        ),
        iconTheme: const IconThemeData(color: MColors.darkText),
      ),
      cardTheme: CardThemeData(
        color: MColors.darkSurface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: MColors.darkBorder, width: 0.5),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: MColors.darkPrimary,
          foregroundColor: Colors.white,
          minimumSize: const Size(double.infinity, 54),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          textStyle: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: MColors.darkPrimary,
          side: const BorderSide(color: MColors.darkPrimary),
          minimumSize: const Size(double.infinity, 52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: MColors.darkSurfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: MColors.darkBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: MColors.darkBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: MColors.darkPrimary, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: MColors.darkError),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        labelStyle: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: MColors.darkTextSub),
        hintStyle: GoogleFonts.inter(fontSize: 14, color: MColors.darkTextFaint),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: MColors.darkPrimary,
        foregroundColor: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: MColors.darkSurface,
        selectedItemColor: MColors.darkPrimary,
        unselectedItemColor: MColors.darkTextFaint,
        elevation: 0,
        type: BottomNavigationBarType.fixed,
      ),
      dividerTheme: const DividerThemeData(color: MColors.darkBorder, thickness: 0.5),
      chipTheme: ChipThemeData(
        backgroundColor: MColors.darkSurfaceAlt,
        selectedColor: MColors.darkPrimarySoft,
        labelStyle: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        side: const BorderSide(color: MColors.darkBorder, width: 0.5),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      listTileTheme: const ListTileThemeData(
        contentPadding: EdgeInsets.symmetric(horizontal: 16),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: MColors.darkSurfaceAlt,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        elevation: 0,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: MColors.darkSurface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        elevation: 0,
      ),
    );
  }
}
