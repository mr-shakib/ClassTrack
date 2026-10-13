import 'package:flutter/material.dart';

import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import 'checking_controller.dart';
import 'room_card.dart';

/// The classes on one floor at one slot: still to do first, then done.
class FloorScreen extends StatelessWidget {
  const FloorScreen({super.key, required this.controller, required this.floorKey});

  final CheckingController controller;
  final String floorKey;

  @override
  Widget build(BuildContext context) {
    final user = SessionScope.of(context).user;
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final p = context.palette;
        final c = controller;
        final floor = c.floors.where((f) => f.floor.key == floorKey).firstOrNull;
        final rooms = c.roomsOn(floorKey);
        final pending = rooms.where((r) => r.check == null).toList();
        final done = rooms.where((r) => r.check != null).toList();
        final locked = c.locked;
        final canOverride = user?.mayCorrect ?? false;

        Widget card(RoomRow row) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: RoomCard(
            key: ValueKey(row.instanceId),
            row: row,
            locked: locked,
            canOverride: canOverride,
            onChanged: c.patch,
          ),
        );

        return Scaffold(
          appBar: AppBar(
            titleSpacing: 0,
            title: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(floor?.floor.label ?? 'Floor'),
                Text(
                  floor?.floor.isMine ?? false ? 'Your floor' : 'Not your floor — you can still check it',
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: floor?.floor.isMine ?? false ? FontWeight.w700 : FontWeight.w500,
                    color: floor?.floor.isMine ?? false ? p.brand : p.inkSoft,
                  ),
                ),
              ],
            ),
          ),
          body: RefreshIndicator(
            onRefresh: () => c.load(),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
              children: [
                _Summary(date: c.date, slot: c.slot, done: done.length, total: rooms.length),
                const SizedBox(height: 14),
                if (locked) ...[
                  Notice(
                    c.closed
                        ? 'This day is over. Classes nobody reported are recorded as not checked.'
                        : 'This class has not started yet.',
                    tone: c.closed ? Tone.gap : Tone.neutral,
                    icon: c.closed ? Icons.event_busy_rounded : Icons.hourglass_top_rounded,
                  ),
                  const SizedBox(height: 14),
                ],
                if (c.loading && rooms.isEmpty)
                  const Loading(label: 'Loading classes…')
                else if (rooms.isEmpty)
                  const Panel(
                    child: EmptyState(
                      icon: Icons.meeting_room_outlined,
                      title: 'No classes on this floor at this time',
                      body: 'Go back and pick another floor, or change the time.',
                    ),
                  )
                else ...[
                  if (pending.isNotEmpty) ...[
                    SectionHeader(locked ? 'Not reported' : 'To do', count: pending.length),
                    ...pending.map(card),
                  ],
                  if (pending.isEmpty && !locked) ...[
                    _FloorDone(onNext: () => Navigator.of(context).pop()),
                    const SizedBox(height: 20),
                  ],
                  if (done.isNotEmpty) ...[
                    if (pending.isNotEmpty) const SizedBox(height: 8),
                    SectionHeader('Done', count: done.length, color: p.ok),
                    ...done.map(card),
                  ],
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Summary extends StatelessWidget {
  const _Summary({required this.date, required this.slot, required this.done, required this.total});
  final String date;
  final String? slot;
  final int done, total;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Panel(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
      child: Column(
        children: [
          Row(
            children: [
              Icon(Icons.schedule_rounded, size: 18, color: p.brand),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${slot == null ? '' : slotLabel(slot!)}  ·  ${shortDay(date)}',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15.5, color: p.ink, fontFeatures: tabular),
                ),
              ),
              Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: '$done',
                      style: TextStyle(color: p.ink),
                    ),
                    TextSpan(
                      text: ' of $total done',
                      style: TextStyle(color: p.inkSoft, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
                style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15.5, fontFeatures: tabular),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ProgressBar(
            value: total == 0 ? 0 : done / total,
            color: done == total && total > 0 ? p.okSolid : p.brandSolid,
            track: p.line,
          ),
        ],
      ),
    );
  }
}

class _FloorDone extends StatelessWidget {
  const _FloorDone({required this.onNext});
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
      decoration: BoxDecoration(color: p.okSolid, borderRadius: BorderRadius.circular(22)),
      child: Column(
        children: [
          const Icon(Icons.task_alt_rounded, color: Colors.white, size: 44),
          const SizedBox(height: 8),
          const Text(
            'This floor is done',
            style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 14),
          FilledButton(
            onPressed: onNext,
            style: FilledButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: p.okSolid,
              minimumSize: const Size(220, 52),
            ),
            child: const Text('Pick the next floor'),
          ),
        ],
      ),
    );
  }
}
