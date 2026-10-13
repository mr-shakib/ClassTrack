import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import '../widgets/status.dart';

/// One room on the checking screen. Mirrors web/src/components/RoomCard.tsx.
///
/// Used one-handed, while walking, by people who were not hired for their
/// comfort with software. Everything here follows from that:
///
/// * The normal case, the class is running, is **one tap**.
/// * Late is **two taps**: the arrival time is prefilled with now, so the
///   second tap confirms rather than asks for data.
/// * Targets are large and full-width, and say what they do in words.
class RoomCard extends StatefulWidget {
  const RoomCard({
    super.key,
    required this.row,
    required this.onChanged,
    this.locked = false,
    this.canOverride = false,
    this.showWhen = false,
  });

  final RoomRow row;
  final ValueChanged<RoomRow> onChanged;

  /// Not open for reporting: not started yet, or the day is over.
  final bool locked;

  /// May correct a record after its day: admins and the committee.
  final bool canOverride;

  /// Show the date and time: for lists that mix days and slots.
  final bool showWhen;

  @override
  State<RoomCard> createState() => _RoomCardState();
}

class _RoomCardState extends State<RoomCard> {
  String? _busy;
  String? _error;
  bool _confirmingLate = false;
  bool _overriding = false;
  bool _noteOpen = false;
  String _arrival = '';
  final _reason = TextEditingController();
  late final _remark = TextEditingController(text: widget.row.check?.remark ?? '');

  RoomRow get row => widget.row;

  @override
  void dispose() {
    _reason.dispose();
    _remark.dispose();
    super.dispose();
  }

  Future<void> _submit(String outcome, {String? arrival}) async {
    HapticFeedback.mediumImpact();
    final messenger = ScaffoldMessenger.of(context);
    final api = context.api;
    final previous = row;
    final remark = _remark.text.trim().isEmpty ? null : _remark.text.trim();
    setState(() {
      _busy = outcome;
      _error = null;
    });

    // Shown at once; an empty `checkedAt` marks it as still saving.
    widget.onChanged(
      previous.withCheck(
        CheckRecord(outcome: outcome, arrivalTime: arrival, remark: remark, checkedAt: ''),
        outcome == 'TEACHER_NOT_FOUND' ? null : outcome,
      ),
    );

    try {
      final res = await api.submitCheck(
        previous.instanceId,
        outcome: outcome,
        arrivalTime: arrival,
        remark: remark,
        reason: _reason.text.trim().isEmpty ? null : _reason.text.trim(),
      );
      widget.onChanged(
        previous.withCheck(
          CheckRecord(
            outcome: outcome,
            arrivalTime: arrival,
            lateMinutes: res.lateMinutes,
            remark: remark,
            checkedAt: res.checkedAt,
            checkedBy: res.checkedBy,
          ),
          res.status,
        ),
      );
      if (mounted) {
        setState(() {
          _confirmingLate = false;
          _overriding = false;
        });
      }
    } on ApiError catch (e) {
      widget.onChanged(previous);
      // The card may have moved lists and lost this state; the snackbar stays.
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text('${previous.room} was not saved. ${e.message}')));
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  Future<void> _pickArrival() async {
    final parts = _arrival.split(':');
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: int.tryParse(parts.first) ?? 0, minute: int.tryParse(parts.last) ?? 0),
      helpText: 'Teacher arrived at',
      builder: (context, child) =>
          MediaQuery(data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true), child: child!),
    );
    if (picked != null) {
      setState(
        () => _arrival = '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final Widget body;
    if (row.check != null && !_confirmingLate && !_overriding) {
      body = _submitted(context);
    } else if (widget.locked && !_overriding) {
      body = _lockedView(context);
    } else if (_confirmingLate) {
      body = _lateView(context);
    } else {
      body = _choices(context);
    }

    final card = AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(20),
        border: row.isMakeup
            ? null
            : Border.all(color: _confirmingLate ? p.warnSolid : p.line, width: _confirmingLate ? 2 : 1.2),
      ),
      child: body,
    );
    // A makeup gets a dashed teal frame, so it stands apart from the routine.
    return row.isMakeup ? DashedBorder(color: p.info.withValues(alpha: 0.7), child: card) : card;
  }

  // --- the parts every state shares ---------------------------------------------

  Widget _header(BuildContext context, {bool range = true}) {
    final p = context.palette;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (widget.showWhen && row.date != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              '${shortDay(row.date!)} · ${row.scheduledStart}–${row.scheduledEnd}',
              style: TextStyle(color: p.brand, fontWeight: FontWeight.w700, fontSize: 14),
            ),
          ),
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Expanded(
              child: Text(
                row.room,
                style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, letterSpacing: -0.5, color: p.ink),
              ),
            ),
            // The line above already says when.
            if (!widget.showWhen)
              Text(
                range ? '${row.scheduledStart}–${row.scheduledEnd}' : row.scheduledStart,
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: p.inkSoft, fontFeatures: tabular),
              ),
          ],
        ),
      ],
    );
  }

  Widget _who(BuildContext context, {bool withTeacher = true}) {
    final p = context.palette;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 4),
        Text(
          '${row.courseCode} · ${row.section}',
          style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: p.ink),
        ),
        if (withTeacher) ...[
          const SizedBox(height: 2),
          Row(
            children: [
              Icon(Icons.person_outline_rounded, size: 17, color: p.inkSoft),
              const SizedBox(width: 5),
              Expanded(
                child: Text(
                  row.teacherName == null ? row.teacherInitial : '${row.teacherName} · ${row.teacherInitial}',
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 15, color: p.inkSoft),
                ),
              ),
            ],
          ),
        ],
        if (row.isMakeup)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: RescheduledTag(from: row.rescheduledFrom, large: true),
          )
        else if (row.isExtra)
          const Padding(padding: EdgeInsets.only(top: 10), child: ExtraTag(large: true)),
      ],
    );
  }

  Widget _errorLine() => _error == null
      ? const SizedBox.shrink()
      : Padding(padding: const EdgeInsets.only(top: 10), child: Notice.error(_error!));

  // --- the default: three big choices ---------------------------------------------

  Widget _choices(BuildContext context) {
    final p = context.palette;
    final busy = _busy != null;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _header(context),
          _who(context),
          if (_overriding) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(14)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Reason for the change (optional)',
                    style: TextStyle(color: p.brand, fontWeight: FontWeight.w700, fontSize: 14),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _reason,
                    decoration: const InputDecoration(hintText: 'Not required'),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 14),
          _BigAction(
            label: 'Class is running',
            icon: Icons.check_circle_rounded,
            color: p.okSolid,
            height: 64,
            busy: _busy == 'RUNNING',
            enabled: !busy,
            onTap: () => _submit('RUNNING'),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _BigAction(
                  label: 'Teacher late',
                  icon: Icons.schedule_rounded,
                  color: p.warnSolid,
                  stacked: true,
                  enabled: !busy,
                  onTap: () => setState(() {
                    _arrival = nowHhmm();
                    _confirmingLate = true;
                  }),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _BigAction(
                  label: 'Teacher absent',
                  icon: Icons.person_off_rounded,
                  color: p.badSolid,
                  stacked: true,
                  busy: _busy == 'TEACHER_NOT_FOUND',
                  enabled: !busy,
                  onTap: () => _submit('TEACHER_NOT_FOUND'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          if (_noteOpen)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: TextField(
                controller: _remark,
                autofocus: true,
                decoration: const InputDecoration(hintText: 'Note (not required)'),
              ),
            )
          else
            TextButton.icon(
              onPressed: () => setState(() => _noteOpen = true),
              style: TextButton.styleFrom(foregroundColor: p.inkSoft),
              icon: const Icon(Icons.edit_note_rounded, size: 22),
              label: const Text('Add a note'),
            ),
          _errorLine(),
        ],
      ),
    );
  }

  // --- the two-tap late confirmation ------------------------------------------------

  Widget _lateView(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _header(context),
          _who(context, withTeacher: false),
          const SizedBox(height: 14),
          Text(
            'Teacher arrived at',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: p.ink),
          ),
          const SizedBox(height: 8),
          Material(
            color: p.warnSoft,
            borderRadius: BorderRadius.circular(16),
            child: InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: _pickArrival,
              child: Container(
                height: 76,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: p.warn.withValues(alpha: 0.35), width: 1.5),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      _arrival,
                      style: TextStyle(
                        fontSize: 38,
                        fontWeight: FontWeight.w800,
                        color: p.warn,
                        fontFeatures: tabular,
                        letterSpacing: -1,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Icon(Icons.edit_rounded, color: p.warn.withValues(alpha: 0.7), size: 22),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Tap the time to change it.',
            textAlign: TextAlign.center,
            style: TextStyle(color: p.inkFaint, fontSize: 13.5),
          ),
          const SizedBox(height: 12),
          _BigAction(
            label: 'Save',
            icon: Icons.check_rounded,
            color: p.warnSolid,
            height: 64,
            busy: _busy == 'LATE',
            enabled: _arrival.isNotEmpty && _busy == null,
            onTap: () => _submit('LATE', arrival: _arrival),
          ),
          const SizedBox(height: 4),
          TextButton(
            onPressed: _busy == null ? () => setState(() => _confirmingLate = false) : null,
            style: TextButton.styleFrom(foregroundColor: p.inkSoft, minimumSize: const Size(48, 48)),
            child: const Text('Back'),
          ),
          _errorLine(),
        ],
      ),
    );
  }

  // --- submitted: a big, unmistakable result ---------------------------------------

  Widget _submitted(BuildContext context) {
    final p = context.palette;
    final check = row.check!;
    final saving = check.checkedAt.isEmpty;
    final (text, color, icon) = switch (check.outcome) {
      'RUNNING' => ('Class is running', p.okSolid, Icons.check_circle_rounded),
      'LATE' => (
        'Teacher was late${check.lateMinutes != null ? ' — ${check.lateMinutes} min' : ''}',
        p.warnSolid,
        Icons.schedule_rounded,
      ),
      _ => ('Teacher not found', p.badSolid, Icons.person_off_rounded),
    };
    final mayChange = !widget.locked || widget.canOverride;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _header(context, range: false),
              _who(context, withTeacher: widget.showWhen),
            ],
          ),
        ),
        Container(
          color: color,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
          child: Row(
            children: [
              Icon(icon, color: Colors.white, size: 24),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  text,
                  style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 6, 4),
          child: Row(
            children: [
              Expanded(
                child: saving
                    ? Row(
                        children: [
                          SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2, color: p.inkFaint),
                          ),
                          const SizedBox(width: 8),
                          Text('Saving…', style: TextStyle(color: p.inkFaint, fontSize: 14)),
                        ],
                      )
                    : Text(
                        check.checkedBy != null ? 'by ${check.checkedBy}' : 'Saved',
                        style: TextStyle(color: p.inkFaint, fontSize: 14),
                      ),
              ),
              if (mayChange && !saving)
                TextButton(
                  onPressed: () {
                    setState(() {
                      if (widget.locked) _overriding = true;
                      _confirmingLate = false;
                    });
                    widget.onChanged(row.withCheck(null, null));
                  },
                  child: const Text('Change'),
                ),
            ],
          ),
        ),
      ],
    );
  }

  // --- not open for reporting -----------------------------------------------------

  Widget _lockedView(BuildContext context) {
    final upcoming = row.slotState == 'UPCOMING';
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Opacity(
            opacity: 0.85,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _header(context, range: false),
                _who(context, withTeacher: widget.showWhen),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Notice(
            upcoming ? 'Not started yet — opens at ${row.scheduledStart}' : 'Not reported — the day is over',
            tone: upcoming ? Tone.neutral : Tone.gap,
            icon: upcoming ? Icons.hourglass_top_rounded : Icons.visibility_off_outlined,
          ),
          if (widget.canOverride && !upcoming) ...[
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () => setState(() => _overriding = true),
              icon: const Icon(Icons.edit_rounded),
              label: const Text('Correct this record'),
            ),
          ],
        ],
      ),
    );
  }
}

/// A tall, solid, full-width button with a word and an icon.
class _BigAction extends StatelessWidget {
  const _BigAction({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
    this.height = 60,
    this.busy = false,
    this.enabled = true,
    this.stacked = false,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  final double height;
  final bool busy, enabled;

  /// The icon above the word: for half-width buttons.
  final bool stacked;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: enabled || busy ? 1 : 0.5,
      child: Material(
        color: color,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: enabled ? onTap : null,
          child: SizedBox(
            height: stacked ? 72 : height,
            child: Center(
              child: stacked && !busy
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(icon, color: Colors.white, size: 24),
                        const SizedBox(height: 4),
                        Text(
                          label,
                          style: const TextStyle(color: Colors.white, fontSize: 16.5, fontWeight: FontWeight.w800),
                        ),
                      ],
                    )
                  : busy
                  ? const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        ButtonSpinner(),
                        SizedBox(width: 10),
                        Text(
                          'Saving…',
                          style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800),
                        ),
                      ],
                    )
                  : Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(icon, color: Colors.white, size: 22),
                          const SizedBox(width: 8),
                          Flexible(
                            child: Text(
                              label,
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 17,
                                fontWeight: FontWeight.w800,
                                height: 1.15,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
