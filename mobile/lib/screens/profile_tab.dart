import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../teacher/teacher_data.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';

/// Who is signed in and how their work is going: for a teacher the semester,
/// their courses and routine; for staff their floors. Then their details, the
/// absence-email address, the password, and the way out.
class ProfileTab extends StatefulWidget {
  const ProfileTab({super.key, this.teacher});

  /// A teacher's classes and figures, shared with their other tabs.
  final TeacherData? teacher;

  @override
  State<ProfileTab> createState() => _ProfileTabState();
}

class _ProfileTabState extends State<ProfileTab> {
  Profile? _profile;
  String? _error;

  /// Past the brand band: the status bar needs a backing of its own.
  final _scroll = ScrollController();
  bool _scrolled = false;

  /// Floor staff: their assigned floors, as the checking screen knows them.
  List<String>? _floors;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      final scrolled = _scroll.offset > 60;
      if (scrolled != _scrolled) setState(() => _scrolled = scrolled);
    });
    _load();
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load({bool withTeacher = false}) async {
    final api = context.api;
    final user = SessionScope.read(context).user!;
    try {
      final profile = await api.profile();
      if (mounted) {
        setState(() {
          _profile = profile;
          _error = null;
        });
      }
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
    if (user.isStaff && user.mayCheck) {
      try {
        final screen = await api.checkingRooms();
        if (mounted) setState(() => _floors = screen.zones);
      } on ApiError {
        // The floors are a nicety; the rest of the profile stands without them.
      }
    }
    if (withTeacher) await widget.teacher?.load();
  }

  Future<void> _editEmail() async {
    final saved = await showModalBottomSheet<Profile>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _EmailSheet(current: _profile?.contactEmail),
    );
    if (saved != null && mounted) {
      setState(() => _profile = saved);
      showMessage(context, 'Saved. Absence emails go to ${saved.contactEmail}.');
    }
  }

  Future<void> _signOut() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text('You will need your password to sign in again.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Stay')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(minimumSize: const Size(64, 44)),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (yes == true && mounted) await SessionScope.read(context).signOut();
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final user = SessionScope.of(context).user!;
    final profile = _profile;
    final teacher = widget.teacher;

    // The brand band runs under the status bar: light icons on it.
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: Scaffold(
        body: Stack(
          children: [
            RefreshIndicator(
              onRefresh: () => _load(withTeacher: true),
              child: ListView(
                controller: _scroll,
                padding: EdgeInsets.zero,
                children: [
                  _Hero(user: user, profile: profile),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 22, 16, 32),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (_error != null && profile == null) ...[Notice.error(_error!), const SizedBox(height: 16)],
                        if (teacher != null)
                          ListenableBuilder(
                            listenable: teacher,
                            builder: (context, _) => _TeacherSections(data: teacher),
                          ),
                        if (user.isStaff && user.mayCheck) ...[
                          const _GroupLabel('Your floors'),
                          _FloorsCard(floors: _floors),
                          const SizedBox(height: 22),
                        ],
                        const _GroupLabel('Details'),
                        _DetailsCard(user: user, profile: profile, onEditEmail: _editEmail),
                        const SizedBox(height: 22),
                        const _GroupLabel('Account'),
                        Panel(
                          padding: EdgeInsets.zero,
                          child: Column(
                            children: [
                              _LinkRow(
                                icon: Icons.lock_outline_rounded,
                                title: 'Change password',
                                subtitle: 'Replace a default password with one only you know',
                                onTap: () => Navigator.of(
                                  context,
                                ).push(MaterialPageRoute(builder: (_) => const ChangePasswordScreen())),
                              ),
                              Divider(indent: 62, color: p.line),
                              _LinkRow(
                                icon: Icons.language_rounded,
                                title: 'Open ClassTrack on the web',
                                subtitle: 'Reports and everything else, on ${Uri.parse(siteUrl).host}',
                                external: true,
                                onTap: () => openLink(context, siteUrl),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 22),
                        OutlinedButton.icon(
                          onPressed: _signOut,
                          style: OutlinedButton.styleFrom(
                            foregroundColor: p.bad,
                            side: BorderSide(color: p.bad.withValues(alpha: 0.35), width: 1.5),
                            minimumSize: const Size.fromHeight(54),
                          ),
                          icon: const Icon(Icons.logout_rounded),
                          label: const Text('Sign out'),
                        ),
                        const SizedBox(height: 26),
                        Center(
                          child: InkWell(
                            onTap: () => openLink(context, 'https://shakibhowlader.online'),
                            borderRadius: BorderRadius.circular(8),
                            child: Padding(
                              padding: const EdgeInsets.all(8),
                              child: Text.rich(
                                TextSpan(
                                  children: [
                                    const TextSpan(text: 'ClassTrack 1.0  ·  Developed by '),
                                    TextSpan(
                                      text: 'Shakib Howlader',
                                      style: TextStyle(color: p.inkSoft, fontWeight: FontWeight.w600),
                                    ),
                                  ],
                                ),
                                style: TextStyle(fontSize: 13, color: p.inkFaint),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              height: MediaQuery.of(context).padding.top,
              child: IgnorePointer(
                child: AnimatedOpacity(
                  opacity: _scrolled ? 1 : 0,
                  duration: const Duration(milliseconds: 150),
                  child: ColoredBox(color: p.brandSolid),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GroupLabel extends StatelessWidget {
  const _GroupLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(left: 4, bottom: 8),
    child: Text(
      text.toUpperCase(),
      style: TextStyle(
        fontSize: 12.5,
        fontWeight: FontWeight.w800,
        letterSpacing: 0.8,
        color: context.palette.inkFaint,
      ),
    ),
  );
}

// --- the person ---------------------------------------------------------------------

class _Hero extends StatelessWidget {
  const _Hero({required this.user, required this.profile});
  final User user;
  final Profile? profile;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final top = MediaQuery.of(context).padding.top;
    final designation = profile?.designation;
    final chips = <(IconData, String)>[
      if (user.teacherInitial != null) (Icons.badge_outlined, user.teacherInitial!),
      if (profile?.department != null) (Icons.apartment_rounded, profile!.department!.toUpperCase()),
      for (final r in user.roles) (Icons.verified_user_outlined, r.name),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              width: double.infinity,
              height: 112 + top,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [p.brandSolid, Color.lerp(p.brandSolid, p.infoSolid, 0.7)!],
                ),
              ),
              padding: EdgeInsets.fromLTRB(20, top + 14, 20, 0),
              child: const Text(
                'Profile',
                style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800),
              ),
            ),
            Positioned(
              left: 20,
              bottom: -46,
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(color: p.canvas, shape: BoxShape.circle),
                child: Avatar(
                  name: user.fullName,
                  initial: user.teacherInitial,
                  photo: profile?.photoUrl ?? user.photoUrl,
                  size: 92,
                ),
              ),
            ),
          ],
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 58, 20, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                user.fullName,
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: p.ink,
                  letterSpacing: -0.5,
                  height: 1.2,
                ),
              ),
              if (designation != null)
                Padding(
                  padding: const EdgeInsets.only(top: 3),
                  child: Text(designation, style: TextStyle(fontSize: 15.5, color: p.inkSoft)),
                ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final (icon, label) in chips)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: p.surface,
                        borderRadius: BorderRadius.circular(99),
                        border: Border.all(color: p.line, width: 1.2),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(icon, size: 15, color: p.brand),
                          const SizedBox(width: 6),
                          Text(
                            label,
                            style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: p.ink),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// --- a teacher's semester -----------------------------------------------------------

class _TeacherSections extends StatelessWidget {
  const _TeacherSections({required this.data});
  final TeacherData data;

  @override
  Widget build(BuildContext context) {
    final report = data.report;
    final routine = data.routine;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (report != null) ...[
          const _GroupLabel('This semester'),
          _SemesterCard(report: report),
          const SizedBox(height: 22),
          if (report.courses.isNotEmpty) ...[
            const _GroupLabel('Your courses'),
            _CoursesCard(report: report),
            const SizedBox(height: 22),
          ],
        ],
        if (routine.isNotEmpty) ...[
          const _GroupLabel('Weekly routine'),
          _RoutineCard(routine: routine),
          const SizedBox(height: 22),
        ],
      ],
    );
  }
}

class _SemesterCard extends StatelessWidget {
  const _SemesterCard({required this.report});
  final TeacherReport report;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final r = report;
    final decided = r.conducted + r.missed > 0;
    final rate = r.conductRate.clamp(0, 100) / 100;
    final ringColor = !decided
        ? p.inkFaint
        : (rate >= 0.9
              ? p.okSolid
              : rate >= 0.75
              ? p.warnSolid
              : p.badSolid);

    Widget stat(String label, String value, Color color, [String? hint]) => Expanded(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800, color: color, fontFeatures: tabular),
            ),
            Text(
              label,
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: p.inkSoft),
            ),
            Text(hint ?? '', style: TextStyle(fontSize: 11.5, color: p.inkFaint)),
          ],
        ),
      ),
    );

    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  r.label ?? 'This semester',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: p.ink),
                ),
              ),
              Text('${shortDay(r.from)} – ${shortDay(r.to)}', style: TextStyle(fontSize: 12.5, color: p.inkFaint)),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              SizedBox(
                width: 104,
                height: 104,
                child: CustomPaint(
                  painter: _Ring(value: decided ? rate.toDouble() : 0, color: ringColor, track: p.line),
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          decided ? '${r.conductRate.round()}%' : '—',
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w800,
                            color: p.ink,
                            fontFeatures: tabular,
                          ),
                        ),
                        Text(
                          'held',
                          style: TextStyle(fontSize: 12, color: p.inkSoft, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  children: [
                    Row(
                      children: [
                        stat('Conducted', '${r.conducted}', p.ok, 'of ${r.totalScheduled}'),
                        stat('Late', '${r.late}', p.warn, r.late > 0 ? 'avg ${r.avgLateMinutes.round()} min' : null),
                      ],
                    ),
                    Row(
                      children: [stat('Missed', '${r.missed}', p.bad), stat('Not checked', '${r.notChecked}', p.gap)],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Held is the share of checked classes that took place, late included. '
            'A class nobody checked is not counted against you.',
            style: TextStyle(fontSize: 12.5, color: p.inkFaint, height: 1.4),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(color: p.infoSoft, borderRadius: BorderRadius.circular(12)),
            child: Row(
              children: [
                Icon(Icons.sync_rounded, size: 18, color: p.info),
                const SizedBox(width: 8),
                Expanded(
                  child: Text.rich(
                    TextSpan(
                      children: [
                        const TextSpan(text: 'Makeups  '),
                        TextSpan(
                          text: '${r.makeupCompleted} done',
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                        TextSpan(text: '  ·  ${r.makeupPending} pending'),
                      ],
                    ),
                    style: TextStyle(fontSize: 14.5, color: p.info, fontWeight: FontWeight.w600),
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

/// A ring filled to `value` (0–1), starting at twelve o'clock.
class _Ring extends CustomPainter {
  _Ring({required this.value, required this.color, required this.track});
  final double value;
  final Color color, track;

  @override
  void paint(Canvas canvas, Size size) {
    const stroke = 10.0;
    final rect = (Offset.zero & size).deflate(stroke / 2);
    final base = Paint()
      ..color = track
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke;
    canvas.drawArc(rect, 0, 2 * math.pi, false, base);
    if (value <= 0) return;
    final arc = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, -math.pi / 2, 2 * math.pi * value, false, arc);
  }

  @override
  bool shouldRepaint(_Ring old) => old.value != value || old.color != color || old.track != track;
}

/// Each course-section's classes held so far, against the minimum.
class _CoursesCard extends StatelessWidget {
  const _CoursesCard({required this.report});
  final TeacherReport report;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final min = report.minConducted;
    return Panel(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        children: [
          for (var i = 0; i < report.courses.length; i++) ...[
            if (i > 0) Divider(indent: 16, endIndent: 16, color: p.line),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              child: Builder(
                builder: (context) {
                  final c = report.courses[i];
                  final met = min > 0 && c.held >= min;
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              '${c.courseCode} · ${c.section}',
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: p.ink),
                            ),
                          ),
                          Text.rich(
                            TextSpan(
                              children: [
                                TextSpan(
                                  text: '${c.held}',
                                  style: TextStyle(color: met ? p.ok : p.ink),
                                ),
                                TextSpan(
                                  text: ' / $min held',
                                  style: TextStyle(color: p.inkSoft, fontWeight: FontWeight.w600),
                                ),
                              ],
                            ),
                            style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800, fontFeatures: tabular),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      ProgressBar(
                        value: min == 0 ? 0 : c.held / min,
                        color: met ? p.okSolid : p.brandSolid,
                        track: p.line,
                        height: 7,
                      ),
                      if (c.missed > 0 || met)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                            met ? 'Minimum reached' : '${c.missed} missed',
                            style: TextStyle(fontSize: 13, color: met ? p.ok : p.bad, fontWeight: FontWeight.w600),
                          ),
                        ),
                    ],
                  );
                },
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// The week's classes, day by day.
class _RoutineCard extends StatelessWidget {
  const _RoutineCard({required this.routine});
  final List<RoutineEntry> routine;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final byDay = <String, List<RoutineEntry>>{};
    for (final e in routine) {
      byDay.putIfAbsent(e.day, () => []).add(e);
    }
    final days = byDay.entries.toList();
    return Panel(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        children: [
          for (var i = 0; i < days.length; i++) ...[
            if (i > 0) Divider(indent: 16, endIndent: 16, color: p.line),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 48,
                    child: Padding(
                      padding: const EdgeInsets.only(top: 3),
                      child: Text(
                        days[i].key.substring(0, 3).toUpperCase(),
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: p.brand, letterSpacing: 0.6),
                      ),
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final e in days[i].value)
                          Padding(
                            padding: const EdgeInsets.symmetric(vertical: 3),
                            child: Row(
                              children: [
                                SizedBox(
                                  width: 50,
                                  child: Text(
                                    clock(slotBounds(e.timeSlot).$1),
                                    style: TextStyle(
                                      fontSize: 14.5,
                                      fontWeight: FontWeight.w700,
                                      color: p.ink,
                                      fontFeatures: tabular,
                                    ),
                                  ),
                                ),
                                Expanded(
                                  child: Text(
                                    '${e.courseCode} · ${e.section}',
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(fontSize: 14.5, color: p.ink),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Text(e.room, style: TextStyle(fontSize: 13.5, color: p.inkSoft)),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// --- floor staff ----------------------------------------------------------------------

/// "KT-3" → "KT · Floor 3", as the checking screen labels floors.
String _floorLabel(String key) {
  if (key == 'UNZONED') return 'Other rooms';
  final cut = key.lastIndexOf('-');
  if (cut < 0) return key;
  final floor = key.substring(cut + 1);
  return '${key.substring(0, cut)} · ${floor == '0' ? 'Ground floor' : 'Floor $floor'}';
}

class _FloorsCard extends StatelessWidget {
  const _FloorsCard({required this.floors});
  final List<String>? floors;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final f = floors;
    return Panel(
      child: f == null
          ? Text('Loading…', style: TextStyle(color: p.inkSoft))
          : f.isEmpty
          ? Text(
              'No floors assigned. You can check classes on any floor.',
              style: TextStyle(fontSize: 15, color: p.inkSoft, height: 1.4),
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final key in f)
                      Pill(
                        _floorLabel(key),
                        color: p.brand,
                        background: p.brandSoft,
                        icon: Icons.layers_rounded,
                        large: true,
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  'They come first on the checking screen. You can still check any floor.',
                  style: TextStyle(fontSize: 13.5, color: p.inkSoft, height: 1.4),
                ),
              ],
            ),
    );
  }
}

// --- details --------------------------------------------------------------------------

class _DetailsCard extends StatelessWidget {
  const _DetailsCard({required this.user, required this.profile, required this.onEditEmail});
  final User user;
  final Profile? profile;
  final VoidCallback onEditEmail;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final pr = profile;
    final rows = <Widget>[
      _DetailRow(
        icon: Icons.login_rounded,
        label: 'Signs in with',
        value: pr?.signIn ?? user.teacherInitial ?? user.email,
      ),
      if (user.email.isNotEmpty && user.email != pr?.signIn)
        _DetailRow(icon: Icons.alternate_email_rounded, label: 'Account email', value: user.email),
      if (pr?.officeRoom != null)
        _DetailRow(icon: Icons.door_front_door_outlined, label: 'Office', value: pr!.officeRoom!),
      if (user.isTeacher)
        _DetailRow(
          icon: Icons.mail_outline_rounded,
          label: 'Absence emails go to',
          value: pr == null ? '…' : (pr.contactEmail ?? 'No address on file'),
          warn: pr != null && pr.contactEmail == null,
          action: pr == null ? null : (pr.contactEmail == null ? 'Add' : 'Change'),
          onTap: pr == null ? null : onEditEmail,
        ),
    ];
    return Panel(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        children: [
          for (var i = 0; i < rows.length; i++) ...[if (i > 0) Divider(indent: 62, color: p.line), rows[i]],
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
            child: Text(
              user.teacherInitial != null
                  ? 'Your name, designation and office come from the faculty list. Ask the department office to correct them.'
                  : 'Your name and role are set by an administrator.',
              style: TextStyle(fontSize: 12.5, color: p.inkFaint, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
    this.warn = false,
    this.action,
    this.onTap,
  });

  final IconData icon;
  final String label, value;
  final bool warn;
  final String? action;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, color: p.brand, size: 18),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: p.inkFaint),
                  ),
                  const SizedBox(height: 1),
                  Text(
                    value,
                    style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: warn ? p.warn : p.ink),
                  ),
                ],
              ),
            ),
            if (action != null)
              Text(
                action!,
                style: TextStyle(color: p.brand, fontWeight: FontWeight.w700, fontSize: 15),
              ),
          ],
        ),
      ),
    );
  }
}

class _LinkRow extends StatelessWidget {
  const _LinkRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.external = false,
  });

  final IconData icon;
  final String title, subtitle;
  final VoidCallback onTap;
  final bool external;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, color: p.brand, size: 18),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: p.ink),
                  ),
                  Text(subtitle, style: TextStyle(fontSize: 13.5, color: p.inkSoft)),
                ],
              ),
            ),
            Icon(
              external ? Icons.open_in_new_rounded : Icons.chevron_right_rounded,
              color: p.inkFaint,
              size: external ? 20 : 24,
            ),
          ],
        ),
      ),
    );
  }
}

/// Change the address absence reports are mailed to.
class _EmailSheet extends StatefulWidget {
  const _EmailSheet({required this.current});
  final String? current;

  @override
  State<_EmailSheet> createState() => _EmailSheetState();
}

class _EmailSheetState extends State<_EmailSheet> {
  late final _email = TextEditingController(text: widget.current ?? '');
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final profile = await context.api.updateContactEmail(_email.text.trim());
      if (mounted) Navigator.of(context).pop(profile);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final unchanged = _email.text.trim() == (widget.current ?? '') || _email.text.trim().isEmpty;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Absence emails',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: p.ink),
          ),
          const SizedBox(height: 4),
          Text(
            'When staff report you absent from a class, ClassTrack emails this address.',
            style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _email,
            autofocus: true,
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.email],
            onChanged: (_) => setState(() {}),
            onSubmitted: (_) => unchanged ? null : _save(),
            decoration: const InputDecoration(
              hintText: 'name@diu.edu.bd',
              prefixIcon: Icon(Icons.mail_outline_rounded),
            ),
          ),
          if (_error != null) ...[const SizedBox(height: 12), Notice.error(_error!)],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy || unchanged ? null : _save,
            child: _busy ? const ButtonSpinner() : const Text('Save email'),
          ),
        ],
      ),
    );
  }
}

/// Change the password, with the server's rules shown as they are met.
class ChangePasswordScreen extends StatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  State<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends State<ChangePasswordScreen> {
  static const _minLength = 6;
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  bool _shown = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  List<(bool, String)> get _rules => [
    (_next.text.length >= _minLength, 'At least $_minLength characters'),
    (_next.text.isNotEmpty && _next.text != _current.text, 'Different from your current password'),
    (_confirm.text.isNotEmpty && _confirm.text == _next.text, 'Both new passwords match'),
  ];

  bool get _ready => _current.text.isNotEmpty && _rules.every((r) => r.$1);

  Future<void> _submit() async {
    if (!_ready) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.api.changePassword(_current.text, _next.text);
      if (!mounted) return;
      showMessage(context, 'Password changed. Use the new one next time you sign in.');
      Navigator.of(context).pop();
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    Widget field(String label, TextEditingController c, List<String> hints) => Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: TextField(
        controller: c,
        obscureText: !_shown,
        autofillHints: hints,
        onChanged: (_) => setState(() {}),
        decoration: InputDecoration(labelText: label),
      ),
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Change password')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
        children: [
          Text(
            'If the department gave you a default password, replace it with one only you know.',
            style: TextStyle(fontSize: 15, color: p.inkSoft, height: 1.4),
          ),
          const SizedBox(height: 18),
          AutofillGroup(
            child: Column(
              children: [
                field('Current password', _current, const [AutofillHints.password]),
                field('New password', _next, const [AutofillHints.newPassword]),
                field('New password again', _confirm, const [AutofillHints.newPassword]),
              ],
            ),
          ),
          SwitchListTile(
            value: _shown,
            onChanged: (v) => setState(() => _shown = v),
            contentPadding: const EdgeInsets.symmetric(horizontal: 4),
            title: const Text('Show passwords'),
          ),
          const SizedBox(height: 6),
          Panel(
            color: p.canvas,
            padding: const EdgeInsets.all(14),
            child: Column(
              children: [
                for (final (met, label) in _rules)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      children: [
                        Icon(
                          met ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                          size: 20,
                          color: met ? p.ok : p.inkFaint,
                        ),
                        const SizedBox(width: 10),
                        Text(
                          label,
                          style: TextStyle(
                            fontSize: 14.5,
                            color: met ? p.ok : p.inkSoft,
                            fontWeight: met ? FontWeight.w700 : FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          if (_error != null) ...[const SizedBox(height: 14), Notice.error(_error!)],
          const SizedBox(height: 18),
          FilledButton(
            onPressed: _busy || !_ready ? null : _submit,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
            child: _busy ? const ButtonSpinner() : const Text('Update password'),
          ),
        ],
      ),
    );
  }
}
