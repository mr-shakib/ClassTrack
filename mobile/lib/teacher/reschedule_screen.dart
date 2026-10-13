import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import 'booking.dart';

/// Reschedule a missed class: into an empty room, booked at once, or online
/// at any time, once the Head of Department approves. Mirrors
/// web/src/app/teacher/makeup/page.tsx.
///
/// Pops with `true` once something was booked or requested.
class RescheduleScreen extends StatefulWidget {
  const RescheduleScreen({super.key, required this.instanceId, this.original});

  final int instanceId;

  /// The class, when the caller already has it.
  final ClassInstance? original;

  @override
  State<RescheduleScreen> createState() => _RescheduleScreenState();
}

class _RescheduleScreenState extends State<RescheduleScreen> {
  late ClassInstance? _original = widget.original;
  String? _loadError;

  bool _online = false;
  String? _date;
  String _slot = slots[5];

  /// Online only: a time off the clock, in 24-hour HH:MM.
  String? _startTime;
  String? _room;
  final _reason = TextEditingController();
  final _driveLink = TextEditingController();

  ConflictReport? _report;
  bool _checking = false;
  int _checkRequest = 0;
  final _debounce = Debouncer();
  late final FreeRoomsLoader _rooms = FreeRoomsLoader(context.api, _roomsChanged);

  bool _busy = false;
  String? _error;
  bool _done = false;

  @override
  void initState() {
    super.initState();
    if (_original == null) _loadOriginal();
  }

  @override
  void dispose() {
    _reason.dispose();
    _driveLink.dispose();
    _debounce.dispose();
    super.dispose();
  }

  Future<void> _loadOriginal() async {
    setState(() => _loadError = null);
    try {
      final inst = await context.api.instance(widget.instanceId);
      if (mounted) setState(() => _original = inst);
    } on ApiError catch (e) {
      if (mounted) setState(() => _loadError = e.message);
    }
  }

  void _roomsChanged() {
    if (!mounted) return;
    setState(() {
      // A room picked for one slot may be taken in the next.
      final rooms = _rooms.rooms;
      if (rooms != null && _room != null && !rooms.any((r) => r.room == _room)) _room = null;
    });
    _validate();
  }

  void _cellChanged() {
    if (!_online) _rooms.load(_date, _slot);
    _validate();
  }

  /// The room list already leaves out taken rooms; this still catches the
  /// teacher or section being busy then, and holidays. For a time off the clock
  /// it is the only check there is.
  void _validate() {
    final o = _original;
    if (o == null || _date == null || (_online ? _startTime == null : _room == null)) {
      setState(() {
        _report = null;
        _checking = false;
      });
      return;
    }
    setState(() => _checking = true);
    _debounce(() async {
      final request = ++_checkRequest;
      try {
        final r = await context.api.checkConflict(
          date: _date!,
          timeSlot: _online ? null : _slot,
          startTime: _online ? _startTime : null,
          room: _online ? null : _room,
          section: o.section,
          courseCode: o.courseCode,
        );
        if (mounted && request == _checkRequest) setState(() => _report = r);
      } on ApiError {
        if (mounted && request == _checkRequest) setState(() => _report = null);
      } finally {
        if (mounted && request == _checkRequest) setState(() => _checking = false);
      }
    });
  }

  Future<void> _pickStart() async {
    final parts = (_startTime ?? '18:00').split(':');
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: int.parse(parts[0]), minute: int.parse(parts[1])),
      helpText: 'Class starts at',
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
        child: child!,
      ),
    );
    if (picked == null) return;
    // The latest start that still finishes before midnight.
    if (picked.hour * 60 + picked.minute > 22 * 60 + 30) {
      if (mounted) showMessage(context, 'Start by 22:30, so the class ends before midnight.');
      return;
    }
    setState(() => _startTime =
        '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}');
    _validate();
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.api.createMakeup(
        originalInstanceId: widget.instanceId,
        mode: _online ? 'ONLINE' : 'PHYSICAL',
        date: _date!,
        timeSlot: _online ? null : _slot,
        startTime: _online ? _startTime : null,
        room: _online ? null : _room,
        reason: _reason.text.trim().isEmpty ? null : _reason.text.trim(),
        driveLink: _online && _driveLink.text.trim().isNotEmpty ? _driveLink.text.trim() : null,
      );
      setState(() => _done = true);
    } on ApiError catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_done) return _success(context);
    final p = context.palette;
    final o = _original;
    final blocked = _report != null && !_report!.ok;
    final ready = !_busy &&
        !blocked &&
        !_checking &&
        _date != null &&
        o != null &&
        (_online ? _startTime != null : _room != null);

    final label = _busy
        ? (_online ? 'Sending…' : 'Booking…')
        : blocked
            ? 'Resolve the conflict first'
            : _date == null
                ? 'Pick a date'
                : _online
                    ? (_startTime == null ? 'Pick a start time' : 'Send for approval')
                    : (_room == null ? 'Pick an empty room' : 'Book $_room');

    return Scaffold(
      appBar: AppBar(title: const Text('Reschedule a class')),
      body: o == null
          ? (_loadError != null ? LoadError(message: _loadError!, onRetry: _loadOriginal) : const Loading())
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              children: [
                _MissedClass(o),
                const SizedBox(height: 20),
                const FieldLabel('How will you hold it?'),
                ChoicePair<bool>(
                  value: _online,
                  options: const [
                    (false, 'In a room', Icons.meeting_room_rounded),
                    (true, 'Online', Icons.videocam_rounded),
                  ],
                  onChanged: (v) {
                    setState(() {
                      _online = v;
                      _report = null;
                    });
                    _cellChanged();
                  },
                ),
                const SizedBox(height: 8),
                Text(
                  _online
                      ? 'Hold it at any time of any day — nobody checks a room for it. Needs approval. '
                          'You can add a Drive link now, or after the class.'
                      : 'Booked as soon as you pick an empty room, with no approval. Staff check it there, at the new time.',
                  style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4),
                ),
                const SizedBox(height: 22),
                const FieldLabel('Date'),
                PickerField(
                  icon: Icons.event_rounded,
                  value: _date == null ? null : formatDay(_date!),
                  placeholder: 'Pick a date',
                  onTap: () async {
                    final d = await pickFutureDate(context, _date);
                    if (d != null) {
                      setState(() => _date = d);
                      _cellChanged();
                    }
                  },
                ),
                const SizedBox(height: 22),
                if (_online) ...[
                  FieldLabel(
                    'Start time',
                    hint: _startTime == null
                        ? 'Any time, any day. The class runs 90 minutes from there.'
                        : 'Runs ${endsLabel(_startTime!)} — 90 minutes.',
                  ),
                  PickerField(
                    icon: Icons.schedule_rounded,
                    value: _startTime,
                    placeholder: 'Pick a start time',
                    onTap: _pickStart,
                  ),
                  const SizedBox(height: 22),
                  const FieldLabel('Drive link (optional)',
                      hint: 'The Head of Department or Associate Head can open it while deciding.'),
                  TextField(
                    controller: _driveLink,
                    keyboardType: TextInputType.url,
                    decoration: const InputDecoration(
                      hintText: 'https://drive.google.com/…',
                      prefixIcon: Icon(Icons.link_rounded),
                    ),
                  ),
                ] else ...[
                  const FieldLabel('Time', hint: 'Classes run on fixed 90-minute slots.'),
                  SlotGrid(
                    selected: _slot,
                    onPick: (s) {
                      setState(() => _slot = s);
                      _cellChanged();
                    },
                  ),
                  const SizedBox(height: 22),
                  RoomPicker(
                    hasCell: _date != null,
                    loader: _rooms,
                    room: _room,
                    roomType: o.roomType,
                    onPick: (r) {
                      setState(() => _room = r);
                      _validate();
                    },
                  ),
                ],
                const SizedBox(height: 22),
                const FieldLabel('Reason'),
                TextField(
                  controller: _reason,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: const InputDecoration(hintText: 'Why was the class missed?'),
                ),
                const SizedBox(height: 18),
                ConflictNotes(checking: _checking, report: _report),
                if (_error != null) ...[const SizedBox(height: 12), Notice.error(_error!)],
              ],
            ),
      bottomNavigationBar: o == null
          ? null
          : _BottomAction(
              label: label,
              busy: _busy,
              enabled: ready,
              onPressed: _submit,
            ),
    );
  }

  Widget _success(BuildContext context) {
    final online = _online;
    final message = online
        ? 'Sent to the Head of Department for ${formatDay(_date!)} at ${endsLabel(_startTime!)}. '
            'You will get a notification when they decide. '
            '${_driveLink.text.trim().isNotEmpty ? 'Your Drive link was sent with the request.' : 'After the class, submit its Drive link.'}'
        : '$_room is booked for you on ${formatDay(_date!)} at ${slotLabel(_slot)}. Staff will check it at that time.';
    return _SuccessView(
      title: online ? 'Reschedule requested' : 'Class rescheduled',
      message: message,
      onDone: () => Navigator.of(context).pop(true),
    );
  }
}

/// The class being made up, in the bad-tone frame the web app gives it.
class _MissedClass extends StatelessWidget {
  const _MissedClass(this.o);
  final ClassInstance o;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: p.badSoft,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: p.bad.withValues(alpha: 0.3), width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('MISSED CLASS',
              style: TextStyle(color: p.bad, fontWeight: FontWeight.w800, fontSize: 12.5, letterSpacing: 0.8)),
          const SizedBox(height: 6),
          Text(o.courseCode, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.5)),
          Text('Section ${o.section}', style: TextStyle(fontSize: 16, color: p.ink)),
          const SizedBox(height: 6),
          Text('${formatDay(o.date)} · ${slotLabel(o.timeSlot)} · ${o.room}',
              style: TextStyle(fontSize: 14.5, color: p.inkSoft, fontFeatures: tabular)),
        ],
      ),
    );
  }
}

/// The screen's one action, pinned above the keyboard and the home bar.
class _BottomAction extends StatelessWidget {
  const _BottomAction({required this.label, required this.busy, required this.enabled, required this.onPressed});
  final String label;
  final bool busy, enabled;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Container(
      decoration: BoxDecoration(color: p.surface, border: Border(top: BorderSide(color: p.line))),
      padding: EdgeInsets.fromLTRB(16, 12, 16, 12 + MediaQuery.of(context).viewPadding.bottom),
      child: FilledButton(
        onPressed: enabled ? onPressed : null,
        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
        child: busy
            ? Row(mainAxisSize: MainAxisSize.min, children: [
                const ButtonSpinner(),
                const SizedBox(width: 10),
                Text(label),
              ])
            : Text(label),
      ),
    );
  }
}

class _SuccessView extends StatelessWidget {
  const _SuccessView({required this.title, required this.message, required this.onDone});
  final String title, message;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const Spacer(),
              Container(
                width: 96,
                height: 96,
                decoration: BoxDecoration(color: p.okSoft, shape: BoxShape.circle),
                child: Icon(Icons.check_rounded, color: p.ok, size: 56),
              ),
              const SizedBox(height: 22),
              Text(title,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.5)),
              const SizedBox(height: 10),
              Text(message,
                  textAlign: TextAlign.center, style: TextStyle(fontSize: 16.5, color: p.inkSoft, height: 1.45)),
              const Spacer(),
              FilledButton(
                onPressed: onDone,
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
                child: const Text('Back to My classes'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
