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

  bool _wanted(FreeRoom r) => _kind == 'all' || (_kind == 'lab') == _isLab(r.roomType);

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final today = todayIso();
    final tomorrow = isoDate(parseDay(today).add(const Duration(days: 1)));
    final slots = _slots;
    final current = slots?.where((s) => s.timeSlot == _slot).firstOrNull;
    final rooms = (current?.rooms ?? const <FreeRoom>[]).where(_wanted).toList();
    // By building: a floor often has one free room, and a panel each would be a long scroll.
    final byBuilding = <String, List<FreeRoom>>{};
    for (final r in rooms) {
      byBuilding.putIfAbsent(_ZoneRooms.place(r.zone).$1, () => []).add(r);
    }
    final now = dhakaMinutesNow();
    final live = _day == today
        ? slots?.where((s) => slotBounds(s.timeSlot).$1 <= now && now < slotBounds(s.timeSlot).$2).firstOrNull?.timeSlot
        : null;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
            children: [
              Text('Free rooms', style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 2),
              Text('Empty classrooms and labs, for group study.', style: TextStyle(fontSize: 14.5, color: p.inkSoft)),
              const SizedBox(height: 16),
              SegmentedSwitch<String>(
                options: [(today, 'Today', null), (tomorrow, 'Tomorrow', null)],
                value: _day,
                onChanged: (d) {
                  if (d == _day) return;
                  _day = d;
                  _load();
                },
              ),
              const SizedBox(height: 14),
              if (!_loaded || slots == null)
                const Loading(label: 'Finding empty rooms…')
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
              else ...[
                Row(
                  children: [
                    for (var i = 0; i < slots.length; i++) ...[
                      if (i > 0) const SizedBox(width: 6),
                      Expanded(
                        child: _SlotPick(
                          slot: slots[i],
                          free: slots[i].rooms.where(_wanted).length,
                          selected: slots[i].timeSlot == _slot,
                          live: slots[i].timeSlot == live,
                          onTap: () => setState(() => _slot = slots[i].timeSlot),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 14),
                _FreeSummary(
                  count: rooms.length,
                  when: '${slot24(_slot!)} · ${_day == today ? 'Today' : 'Tomorrow'}',
                  live: _slot == live,
                ),
                const SizedBox(height: 14),
                SegmentedSwitch<String>(
                  options: const [
                    ('all', 'All', null),
                    ('theory', 'Classrooms', Icons.chair_alt_outlined),
                    ('lab', 'Labs', Icons.computer_rounded),
                  ],
                  value: _kind,
                  onChanged: (k) => setState(() => _kind = k),
                ),
                const SizedBox(height: 16),
                if (rooms.isEmpty)
                  const Panel(
                    child: EmptyState(
                      icon: Icons.meeting_room_outlined,
                      title: 'Nothing free then',
                      body: 'Every room of this kind is taken in that slot. Try another time.',
                    ),
                  )
                else
                  for (final entry in byBuilding.entries) ...[
                    _ZoneRooms(building: entry.key, rooms: entry.value),
                    const SizedBox(height: 12),
                  ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// A slot to pick: when it starts, and how many rooms are free in it.
class _SlotPick extends StatelessWidget {
  const _SlotPick({
    required this.slot,
    required this.free,
    required this.selected,
    required this.live,
    required this.onTap,
  });

  final FreeSlot slot;
  final int free;
  final bool selected, live;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final fg = selected ? Colors.white : p.ink;
    return Material(
      color: selected ? p.brandSolid : p.surface,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Container(
          height: 62,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: selected ? p.brandSolid : p.line, width: 1.2),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              FittedBox(
                child: Text(
                  clock(slotBounds(slot.timeSlot).$1),
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: fg, fontFeatures: tabular),
                ),
              ),
              const SizedBox(height: 3),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (live) ...[
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(color: selected ? Colors.white : p.ok, shape: BoxShape.circle),
                    ),
                    const SizedBox(width: 4),
                  ],
                  Text(
                    '$free',
                    style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      color: selected ? Colors.white70 : (free == 0 ? p.inkFaint : p.ok),
                      fontFeatures: tabular,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// How many are free, and when: the answer, before the list.
class _FreeSummary extends StatelessWidget {
  const _FreeSummary({required this.count, required this.when, required this.live});
  final int count;
  final String when;
  final bool live;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
      decoration: p.hero(radius: 20),
      child: Row(
        children: [
          Text(
            '$count',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 40,
              fontWeight: FontWeight.w800,
              letterSpacing: -1,
              height: 1,
              fontFeatures: tabular,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  count == 1 ? 'room free' : 'rooms free',
                  style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 2),
                Text(
                  live ? '$when · on now' : when,
                  style: const TextStyle(color: Colors.white70, fontSize: 14, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.meeting_room_rounded, color: Colors.white),
          ),
        ],
      ),
    );
  }
}

/// One building's free rooms, as a grid of tiles, lowest floor first.
class _ZoneRooms extends StatelessWidget {
  const _ZoneRooms({required this.building, required this.rooms});
  final String building;
  final List<FreeRoom> rooms;

  /// "ANX1-2" -> ("ANX1", "Floor 2"); "G1-0" -> ("G1", "Ground floor").
  static (String, String?) place(String zone) {
    final m = RegExp(r'^(.+)-(\d+)$').firstMatch(zone);
    if (m == null) return (zone, null);
    final floor = int.parse(m.group(2)!);
    return (m.group(1)!, floor == 0 ? 'Ground floor' : 'Floor $floor');
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Panel(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(10)),
                child: Icon(Icons.apartment_rounded, size: 18, color: p.brand),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  building,
                  style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w800, color: p.ink),
                ),
              ),
              Text(
                '${rooms.length} free',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: p.ok),
              ),
            ],
          ),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, box) {
              const gap = 8.0;
              final columns = box.maxWidth > 420 ? 4 : 3;
              final width = (box.maxWidth - gap * (columns - 1)) / columns;
              return Wrap(
                spacing: gap,
                runSpacing: gap,
                children: [
                  for (final r in rooms)
                    SizedBox(
                      width: width,
                      child: _RoomTile(room: r),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _RoomTile extends StatelessWidget {
  const _RoomTile({required this.room});
  final FreeRoom room;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final lab = room.roomType.toLowerCase().contains('lab');
    // "ANX1-210": the building is on the card already; the number is what people look for.
    final dash = room.room.lastIndexOf('-');
    final number = dash > 0 ? room.room.substring(dash + 1) : room.room;
    final floor = _ZoneRooms.place(room.zone).$2?.replaceFirst(' floor', '');
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
      decoration: BoxDecoration(
        color: p.okSoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: p.ok.withValues(alpha: 0.22)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            number,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: p.ink, fontFeatures: tabular),
          ),
          const SizedBox(height: 2),
          Row(
            children: [
              Icon(lab ? Icons.computer_rounded : Icons.chair_alt_outlined, size: 13, color: p.ok),
              const SizedBox(width: 4),
              Flexible(
                child: Text(
                  floor ?? (lab ? 'Lab' : 'Room'),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: p.ok),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
