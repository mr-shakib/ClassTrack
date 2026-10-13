import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../settings.dart';
import '../teacher/teacher_data.dart';
import '../theme.dart';
import '../widgets/appearance_sheet.dart';
import '../widgets/common.dart';

/// Who is signed in, as a stack of cards: who they are, how the semester is
/// going and their courses (a teacher) or their floors (staff), their details,
/// and their settings.
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

  /// Floor staff: their assigned floors, as the checking screen knows them.
  List<String>? _floors;

  @override
  void initState() {
    super.initState();
    _load();
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
    final mode = SettingsScope.of(context).themeMode;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: () => _load(withTeacher: true),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
            children: [
              Text('Profile', style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 14),
              if (_error != null && profile == null) ...[Notice.error(_error!), const SizedBox(height: 12)],
              _IdentityCard(user: user, profile: profile),
              if (teacher != null)
                ListenableBuilder(
                  listenable: teacher,
                  builder: (context, _) => _TeacherCards(data: teacher),
                ),
              if (user.isStaff && user.mayCheck) ...[const _Label('Your floors'), _FloorsCard(floors: _floors)],
              const _Label('Details'),
              _Card(
                children: [
                  if (profile?.officeRoom != null)
                    _Row(icon: Icons.door_front_door_outlined, label: 'Office', value: profile!.officeRoom!),
                  if (user.isTeacher)
                    _Row(
                      icon: Icons.mail_outline_rounded,
                      label: 'Absence emails',
                      value: profile == null ? '…' : (profile.contactEmail ?? 'Not set'),
                      warn: profile != null && profile.contactEmail == null,
                      trailing: profile == null
                          ? null
                          : _EditButton(add: profile.contactEmail == null, onTap: _editEmail),
                      onTap: profile == null ? null : _editEmail,
                    ),
                  _Row(
                    icon: Icons.login_rounded,
                    label: 'Signs in with',
                    value: profile?.signIn ?? user.teacherInitial ?? user.email,
                  ),
                ],
              ),
              const _Label('Settings'),
              _Card(
                children: [
                  _Row(
                    icon: appearanceIcon(mode),
                    label: 'Appearance',
                    trailing: _Value(appearanceLabel(mode)),
                    onTap: () => showAppearanceSheet(context),
                  ),
                  _Row(
                    icon: Icons.lock_outline_rounded,
                    label: 'Change password',
                    trailing: Icon(Icons.chevron_right_rounded, color: p.inkFaint),
                    onTap: () =>
                        Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ChangePasswordScreen())),
                  ),
                  _Row(
                    icon: Icons.language_rounded,
                    label: 'Open the website',
                    trailing: Icon(Icons.open_in_new_rounded, color: p.inkFaint, size: 20),
                    onTap: () => openLink(context, siteUrl),
                  ),
                  _Row(icon: Icons.logout_rounded, label: 'Sign out', danger: true, onTap: _signOut),
                ],
              ),
              const SizedBox(height: 22),
              Center(
                child: InkWell(
                  onTap: () => openLink(context, 'https://shakibhowlader.online'),
                  borderRadius: BorderRadius.circular(8),
                  child: Padding(
                    padding: const EdgeInsets.all(8),
                    child: Text.rich(
                      TextSpan(
                        children: [
                          const TextSpan(text: 'ClassTrack 1.0  ·  '),
                          TextSpan(
                            text: 'Shakib Howlader',
                            style: TextStyle(color: p.inkSoft, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                      style: TextStyle(fontSize: 12.5, color: p.inkFaint),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A small heading over a card.
class _Label extends StatelessWidget {
  const _Label(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(4, 22, 4, 10),
    child: Text(
      text,
      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: context.palette.ink, letterSpacing: -0.2),
    ),
  );
}

// --- who they are -------------------------------------------------------------------

/// The person, on the hero gradient: like the card on a lanyard.
class _IdentityCard extends StatelessWidget {
  const _IdentityCard({required this.user, required this.profile});
  final User user;
  final Profile? profile;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final chips = <(IconData, String)>[
      if (user.teacherInitial != null) (Icons.badge_outlined, user.teacherInitial!),
      if (profile?.department != null) (Icons.apartment_rounded, profile!.department!.toUpperCase()),
      for (final r in user.roles) (Icons.verified_user_outlined, r.name),
    ];

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: p.hero(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(3),
                decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.9), shape: BoxShape.circle),
                child: Avatar(
                  name: user.fullName,
                  initial: user.teacherInitial,
                  photo: profile?.photoUrl ?? user.photoUrl,
                  size: 66,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      user.fullName,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 19,
                        fontWeight: FontWeight.w800,
                        height: 1.2,
                        letterSpacing: -0.3,
                      ),
                    ),
                    if (profile?.designation != null) ...[
                      const SizedBox(height: 3),
                      Text(
                        profile!.designation!,
                        style: TextStyle(color: Colors.white.withValues(alpha: 0.75), fontSize: 14),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final (icon, label) in chips)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(99),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(icon, size: 14, color: Colors.white),
                      const SizedBox(width: 6),
                      Text(
                        label,
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Colors.white),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

// --- a teacher's semester -----------------------------------------------------------

class _TeacherCards extends StatelessWidget {
  const _TeacherCards({required this.data});
  final TeacherData data;

  @override
  Widget build(BuildContext context) {
    final r = data.report;
    if (r == null) return const SizedBox.shrink();
    final p = context.palette;
    final (term, _) = _splitLabel(r.label);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Label(term),
        _SemesterCard(report: r),
        const SizedBox(height: 10),
        Row(
          children: [
            _StatTile(
              icon: Icons.check_circle_outline_rounded,
              value: r.conducted,
              label: 'Conducted',
              color: p.ok,
              tint: p.okSoft,
            ),
            const SizedBox(width: 10),
            _StatTile(icon: Icons.schedule_rounded, value: r.late, label: 'Late', color: p.warn, tint: p.warnSoft),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            _StatTile(icon: Icons.event_busy_rounded, value: r.missed, label: 'Missed', color: p.bad, tint: p.badSoft),
            const SizedBox(width: 10),
            _StatTile(
              icon: Icons.visibility_off_outlined,
              value: r.notChecked,
              label: 'Not checked',
              color: p.gap,
              tint: p.gapSoft,
            ),
          ],
        ),
        if (r.courses.isNotEmpty) ...[
          const _Label('Courses'),
          SizedBox(
            height: 142,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              clipBehavior: Clip.none,
              itemCount: r.courses.length,
              separatorBuilder: (_, _) => const SizedBox(width: 10),
              itemBuilder: (context, i) => _CourseCard(course: r.courses[i], min: r.minConducted),
            ),
          ),
        ],
      ],
    );
  }
}

/// "Fall 2026 · Full semester" → ("Fall 2026", "Full semester").
(String, String?) _splitLabel(String? label) {
  if (label == null) return ('This semester', null);
  final parts = label.split(' · ');
  return (parts.first, parts.length > 1 ? parts.sublist(1).join(' · ') : null);
}

/// How much of what was checked was held, and the makeups.
class _SemesterCard extends StatelessWidget {
  const _SemesterCard({required this.report});
  final TeacherReport report;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final r = report;
    final decided = r.conducted + r.missed > 0;
    final rate = r.conductRate.clamp(0, 100) / 100;
    final ringColor = !decided ? p.inkFaint : (rate >= 0.9 ? p.okSolid : (rate >= 0.75 ? p.warnSolid : p.badSolid));
    final (_, span) = _splitLabel(r.label);

    return Panel(
      padding: const EdgeInsets.all(18),
      child: Row(
        children: [
          SizedBox(
            width: 96,
            height: 96,
            child: CustomPaint(
              painter: _Ring(value: decided ? rate.toDouble() : 0, color: ringColor, track: p.line),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      decided ? '${r.conductRate.round()}%' : '—',
                      style: TextStyle(fontSize: 23, fontWeight: FontWeight.w800, color: p.ink, fontFeatures: tabular),
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
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: '${r.conducted}',
                        style: TextStyle(color: p.ink),
                      ),
                      TextSpan(
                        text: ' / ${r.totalScheduled}',
                        style: TextStyle(color: p.inkFaint),
                      ),
                    ],
                  ),
                  style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800, fontFeatures: tabular),
                ),
                Text(
                  'classes held${span != null ? ' · ${span.toLowerCase()}' : ''}',
                  style: TextStyle(fontSize: 13, color: p.inkSoft, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    Pill(
                      '${r.makeupCompleted} made up',
                      color: p.info,
                      background: p.infoSoft,
                      icon: Icons.sync_rounded,
                    ),
                    if (r.makeupPending > 0) Pill('${r.makeupPending} pending', color: p.warn, background: p.warnSoft),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// One figure, with its icon and colour.
class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
    required this.tint,
  });

  final IconData icon;
  final int value;
  final String label;
  final Color color, tint;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Expanded(
      child: Panel(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(color: tint, borderRadius: BorderRadius.circular(12)),
              child: Icon(icon, color: color, size: 21),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '$value',
                    style: TextStyle(
                      fontSize: 22,
                      height: 1.1,
                      fontWeight: FontWeight.w800,
                      color: value == 0 ? p.inkFaint : p.ink,
                      fontFeatures: tabular,
                    ),
                  ),
                  Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12.5, color: p.inkSoft, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// One course-section: classes held so far against the minimum.
class _CourseCard extends StatelessWidget {
  const _CourseCard({required this.course, required this.min});
  final CourseTally course;
  final int min;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final c = course;
    final met = min > 0 && c.held >= min;
    final progress = min == 0 ? 0.0 : (c.held / min).clamp(0, 1).toDouble();

    return SizedBox(
      width: 168,
      child: Panel(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    c.courseCode.split('(').first,
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.3),
                  ),
                ),
                if (met) Icon(Icons.verified_rounded, color: p.ok, size: 20),
              ],
            ),
            Text('Section ${c.section}', style: TextStyle(fontSize: 13, color: p.inkSoft)),
            const Spacer(),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${c.held}',
                  style: TextStyle(
                    fontSize: 24,
                    height: 1,
                    fontWeight: FontWeight.w800,
                    color: met ? p.ok : p.ink,
                    fontFeatures: tabular,
                  ),
                ),
                Text(
                  ' / $min',
                  style: TextStyle(fontSize: 14, color: p.inkFaint, fontWeight: FontWeight.w700, fontFeatures: tabular),
                ),
                const Spacer(),
                if (c.missed > 0)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(color: p.bad, shape: BoxShape.circle),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '${c.missed}',
                        style: TextStyle(fontSize: 13, color: p.bad, fontWeight: FontWeight.w800),
                      ),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 10),
            ProgressBar(value: progress, color: met ? p.okSolid : p.brandSolid, track: p.line, height: 6),
          ],
        ),
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
          ? Row(
              children: [
                Icon(Icons.layers_outlined, color: p.inkFaint),
                const SizedBox(width: 10),
                Expanded(
                  child: Text('None assigned — any floor is yours to check.', style: TextStyle(color: p.inkSoft)),
                ),
              ],
            )
          : Wrap(
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
    );
  }
}

// --- rows in a card -------------------------------------------------------------------

/// A card of rows, divided by hairlines.
class _Card extends StatelessWidget {
  const _Card({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Panel(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[if (i > 0) Divider(indent: 64, color: p.line), children[i]],
        ],
      ),
    );
  }
}

/// An icon, a label, and a value under it or a control beside it.
class _Row extends StatelessWidget {
  const _Row({
    required this.icon,
    required this.label,
    this.value,
    this.trailing,
    this.onTap,
    this.warn = false,
    this.danger = false,
  });

  final IconData icon;
  final String label;
  final String? value;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool warn, danger;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final (fg, tint) = danger ? (p.bad, p.badSoft) : (p.brand, p.brandSoft);
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(color: tint, borderRadius: BorderRadius.circular(11)),
              child: Icon(icon, color: fg, size: 19),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: value == null
                  ? Text(
                      label,
                      style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: danger ? p.bad : p.ink),
                    )
                  : Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          label,
                          style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: p.inkFaint),
                        ),
                        const SizedBox(height: 1),
                        Text(
                          value!,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: warn ? p.warn : p.ink),
                        ),
                      ],
                    ),
            ),
            ?trailing,
          ],
        ),
      ),
    );
  }
}

/// The current choice, then a chevron.
class _Value extends StatelessWidget {
  const _Value(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          text,
          style: TextStyle(fontSize: 14.5, color: p.inkSoft, fontWeight: FontWeight.w600),
        ),
        Icon(Icons.chevron_right_rounded, color: p.inkFaint),
      ],
    );
  }
}

/// Add or change, as a small round button.
class _EditButton extends StatelessWidget {
  const _EditButton({required this.add, required this.onTap});
  final bool add;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return IconButton(
      onPressed: onTap,
      tooltip: add ? 'Add' : 'Change',
      style: IconButton.styleFrom(
        backgroundColor: p.subtle,
        side: BorderSide(color: p.line),
      ),
      icon: Icon(add ? Icons.add_rounded : Icons.edit_outlined, size: 19, color: p.brand),
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
            color: p.subtle,
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
