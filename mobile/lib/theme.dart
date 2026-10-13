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
    required this.raised,
    required this.subtle,
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
    required this.heroFrom,
    required this.heroTo,
    required this.heroLine,
    required this.isDark,
  });

  final Color ink, inkSoft, inkFaint, line;

  /// The page, the cards on it, and what floats above them: sheets, dialogs.
  final Color canvas, surface, raised;

  /// A fill set into a card: a quote, a field, a neutral chip.
  final Color subtle;
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

  /// The one card a screen leads with: the class on now, the slot being checked.
  final Color heroFrom, heroTo, heroLine;
  final bool isDark;

  static const light = Palette(
    ink: Color(0xFF0F172A),
    inkSoft: Color(0xFF475569),
    inkFaint: Color(0xFF94A3B8),
    line: Color(0xFFE2E8F0),
    canvas: Color(0xFFF6F8FB),
    surface: Color(0xFFFFFFFF),
    raised: Color(0xFFFFFFFF),
    subtle: Color(0xFFF6F8FB),
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
    heroFrom: Color(0xFF1D4ED8),
    heroTo: Color(0xFF1563B0),
    heroLine: Color(0x00000000),
    isDark: false,
  );

  /// Charcoal, built in layers: a near-black page, cards a step lighter,
  /// sheets a step lighter again, divided by hairlines of white rather than
  /// grey. Status tints are the hue at low opacity, so they sit on any layer
  /// without turning muddy, and accents are softened so nothing glares.
  static const dark = Palette(
    ink: Color(0xFFEDEDEF),
    inkSoft: Color(0xFFA1A1AA),
    inkFaint: Color(0xFF6B6B75),
    line: Color(0x17FFFFFF),
    canvas: Color(0xFF0F0F10),
    surface: Color(0xFF18181B),
    raised: Color(0xFF222226),
    subtle: Color(0x0AFFFFFF),
    brand: Color(0xFF8EA8FF),
    brandSoft: Color(0x264C6FFF),
    brandSolid: Color(0xFF3B63EE),
    ok: Color(0xFF5CD49A),
    okSoft: Color(0x1F2FBF7A),
    okSolid: Color(0xFF0E7A55),
    warn: Color(0xFFF0B45A),
    warnSoft: Color(0x1FF0A030),
    warnSolid: Color(0xFFB5620E),
    bad: Color(0xFFF28C8C),
    badSoft: Color(0x1FF05252),
    badSolid: Color(0xFFC2362F),
    gap: Color(0xFFB6A3FF),
    gapSoft: Color(0x248B6CF6),
    gapSolid: Color(0xFF6A3FD9),
    info: Color(0xFF66CBDD),
    infoSoft: Color(0x1F2AB3CC),
    infoSolid: Color(0xFF0F7A91),
    heroFrom: Color(0xFF1E2A48),
    heroTo: Color(0xFF151C2B),
    heroLine: Color(0x1AFFFFFF),
    isDark: true,
  );

  /// The hero card's fill and edge.
  BoxDecoration hero({double radius = 24}) => BoxDecoration(
    borderRadius: BorderRadius.circular(radius),
    gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [heroFrom, heroTo]),
    border: Border.all(color: heroLine),
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
      canvas: l(canvas, other.canvas),
      surface: l(surface, other.surface),
      raised: l(raised, other.raised),
      subtle: l(subtle, other.subtle),
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
      heroFrom: l(heroFrom, other.heroFrom),
      heroTo: l(heroTo, other.heroTo),
      heroLine: l(heroLine, other.heroLine),
      isDark: t < 0.5 ? isDark : other.isDark,
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
  final dark = p.isDark;
  final scheme = ColorScheme.fromSeed(seedColor: Palette.light.brand, brightness: brightness).copyWith(
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
    surfaceContainer: p.raised,
    surfaceContainerHigh: p.raised,
    surfaceContainerHighest: dark ? p.raised : p.canvas,
    inverseSurface: dark ? p.raised : p.ink,
    onInverseSurface: dark ? p.ink : p.canvas,
  );

  final base = ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: scheme,
    fontFamily: 'Inter',
    scaffoldBackgroundColor: p.canvas,
    splashFactory: InkSparkle.splashFactory,
    extensions: [p],
  );

  final text = base.textTheme.apply(bodyColor: p.ink, displayColor: p.ink);
  final radius = BorderRadius.circular(14);
  OutlineInputBorder field(Color color, double width) => OutlineInputBorder(
    borderRadius: radius,
    borderSide: BorderSide(color: color, width: width),
  );

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
      // Set into the card on dark, rather than a second card on top of it.
      fillColor: dark ? p.subtle : p.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      hintStyle: TextStyle(color: p.inkFaint, fontWeight: FontWeight.w400),
      labelStyle: TextStyle(color: p.inkSoft),
      prefixIconColor: p.inkSoft,
      suffixIconColor: p.inkSoft,
      border: field(p.line, 1.5),
      enabledBorder: field(p.line, 1.5),
      focusedBorder: field(p.brand, 2),
      errorBorder: field(p.bad, 1.5),
      focusedErrorBorder: field(p.bad, 2),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(64, 54),
        shape: RoundedRectangleBorder(borderRadius: radius),
        textStyle: const TextStyle(fontFamily: 'Inter', fontSize: 16, fontWeight: FontWeight.w700),
        disabledBackgroundColor: dark ? p.subtle : p.line,
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
      // Dark: a step between the page and the cards, so the bar reads as chrome.
      backgroundColor: dark ? const Color(0xFF141416) : p.surface,
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
      backgroundColor: dark ? p.raised : p.ink,
      contentTextStyle: TextStyle(fontFamily: 'Inter', color: dark ? p.ink : p.canvas, fontSize: 15),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: dark ? BorderSide(color: p.line) : BorderSide.none,
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: p.raised,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(22),
        side: dark ? BorderSide(color: p.line) : BorderSide.none,
      ),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: p.raised,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      dragHandleColor: p.inkFaint,
    ),
    datePickerTheme: DatePickerThemeData(
      backgroundColor: p.raised,
      surfaceTintColor: Colors.transparent,
      headerForegroundColor: p.ink,
      dividerColor: p.line,
    ),
    timePickerTheme: TimePickerThemeData(
      backgroundColor: p.raised,
      dialBackgroundColor: dark ? p.subtle : p.canvas,
      hourMinuteColor: WidgetStateColor.resolveWith((s) => s.contains(WidgetState.selected) ? p.brandSoft : p.subtle),
      hourMinuteTextColor: WidgetStateColor.resolveWith((s) => s.contains(WidgetState.selected) ? p.brand : p.ink),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(color: p.brand),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.selected) ? Colors.white : (dark ? p.inkSoft : null),
      ),
      trackColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.selected) ? p.brandSolid : (dark ? p.subtle : null),
      ),
      trackOutlineColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.selected) ? Colors.transparent : (dark ? p.line : null),
      ),
    ),
    listTileTheme: ListTileThemeData(
      iconColor: p.inkSoft,
      titleTextStyle: TextStyle(fontFamily: 'Inter', fontSize: 16, fontWeight: FontWeight.w600, color: p.ink),
      subtitleTextStyle: TextStyle(fontFamily: 'Inter', fontSize: 14, color: p.inkSoft),
    ),
    badgeTheme: BadgeThemeData(backgroundColor: p.badSolid, textColor: Colors.white),
  );
}
