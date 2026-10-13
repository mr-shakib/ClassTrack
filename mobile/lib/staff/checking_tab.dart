import 'package:flutter/material.dart';

import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import 'checking_controller.dart';
import 'floor_screen.dart';
import 'teacher_search.dart';

/// Room-wise checking, in two steps: pick a floor, then check its classes.
/// Mirrors web/src/app/staff/page.tsx.
///
/// Every floor is offered to everyone. A staff member's assigned floors come
/// first and are marked, but anyone passing another floor can check it too.
class CheckingTab extends StatefulWidget {
  const CheckingTab({super.key, required this.active});

  /// On screen: only then does it refresh itself.
  final bool active;

  @override
  State<CheckingTab> createState() => _CheckingTabState();
}

class _CheckingTabState extends State<CheckingTab> with WidgetsBindingObserver {
  late final CheckingController _c = CheckingController(context.api);
  bool _byTeacher = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _c.load(spinner: true);
    if (widget.active) _c.startPolling();
  }

  @override
  void didUpdateWidget(CheckingTab old) {
    super.didUpdateWidget(old);
    if (widget.active && !old.active) {
      _c.load();
      _c.startPolling();
    } else if (!widget.active && old.active) {
      _c.stopPolling();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && widget.active) {
      _c.load();
      _c.startPolling();
    } else if (state == AppLifecycleState.paused) {
      _c.stopPolling();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _c.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: parseDay(_c.date),
      firstDate: DateTime(2024),
      lastDate: DateTime(2035),
      helpText: 'Check classes on',
    );
    if (picked != null) _c.setDate(isoDate(picked));
  }

  void _openFloor(FloorTally f) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => FloorScreen(controller: _c, floorKey: f.floor.key),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final user = SessionScope.of(context).user!;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            Container(
              height: 60,
              padding: const EdgeInsets.fromLTRB(16, 12, 12, 0),
              child: Row(
                children: [
                  Expanded(child: Text('Checking', style: Theme.of(context).textTheme.headlineSmall)),
                  if (!_byTeacher)
                    ListenableBuilder(
                      listenable: _c,
                      builder: (context, _) =>
                          _DateButton(label: _c.isToday ? 'Today' : shortDay(_c.date), onTap: _pickDate),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: _ModeSwitch(byTeacher: _byTeacher, onChanged: (v) => setState(() => _byTeacher = v)),
            ),
            Expanded(
              child: _byTeacher
                  ? TeacherSearch(canOverride: user.mayCorrect)
                  : ListenableBuilder(
                      listenable: _c,
                      builder: (context, _) => RefreshIndicator(
                        onRefresh: () => _c.load(),
                        child: ListView(
                          padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
                          children: [
                            _SlotHero(controller: _c),
                            const SizedBox(height: 12),
                            _SlotStrip(controller: _c),
                            if (!_c.isToday || (_c.liveSlot != null && _c.slot != _c.liveSlot))
                              Align(
                                alignment: Alignment.centerRight,
                                child: TextButton.icon(
                                  onPressed: _c.resetToNow,
                                  icon: const Icon(Icons.my_location_rounded, size: 18),
                                  label: const Text('Back to now'),
                                ),
                              ),
                            const SizedBox(height: 12),
                            if (_c.error != null && _c.screen != null) ...[
                              Notice.error(_c.error!),
                              const SizedBox(height: 12),
                            ],
                            ..._floors(context, p),
                          ],
                        ),
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _floors(BuildContext context, Palette p) {
    if (_c.loading) return const [Loading(label: 'Loading classes…')];
    if (_c.screen == null) {
      return [LoadError(message: _c.error ?? 'Something went wrong.', onRetry: () => _c.load(spinner: true))];
    }
    final floors = _c.floors;
    return [
      if (_c.slotState == 'ONGOING')
        Notice('You can report these classes any time today.', tone: Tone.ok, icon: Icons.lock_open_rounded)
      else if (_c.closed)
        Notice(
          'This day is over. Classes nobody reported are recorded as not checked.',
          tone: Tone.gap,
          icon: Icons.event_busy_rounded,
        )
      else
        Notice(
          'This class has not started yet. It opens at '
          '${_c.screen!.rooms.isNotEmpty ? _c.screen!.rooms.first.scheduledStart : slotStart(_c.screen!.timeSlot)}.',
          tone: Tone.neutral,
          icon: Icons.hourglass_top_rounded,
        ),
      const SizedBox(height: 20),
      if (floors.isEmpty)
        const Panel(
          child: EmptyState(
            icon: Icons.meeting_room_outlined,
            title: 'No classes in this slot',
            body: 'Nothing is scheduled here, or the routine has no entry for this day.',
          ),
        )
      else ...[
        const SectionHeader('Choose a floor', subtitle: 'Your floors come first. You can check classes on any floor.'),
        LayoutBuilder(
          builder: (context, box) {
            final columns = box.maxWidth > 720 ? 3 : (box.maxWidth > 480 ? 2 : 1);
            return Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                for (final f in floors)
                  SizedBox(
                    width: (box.maxWidth - 12 * (columns - 1)) / columns,
                    child: _FloorCard(tally: f, closed: _c.closed, onTap: () => _openFloor(f)),
                  ),
              ],
            );
          },
        ),
      ],
    ];
  }
}

class _DateButton extends StatelessWidget {
  const _DateButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Material(
      color: p.surface,
      shape: StadiumBorder(side: BorderSide(color: p.line, width: 1.2)),
      child: InkWell(
        customBorder: const StadiumBorder(),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.calendar_today_rounded, size: 17, color: p.brand),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: p.ink),
              ),
              Icon(Icons.arrow_drop_down_rounded, color: p.inkSoft),
            ],
          ),
        ),
      ),
    );
  }
}

/// By floor, or find a teacher's classes to correct one.
class _ModeSwitch extends StatelessWidget {
  const _ModeSwitch({required this.byTeacher, required this.onChanged});
  final bool byTeacher;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dark = Theme.of(context).brightness == Brightness.dark;
    Widget option(String label, IconData icon, bool value) {
      final on = byTeacher == value;
      return Expanded(
        child: GestureDetector(
          onTap: () => onChanged(value),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            height: 46,
            decoration: BoxDecoration(
              color: on ? (dark ? p.raised : p.surface) : Colors.transparent,
              border: dark && on ? Border.all(color: p.line) : null,
              borderRadius: BorderRadius.circular(11),
              boxShadow: on && !dark
                  ? [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 6, offset: const Offset(0, 1))]
                  : null,
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, size: 19, color: on ? p.brand : p.inkSoft),
                const SizedBox(width: 7),
                Text(
                  label,
                  style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: on ? p.brand : p.inkSoft),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: dark ? p.surface : p.line.withValues(alpha: 0.6),
        border: dark ? Border.all(color: p.line) : null,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          option('By floor', Icons.layers_outlined, false),
          option('Find by teacher', Icons.person_search_outlined, true),
        ],
      ),
    );
  }
}

/// The day, the slot, and how much of it is done.
class _SlotHero extends StatelessWidget {
  const _SlotHero({required this.controller});
  final CheckingController controller;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final c = controller;
    final rooms = c.screen?.rooms ?? const [];
    final done = rooms.where((r) => r.check != null).length;
    final state = switch (c.slotState) {
      'ONGOING' => ('Open for checking', const Color(0xFF6EE7B7)),
      'CLOSED' => ('Reporting closed', const Color(0xFFC4B5FD)),
      'UPCOMING' => ('Not started', Colors.white70),
      _ => (null, Colors.white70),
    };

    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
      decoration: p.hero(radius: 22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      mediumDay(c.date),
                      style: const TextStyle(color: Colors.white70, fontSize: 14.5, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 2),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Text(
                        c.slot == null ? '—' : slotLabel(c.slot!),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 32,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -1,
                          fontFeatures: tabular,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              if (c.screen != null)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text.rich(
                      TextSpan(
                        children: [
                          TextSpan(text: '$done'),
                          TextSpan(
                            text: '/${rooms.length}',
                            style: const TextStyle(fontSize: 22, color: Colors.white70),
                          ),
                        ],
                      ),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 34,
                        fontWeight: FontWeight.w800,
                        fontFeatures: tabular,
                        letterSpacing: -1,
                      ),
                    ),
                    const Text(
                      'rooms done',
                      style: TextStyle(color: Colors.white70, fontSize: 13.5, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
            ],
          ),
          const SizedBox(height: 14),
          ProgressBar(
            value: rooms.isEmpty ? 0 : done / rooms.length,
            color: Colors.white,
            track: Colors.white.withValues(alpha: 0.25),
            height: 9,
          ),
          if (state.$1 != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Container(
                  width: 9,
                  height: 9,
                  decoration: BoxDecoration(color: state.$2, shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Text(
                  state.$1!,
                  style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w700),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// The six slots of the day, one tap each. The one running now has a dot.
class _SlotStrip extends StatelessWidget {
  const _SlotStrip({required this.controller});
  final CheckingController controller;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final live = controller.isToday ? controller.liveSlot : null;
    return Row(
      children: [
        for (var i = 0; i < slots.length; i++) ...[
          if (i > 0) const SizedBox(width: 6),
          Expanded(
            child: _SlotCell(
              label: slotStart(slots[i]),
              selected: controller.slot == slots[i],
              live: live == slots[i],
              onTap: () => controller.setSlot(slots[i]),
              palette: p,
            ),
          ),
        ],
      ],
    );
  }
}

class _SlotCell extends StatelessWidget {
  const _SlotCell({
    required this.label,
    required this.selected,
    required this.live,
    required this.onTap,
    required this.palette,
  });

  final String label;
  final bool selected, live;
  final VoidCallback onTap;
  final Palette palette;

  @override
  Widget build(BuildContext context) {
    final p = palette;
    return Material(
      color: selected ? p.brandSolid : p.surface,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Container(
          height: 50,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: selected ? p.brandSolid : p.line, width: 1.2),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              FittedBox(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    color: selected ? Colors.white : p.ink,
                    fontFeatures: tabular,
                  ),
                ),
              ),
              const SizedBox(height: 3),
              Container(
                width: 5,
                height: 5,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: live ? (selected ? Colors.white : p.ok) : Colors.transparent,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// One floor: how many classes it has, how many are checked, and a way in.
class _FloorCard extends StatelessWidget {
  const _FloorCard({required this.tally, required this.closed, required this.onTap});
  final FloorTally tally;
  final bool closed;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final f = tally;
    final complete = f.left == 0;
    final mine = f.floor.isMine;
    return Material(
      color: p.surface,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: mine ? p.brand : p.line, width: mine ? 2 : 1.2),
          ),
          child: Column(
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
                          f.floor.label,
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.4,
                            color: p.ink,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${f.total} ${f.total == 1 ? 'class' : 'classes'}',
                          style: TextStyle(fontSize: 14.5, color: p.inkSoft),
                        ),
                      ],
                    ),
                  ),
                  if (mine) Pill('Your floor', color: p.brand, background: p.brandSoft, icon: Icons.star_rounded),
                ],
              ),
              const SizedBox(height: 14),
              ProgressBar(
                value: f.total == 0 ? 0 : f.checked / f.total,
                color: complete ? p.okSolid : p.brandSolid,
                track: p.line,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  if (complete) ...[Icon(Icons.check_circle_rounded, color: p.ok, size: 20), const SizedBox(width: 6)],
                  Expanded(
                    child: Text(
                      complete
                          ? 'All done'
                          : closed
                          ? '${f.left} not reported'
                          : '${f.left} to check',
                      style: TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        color: complete
                            ? p.ok
                            : closed
                            ? p.gap
                            : p.ink,
                      ),
                    ),
                  ),
                  Text(
                    '${f.checked}/${f.total}',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: p.inkSoft,
                      fontFeatures: tabular,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(color: p.brandSoft, shape: BoxShape.circle),
                    child: Icon(Icons.chevron_right_rounded, color: p.brand),
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
