import 'dart:async';

import 'package:flutter/material.dart';

import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import '../widgets/status.dart';
import 'student_note.dart';
import 'teacher_data.dart';
import 'week_calendar.dart';

/// A teacher's day: the class on now or next, anything waiting on them, today
/// as a timeline, and the week ahead.
class HomeTab extends StatefulWidget {
  const HomeTab({super.key, required this.data, required this.onOpenReschedule});

  final TeacherData data;

  /// Switches to the Reschedule tab.
  final VoidCallback onOpenReschedule;

  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> {
  late final Timer _tick;

  @override
  void initState() {
    super.initState();
    // "Starts in 12 min" has to move on its own.
    _tick = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = SessionScope.of(context).user!;
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListenableBuilder(
          listenable: widget.data,
          builder: (context, _) {
            final d = widget.data;
            return RefreshIndicator(
              onRefresh: d.load,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                children: [
                  _Greeting(user: user),
                  const SizedBox(height: 18),
                  if (d.loading)
                    const Loading(label: 'Loading your classes…')
                  else if (d.error != null && d.upcoming.isEmpty)
                    LoadError(message: d.error!, onRetry: d.load)
                  else
                    ..._body(context, d),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  List<Widget> _body(BuildContext context, TeacherData d) {
    final p = context.palette;
    final today = todayIso();
    final now = dhakaMinutesNow();
    final todays = d.today;
    final current = todays.where((c) => c.start <= now && now < c.end).firstOrNull;
    final next = d.upcoming.where((c) => c.date != today || c.start > now).firstOrNull;

    return [
      if (d.error != null) ...[Notice.error(d.error!), const SizedBox(height: 14)],
      if (current != null) _NowCard(c: current, now: now) else _NextCard(c: next, now: now),
      if (d.needsAction.isNotEmpty || d.toMarkDone.isNotEmpty || d.awaitingApproval.isNotEmpty)
        const SizedBox(height: 14),
      if (d.needsAction.isNotEmpty)
        _ActionStrip(
          icon: Icons.event_busy_rounded,
          color: p.bad,
          background: p.badSoft,
          text: d.needsAction.length == 1
              ? '1 missed class needs a new time'
              : '${d.needsAction.length} missed classes need a new time',
          onTap: widget.onOpenReschedule,
        ),
      if (d.toMarkDone.isNotEmpty)
        _ActionStrip(
          icon: Icons.task_alt_rounded,
          color: p.warn,
          background: p.warnSoft,
          text: d.toMarkDone.length == 1
              ? '1 makeup is over — mark it done'
              : '${d.toMarkDone.length} makeups are over — mark them done',
          onTap: widget.onOpenReschedule,
        ),
      if (d.awaitingApproval.isNotEmpty)
        _ActionStrip(
          icon: Icons.hourglass_top_rounded,
          color: p.info,
          background: p.infoSoft,
          text: d.awaitingApproval.length == 1
              ? '1 online class is waiting for approval'
              : '${d.awaitingApproval.length} online classes are waiting for approval',
          onTap: widget.onOpenReschedule,
        ),
      if (SessionScope.read(context).user?.mayMessageStudents ?? false) ...[
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const MessageStudentsScreen())),
          style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(50)),
          icon: const Icon(Icons.campaign_outlined),
          label: const Text('Message your students'),
        ),
      ],
      const SizedBox(height: 26),
      SectionHeader('Today', count: todays.length, subtitle: formatDay(today)),
      if (todays.isEmpty)
        const Panel(
          child: EmptyState(icon: Icons.free_breakfast_outlined, title: 'No classes today'),
        )
      else
        Panel(
          padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
          child: Column(
            children: [
              for (var i = 0; i < todays.length; i++)
                _TimelineRow(
                  c: todays[i],
                  now: now,
                  isNext: identical(todays[i], next),
                  first: i == 0,
                  last: i == todays.length - 1,
                ),
            ],
          ),
        ),
      const SizedBox(height: 26),
      const SectionHeader('Week', subtitle: 'Every class, by day and slot. Tap one for its details.'),
      WeekCalendar(data: d),
    ];
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
              Text(
                '${greeting()},',
                style: TextStyle(fontSize: 15, color: p.inkSoft, fontWeight: FontWeight.w500),
              ),
              const SizedBox(height: 2),
              Text(
                user.fullName,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 23,
                  fontWeight: FontWeight.w800,
                  color: p.ink,
                  letterSpacing: -0.5,
                  height: 1.2,
                ),
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

/// Where and when, in a row of icons under a class's name.
class _Facts extends StatelessWidget {
  const _Facts({required this.c, required this.color});
  final UpcomingClass c;
  final Color color;

  @override
  Widget build(BuildContext context) {
    Widget fact(IconData icon, String text) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: color),
        const SizedBox(width: 6),
        Text(
          text,
          style: TextStyle(color: color, fontSize: 15.5, fontWeight: FontWeight.w700, fontFeatures: tabular),
        ),
      ],
    );
    return Wrap(
      spacing: 18,
      runSpacing: 6,
      children: [
        fact(c.online ? Icons.videocam_rounded : Icons.meeting_room_rounded, c.online ? 'Online' : c.room!),
        fact(Icons.schedule_rounded, c.times),
      ],
    );
  }
}

/// The class on now: how far through it is, and what staff recorded.
class _NowCard extends StatelessWidget {
  const _NowCard({required this.c, required this.now});
  final UpcomingClass c;
  final int now;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final elapsed = (now - c.start) / (c.end - c.start);
    final check = c.check;
    final recorded = switch (check?.outcome) {
      'RUNNING' => 'Staff recorded it conducted',
      'LATE' => 'Staff recorded you late${check?.lateMinutes != null ? ' · ${check!.lateMinutes} min' : ''}',
      'TEACHER_NOT_FOUND' => 'Staff reported you absent',
      _ => null,
    };

    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
      decoration: p.hero(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _HeroLabel(text: 'In class now', live: true),
          const SizedBox(height: 12),
          Text(
            c.courseCode,
            style: const TextStyle(color: Colors.white, fontSize: 27, fontWeight: FontWeight.w800, letterSpacing: -0.6),
          ),
          Text('Section ${c.section}', style: const TextStyle(color: Colors.white70, fontSize: 15.5)),
          const SizedBox(height: 12),
          _Facts(c: c, color: Colors.white),
          const SizedBox(height: 16),
          ProgressBar(value: elapsed, color: Colors.white, track: Colors.white.withValues(alpha: 0.25), height: 8),
          const SizedBox(height: 10),
          Row(
            children: [
              Text(
                'Ends in ${spanLabel(c.end - now)}',
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14.5),
              ),
              const Spacer(),
              if (recorded != null)
                Flexible(
                  child: Text(
                    recorded,
                    textAlign: TextAlign.right,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white70, fontSize: 13.5, fontWeight: FontWeight.w600),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

/// The next class, today or on a coming day; or that there is none.
class _NextCard extends StatelessWidget {
  const _NextCard({required this.c, required this.now});
  final UpcomingClass? c;
  final int now;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final c = this.c;
    if (c == null) {
      return Panel(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(14)),
              child: Icon(Icons.beach_access_rounded, color: p.brand),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'No classes coming up',
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: p.ink),
                  ),
                  Text(
                    'Nothing on your schedule for the next three weeks.',
                    style: TextStyle(fontSize: 14.5, color: p.inkSoft),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    final today = c.date == todayIso();
    final wait = c.start - now;
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
      decoration: p.hero(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _HeroLabel(text: today ? 'Next class' : 'Next class · ${dayLabel(c.date)}'),
          const SizedBox(height: 12),
          Text(
            c.courseCode,
            style: const TextStyle(color: Colors.white, fontSize: 27, fontWeight: FontWeight.w800, letterSpacing: -0.6),
          ),
          Text('Section ${c.section}', style: const TextStyle(color: Colors.white70, fontSize: 15.5)),
          const SizedBox(height: 12),
          _Facts(c: c, color: Colors.white),
          if (c.isMakeup || c.isExtra) ...[
            const SizedBox(height: 10),
            _HeroTag(c.isExtra ? 'Extra class' : (c.online ? 'Online makeup' : 'Makeup class')),
          ],
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
                  today ? 'Starts in ${spanLabel(wait)}' : '${mediumDay(c.date)} at ${clock(c.start)}',
                  style: const TextStyle(color: Colors.white, fontSize: 15.5, fontWeight: FontWeight.w800),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _HeroLabel extends StatelessWidget {
  const _HeroLabel({required this.text, this.live = false});
  final String text;
  final bool live;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.16), borderRadius: BorderRadius.circular(99)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (live) ...[
            Container(
              width: 8,
              height: 8,
              decoration: const BoxDecoration(color: Color(0xFF6EE7B7), shape: BoxShape.circle),
            ),
            const SizedBox(width: 7),
          ],
          Text(
            text.toUpperCase(),
            style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: 0.8),
          ),
        ],
      ),
    );
  }
}

class _HeroTag extends StatelessWidget {
  const _HeroTag(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(8),
      border: Border.all(color: Colors.white54),
    ),
    child: Text(
      text,
      style: const TextStyle(color: Colors.white, fontSize: 12.5, fontWeight: FontWeight.w700),
    ),
  );
}

/// Something waiting on the teacher, one tap from where it is dealt with.
class _ActionStrip extends StatelessWidget {
  const _ActionStrip({
    required this.icon,
    required this.color,
    required this.background,
    required this.text,
    required this.onTap,
  });

  final IconData icon;
  final Color color, background;
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: background,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: color.withValues(alpha: 0.25)),
            ),
            child: Row(
              children: [
                Icon(icon, color: color, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    text,
                    style: TextStyle(color: color, fontSize: 15.5, fontWeight: FontWeight.w700),
                  ),
                ),
                Icon(Icons.chevron_right_rounded, color: color),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// One of today's classes on a timeline: done, on now, or still to come.
class _TimelineRow extends StatelessWidget {
  const _TimelineRow({
    required this.c,
    required this.now,
    required this.isNext,
    required this.first,
    required this.last,
  });

  final UpcomingClass c;
  final int now;
  final bool isNext, first, last;

  static const _recorded = {
    'RUNNING',
    'LATE',
    'MISSED',
    'NOT_CHECKED',
    'MAKEUP_REQUESTED',
    'MAKEUP_SCHEDULED',
    'MAKEUP_COMPLETED',
    'CANCELLED',
  };

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final past = c.end <= now;
    final current = c.start <= now && now < c.end;
    final recorded = _recorded.contains(c.status);

    final dotColor = current
        ? p.brandSolid
        : past
        ? (recorded ? statusStyle(context, c.status).$2 : p.inkFaint)
        : p.surface;

    final Widget trailing;
    if (current) {
      trailing = Pill('Now', color: p.brand, background: p.brandSoft, icon: Icons.circle);
    } else if (recorded) {
      trailing = StatusBadge(c.status, lateMinutes: c.check?.lateMinutes);
    } else if (past) {
      trailing = Pill('Not reported yet', color: p.inkSoft, background: p.subtle);
    } else if (isNext) {
      trailing = Pill('Next', color: p.brand, background: p.brandSoft);
    } else {
      trailing = const SizedBox.shrink();
    }

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 50,
            child: Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    clock(c.start),
                    style: TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.w800,
                      color: past && !current ? p.inkSoft : p.ink,
                      fontFeatures: tabular,
                    ),
                  ),
                  Text(
                    clock(c.end),
                    style: TextStyle(fontSize: 12.5, color: p.inkFaint, fontFeatures: tabular),
                  ),
                ],
              ),
            ),
          ),
          SizedBox(
            width: 26,
            child: Column(
              children: [
                Container(width: 2, height: 14, color: first ? Colors.transparent : p.line),
                Container(
                  width: 14,
                  height: 14,
                  decoration: BoxDecoration(
                    color: dotColor,
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: current ? p.brandSoft : (past ? dotColor : p.line),
                      width: current ? 3 : 2,
                    ),
                  ),
                ),
                Expanded(child: Container(width: 2, color: last ? Colors.transparent : p.line)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          '${c.courseCode} · ${c.section}',
                          style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: p.ink),
                        ),
                      ),
                      const SizedBox(width: 8),
                      trailing,
                    ],
                  ),
                  const SizedBox(height: 3),
                  Row(
                    children: [
                      Icon(
                        c.online ? Icons.videocam_outlined : Icons.meeting_room_outlined,
                        size: 15,
                        color: p.inkSoft,
                      ),
                      const SizedBox(width: 5),
                      Text(c.online ? 'Online' : c.room!, style: TextStyle(fontSize: 14, color: p.inkSoft)),
                    ],
                  ),
                  if (c.isMakeup && !c.online)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: RescheduledTag(from: c.rescheduledFrom),
                    )
                  else if (c.online)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Pill('Online makeup', color: p.info, background: p.infoSoft, icon: Icons.videocam_rounded),
                    )
                  else if (c.isExtra)
                    const Padding(padding: EdgeInsets.only(top: 6), child: ExtraTag()),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
