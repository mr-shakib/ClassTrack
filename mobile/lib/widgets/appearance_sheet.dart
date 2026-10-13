import 'package:flutter/material.dart';

import '../settings.dart';
import '../theme.dart';

/// What each choice is called, for the row that opens the sheet.
String appearanceLabel(ThemeMode mode) => switch (mode) {
  ThemeMode.light => 'Light',
  ThemeMode.dark => 'Dark',
  ThemeMode.system => 'Match phone',
};

IconData appearanceIcon(ThemeMode mode) => switch (mode) {
  ThemeMode.light => Icons.light_mode_outlined,
  ThemeMode.dark => Icons.dark_mode_outlined,
  ThemeMode.system => Icons.brightness_auto_outlined,
};

Future<void> showAppearanceSheet(BuildContext context) =>
    showModalBottomSheet<void>(context: context, builder: (_) => const _AppearanceSheet());

/// Light, dark, or whatever the phone is set to, each shown as a small
/// picture of the app in it.
class _AppearanceSheet extends StatelessWidget {
  const _AppearanceSheet();

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final settings = SettingsScope.of(context);
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Appearance',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: p.ink),
            ),
            const SizedBox(height: 4),
            Text(
              'Saved on this phone. Match phone follows its dark mode as it changes.',
              style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4),
            ),
            const SizedBox(height: 18),
            Row(
              children: [
                for (final (i, mode) in const [ThemeMode.light, ThemeMode.dark, ThemeMode.system].indexed) ...[
                  if (i > 0) const SizedBox(width: 10),
                  Expanded(
                    child: _Choice(
                      mode: mode,
                      selected: settings.themeMode == mode,
                      onTap: () => settings.setThemeMode(mode),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Choice extends StatelessWidget {
  const _Choice({required this.mode, required this.selected, required this.onTap});
  final ThemeMode mode;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Semantics(
      selected: selected,
      button: true,
      label: appearanceLabel(mode),
      child: GestureDetector(
        onTap: onTap,
        child: Column(
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 160),
              padding: const EdgeInsets.all(3),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: selected ? p.brand : p.line, width: selected ? 2 : 1.2),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: AspectRatio(
                  aspectRatio: 0.72,
                  child: mode == ThemeMode.system
                      ? const Row(
                          children: [
                            Expanded(
                              child: _Preview(palette: Palette.light, align: Alignment.centerLeft),
                            ),
                            Expanded(
                              child: _Preview(palette: Palette.dark, align: Alignment.centerRight),
                            ),
                          ],
                        )
                      : _Preview(palette: mode == ThemeMode.dark ? Palette.dark : Palette.light),
                ),
              ),
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  selected ? Icons.radio_button_checked_rounded : Icons.radio_button_off_rounded,
                  size: 18,
                  color: selected ? p.brand : p.inkFaint,
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    appearanceLabel(mode),
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                      color: selected ? p.ink : p.inkSoft,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// A miniature of the Home tab in one palette: a hero card, then two rows.
/// `align` shows one half of it, for the split "Match phone" picture.
class _Preview extends StatelessWidget {
  const _Preview({required this.palette, this.align = Alignment.center});
  final Palette palette;
  final Alignment align;

  @override
  Widget build(BuildContext context) {
    final p = palette;
    Widget bar(double width, Color color, {double height = 5}) => Container(
      width: width,
      height: height,
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
    );

    final full = Container(
      color: p.canvas,
      padding: const EdgeInsets.all(8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 34,
            width: double.infinity,
            padding: const EdgeInsets.all(6),
            decoration: p.hero(radius: 7),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                bar(28, Colors.white.withValues(alpha: 0.9)),
                const Spacer(),
                bar(44, Colors.white.withValues(alpha: 0.35), height: 3),
              ],
            ),
          ),
          const SizedBox(height: 6),
          for (final tone in [p.ok, p.warn])
            Container(
              margin: const EdgeInsets.only(bottom: 5),
              padding: const EdgeInsets.all(5),
              decoration: BoxDecoration(
                color: p.surface,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: p.line),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        bar(30, p.ink.withValues(alpha: 0.85), height: 4),
                        const SizedBox(height: 3),
                        bar(20, p.inkFaint, height: 3),
                      ],
                    ),
                  ),
                  Container(
                    width: 6,
                    height: 6,
                    decoration: BoxDecoration(color: tone, shape: BoxShape.circle),
                  ),
                ],
              ),
            ),
          const Spacer(),
          Container(
            height: 16,
            decoration: BoxDecoration(
              color: p.isDark ? const Color(0xFF141416) : p.surface,
              borderRadius: BorderRadius.circular(5),
              border: Border.all(color: p.line),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                for (var i = 0; i < 4; i++)
                  Container(
                    width: i == 0 ? 12 : 6,
                    height: 6,
                    decoration: BoxDecoration(
                      color: i == 0 ? p.brand : p.inkFaint,
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );

    if (align == Alignment.center) return full;
    // Half of a full-width picture: lay it out twice as wide, show one side.
    return LayoutBuilder(
      builder: (context, box) => ClipRect(
        child: OverflowBox(alignment: align, minWidth: box.maxWidth * 2, maxWidth: box.maxWidth * 2, child: full),
      ),
    );
  }
}
