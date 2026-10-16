import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../theme.dart';

/// The ClassTrack logo's blue, as on the launcher icon (assets/icon): fixed, not themed.
const logoGradient = LinearGradient(
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
  colors: [Color(0xFF2563EB), Color(0xFF0E7490)],
);

/// A white panel with a hairline border: the app's basic card.
class Panel extends StatelessWidget {
  const Panel({super.key, required this.child, this.padding = const EdgeInsets.all(16), this.color, this.border});

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? color;
  final Color? border;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? p.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: border ?? p.line, width: 1.2),
      ),
      child: child,
    );
  }
}

/// A heading over a group, with an optional count and line of explanation.
class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.count, this.subtitle, this.color, this.trailing});

  final String title;
  final int? count;
  final String? subtitle;
  final Color? color;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(text: title),
                      if (count != null)
                        TextSpan(
                          text: '  $count',
                          style: TextStyle(color: p.inkFaint, fontWeight: FontWeight.w700),
                        ),
                    ],
                  ),
                  style: TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                    color: color ?? p.ink,
                    letterSpacing: -0.3,
                  ),
                ),
                if (subtitle != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 3),
                    child: Text(subtitle!, style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.35)),
                  ),
              ],
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

/// A small rounded label: a status, a tag, a role.
class Pill extends StatelessWidget {
  const Pill(this.label, {super.key, required this.color, required this.background, this.icon, this.large = false});

  final String label;
  final Color color, background;
  final IconData? icon;
  final bool large;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: large ? 12 : 9, vertical: large ? 6 : 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: color.withValues(alpha: 0.22)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[Icon(icon, size: large ? 16 : 14, color: color), const SizedBox(width: 5)],
          Flexible(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: color, fontSize: large ? 14 : 12.5, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

/// A coloured note: what went wrong, what to know, what worked.
class Notice extends StatelessWidget {
  const Notice(this.message, {super.key, required this.tone, this.icon, this.title});

  factory Notice.error(String message) => Notice(message, tone: Tone.bad, icon: Icons.error_outline_rounded);

  final String message;
  final String? title;
  final Tone tone;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final (fg, bg) = switch (tone) {
      Tone.ok => (p.ok, p.okSoft),
      Tone.warn => (p.warn, p.warnSoft),
      Tone.bad => (p.bad, p.badSoft),
      Tone.gap => (p.gap, p.gapSoft),
      Tone.info => (p.info, p.infoSoft),
      Tone.neutral => (p.inkSoft, p.subtle),
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: fg.withValues(alpha: 0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (icon != null) ...[
            Padding(
              padding: const EdgeInsets.only(top: 1),
              child: Icon(icon, color: fg, size: 20),
            ),
            const SizedBox(width: 10),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (title != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child: Text(
                      title!,
                      style: TextStyle(color: fg, fontWeight: FontWeight.w800, fontSize: 15.5),
                    ),
                  ),
                Text(
                  message,
                  style: TextStyle(color: fg, fontWeight: FontWeight.w600, fontSize: 15, height: 1.35),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

enum Tone { ok, warn, bad, gap, info, neutral }

/// Nothing to show, said plainly.
class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, this.body, this.action});

  final IconData icon;
  final String title;
  final String? body;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(color: p.brandSoft, shape: BoxShape.circle),
            child: Icon(icon, color: p.brand, size: 30),
          ),
          const SizedBox(height: 14),
          Text(
            title,
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: p.ink),
          ),
          if (body != null) ...[
            const SizedBox(height: 6),
            Text(
              body!,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, color: p.inkSoft, height: 1.4),
            ),
          ],
          if (action != null) ...[const SizedBox(height: 16), action!],
        ],
      ),
    );
  }
}

/// A full-width loading state.
class Loading extends StatelessWidget {
  const Loading({super.key, this.label = 'Loading…'});
  final String label;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(width: 28, height: 28, child: CircularProgressIndicator(strokeWidth: 3)),
          const SizedBox(height: 14),
          Text(label, style: TextStyle(color: p.inkSoft, fontSize: 15)),
        ],
      ),
    );
  }
}

/// Could not load: what happened, and a way to try again.
class LoadError extends StatelessWidget {
  const LoadError({super.key, required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return EmptyState(
      icon: Icons.cloud_off_rounded,
      title: 'Could not load',
      body: message,
      action: OutlinedButton.icon(
        onPressed: onRetry,
        icon: const Icon(Icons.refresh_rounded),
        label: const Text('Try again'),
      ),
    );
  }
}

/// A spinner sized for a button label.
class ButtonSpinner extends StatelessWidget {
  const ButtonSpinner({super.key, this.color = Colors.white});
  final Color color;

  @override
  Widget build(BuildContext context) =>
      SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.5, color: color));
}

/// A thin, rounded progress bar.
class ProgressBar extends StatelessWidget {
  const ProgressBar({super.key, required this.value, required this.color, required this.track, this.height = 8});
  final double value;
  final Color color, track;
  final double height;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(height),
      child: SizedBox(
        height: height,
        child: Stack(
          children: [
            Container(color: track),
            AnimatedFractionallySizedBox(
              duration: const Duration(milliseconds: 350),
              curve: Curves.easeOutCubic,
              widthFactor: value.clamp(0, 1).toDouble(),
              child: Container(
                decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(height)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A round photo, or the person's initials on brand blue when there is none
/// or it fails to load. Mirrors web/src/components/Avatar.tsx.
class Avatar extends StatelessWidget {
  const Avatar({super.key, required this.name, this.initial, this.photo, this.size = 44});

  final String name;
  final String? initial, photo;
  final double size;

  static const _titles = {'dr', 'mr', 'mrs', 'ms', 'md', 'prof', 'engr'};

  static String initialsOf(String name, String? initial) {
    if (initial != null && initial.isNotEmpty) {
      return initial.substring(0, math.min(3, initial.length)).toUpperCase();
    }
    final words = name
        .replaceAll('.', ' ')
        .split(RegExp(r'\s+'))
        .where((w) => w.isNotEmpty && RegExp(r'^[A-Z]').hasMatch(w) && !_titles.contains(w.toLowerCase()))
        .toList();
    if (words.isEmpty) return name.trim().isEmpty ? '?' : name.trim()[0].toUpperCase();
    final last = words.length > 1 ? words.last[0] : '';
    return (words.first[0] + last).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final letters = initialsOf(name, initial);
    final fallback = Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [p.brandSolid, p.infoSolid],
        ),
      ),
      child: Text(
        letters,
        style: TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w800,
          fontSize: size * (letters.length > 2 ? 0.3 : 0.36),
          letterSpacing: -0.3,
        ),
      ),
    );
    if (photo == null || photo!.isEmpty) return fallback;
    return ClipOval(
      child: Image.network(
        photo!,
        width: size,
        height: size,
        fit: BoxFit.cover,
        alignment: Alignment.topCenter,
        errorBuilder: (_, _, _) => fallback,
      ),
    );
  }
}

/// A rounded rectangle drawn with a dashed line: the mark of a makeup class.
class DashedBorder extends StatelessWidget {
  const DashedBorder({super.key, required this.child, required this.color, this.radius = 20, this.width = 2});

  final Widget child;
  final Color color;
  final double radius, width;

  @override
  Widget build(BuildContext context) => CustomPaint(
    foregroundPainter: _DashPainter(color: color, radius: radius, width: width),
    child: child,
  );
}

class _DashPainter extends CustomPainter {
  _DashPainter({required this.color, required this.radius, required this.width});
  final Color color;
  final double radius, width;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset(width / 2, width / 2) & Size(size.width - width, size.height - width);
    final path = Path()..addRRect(RRect.fromRectAndRadius(rect, Radius.circular(radius)));
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = width;
    for (final metric in path.computeMetrics()) {
      var d = 0.0;
      while (d < metric.length) {
        canvas.drawPath(metric.extractPath(d, d + 7), paint);
        d += 12;
      }
    }
  }

  @override
  bool shouldRepaint(_DashPainter old) => old.color != color || old.width != width;
}

/// Opens a link in the browser, or says why it could not.
Future<void> openLink(BuildContext context, String url) async {
  final uri = Uri.tryParse(url);
  final ok = uri != null && await launchUrl(uri, mode: LaunchMode.externalApplication);
  if (!ok && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not open the link.')));
  }
}

void showMessage(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message)));
}

/// Two or three choices side by side, the picked one raised: the same switch as
/// Checking's "By floor / Find by teacher".
class SegmentedSwitch<T> extends StatelessWidget {
  const SegmentedSwitch({super.key, required this.options, required this.value, required this.onChanged});

  /// Each choice's value, label, and an optional icon.
  final List<(T, String, IconData?)> options;
  final T value;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dark = p.isDark;
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: dark ? p.surface : p.line.withValues(alpha: 0.6),
        border: dark ? Border.all(color: p.line) : null,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          for (final (v, label, icon) in options)
            Expanded(
              child: GestureDetector(
                onTap: () => onChanged(v),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  height: 42,
                  decoration: BoxDecoration(
                    color: v == value ? (dark ? p.raised : p.surface) : Colors.transparent,
                    border: dark && v == value ? Border.all(color: p.line) : null,
                    borderRadius: BorderRadius.circular(11),
                    boxShadow: v == value && !dark
                        ? [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.06),
                              blurRadius: 6,
                              offset: const Offset(0, 1),
                            ),
                          ]
                        : null,
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      if (icon != null) ...[
                        Icon(icon, size: 18, color: v == value ? p.brand : p.inkSoft),
                        const SizedBox(width: 6),
                      ],
                      Flexible(
                        child: Text(
                          label,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: v == value ? p.brand : p.inkSoft,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
