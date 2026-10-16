import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import 'class_view.dart';
import 'student.dart';

/// Makeup Radar: makeups, extra classes and cancellations for the student's
/// groups over the next four weeks.
class StudentRadarTab extends StatelessWidget {
  const StudentRadarTab({super.key, required this.feed});
  final StudentFeed feed;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Scaffold(
      appBar: AppBar(title: const Text('Makeup Radar')),
      body: ListenableBuilder(
        listenable: feed,
        builder: (context, _) {
          final radar = feed.radar;
          return RefreshIndicator(
            onRefresh: feed.load,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
              children: [
                Text(
                  'Makeups, extra classes and cancellations for your groups, the next four weeks.',
                  style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4),
                ),
                const SizedBox(height: 14),
                if (feed.loading)
                  const Loading()
                else if (feed.error != null && feed.upcoming.isEmpty)
                  LoadError(message: feed.error!, onRetry: feed.load)
                else if (radar.isEmpty)
                  const Panel(
                    child: EmptyState(
                      icon: Icons.radar_rounded,
                      title: 'Nothing off the routine',
                      body: 'No makeup, extra or cancelled class coming up. You will hear the moment one is.',
                    ),
                  )
                else
                  Panel(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    child: Column(
                      children: [
                        for (var i = 0; i < radar.length; i++) ...[
                          if (i > 0) Divider(height: 1, color: p.line),
                          StudentClassTile(c: radar[i], showDay: true),
                        ],
                      ],
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}

/// Updates: Change Alerts when a class moves, and Section Notices from
/// teachers and the department.
class StudentUpdatesTab extends StatefulWidget {
  const StudentUpdatesTab({super.key, required this.feed, required this.active});
  final StudentFeed feed;
  final bool active;

  @override
  State<StudentUpdatesTab> createState() => _StudentUpdatesTabState();
}

class _StudentUpdatesTabState extends State<StudentUpdatesTab> {
  /// What had been read when the tab opened, so new ones stay marked while it is open.
  int _seenAtOpen = 0;

  @override
  void initState() {
    super.initState();
    _seenAtOpen = StudentScope.read(context).seen;
    if (widget.active) _markRead();
  }

  @override
  void didUpdateWidget(StudentUpdatesTab old) {
    super.didUpdateWidget(old);
    if (widget.active && !old.active) {
      _seenAtOpen = StudentScope.read(context).seen;
      widget.feed.load().then((_) => _markRead());
    }
  }

  void _markRead() {
    final newest = widget.feed.notices.firstOrNull;
    if (newest != null) StudentScope.read(context).markSeen(newest.id);
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Scaffold(
      appBar: AppBar(title: const Text('Updates')),
      body: ListenableBuilder(
        listenable: widget.feed,
        builder: (context, _) {
          final items = widget.feed.notices;
          return RefreshIndicator(
            onRefresh: widget.feed.load,
            child: widget.feed.loading
                ? ListView(children: const [Loading()])
                : items.isEmpty
                ? ListView(
                    children: const [
                      SizedBox(height: 60),
                      EmptyState(
                        icon: Icons.notifications_none_rounded,
                        title: 'Nothing yet',
                        body: 'When one of your classes moves, or someone writes to your section, it shows here.',
                      ),
                    ],
                  )
                : ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
                    itemCount: items.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (context, i) => _NoticeTile(n: items[i], unread: items[i].id > _seenAtOpen, p: p),
                  ),
          );
        },
      ),
    );
  }
}

class _NoticeTile extends StatelessWidget {
  const _NoticeTile({required this.n, required this.unread, required this.p});
  final StudentNotice n;
  final bool unread;
  final Palette p;

  @override
  Widget build(BuildContext context) {
    final (icon, fg, bg) = switch (n.kind) {
      'CHANGE' => (Icons.sync_rounded, p.info, p.infoSoft),
      'TEACHER' => (Icons.chat_bubble_outline_rounded, p.brand, p.brandSoft),
      _ => (Icons.campaign_rounded, p.warn, p.warnSoft),
    };
    final about = n.about;
    return Material(
      color: p.surface,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: about == null ? null : () => showStudentClass(context, about),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: unread ? p.brand.withValues(alpha: p.isDark ? 0.25 : 0.35) : p.line, width: 1.2),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, color: fg, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            n.title,
                            style: TextStyle(
                              fontSize: 15.5,
                              fontWeight: unread ? FontWeight.w800 : FontWeight.w600,
                              color: p.ink,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(relativeTime(n.createdAt), style: TextStyle(fontSize: 12.5, color: p.inkFaint)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(n.body, style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4)),
                    const SizedBox(height: 4),
                    Text(n.author, style: TextStyle(fontSize: 12.5, color: p.inkFaint)),
                    if (about != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          'Open the class ›',
                          style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: p.brand),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Free Room Finder: rooms with no class in them, today or tomorrow, by slot.
class StudentRoomsTab extends StatefulWidget {
  const StudentRoomsTab({super.key, required this.active});
  final bool active;

  @override
  State<StudentRoomsTab> createState() => _StudentRoomsTabState();
}

class _StudentRoomsTabState extends State<StudentRoomsTab> {
  late String _day = todayIso();
  List<FreeSlot>? _slots;
  String? _slot;
  String? _error;
  String _kind = 'all';
  int _request = 0;
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    if (widget.active) _load();
  }

  @override
  void didUpdateWidget(StudentRoomsTab old) {
    super.didUpdateWidget(old);
    if (widget.active && !old.active) _load();
  }

  Future<void> _load() async {
    final request = ++_request;
    _loaded = true;
    setState(() => _slots = null);
    try {
      final slots = await context.api.studentFreeRooms(_day);
      if (!mounted || request != _request) return;
      final now = dhakaMinutesNow();
      // The slot on now or the next one; on another day, the first.
      final pick = _day == todayIso() ? slots.where((s) => slotBounds(s.timeSlot).$2 > now).firstOrNull : null;
      setState(() {
        _slots = slots;
        _slot = (pick ?? slots.firstOrNull)?.timeSlot;
        _error = null;
      });
    } on ApiError catch (e) {
      if (!mounted || request != _request) return;
      setState(() {
        _error = e.message;
        _slots = const [];
      });
    }
  }

  static bool _isLab(String type) => type.toLowerCase().contains('lab');

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final today = todayIso();
    final tomorrow = isoDate(parseDay(today).add(const Duration(days: 1)));
    final slots = _slots;
    final current = slots?.where((s) => s.timeSlot == _slot).firstOrNull;
    final rooms = (current?.rooms ?? const <FreeRoom>[])
        .where((r) => _kind == 'all' || (_kind == 'lab') == _isLab(r.roomType))
        .toList();
    final byZone = <String, List<FreeRoom>>{};
    for (final r in rooms) {
      byZone.putIfAbsent(r.zone, () => []).add(r);
    }

    Widget choice(String label, bool on, VoidCallback onTap) =>
        ChoiceChip(label: Text(label), selected: on, onSelected: (_) => onTap());

    return Scaffold(
      appBar: AppBar(title: const Text('Free Room Finder')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
          children: [
            Text('Rooms with no class in them, for group study.', style: TextStyle(fontSize: 14.5, color: p.inkSoft)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                choice('Today', _day == today, () {
                  _day = today;
                  _load();
                }),
                choice('Tomorrow', _day == tomorrow, () {
                  _day = tomorrow;
                  _load();
                }),
              ],
            ),
            if (slots != null && slots.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: [
                  for (final s in slots)
                    choice(slot24(s.timeSlot), s.timeSlot == _slot, () => setState(() => _slot = s.timeSlot)),
                ],
              ),
              const SizedBox(height: 4),
              Wrap(
                spacing: 8,
                children: [
                  choice('All rooms', _kind == 'all', () => setState(() => _kind = 'all')),
                  choice('Classrooms', _kind == 'theory', () => setState(() => _kind = 'theory')),
                  choice('Labs', _kind == 'lab', () => setState(() => _kind = 'lab')),
                ],
              ),
            ],
            const SizedBox(height: 14),
            if (!_loaded || slots == null)
              const Loading()
            else if (_error != null)
              LoadError(message: _error!, onRetry: _load)
            else if (slots.isEmpty)
              const Panel(
                child: EmptyState(
                  icon: Icons.door_front_door_outlined,
                  title: 'No classes that day',
                  body: 'On a weekend or a holiday nothing is listed, since rooms may be locked.',
                ),
              )
            else if (rooms.isEmpty)
              const Panel(
                child: EmptyState(
                  icon: Icons.meeting_room_outlined,
                  title: 'No free room then',
                  body: 'Every room is taken in that slot. Try another.',
                ),
              )
            else
              Panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${rooms.length} free at ${slot24(_slot!)}',
                      style: TextStyle(fontWeight: FontWeight.w800, color: p.ok, fontSize: 15),
                    ),
                    for (final entry in byZone.entries) ...[
                      const SizedBox(height: 14),
                      Text(
                        entry.key.toUpperCase(),
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                          color: p.inkFaint,
                          letterSpacing: 0.6,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final r in entry.value)
                            Pill(
                              _isLab(r.roomType) ? '${r.room} · Lab' : r.room,
                              color: p.ok,
                              background: p.okSoft,
                              large: true,
                            ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
