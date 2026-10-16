import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../settings.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/appearance_sheet.dart';
import '../widgets/common.dart';
import 'setup_screen.dart';
import 'student.dart';

/// The student's groups and settings: Class Alarm, their section, the
/// Semester Calendar, appearance, and the way back to signing in.
class StudentMoreTab extends StatelessWidget {
  const StudentMoreTab({super.key});

  Future<void> _change(BuildContext context) async {
    final student = StudentScope.read(context);
    final picked = await Navigator.of(
      context,
    ).push<List<String>>(MaterialPageRoute(builder: (_) => StudentSetupScreen(initial: student.groups)));
    if (picked != null && picked.isNotEmpty) await student.setGroups(picked);
  }

  Future<void> _leave(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('Sign in as staff or a teacher?'),
        content: const Text('This phone stops following your section. You can pick it again any time.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialog).pop(false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(dialog).pop(true), child: const Text('Continue')),
        ],
      ),
    );
    if (ok == true && context.mounted) await StudentScope.read(context).leave();
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final student = StudentScope.of(context);
    final mode = SettingsScope.of(context).themeMode;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
          children: [
            Text('More', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 14),
            Panel(
              child: Row(
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(16)),
                    child: Icon(Icons.school_rounded, color: p.brand, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Student',
                          style: TextStyle(fontSize: 13, color: p.inkFaint, fontWeight: FontWeight.w600),
                        ),
                        for (final g in student.groups)
                          Text(
                            groupLabel(g),
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: p.ink),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            _Card(
              children: [
                SwitchListTile(
                  value: student.alarm,
                  onChanged: student.setAlarm,
                  secondary: _Icon(Icons.alarm_rounded, p.brand, p.brandSoft),
                  title: Text(
                    'Class Alarm',
                    style: TextStyle(fontWeight: FontWeight.w700, color: p.ink),
                  ),
                  subtitle: Text(
                    'A buzz shortly before each of your classes.',
                    style: TextStyle(color: p.inkSoft, fontSize: 13.5),
                  ),
                ),
                ListTile(
                  leading: _Icon(Icons.sync_rounded, p.info, p.infoSoft),
                  title: Text(
                    'Change Alerts',
                    style: TextStyle(fontWeight: FontWeight.w700, color: p.ink),
                  ),
                  subtitle: Text(
                    'Always on: you hear when a class of yours moves or is cancelled.',
                    style: TextStyle(color: p.inkSoft, fontSize: 13.5),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            _Card(
              children: [
                _Row(icon: Icons.groups_rounded, label: 'Change section', onTap: () => _change(context)),
                _Row(
                  icon: Icons.event_note_rounded,
                  label: 'Semester Calendar',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CalendarScreen())),
                ),
                _Row(
                  icon: appearanceIcon(mode),
                  label: 'Appearance',
                  value: appearanceLabel(mode),
                  onTap: () => showAppearanceSheet(context),
                ),
                _Row(
                  icon: Icons.language_rounded,
                  label: 'Open on the web',
                  external: true,
                  onTap: () => openLink(context, '$siteUrl/students?g=${student.groups.join(',')}'),
                ),
                _Row(icon: Icons.login_rounded, label: 'Staff or teacher? Sign in', onTap: () => _leave(context)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Card extends StatelessWidget {
  const _Card({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Panel(
      padding: EdgeInsets.zero,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        // The rows paint their ink on the nearest Material: it must sit above the card's colour.
        child: Material(
          type: MaterialType.transparency,
          child: Column(
            children: [
              for (var i = 0; i < children.length; i++) ...[if (i > 0) Divider(height: 1, color: p.line), children[i]],
            ],
          ),
        ),
      ),
    );
  }
}

class _Icon extends StatelessWidget {
  const _Icon(this.icon, this.fg, this.bg);
  final IconData icon;
  final Color fg, bg;

  @override
  Widget build(BuildContext context) => Container(
    width: 36,
    height: 36,
    decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(11)),
    child: Icon(icon, color: fg, size: 19),
  );
}

class _Row extends StatelessWidget {
  const _Row({required this.icon, required this.label, required this.onTap, this.value, this.external = false});
  final IconData icon;
  final String label;
  final String? value;
  final bool external;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return ListTile(
      onTap: onTap,
      leading: _Icon(icon, p.brand, p.brandSoft),
      title: Text(
        label,
        style: TextStyle(fontWeight: FontWeight.w700, color: p.ink),
      ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (value != null) Text(value!, style: TextStyle(color: p.inkSoft)),
          Icon(external ? Icons.open_in_new_rounded : Icons.chevron_right_rounded, color: p.inkFaint, size: 20),
        ],
      ),
    );
  }
}

/// The Semester Calendar: the exams and every day with no classes.
class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  StudentCalendar? _cal;
  bool _loaded = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final cal = await context.api.studentCalendar();
      if (!mounted) return;
      setState(() {
        _cal = cal;
        _loaded = true;
        _error = null;
      });
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  static String _kind(String k) => switch (k) {
    'SPECIAL' => 'Extra teaching day',
    'EXAM' => 'Exam day',
    'CLOSED' => 'Closed',
    _ => 'Holiday',
  };

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final today = todayIso();
    final cal = _cal;
    return Scaffold(
      appBar: AppBar(title: const Text('Semester Calendar')),
      body: !_loaded
          ? (_error != null ? LoadError(message: _error!, onRetry: _load) : const Loading())
          : cal == null
          ? const EmptyState(icon: Icons.event_busy_rounded, title: 'No semester running')
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
              children: [
                Text(
                  cal.name,
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: p.ink),
                ),
                Text(
                  '${mediumDay(cal.startDate)} – ${mediumDay(cal.endDate)}',
                  style: TextStyle(fontSize: 15, color: p.inkSoft),
                ),
                const SizedBox(height: 16),
                for (final (name, start, end) in cal.exams) ...[
                  _ExamCard(name: name, start: start, end: end, today: today),
                  const SizedBox(height: 10),
                ],
                const SizedBox(height: 8),
                const SectionHeader('Days with no classes'),
                if (cal.holidays.isEmpty)
                  const Panel(
                    child: EmptyState(icon: Icons.event_available_rounded, title: 'None announced'),
                  )
                else
                  Panel(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                    child: Column(
                      children: [
                        for (final (date, title, kind) in [
                          ...cal.holidays.where((h) => h.$1.compareTo(today) >= 0),
                          ...cal.holidays.where((h) => h.$1.compareTo(today) < 0),
                        ])
                          Opacity(
                            opacity: date.compareTo(today) < 0 ? 0.5 : 1,
                            child: Padding(
                              padding: const EdgeInsets.symmetric(vertical: 10),
                              child: Row(
                                children: [
                                  SizedBox(
                                    width: 50,
                                    child: Column(
                                      children: [
                                        Text(
                                          '${parseDay(date).day}',
                                          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: p.ink),
                                        ),
                                        Text(
                                          shortDay(date).split(' ').last.toUpperCase(),
                                          style: TextStyle(
                                            fontSize: 11.5,
                                            fontWeight: FontWeight.w700,
                                            color: p.inkFaint,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          title,
                                          style: TextStyle(fontWeight: FontWeight.w700, color: p.ink),
                                        ),
                                        Text(
                                          '${shortDay(date).split(' ').first} · ${_kind(kind)}',
                                          style: TextStyle(fontSize: 13.5, color: p.inkSoft),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
              ],
            ),
    );
  }
}

class _ExamCard extends StatelessWidget {
  const _ExamCard({required this.name, required this.start, required this.end, required this.today});
  final String name, start, end, today;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final days = parseDay(start).difference(parseDay(today)).inDays;
    final when = days > 0
        ? 'In $days day${days == 1 ? '' : 's'}'
        : end.compareTo(today) >= 0
        ? 'Under way'
        : 'Over';
    return Panel(
      color: p.warnSoft,
      border: p.warn.withValues(alpha: 0.25),
      child: Row(
        children: [
          Icon(Icons.edit_note_rounded, color: p.warn, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: TextStyle(fontWeight: FontWeight.w800, color: p.warn, fontSize: 16),
                ),
                Text('${shortDay(start)} – ${shortDay(end)}', style: TextStyle(color: p.ink)),
              ],
            ),
          ),
          Text(
            when,
            style: TextStyle(fontWeight: FontWeight.w800, color: p.warn),
          ),
        ],
      ),
    );
  }
}
