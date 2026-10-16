import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import 'class_view.dart';
import 'student.dart';

/// My Routine: the class on now or next, and the week a day at a time.
class StudentRoutineTab extends StatefulWidget {
  const StudentRoutineTab({super.key, required this.feed, this.focusDate});
  final StudentFeed feed;

  /// A day to open on, from a push about a class.
  final String? focusDate;

  @override
  State<StudentRoutineTab> createState() => _StudentRoutineTabState();
}

class _StudentRoutineTabState extends State<StudentRoutineTab> {
  late DateTime _week;
  late String _day;
  final _cache = <String, List<StudentClass>>{};
  String? _error;
  int _request = 0;
  late final Timer _tick;

  /// This week; next week on the Friday, when this one is over.
  static DateTime _thisWeek() {
    final today = parseDay(todayIso());
    final start = weekStartOf(today);
    return today.weekday == DateTime.friday ? start.add(const Duration(days: 7)) : start;
  }

  @override
  void initState() {
    super.initState();
    _openOn(widget.focusDate);
    widget.feed.addListener(_refresh);
    _tick = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void didUpdateWidget(StudentRoutineTab old) {
    super.didUpdateWidget(old);
    if (widget.focusDate != null && widget.focusDate != old.focusDate) _openOn(widget.focusDate);
  }

  void _openOn(String? date) {
    final today = todayIso();
    if (date != null) {
      _week = weekStartOf(parseDay(date));
      _day = date;
    } else {
      _week = _thisWeek();
      final inWeek = today.compareTo(isoDate(_week)) >= 0;
      _day = inWeek ? today : isoDate(_week);
    }
    _load();
  }

  @override
  void dispose() {
    widget.feed.removeListener(_refresh);
    _tick.cancel();
    super.dispose();
  }

  void _refresh() => _load(quiet: true);

  String get _key => isoDate(_week);

  Future<void> _load({bool quiet = false}) async {
    final request = ++_request;
    final from = isoDate(_week);
    final to = isoDate(_week.add(const Duration(days: 6)));
    if (!quiet) setState(() => _error = null);
    try {
      final rows = await context.api.studentClasses(widget.feed.groups, from, to);
      if (!mounted || request != _request) return;
      setState(() => _cache[from] = rows);
    } on ApiError catch (e) {
      if (!mounted || request != _request) return;
      final feed = widget.feed.upcoming;
      // No signal, and this week was never kept: the four weeks the feed keeps
      // hold it, from today on.
      if (e.offline && feed.isNotEmpty && to.compareTo(todayIso()) >= 0 && from.compareTo(feed.last.date) <= 0) {
        setState(() {
          _cache[from] = [
            for (final c in feed)
              if (c.date.compareTo(from) >= 0 && c.date.compareTo(to) <= 0) c,
          ];
        });
      } else {
        setState(() => _error = e.message);
      }
    }
  }

  void _move(int weeks) {
    setState(() {
      _week = _week.add(Duration(days: 7 * weeks));
      _day = isoDate(_week);
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final student = StudentScope.of(context);
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListenableBuilder(
          listenable: widget.feed,
          builder: (context, _) {
            final feed = widget.feed;
            final week = _cache[_key];
            final days = [for (var i = 0; i < 6; i++) isoDate(_week.add(Duration(days: i)))];
            final list = (week ?? const <StudentClass>[]).where((c) => c.date == _day).toList();
            final next = feed.nowOrNext;
            return RefreshIndicator(
              onRefresh: () async {
                await feed.load();
                await _load(quiet: true);
              },
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                children: [
                  Text('My Routine', style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 4),
                  Text(student.groups.map(groupLabel).join(' · '), style: TextStyle(fontSize: 14.5, color: p.inkSoft)),
                  const SizedBox(height: 16),
                  if (feed.loading)
                    const Loading(label: 'Loading your classes…')
                  else if (next != null)
                    _UpNext(c: next.$1, now: next.$2)
                  else
                    const Panel(
                      child: EmptyState(
                        icon: Icons.beach_access_rounded,
                        title: 'No classes coming up',
                        body: 'Nothing for your groups in the next four weeks.',
                      ),
                    ),
                  const SizedBox(height: 22),
                  _WeekStrip(
                    week: _week,
                    days: days,
                    selected: _day,
                    counts: {for (final d in days) d: week?.where((c) => c.date == d).length},
                    onPick: (d) => setState(() => _day = d),
                    onMove: _move,
                  ),
                  const SizedBox(height: 12),
                  if (_error != null && week == null)
                    LoadError(message: _error!, onRetry: _load)
                  else if (week == null)
                    const Loading()
                  else if (list.isEmpty)
                    Panel(
                      child: EmptyState(icon: Icons.free_breakfast_outlined, title: 'No classes', body: dayLabel(_day)),
                    )
                  else
                    Panel(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      child: Column(
                        children: [
                          for (var i = 0; i < list.length; i++) ...[
                            if (i > 0) Divider(height: 1, color: p.line),
                            StudentClassTile(c: list[i]),
                          ],
                        ],
                      ),
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _UpNext extends StatelessWidget {
  const _UpNext({required this.c, required this.now});
  final StudentClass c;
  final bool now;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final minutes = dhakaMinutesNow();
    final today = c.date == todayIso();
    final label = now
        ? 'In class now'
        : today
        ? 'Next class'
        : 'Next class · ${dayLabel(c.date)}';
    Widget fact(IconData icon, String text) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: Colors.white),
        const SizedBox(width: 6),
        Text(
          text,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 15.5,
            fontWeight: FontWeight.w700,
            fontFeatures: tabular,
          ),
        ),
      ],
    );
    return InkWell(
      onTap: () => showStudentClass(context, c),
      borderRadius: BorderRadius.circular(24),
      child: Container(
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
        decoration: p.hero(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.16),
                borderRadius: BorderRadius.circular(99),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (now) ...[
                    Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(color: Color(0xFF6EE7B7), shape: BoxShape.circle),
                    ),
                    const SizedBox(width: 7),
                  ],
                  Text(
                    label.toUpperCase(),
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.8,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Text(
              c.courseCode,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 27,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.6,
              ),
            ),
            Text(c.teacher.display, style: const TextStyle(color: Colors.white70, fontSize: 15.5)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 18,
              runSpacing: 6,
              children: [
                fact(
                  c.online ? Icons.videocam_rounded : Icons.meeting_room_rounded,
                  c.online ? 'Online' : c.room ?? '',
                ),
                fact(Icons.schedule_rounded, '${clock(c.start)}–${clock(c.end)}'),
              ],
            ),
            if (c.isMakeup || c.isExtra) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white54),
                ),
                child: Text(
                  c.isExtra ? 'Extra class' : (c.online ? 'Online makeup' : 'Makeup class'),
                  style: const TextStyle(color: Colors.white, fontSize: 12.5, fontWeight: FontWeight.w700),
                ),
              ),
            ],
            if (now || today) ...[
              const SizedBox(height: 16),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.timer_outlined, color: Colors.white, size: 20),
                    const SizedBox(width: 10),
                    Text(
                      now ? 'Ends in ${spanLabel(c.end - minutes)}' : 'Starts in ${spanLabel(c.start - minutes)}',
                      style: const TextStyle(color: Colors.white, fontSize: 15.5, fontWeight: FontWeight.w800),
                    ),
                  ],
                ),
              ),
            ],
            if (c.online && c.joinLink != null) ...[
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: () => openLink(context, c.joinLink!),
                style: FilledButton.styleFrom(backgroundColor: Colors.white, foregroundColor: p.brandSolid),
                icon: const Icon(Icons.videocam_rounded),
                label: const Text('Join the class'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Saturday to Thursday as a row of days, and arrows to the weeks around it.
class _WeekStrip extends StatelessWidget {
  const _WeekStrip({
    required this.week,
    required this.days,
    required this.selected,
    required this.counts,
    required this.onPick,
    required this.onMove,
  });

  final DateTime week;
  final List<String> days;
  final String selected;
  final Map<String, int?> counts;
  final ValueChanged<String> onPick;
  final ValueChanged<int> onMove;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final today = todayIso();
    final end = week.add(const Duration(days: 5));
    return Panel(
      padding: const EdgeInsets.fromLTRB(8, 6, 8, 10),
      child: Column(
        children: [
          Row(
            children: [
              IconButton(
                tooltip: 'Previous week',
                onPressed: () => onMove(-1),
                icon: const Icon(Icons.chevron_left_rounded),
              ),
              Expanded(
                child: Text(
                  '${DateFormat('d MMM').format(week)} – ${DateFormat('d MMM').format(end)}',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: p.ink),
                ),
              ),
              IconButton(
                tooltip: 'Next week',
                onPressed: () => onMove(1),
                icon: const Icon(Icons.chevron_right_rounded),
              ),
            ],
          ),
          Row(
            children: [
              for (final d in days)
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2),
                    child: Material(
                      color: d == selected ? p.brandSolid : Colors.transparent,
                      borderRadius: BorderRadius.circular(14),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(14),
                        onTap: () => onPick(d),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          child: Column(
                            children: [
                              Text(
                                DateFormat('E').format(parseDay(d)),
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: d == selected ? Colors.white70 : p.inkFaint,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                '${parseDay(d).day}',
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                  color: d == selected
                                      ? Colors.white
                                      : d == today
                                      ? p.brand
                                      : p.ink,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Container(
                                width: 6,
                                height: 6,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: (counts[d] ?? 0) == 0
                                      ? Colors.transparent
                                      : d == selected
                                      ? Colors.white
                                      : p.brand,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
