import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/client.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import '../widgets/status.dart';
import 'reschedule_screen.dart';
import 'teacher_data.dart';

/// The department's week runs Saturday to Thursday; Friday is the weekend.
DateTime weekStartOf(DateTime day) => day.subtract(Duration(days: (day.weekday + 1) % 7));

/// A teacher's week as a timetable: days across, the six routine slots down,
/// and a row for classes held off the routine's clock, such as an online
/// makeup in the evening. Each class is coloured by what happened to it.
class WeekCalendar extends StatefulWidget {
  const WeekCalendar({super.key, required this.data});
  final TeacherData data;

  @override
  State<WeekCalendar> createState() => _WeekCalendarState();
}

class _WeekCalendarState extends State<WeekCalendar> {
  late DateTime _week = _defaultWeek();
  final _cache = <String, List<UpcomingClass>>{};
  bool _loading = false;
  String? _error;
  int _request = 0;

  /// This week; next week on the Friday, when this one is over.
  static DateTime _defaultWeek() {
    final today = parseDay(todayIso());
    final start = weekStartOf(today);
    return today.weekday == DateTime.friday ? start.add(const Duration(days: 7)) : start;
  }

  String get _key => isoDate(_week);

  @override
  void initState() {
    super.initState();
    widget.data.addListener(_refresh);
    _load();
  }

  @override
  void dispose() {
    widget.data.removeListener(_refresh);
    super.dispose();
  }

  /// The teacher's data reloaded (pull to refresh, a booking): so does the week.
  void _refresh() => _load(quiet: true);

  Future<void> _load({bool quiet = false}) async {
    final request = ++_request;
    final from = isoDate(_week);
    final to = isoDate(_week.add(const Duration(days: 6)));
    if (!quiet || !_cache.containsKey(_key)) setState(() => _loading = true);
    try {
      final rows = await context.api.instances(from: from, to: to, limit: 300);
      if (!mounted || request != _request) return;
      setState(() {
        // An older server ignores from/to: keep the week here too.
        _cache[from] = rows
            .where((i) => i.date.compareTo(from) >= 0 && i.date.compareTo(to) <= 0)
            .map(UpcomingClass.new)
            .toList();
        _error = null;
      });
    } on ApiError catch (e) {
      if (mounted && request == _request) setState(() => _error = e.message);
    } finally {
      if (mounted && request == _request) setState(() => _loading = false);
    }
  }

  void _move(int weeks) {
    setState(() => _week = _week.add(Duration(days: 7 * weeks)));
    _load();
  }

  String _rangeLabel() {
    final end = _week.add(const Duration(days: 5));
    final sameMonth = end.month == _week.month;
    return sameMonth
        ? '${_week.day} – ${DateFormat('d MMM').format(end)}'
        : '${DateFormat('d MMM').format(_week)} – ${DateFormat('d MMM').format(end)}';
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final classes = _cache[_key];
    final thisWeek = isoDate(weekStartOf(parseDay(todayIso()))) == _key;

    // Saturday to Thursday, and Friday only when something is on it.
    final hasFriday = classes?.any((c) => parseDay(c.date).weekday == DateTime.friday) ?? false;
    final days = [for (var i = 0; i < (hasFriday ? 7 : 6); i++) _week.add(Duration(days: i))];

    return Panel(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              _NavButton(icon: Icons.chevron_left_rounded, onTap: () => _move(-1), tooltip: 'Previous week'),
              Expanded(
                child: Column(
                  children: [
                    Text(
                      _rangeLabel(),
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: p.ink, fontFeatures: tabular),
                    ),
                    Text(
                      thisWeek ? 'This week' : (_week.isAfter(parseDay(todayIso())) ? 'Coming week' : 'Past week'),
                      style: TextStyle(fontSize: 12.5, color: p.inkSoft, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
              if (!thisWeek)
                TextButton(
                  onPressed: () {
                    setState(() => _week = _defaultWeek());
                    _load();
                  },
                  style: TextButton.styleFrom(
                    minimumSize: const Size(40, 36),
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                  child: const Text('Today'),
                ),
              _NavButton(icon: Icons.chevron_right_rounded, onTap: () => _move(1), tooltip: 'Next week'),
            ],
          ),
          const SizedBox(height: 10),
          if (_error != null && classes == null)
            Padding(padding: const EdgeInsets.only(bottom: 8), child: Notice.error(_error!))
          else
            Stack(
              children: [
                _Grid(days: days, classes: classes ?? const [], data: widget.data),
                if (_loading && classes == null)
                  const Positioned.fill(
                    child: Center(
                      child: SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2.5)),
                    ),
                  ),
              ],
            ),
          const SizedBox(height: 12),
          const _Legend(),
        ],
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({required this.icon, required this.onTap, required this.tooltip});
  final IconData icon;
  final VoidCallback onTap;
  final String tooltip;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Tooltip(
      message: tooltip,
      child: Material(
        color: p.subtle,
        shape: CircleBorder(side: BorderSide(color: p.line)),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: onTap,
          child: SizedBox(width: 38, height: 38, child: Icon(icon, color: p.ink)),
        ),
      ),
    );
  }
}

/// The timetable itself.
class _Grid extends StatelessWidget {
  const _Grid({required this.days, required this.classes, required this.data});
  final List<DateTime> days;
  final List<UpcomingClass> classes;
  final TeacherData data;

  static const _rowHeight = 58.0;
  static const _timeWidth = 40.0;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final today = todayIso();
    final offClock = classes.where((c) => !slots.contains(c.timeSlot)).toList();

    UpcomingClass? at(String date, String slot) =>
        classes.where((c) => c.date == date && c.timeSlot == slot).firstOrNull;

    Widget dayHeader(DateTime d) {
      final isToday = isoDate(d) == today;
      return Expanded(
        child: Column(
          children: [
            Text(
              DateFormat('EEE').format(d).toUpperCase(),
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.4,
                color: isToday ? p.brand : p.inkFaint,
              ),
            ),
            const SizedBox(height: 3),
            Container(
              width: 28,
              height: 28,
              alignment: Alignment.center,
              decoration: BoxDecoration(color: isToday ? p.brandSolid : Colors.transparent, shape: BoxShape.circle),
              child: Text(
                '${d.day}',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: isToday ? Colors.white : p.ink,
                  fontFeatures: tabular,
                ),
              ),
            ),
          ],
        ),
      );
    }

    Widget row({required Widget label, required List<Widget> cells, double height = _rowHeight}) => SizedBox(
      height: height,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(width: _timeWidth, child: label),
          ...cells,
        ],
      ),
    );

    Widget cell(DateTime d, UpcomingClass? c) {
      final isToday = isoDate(d) == today;
      return Expanded(
        child: Container(
          decoration: BoxDecoration(
            color: isToday ? p.brandSoft.withValues(alpha: p.isDark ? 0.5 : 0.55) : null,
            border: Border(
              top: BorderSide(color: p.line),
              left: BorderSide(color: p.line),
            ),
          ),
          padding: const EdgeInsets.all(2.5),
          child: c == null ? null : _Block(c: c, data: data),
        ),
      );
    }

    return Column(
      children: [
        row(height: 50, label: const SizedBox.shrink(), cells: [for (final d in days) dayHeader(d)]),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Container(
            decoration: BoxDecoration(
              border: Border(
                bottom: BorderSide(color: p.line),
                right: BorderSide(color: p.line),
              ),
            ),
            child: Column(
              children: [
                for (final s in slots)
                  row(
                    label: _TimeLabel(slot: s),
                    cells: [for (final d in days) cell(d, at(isoDate(d), s))],
                  ),
                // Online makeups at a time of their own.
                if (offClock.isNotEmpty)
                  row(
                    label: Center(
                      child: Text(
                        'Other',
                        style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: p.inkFaint),
                      ),
                    ),
                    cells: [for (final d in days) cell(d, offClock.where((c) => c.date == isoDate(d)).firstOrNull)],
                  ),
              ],
            ),
          ),
        ),
        if (classes.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text('No classes this week.', style: TextStyle(fontSize: 14, color: p.inkSoft)),
          ),
      ],
    );
  }
}

class _TimeLabel extends StatelessWidget {
  const _TimeLabel({required this.slot});
  final String slot;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final (start, end) = slotBounds(slot);
    return Padding(
      padding: const EdgeInsets.only(top: 4, right: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(
            clock(start),
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: p.inkSoft, fontFeatures: tabular),
          ),
          Text(
            clock(end),
            style: TextStyle(fontSize: 9.5, color: p.inkFaint, fontFeatures: tabular),
          ),
        ],
      ),
    );
  }
}

/// What a class looks like on the grid, and what the legend calls it.
enum _Kind { now, upcoming, held, late, missed, notChecked, makeup, moved, cancelled }

_Kind _kindOf(UpcomingClass c) {
  final today = todayIso();
  final now = dhakaMinutesNow();
  if (c.date == today && c.start <= now && now < c.end) return _Kind.now;
  return switch (c.status) {
    'RUNNING' => _Kind.held,
    'LATE' => _Kind.late,
    'MISSED' || 'ONLINE_REJECTED' => _Kind.missed,
    'NOT_CHECKED' => _Kind.notChecked,
    'CANCELLED' => _Kind.cancelled,
    // The original of a reschedule: it now happens elsewhere.
    'MAKEUP_REQUESTED' ||
    'MAKEUP_SCHEDULED' ||
    'MAKEUP_COMPLETED' ||
    'ONLINE_PENDING' ||
    'ONLINE_APPROVED' when !c.isMakeup => _Kind.moved,
    _ => c.isMakeup || c.online ? _Kind.makeup : _Kind.upcoming,
  };
}

/// Text colour, fill and edge for each kind.
(Color, Color, Color) _look(Palette p, _Kind k) => switch (k) {
  _Kind.now => (Colors.white, p.brandSolid, p.brandSolid),
  _Kind.upcoming => (p.brand, p.brandSoft, p.brand.withValues(alpha: 0.3)),
  _Kind.held => (p.ok, p.okSoft, p.ok.withValues(alpha: 0.3)),
  _Kind.late => (p.warn, p.warnSoft, p.warn.withValues(alpha: 0.3)),
  _Kind.missed => (p.bad, p.badSoft, p.bad.withValues(alpha: 0.3)),
  _Kind.notChecked => (p.gap, p.gapSoft, p.gap.withValues(alpha: 0.3)),
  _Kind.makeup => (p.info, p.infoSoft, p.info.withValues(alpha: 0.35)),
  _Kind.moved || _Kind.cancelled => (p.inkFaint, p.subtle, p.line),
};

class _Block extends StatelessWidget {
  const _Block({required this.c, required this.data});
  final UpcomingClass c;
  final TeacherData data;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final kind = _kindOf(c);
    final (fg, bg, edge) = _look(p, kind);
    final struck = kind == _Kind.moved || kind == _Kind.cancelled;
    final code = c.courseCode.split('(').first;

    return Material(
      color: bg,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        // An extra class is outlined: booked on top of the routine.
        side: c.isExtra ? BorderSide(color: edge) : BorderSide.none,
      ),
      child: InkWell(
        onTap: () => _showDetails(context, c, data),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(width: 3, color: kind == _Kind.now ? Colors.white70 : fg),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(4, 4, 3, 3),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        code,
                        style: TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w800,
                          color: fg,
                          decoration: struck ? TextDecoration.lineThrough : null,
                          decorationColor: fg,
                        ),
                      ),
                    ),
                    const SizedBox(height: 1),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        c.online ? clock(c.start) : (c.room ?? ''),
                        style: TextStyle(
                          fontSize: 9.5,
                          fontWeight: FontWeight.w600,
                          color: kind == _Kind.now ? Colors.white70 : p.inkSoft,
                          fontFeatures: tabular,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend();

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    const items = [
      (_Kind.upcoming, 'Upcoming'),
      (_Kind.held, 'Held'),
      (_Kind.late, 'Late'),
      (_Kind.missed, 'Missed'),
      (_Kind.notChecked, 'Not checked'),
      (_Kind.makeup, 'Makeup'),
      (_Kind.moved, 'Moved'),
    ];
    return Wrap(
      spacing: 14,
      runSpacing: 6,
      children: [
        for (final (kind, label) in items)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(color: _look(p, kind).$1, borderRadius: BorderRadius.circular(3)),
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(fontSize: 12.5, color: p.inkSoft, fontWeight: FontWeight.w600),
              ),
            ],
          ),
      ],
    );
  }
}

/// One class in full, and the reschedule it may need.
void _showDetails(BuildContext context, UpcomingClass c, TeacherData data) {
  final user = SessionScope.read(context).user;
  final owed = data.needsAction
      .where((i) => i.date == c.date && i.timeSlot == c.timeSlot && i.courseCode == c.courseCode)
      .firstOrNull;
  showModalBottomSheet<void>(
    context: context,
    builder: (sheet) {
      final p = sheet.palette;
      Widget fact(IconData icon, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(
          children: [
            Icon(icon, size: 20, color: p.inkSoft),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                text,
                style: TextStyle(fontSize: 15.5, color: p.ink, fontWeight: FontWeight.w600, fontFeatures: tabular),
              ),
            ),
          ],
        ),
      );

      return SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          c.courseCode,
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w800,
                            color: p.ink,
                            letterSpacing: -0.4,
                          ),
                        ),
                        Text('Section ${c.section}', style: TextStyle(fontSize: 15.5, color: p.inkSoft)),
                      ],
                    ),
                  ),
                  if (_kindOf(c) == _Kind.now)
                    Pill('Now', color: p.brand, background: p.brandSoft, icon: Icons.circle, large: true)
                  else if (_kindOf(c) != _Kind.upcoming && _kindOf(c) != _Kind.makeup)
                    StatusBadge(c.status, lateMinutes: c.check?.lateMinutes, large: true),
                ],
              ),
              const SizedBox(height: 18),
              fact(Icons.event_rounded, formatDay(c.date)),
              fact(Icons.schedule_rounded, c.times),
              fact(
                c.online ? Icons.videocam_rounded : Icons.meeting_room_rounded,
                c.online ? 'Online' : 'Room ${c.room}',
              ),
              if (c.isMakeup || c.isExtra || c.online)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: c.isExtra
                      ? const ExtraTag(large: true)
                      : c.online
                      ? Pill(
                          'Online makeup',
                          color: p.info,
                          background: p.infoSoft,
                          icon: Icons.videocam_rounded,
                          large: true,
                        )
                      : RescheduledTag(from: c.rescheduledFrom, large: true),
                ),
              if (c.rescheduledTo != null && !c.isMakeup)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Notice(
                    'Moved to ${formatDay(c.rescheduledTo!.date)}, ${slot24(c.rescheduledTo!.timeSlot)}'
                    '${c.rescheduledTo!.mode == 'ONLINE' ? ', online' : (c.rescheduledTo!.room != null ? ', room ${c.rescheduledTo!.room}' : '')}'
                    '${c.rescheduledTo!.status == 'PENDING' ? ' — waiting for approval' : ''}.',
                    tone: Tone.info,
                    icon: Icons.sync_rounded,
                  ),
                ),
              if (owed != null && (user?.mayReschedule ?? false)) ...[
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () async {
                      Navigator.of(sheet).pop();
                      final booked = await Navigator.of(context).push<bool>(
                        MaterialPageRoute(
                          builder: (_) => RescheduleScreen(instanceId: owed.id, original: owed),
                        ),
                      );
                      if (booked == true) data.load();
                    },
                    icon: const Icon(Icons.event_repeat_rounded),
                    label: const Text('Request reschedule'),
                  ),
                ),
              ],
            ],
          ),
        ),
      );
    },
  );
}
