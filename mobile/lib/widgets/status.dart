import 'package:flutter/material.dart';

import '../api/models.dart';
import '../theme.dart';
import '../util/time.dart';
import 'common.dart';

/// One colour map for every status, used everywhere. Mirrors StatusBadge.tsx.
///
/// MISSED and NOT_CHECKED get different hues on purpose: one is a teacher-side
/// problem, the other a staff-side one. Never collapse them.
(String, Color, Color) statusStyle(BuildContext context, String? status, {int? lateMinutes}) {
  final p = context.palette;
  return switch (status) {
    'UPCOMING' => ('Upcoming', p.inkSoft, p.canvas),
    'ONGOING' => ('Ongoing', p.brand, p.brandSoft),
    'RUNNING' => ('Running', p.ok, p.okSoft),
    'LATE' => (lateMinutes != null ? 'Late · $lateMinutes min' : 'Late', p.warn, p.warnSoft),
    'MISSED' => ('Missed', p.bad, p.badSoft),
    'NOT_CHECKED' => ('Not checked', p.gap, p.gapSoft),
    'MAKEUP_REQUESTED' => ('Reschedule requested', p.warn, p.warnSoft),
    'MAKEUP_SCHEDULED' => ('Makeup scheduled', p.info, p.infoSoft),
    'MAKEUP_COMPLETED' => ('Makeup completed', p.ok, p.okSoft),
    'ONLINE_PENDING' => ('Online pending', p.warn, p.warnSoft),
    'ONLINE_APPROVED' => ('Online approved', p.info, p.infoSoft),
    'ONLINE_REJECTED' => ('Online rejected', p.bad, p.badSoft),
    'CANCELLED' => ('Cancelled', p.inkFaint, p.canvas),
    _ => ('—', p.inkFaint, p.canvas),
  };
}

class StatusBadge extends StatelessWidget {
  const StatusBadge(this.status, {super.key, this.lateMinutes, this.large = false});

  final String? status;
  final int? lateMinutes;
  final bool large;

  @override
  Widget build(BuildContext context) {
    final (label, fg, bg) = statusStyle(context, status, lateMinutes: lateMinutes);
    return Pill(label, color: fg, background: bg, large: large);
  }
}

/// The mark of a rescheduled class: which missed class it makes up.
class RescheduledTag extends StatelessWidget {
  const RescheduledTag({super.key, this.from, this.large = false});

  final SlotRef? from;
  final bool large;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final label = from == null ? 'Makeup class' : 'Makeup · from ${shortDay(from!.date)} ${slotStart(from!.timeSlot)}';
    return Pill(label, color: p.info, background: p.infoSoft, icon: Icons.sync_rounded, large: large);
  }
}

/// The mark of an extra class: booked by the teacher on top of the routine.
class ExtraTag extends StatelessWidget {
  const ExtraTag({super.key, this.large = false});
  final bool large;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Pill('Extra class', color: p.brand, background: p.brandSoft, icon: Icons.add_rounded, large: large);
  }
}
