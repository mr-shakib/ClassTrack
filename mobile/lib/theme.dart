import 'package:flutter/material.dart';

/// The ClassTrack palette, as the web app defines it in `globals.css`.
///
/// Status colours carry meaning, so they are defined once here and never
/// re-picked per screen. MISSED (`bad`) and NOT_CHECKED (`gap`) are different
/// hues on purpose: one is a teacher-side problem, the other a staff-side one.
///
/// Each status has three tones: the colour for text and icons (`ok`), a tint
/// for backgrounds (`okSoft`), and a solid fill that carries white text
/// (`okSolid`). In light mode the first and last are the same.
@immutable
class Palette extends ThemeExtension<Palette> {
  const Palette({
    required this.ink,
    required this.inkSoft,
    required this.inkFaint,
    required this.line,
    required this.surface,
    required this.canvas,
    required this.brand,
    required this.brandSoft,
    required this.brandSolid,
    required this.ok,
    required this.okSoft,
    required this.okSolid,
    required this.warn,
    required this.warnSoft,
    required this.warnSolid,
    required this.bad,
    required this.badSoft,
    required this.badSolid,
    required this.gap,
    required this.gapSoft,
    required this.gapSolid,
    required this.info,
    required this.infoSoft,
    required this.infoSolid,
  });

  final Color ink, inkSoft, inkFaint, line, surface, canvas;
  final Color brand, brandSoft, brandSolid;

  /// The class ran.
  final Color ok, okSoft, okSolid;

  /// The teacher was late.
  final Color warn, warnSoft, warnSolid;

  /// The teacher was absent: a teacher-side problem.
  final Color bad, badSoft, badSolid;

  /// Nobody checked: a staff-side problem.
  final Color gap, gapSoft, gapSolid;

  /// Recovery in progress: makeups and reschedules.
  final Color info, infoSoft, infoSolid;

  static const light = Palette(
    ink: Color(0xFF0F172A),
    inkSoft: Color(0xFF475569),
    inkFaint: Color(0xFF94A3B8),
    line: Color(0xFFE2E8F0),
    surface: Color(0xFFFFFFFF),
    canvas: Color(0xFFF6F8FB),
    brand: Color(0xFF1D4ED8),
    brandSoft: Color(0xFFEEF2FF),
    brandSolid: Color(0xFF1D4ED8),
    ok: Color(0xFF047857),
    okSoft: Color(0xFFECFDF5),
    okSolid: Color(0xFF047857),
    warn: Color(0xFFB45309),
    warnSoft: Color(0xFFFFFBEB),
    warnSolid: Color(0xFFB45309),
    bad: Color(0xFFB91C1C),
    badSoft: Color(0xFFFEF2F2),
    badSolid: Color(0xFFB91C1C),
    gap: Color(0xFF6D28D9),
    gapSoft: Color(0xFFF5F3FF),
    gapSolid: Color(0xFF6D28D9),
    info: Color(0xFF0E7490),
    infoSoft: Color(0xFFECFEFF),
    infoSolid: Color(0xFF0E7490),
  );

  static const dark = Palette(
    ink: Color(0xFFE6EBF5),
    inkSoft: Color(0xFFA9B4C8),
    inkFaint: Color(0xFF6B7891),
    line: Color(0xFF243049),
    surface: Color(0xFF131C2E),
    canvas: Color(0xFF0B1220),
    brand: Color(0xFF8DA8FF),
    brandSoft: Color(0xFF1A2550),
    brandSolid: Color(0xFF2F5FE6),
    ok: Color(0xFF6EE7B7),
    okSoft: Color(0xFF0B2A22),
    okSolid: Color(0xFF05845F),
    warn: Color(0xFFFCD34D),
    warnSoft: Color(0xFF2E2210),
    warnSolid: Color(0xFFB45309),
    bad: Color(0xFFFCA5A5),
    badSoft: Color(0xFF341416),
    badSolid: Color(0xFFC62828),
    gap: Color(0xFFC4B5FD),
    gapSoft: Color(0xFF221A3D),
    gapSolid: Color(0xFF6D28D9),
    info: Color(0xFF67E8F9),
    infoSoft: Color(0xFF0B2A33),
    infoSolid: Color(0xFF0E7490),
  );

  @override
  Palette copyWith() => this;

  @override
  Palette lerp(ThemeExtension<Palette>? other, double t) {
    if (other is! Palette) return this;
    Color l(Color a, Color b) => Color.lerp(a, b, t)!;
    return Palette(
      ink: l(ink, other.ink),
      inkSoft: l(inkSoft, other.inkSoft),
      inkFaint: l(inkFaint, other.inkFaint),
      line: l(line, other.line),
      surface: l(surface, other.surface),
      canvas: l(canvas, other.canvas),
      brand: l(brand, other.brand),
      brandSoft: l(brandSoft, other.brandSoft),
      brandSolid: l(brandSolid, other.brandSolid),
      ok: l(ok, other.ok),
      okSoft: l(okSoft, other.okSoft),
      okSolid: l(okSolid, other.okSolid),
      warn: l(warn, other.warn),
      warnSoft: l(warnSoft, other.warnSoft),
      warnSolid: l(warnSolid, other.warnSolid),
      bad: l(bad, other.bad),
      badSoft: l(badSoft, other.badSoft),
      badSolid: l(badSolid, other.badSolid),
      gap: l(gap, other.gap),
      gapSoft: l(gapSoft, other.gapSoft),
      gapSolid: l(gapSolid, other.gapSolid),
      info: l(info, other.info),
      infoSoft: l(infoSoft, other.infoSoft),
      infoSolid: l(infoSolid, other.infoSolid),
    );
  }
}

extension PaletteOf on BuildContext {
  Palette get palette => Theme.of(this).extension<Palette>()!;
}

/// Figures that line up in columns: times, counts, room numbers.
const tabular = [FontFeature.tabularFigures()];

ThemeData buildTheme(Brightness brightness) {
  final p = brightness == Brightness.dark ? Palette.dark : Palette.light;
  final scheme = ColorScheme.fromSeed(
    seedColor: Palette.light.brand,
    brightness: brightness,
  ).copyWith(
    primary: p.brandSolid,
    onPrimary: Colors.white,
    primaryContainer: p.brandSoft,
    onPrimaryContainer: p.brand,
    secondary: p.info,
    error: p.bad,
    errorContainer: p.badSoft,
    onErrorContainer: p.bad,
    surface: p.surface,
    onSurface: p.ink,
    onSurfaceVariant: p.inkSoft,
    outline: p.line,
    outlineVariant: p.line,
    surfaceContainerLowest: p.surface,
    surfaceContainerLow: p.surface,
    surfaceContainer: p.surface,
    surfaceContainerHigh: p.surface,
    surfaceContainerHighest: p.canvas,
  );

  final base = ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    fontFamily: 'Inter',
    scaffoldBackgroundColor: p.canvas,
    extensions: [p],
  );

  final text = base.textTheme.apply(bodyColor: p.ink, displayColor: p.ink);
  final radius = BorderRadius.circular(14);

  return base.copyWith(
    textTheme: text.copyWith(
      headlineMedium: text.headlineMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.6),
      headlineSmall: text.headlineSmall?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.4),
      titleLarge: text.titleLarge?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.2),
      titleMedium: text.titleMedium?.copyWith(fontWeight: FontWeight.w700),
      bodyLarge: text.bodyLarge?.copyWith(height: 1.4),
      bodyMedium: text.bodyMedium?.copyWith(height: 1.4, color: p.inkSoft),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: p.canvas,
      foregroundColor: p.ink,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontFamily: 'Inter',
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: p.ink,
        letterSpacing: -0.2,
      ),
    ),
    dividerTheme: DividerThemeData(color: p.line, thickness: 1, space: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: p.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      hintStyle: TextStyle(color: p.inkFaint, fontWeight: FontWeight.w400),
      labelStyle: TextStyle(color: p.inkSoft),
      border: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: p.line, width: 1.5)),
      enabledBorder: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: p.line, width: 1.5)),
      focusedBorder: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: p.brand, width: 2)),
      errorBorder: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: p.bad, width: 1.5)),
      focusedErrorBorder: OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: p.bad, width: 2)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(64, 54),
        shape: RoundedRectangleBorder(borderRadius: radius),
        textStyle: const TextStyle(fontFamily: 'Inter', fontSize: 16, fontWeight: FontWeight.w700),
        disabledBackgroundColor: p.line,
        disabledForegroundColor: p.inkFaint,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(64, 52),
        foregroundColor: p.brand,
        side: BorderSide(color: p.line, width: 1.5),
        shape: RoundedRectangleBorder(borderRadius: radius),
        textStyle: const TextStyle(fontFamily: 'Inter', fontSize: 16, fontWeight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: p.brand,
        minimumSize: const Size(48, 44),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        textStyle: const TextStyle(fontFamily: 'Inter', fontSize: 15, fontWeight: FontWeight.w700),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: p.surface,
      surfaceTintColor: Colors.transparent,
      indicatorColor: p.brandSoft,
      elevation: 0,
      height: 68,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (s) => TextStyle(
          fontFamily: 'Inter',
          fontSize: 12.5,
          fontWeight: s.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          color: s.contains(WidgetState.selected) ? p.brand : p.inkSoft,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (s) => IconThemeData(color: s.contains(WidgetState.selected) ? p.brand : p.inkSoft),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: p.ink,
      contentTextStyle: TextStyle(fontFamily: 'Inter', color: p.canvas, fontSize: 15),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: p.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: p.surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
    ),
    datePickerTheme: DatePickerThemeData(
      backgroundColor: p.surface,
      surfaceTintColor: Colors.transparent,
    ),
    timePickerTheme: TimePickerThemeData(
      backgroundColor: p.surface,
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(color: p.brand),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? Colors.white : null),
      trackColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? p.brandSolid : null),
    ),
    listTileTheme: ListTileThemeData(
      iconColor: p.inkSoft,
      titleTextStyle: TextStyle(fontFamily: 'Inter', fontSize: 16, fontWeight: FontWeight.w600, color: p.ink),
      subtitleTextStyle: TextStyle(fontFamily: 'Inter', fontSize: 14, color: p.inkSoft),
    ),
  );
}
