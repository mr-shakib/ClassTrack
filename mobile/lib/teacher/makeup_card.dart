import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';

/// An online class waits for a decision; one in a room is booked outright.
const _steps = {
  'ONLINE': ['Requested', 'Approved', 'Class time', 'Done'],
  'PHYSICAL': ['Booked', 'Class time', 'Done'],
};

bool _ended(Makeup m) => m.endsAt != null && !parseServerTime(m.endsAt!).isAfter(DateTime.now().toUtc());

/// One open reschedule: which class moved, to when and where, how far along it
/// is, and the one thing the teacher can do next. Mirrors MakeupTracker.tsx.
class MakeupCard extends StatefulWidget {
  const MakeupCard({super.key, required this.makeup, required this.onChanged});
  final Makeup makeup;
  final VoidCallback onChanged;

  @override
  State<MakeupCard> createState() => _MakeupCardState();
}

class _MakeupCardState extends State<MakeupCard> {
  // A link sent with the request is already on file; start from it.
  late final _link = TextEditingController(text: widget.makeup.driveLink ?? '');
  bool _busy = false;
  String? _error;

  Makeup get m => widget.makeup;

  @override
  void dispose() {
    _link.dispose();
    super.dispose();
  }

  Future<void> _markDone() async {
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.api.completeMakeup(m.id, driveLink: m.online ? _link.text.trim() : null);
      if (mounted) showMessage(context, '${m.originalCourseCode ?? 'Class'} marked as done.');
      widget.onChanged();
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final pending = m.status == 'PENDING';
    final ended = _ended(m);
    final steps = _steps[m.mode] ?? _steps['PHYSICAL']!;
    final step = m.status == 'COMPLETED'
        ? steps.length
        : pending
            ? 1
            : steps.length - (ended ? 1 : 2);

    final (footerBg, footerBorder) = pending
        ? (p.canvas, p.line)
        : ended
            ? (p.warnSoft, p.warn.withValues(alpha: 0.25))
            : (p.okSoft, p.ok.withValues(alpha: 0.2));

    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: p.line, width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(m.originalCourseCode ?? '—',
                          style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.4)),
                      Text('Section ${m.originalSection ?? '—'}', style: TextStyle(fontSize: 15.5, color: p.inkSoft)),
                    ],
                  ),
                ),
                ModeBadge(makeup: m),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                MakeupTimes(makeup: m),
                const SizedBox(height: 18),
                _Steps(steps: steps, step: step),
                if (m.decisionNote != null && m.decisionNote!.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Notice('“${m.decisionNote}”', title: 'Head of Department', tone: Tone.neutral, icon: Icons.format_quote_rounded),
                ],
                if (m.driveLink != null && m.driveLink!.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: () => openLink(context, m.driveLink!),
                    icon: const Icon(Icons.open_in_new_rounded, size: 20),
                    label: const Text('Open the Drive link sent'),
                  ),
                ],
              ],
            ),
          ),
          Container(
            decoration: BoxDecoration(color: footerBg, border: Border(top: BorderSide(color: footerBorder, width: 1.5))),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ..._footer(context, pending: pending, ended: ended),
                if (_error != null) ...[const SizedBox(height: 12), Notice.error(_error!)],
              ],
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _footer(BuildContext context, {required bool pending, required bool ended}) {
    final p = context.palette;
    TextStyle head(Color c) => TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: c);
    final body = TextStyle(fontSize: 15, color: p.inkSoft, height: 1.4);

    if (pending) {
      return [
        Text('Waiting for the Head of Department', style: head(p.ink)),
        const SizedBox(height: 4),
        Text('You will get a notification as soon as they decide.', style: body),
      ];
    }
    if (!ended) {
      return [
        Text(m.online ? 'Approved — hold the class at the new time' : 'Booked — hold the class at the new time',
            style: head(p.ok)),
        const SizedBox(height: 4),
        Text(
          m.online
              ? (m.driveLink != null && m.driveLink!.isNotEmpty
                  ? 'It is not checked in a room. Your Drive link is saved — after the class, come back here and mark it done.'
                  : 'It is not checked in a room. After it ends, come back here and submit its Drive link.')
              : 'Room ${m.room} is held for you and staff will check it. After the class, come back here and mark it done.',
          style: body,
        ),
      ];
    }
    if (m.online) {
      return [
        Text(
          m.driveLink != null && m.driveLink!.isNotEmpty
              ? 'Class time is over — confirm the Drive link'
              : 'Class time is over — submit the Drive link',
          style: head(p.warn),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _link,
          keyboardType: TextInputType.url,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
            hintText: 'https://drive.google.com/…',
            prefixIcon: Icon(Icons.link_rounded),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: _busy || _link.text.trim().isEmpty ? null : _markDone,
          child: _busy ? const ButtonSpinner() : const Text('Submit link & mark done'),
        ),
      ];
    }
    return [
      Text('Class time is over — did you hold it?', style: head(p.warn)),
      const SizedBox(height: 12),
      FilledButton(
        onPressed: _busy ? null : _markDone,
        child: _busy ? const ButtonSpinner() : const Text('Yes, mark as done'),
      ),
    ];
  }
}

/// Online or in a room, in words and an icon.
class ModeBadge extends StatelessWidget {
  const ModeBadge({super.key, required this.makeup});
  final Makeup makeup;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final online = makeup.online;
    return Pill(
      online ? 'Online' : 'Room ${makeup.room}',
      color: online ? p.info : p.brand,
      background: online ? p.infoSoft : p.brandSoft,
      icon: online ? Icons.videocam_rounded : Icons.meeting_room_rounded,
      large: true,
    );
  }
}

/// The missed class above its new time, the new time emphasised.
class MakeupTimes extends StatelessWidget {
  const MakeupTimes({super.key, required this.makeup});
  final Makeup makeup;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final m = makeup;
    TextStyle label(Color c) => TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: c, letterSpacing: 0.8);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: p.canvas, borderRadius: BorderRadius.circular(14)),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('MISSED CLASS', style: label(p.inkFaint)),
              const SizedBox(height: 4),
              Text(m.originalDate == null ? '—' : formatDay(m.originalDate!),
                  style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w600, color: p.ink)),
              Text(
                [if (m.originalTimeSlot != null) slotLabel(m.originalTimeSlot!), ?m.originalRoom].join(' · '),
                style: TextStyle(fontSize: 14.5, color: p.inkSoft, fontFeatures: tabular),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Icon(Icons.arrow_downward_rounded, color: p.inkFaint, size: 20),
        ),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: p.brandSoft,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: p.brand.withValues(alpha: 0.25), width: 1.5),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('RESCHEDULED TO', style: label(p.brand)),
              const SizedBox(height: 4),
              Text(formatDay(m.date), style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: p.ink)),
              Text('${slotLabel(m.timeSlot)} · ${m.online ? 'Online' : 'Room ${m.room}'}',
                  style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w600, color: p.ink, fontFeatures: tabular)),
            ],
          ),
        ),
      ],
    );
  }
}

class _Steps extends StatelessWidget {
  const _Steps({required this.steps, required this.step});
  final List<String> steps;
  final int step;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < steps.length; i++)
          Expanded(
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Container(height: 3, color: i == 0 ? Colors.transparent : (i <= step ? p.okSolid : p.line)),
                    ),
                    Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: i < step ? p.okSolid : (i == step ? p.warnSolid : p.canvas),
                        border: i > step ? Border.all(color: p.line, width: 2) : null,
                        boxShadow: i == step
                            ? [BoxShadow(color: p.warnSolid.withValues(alpha: 0.3), blurRadius: 0, spreadRadius: 4)]
                            : null,
                      ),
                      child: Center(
                        child: i < step
                            ? const Icon(Icons.check_rounded, color: Colors.white, size: 20)
                            : Text('${i + 1}',
                                style: TextStyle(
                                  fontWeight: FontWeight.w800,
                                  color: i == step ? Colors.white : p.inkFaint,
                                )),
                      ),
                    ),
                    Expanded(
                      child: Container(
                        height: 3,
                        color: i == steps.length - 1 ? Colors.transparent : (i < step ? p.okSolid : p.line),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  steps[i],
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: i < step ? p.ok : (i == step ? p.warn : p.inkFaint),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

/// A finished reschedule: done (with its Drive link, if online) or rejected.
class MakeupHistoryRow extends StatelessWidget {
  const MakeupHistoryRow({super.key, required this.makeup});
  final Makeup makeup;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final m = makeup;
    final done = m.status == 'COMPLETED';
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${m.originalCourseCode ?? '—'} · ${m.originalSection ?? '—'}',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: p.ink)),
                const SizedBox(height: 2),
                Text('${shortDay(m.date)} · ${slotLabel(m.timeSlot)} · ${m.online ? 'Online' : 'Room ${m.room}'}',
                    style: TextStyle(fontSize: 14, color: p.inkSoft, fontFeatures: tabular)),
                if (m.originalDate != null)
                  Text('Makes up ${shortDay(m.originalDate!)}', style: TextStyle(fontSize: 13, color: p.inkFaint)),
                if (m.status == 'REJECTED' && !m.online)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text('Request another slot from “Reschedule required”.',
                        style: TextStyle(fontSize: 14, color: p.bad, fontWeight: FontWeight.w600)),
                  ),
                if (m.decisionNote != null && m.decisionNote!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text('“${m.decisionNote}”',
                        style: TextStyle(fontSize: 14, color: p.inkSoft, fontStyle: FontStyle.italic)),
                  ),
                if (m.driveLink != null && m.driveLink!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: InkWell(
                      onTap: () => openLink(context, m.driveLink!),
                      borderRadius: BorderRadius.circular(8),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Row(mainAxisSize: MainAxisSize.min, children: [
                          Icon(Icons.open_in_new_rounded, size: 16, color: p.brand),
                          const SizedBox(width: 6),
                          Text('Open Drive link',
                              style: TextStyle(color: p.brand, fontWeight: FontWeight.w700, fontSize: 14.5)),
                        ]),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Pill(done ? 'Done' : 'Rejected', color: done ? p.ok : p.bad, background: done ? p.okSoft : p.badSoft),
        ],
      ),
    );
  }
}
