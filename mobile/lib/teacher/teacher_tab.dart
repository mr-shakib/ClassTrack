import 'dart:async';

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import '../widgets/status.dart';
import 'extra_class_screen.dart';
import 'makeup_card.dart';
import 'reschedule_screen.dart';

/// A teacher's own classes: what needs rescheduling, what is rescheduled,
/// today, and how the semester is going. Mirrors web/src/app/teacher/page.tsx.
class TeacherTab extends StatefulWidget {
  const TeacherTab({super.key, required this.active});
  final bool active;

  @override
  State<TeacherTab> createState() => TeacherTabState();
}

class TeacherTabState extends State<TeacherTab> with WidgetsBindingObserver {
  List<ClassInstance> _today = [];
  List<ClassInstance> _needsAction = [];
  List<Makeup> _makeups = [];
  TeacherReport? _report;
  bool _loading = true;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    load();
    if (widget.active) _startPolling();
  }

  @override
  void didUpdateWidget(TeacherTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.active && !oldWidget.active) {
      load();
      _startPolling();
    } else if (!widget.active) {
      _timer?.cancel();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && widget.active) {
      load();
      _startPolling();
    } else if (state == AppLifecycleState.paused) {
      _timer?.cancel();
    }
  }

  // A staff report can land while the screen is open; pick it up.
  void _startPolling() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => load());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    super.dispose();
  }

  Future<void> load() async {
    final api = context.api;
    final initial = SessionScope.read(context).user?.teacherInitial;
    if (initial == null) {
      setState(() => _loading = false);
      return;
    }
    try {
      final results = await Future.wait<Object?>([
        api.instances(date: todayIso()),
        api.instances(needsReschedule: true, limit: 50),
        api.makeups(),
        // The current semester so far. None yet, or not begun: no figures.
        api.teacherReport(initial).then<TeacherReport?>((r) => r).catchError((Object _) => null),
      ]);
      if (!mounted) return;
      setState(() {
        _today = results[0] as List<ClassInstance>;
        _needsAction = results[1] as List<ClassInstance>;
        _makeups = results[2] as List<Makeup>;
        _report = results[3] as TeacherReport?;
        _error = null;
      });
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _reschedule(ClassInstance inst) async {
    final booked = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => RescheduleScreen(instanceId: inst.id, original: inst)),
    );
    if (booked == true) load();
  }

  Future<void> _bookExtra() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ExtraClassScreen()));
    load();
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final user = SessionScope.of(context).user!;

    if (user.teacherInitial == null) {
      return const Scaffold(
        body: Center(
          child: EmptyState(
            icon: Icons.link_off_rounded,
            title: 'This account is not linked to a faculty initial',
            body: 'An administrator needs to set your teacher initial before your schedule can be shown.',
          ),
        ),
      );
    }

    // Soonest first, so the next class to hold is at the top.
    final open = _makeups.where((m) => m.isOpen).toList()..sort((a, b) => a.date.compareTo(b.date));
    final past = _makeups.where((m) => !m.isOpen).toList();
    final todays = [..._today]..sort((a, b) => slots.indexOf(a.timeSlot).compareTo(slots.indexOf(b.timeSlot)));

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: load,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
            children: [
              _Greeting(user: user),
              const SizedBox(height: 18),
              if (_loading)
                const Loading(label: 'Loading your classes…')
              else if (_error != null && _today.isEmpty && _makeups.isEmpty && _needsAction.isEmpty)
                LoadError(message: _error!, onRetry: () {
                  setState(() => _loading = true);
                  load();
                })
              else ...[
                if (_error != null) ...[Notice.error(_error!), const SizedBox(height: 14)],
                if (_report != null) ...[_Stats(report: _report!), const SizedBox(height: 14)],
                if (user.mayBookExtra) ...[
                  _ActionTile(
                    icon: Icons.add_business_rounded,
                    title: 'Book an extra class',
                    subtitle: 'Take an empty room for one of your sections',
                    onTap: _bookExtra,
                  ),
                  const SizedBox(height: 22),
                ],
                // Missed classes come first: they are the only thing here that
                // needs the teacher to act.
                if (_needsAction.isNotEmpty) ...[
                  _NeedsReschedule(
                    classes: _needsAction,
                    mayReschedule: user.mayReschedule,
                    onReschedule: _reschedule,
                  ),
                  const SizedBox(height: 26),
                ],
                if (open.isNotEmpty) ...[
                  SectionHeader(
                    'Rescheduled classes',
                    count: open.length,
                    subtitle: 'Each stays here until you mark it done after the class. An online class needs its Drive link.',
                  ),
                  for (final m in open)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 14),
                      child: MakeupCard(key: ValueKey(m.id), makeup: m, onChanged: load),
                    ),
                  const SizedBox(height: 12),
                ],
                SectionHeader('Today', count: todays.length, subtitle: formatDay(todayIso())),
                Panel(
                  padding: EdgeInsets.zero,
                  child: todays.isEmpty
                      ? const EmptyState(icon: Icons.free_breakfast_outlined, title: 'No classes scheduled today')
                      : Column(
                          children: [
                            for (var i = 0; i < todays.length; i++) ...[
                              if (i > 0) Divider(indent: 16, endIndent: 16, color: p.line),
                              _TodayRow(inst: todays[i]),
                            ],
                          ],
                        ),
                ),
                if (_report != null && _report!.courses.isNotEmpty) ...[
                  const SizedBox(height: 26),
                  SectionHeader(
                    'Your courses',
                    subtitle: 'Classes held so far, against the ${_report!.minConducted} each course needs.',
                  ),
                  _Courses(report: _report!),
                ],
                const SizedBox(height: 26),
                SectionHeader('Past reschedules', count: past.length),
                Panel(
                  padding: EdgeInsets.zero,
                  child: past.isEmpty
                      ? const EmptyState(icon: Icons.history_rounded, title: 'No finished reschedules yet')
                      : Column(
                          children: [
                            for (var i = 0; i < past.length; i++) ...[
                              if (i > 0) Divider(indent: 16, endIndent: 16, color: p.line),
                              MakeupHistoryRow(makeup: past[i]),
                            ],
                          ],
                        ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _Greeting extends StatelessWidget {
  const _Greeting({required this.user});
  final User user;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(greeting(), style: TextStyle(fontSize: 15, color: p.inkSoft, fontWeight: FontWeight.w500)),
              const SizedBox(height: 2),
              Text(
                user.fullName,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 23, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.5, height: 1.2),
              ),
            ],
          ),
        ),
        const SizedBox(width: 12),
        Avatar(name: user.fullName, initial: user.teacherInitial, photo: user.photoUrl, size: 52),
      ],
    );
  }
}

/// The semester so far, in five numbers.
class _Stats extends StatelessWidget {
  const _Stats({required this.report});
  final TeacherReport report;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final r = report;
    Widget metric(String label, int value, Color color) => Expanded(
          child: Column(
            children: [
              Text('$value',
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: color, fontFeatures: tabular)),
              const SizedBox(height: 2),
              Text(label, style: TextStyle(fontSize: 12.5, color: p.inkSoft, fontWeight: FontWeight.w600)),
            ],
          ),
        );

    return Panel(
      padding: const EdgeInsets.fromLTRB(12, 14, 12, 12),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Row(
              children: [
                Icon(Icons.insights_rounded, size: 18, color: p.brand),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(r.label ?? 'This semester',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: p.ink)),
                ),
                Text('${shortDay(r.from)} – ${shortDay(r.to)}', style: TextStyle(fontSize: 12.5, color: p.inkFaint)),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              metric('Scheduled', r.totalScheduled, p.ink),
              metric('Conducted', r.conducted, p.ok),
              metric('Late', r.late, p.warn),
              metric('Missed', r.missed, p.bad),
            ],
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
                    TextSpan(children: [
                      const TextSpan(text: 'Makeups  '),
                      TextSpan(text: '${r.makeupCompleted} done', style: const TextStyle(fontWeight: FontWeight.w800)),
                      TextSpan(text: '  ·  ${r.makeupPending} pending'),
                    ]),
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

class _ActionTile extends StatelessWidget {
  const _ActionTile({required this.icon, required this.title, required this.subtitle, required this.onTap});
  final IconData icon;
  final String title, subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Material(
      color: p.surface,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: p.line, width: 1.2),
          ),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, color: p.brand),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: TextStyle(fontSize: 16.5, fontWeight: FontWeight.w700, color: p.ink)),
                    Text(subtitle, style: TextStyle(fontSize: 14, color: p.inkSoft)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: p.inkFaint),
            ],
          ),
        ),
      ),
    );
  }
}

/// Classes staff reported as not held: each needs a new time.
class _NeedsReschedule extends StatelessWidget {
  const _NeedsReschedule({required this.classes, required this.mayReschedule, required this.onReschedule});
  final List<ClassInstance> classes;
  final bool mayReschedule;
  final ValueChanged<ClassInstance> onReschedule;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: p.bad.withValues(alpha: 0.35), width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            color: p.badSoft,
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.event_busy_rounded, color: p.bad),
                    const SizedBox(width: 8),
                    Text('Reschedule required (${classes.length})',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: p.bad)),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  'Staff reported these classes as not held. Pick a new time and an empty room — '
                  'it is booked straight away, with no approval, and checked like any other class.',
                  style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4),
                ),
              ],
            ),
          ),
          for (var i = 0; i < classes.length; i++) ...[
            if (i > 0) Divider(color: p.line, height: 2, thickness: 2),
            _MissedRow(inst: classes[i], mayReschedule: mayReschedule, onReschedule: onReschedule),
          ],
        ],
      ),
    );
  }
}

class _MissedRow extends StatelessWidget {
  const _MissedRow({required this.inst, required this.mayReschedule, required this.onReschedule});
  final ClassInstance inst;
  final bool mayReschedule;
  final ValueChanged<ClassInstance> onReschedule;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    // Not settled yet: staff may still record a late arrival.
    final reported = inst.status != 'MISSED';
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(inst.courseCode, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.4)),
          Text('Section ${inst.section}', style: TextStyle(fontSize: 15.5, color: p.inkSoft)),
          const SizedBox(height: 6),
          Text('${formatDay(inst.date)} · ${slotLabel(inst.timeSlot)} · ${inst.room}',
              style: TextStyle(fontSize: 14.5, color: p.ink, fontFeatures: tabular)),
          if (reported) ...[
            const SizedBox(height: 10),
            Pill('Reported absent · not final yet', color: p.warn, background: p.warnSoft, icon: Icons.hourglass_top_rounded, large: true),
          ],
          if (mayReschedule) ...[
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () => onReschedule(inst),
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
                icon: const Icon(Icons.event_repeat_rounded),
                label: const Text('Request reschedule'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _TodayRow extends StatelessWidget {
  const _TodayRow({required this.inst});
  final ClassInstance inst;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 62,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(slotStart(inst.timeSlot),
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: p.ink, fontFeatures: tabular)),
                Text(inst.timeSlot.split('-').last,
                    style: TextStyle(fontSize: 13, color: p.inkFaint, fontFeatures: tabular)),
              ],
            ),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${inst.courseCode} · ${inst.section}',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: p.ink)),
                Row(children: [
                  Icon(Icons.meeting_room_outlined, size: 15, color: p.inkSoft),
                  const SizedBox(width: 4),
                  Text(inst.room, style: TextStyle(fontSize: 14.5, color: p.inkSoft)),
                ]),
                if (inst.isMakeup)
                  Padding(padding: const EdgeInsets.only(top: 6), child: RescheduledTag(from: inst.rescheduledFrom))
                else if (inst.isExtra)
                  const Padding(padding: EdgeInsets.only(top: 6), child: ExtraTag()),
              ],
            ),
          ),
          const SizedBox(width: 8),
          StatusBadge(inst.status, lateMinutes: inst.check?.lateMinutes),
        ],
      ),
    );
  }
}

/// Each course-section's classes held so far, against the minimum.
class _Courses extends StatelessWidget {
  const _Courses({required this.report});
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
              child: Builder(builder: (context) {
                final c = report.courses[i];
                final met = min > 0 && c.held >= min;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text('${c.courseCode} · ${c.section}',
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: p.ink)),
                        ),
                        Text.rich(
                          TextSpan(children: [
                            TextSpan(text: '${c.held}', style: TextStyle(color: met ? p.ok : p.ink)),
                            TextSpan(text: ' / $min held', style: TextStyle(color: p.inkSoft, fontWeight: FontWeight.w600)),
                          ]),
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
                    if (c.missed > 0)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text('${c.missed} missed', style: TextStyle(fontSize: 13, color: p.bad, fontWeight: FontWeight.w600)),
                      ),
                  ],
                );
              }),
            ),
          ],
        ],
      ),
    );
  }
}
