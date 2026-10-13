import 'package:flutter/material.dart';

import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import 'extra_class_screen.dart';
import 'makeup_card.dart';
import 'reschedule_screen.dart';
import 'teacher_data.dart';

/// Missed classes to reschedule, makeups under way, extra classes, and what is
/// finished. Mirrors the action half of web/src/app/teacher/page.tsx.
class RescheduleTab extends StatelessWidget {
  const RescheduleTab({super.key, required this.data});
  final TeacherData data;

  Future<void> _reschedule(BuildContext context, ClassInstance inst) async {
    final booked = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => RescheduleScreen(instanceId: inst.id, original: inst),
      ),
    );
    if (booked == true) data.load();
  }

  Future<void> _bookExtra(BuildContext context) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ExtraClassScreen()));
    data.load();
  }

  @override
  Widget build(BuildContext context) {
    final user = SessionScope.of(context).user!;
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListenableBuilder(
          listenable: data,
          builder: (context, _) {
            final p = context.palette;
            final open = data.openMakeups;
            final past = data.pastMakeups;
            final done = past.where((m) => m.status == 'COMPLETED').length;
            return RefreshIndicator(
              onRefresh: data.load,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                children: [
                  Text('Reschedule', style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 4),
                  Text('Missed classes, makeups and extra classes.', style: TextStyle(fontSize: 15, color: p.inkSoft)),
                  const SizedBox(height: 16),
                  if (data.loading)
                    const Loading()
                  else if (data.error != null && data.makeups.isEmpty && data.needsAction.isEmpty)
                    LoadError(message: data.error!, onRetry: data.load)
                  else ...[
                    if (data.error != null) ...[Notice.error(data.error!), const SizedBox(height: 14)],
                    Row(
                      children: [
                        _Count(label: 'To reschedule', value: data.needsAction.length, color: p.bad),
                        const SizedBox(width: 8),
                        _Count(label: 'In progress', value: open.length, color: p.info),
                        const SizedBox(width: 8),
                        _Count(label: 'Made up', value: done, color: p.ok),
                      ],
                    ),
                    const SizedBox(height: 20),
                    // Missed classes come first: they are what needs the teacher.
                    if (data.needsAction.isNotEmpty) ...[
                      _NeedsReschedule(
                        classes: data.needsAction,
                        mayReschedule: user.mayReschedule,
                        onReschedule: (inst) => _reschedule(context, inst),
                      ),
                      const SizedBox(height: 26),
                    ] else ...[
                      const Notice(
                        'No missed classes to reschedule.',
                        tone: Tone.ok,
                        icon: Icons.check_circle_outline_rounded,
                      ),
                      const SizedBox(height: 26),
                    ],
                    if (open.isNotEmpty) ...[
                      SectionHeader(
                        'Rescheduled classes',
                        count: open.length,
                        subtitle:
                            'Each stays here until you mark it done after the class. An online class needs its Drive link.',
                      ),
                      for (final m in open)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 14),
                          child: MakeupCard(key: ValueKey(m.id), makeup: m, onChanged: data.load),
                        ),
                      const SizedBox(height: 12),
                    ],
                    if (user.mayBookExtra) ...[
                      const SectionHeader('Extra classes'),
                      _ActionTile(
                        icon: Icons.add_business_rounded,
                        title: 'Book an extra class',
                        subtitle: 'Take an empty room for one of your sections',
                        onTap: () => _bookExtra(context),
                      ),
                      const SizedBox(height: 26),
                    ],
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
            );
          },
        ),
      ),
    );
  }
}

class _Count extends StatelessWidget {
  const _Count({required this.label, required this.value, required this.color});
  final String label;
  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Expanded(
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
        decoration: BoxDecoration(
          color: p.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: p.line, width: 1.2),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '$value',
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.w800,
                color: value == 0 ? p.inkFaint : color,
                fontFeatures: tabular,
              ),
            ),
            Text(
              label,
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: p.inkSoft),
            ),
          ],
        ),
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
                    Text(
                      title,
                      style: TextStyle(fontSize: 16.5, fontWeight: FontWeight.w700, color: p.ink),
                    ),
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
        border: Border.all(
          color: p.bad.withValues(alpha: p.isDark ? 0.22 : 0.35),
          width: p.isDark ? 1.5 : 2,
        ),
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
                    Text(
                      'Reschedule required (${classes.length})',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: p.bad),
                    ),
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
          Text(
            inst.courseCode,
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.4),
          ),
          Text('Section ${inst.section}', style: TextStyle(fontSize: 15.5, color: p.inkSoft)),
          const SizedBox(height: 6),
          Text(
            '${formatDay(inst.date)} · ${slotLabel(inst.timeSlot)} · ${inst.room}',
            style: TextStyle(fontSize: 14.5, color: p.ink, fontFeatures: tabular),
          ),
          if (reported) ...[
            const SizedBox(height: 10),
            Pill(
              'Reported absent · not final yet',
              color: p.warn,
              background: p.warnSoft,
              icon: Icons.hourglass_top_rounded,
              large: true,
            ),
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
