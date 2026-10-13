import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import '../widgets/status.dart';
import 'booking.dart';

/// Take an empty room for one of your sections. Booked at once, with no
/// approval, and checked like any class. Mirrors web/src/app/teacher/extra/page.tsx.
class ExtraClassScreen extends StatefulWidget {
  const ExtraClassScreen({super.key});

  @override
  State<ExtraClassScreen> createState() => _ExtraClassScreenState();
}

class _ExtraClassScreenState extends State<ExtraClassScreen> {
  List<ExtraSection>? _sections;
  List<ClassInstance> _booked = [];
  String? _error;

  String? _picked;
  String? _date;
  String _slot = slots[0];
  String? _room;
  ConflictReport? _report;
  bool _checking = false;
  int _checkRequest = 0;
  bool _busy = false;
  String? _formError;
  String? _notice;
  final _debounce = Debouncer();
  late final FreeRoomsLoader _rooms = FreeRoomsLoader(context.api, _roomsChanged);

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _debounce.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final api = context.api;
    try {
      final sections = await api.extraSections();
      if (!mounted) return;
      setState(() {
        _sections = sections;
        _picked ??= sections.isEmpty ? null : sections.first.key;
      });
    } on ApiError catch (e) {
      if (mounted) {
        setState(() {
          _sections = [];
          _error = e.message;
        });
      }
    }
    await _loadBooked();
  }

  Future<void> _loadBooked() async {
    try {
      final booked = await context.api.extraClasses();
      if (mounted) setState(() => _booked = booked);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  ExtraSection? get _section => _sections?.where((s) => s.key == _picked).firstOrNull;

  void _roomsChanged() {
    if (!mounted) return;
    setState(() {
      final rooms = _rooms.rooms;
      if (rooms != null && _room != null && !rooms.any((r) => r.room == _room)) _room = null;
    });
    _validate();
  }

  void _cellChanged() {
    _rooms.load(_date, _slot);
    _validate();
  }

  void _validate() {
    final s = _section;
    if (_date == null || _room == null || s == null) {
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
          timeSlot: _slot,
          room: _room,
          section: s.section,
          courseCode: s.courseCode,
        );
        if (mounted && request == _checkRequest) setState(() => _report = r);
      } on ApiError {
        if (mounted && request == _checkRequest) setState(() => _report = null);
      } finally {
        if (mounted && request == _checkRequest) setState(() => _checking = false);
      }
    });
  }

  Future<void> _book() async {
    final s = _section!;
    setState(() {
      _busy = true;
      _formError = null;
      _notice = null;
    });
    try {
      final made = await context.api.bookExtraClass(
        courseCode: s.courseCode,
        section: s.section,
        date: _date!,
        timeSlot: _slot,
        room: _room!,
      );
      setState(() {
        _notice =
            '${made.room} is booked for ${made.courseCode} · ${made.section} on '
            '${formatDay(made.date)} at ${slotLabel(made.timeSlot)}. Staff will check it then.';
        _room = null;
        _report = null;
      });
      // The room just taken leaves the list.
      _rooms.load(_date, _slot);
      _loadBooked();
    } on ApiError catch (e) {
      setState(() => _formError = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancel(ClassInstance inst) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel this class?'),
        content: Text('${inst.room} on ${formatDay(inst.date)} at ${slotLabel(inst.timeSlot)} is given back.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Keep it')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(backgroundColor: context.palette.badSolid, minimumSize: const Size(64, 44)),
            child: const Text('Yes, cancel it'),
          ),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    try {
      await context.api.cancelExtraClass(inst.id);
      if (mounted) showMessage(context, 'Cancelled. ${inst.room} is free again.');
      _loadBooked();
      _rooms.load(_date, _slot);
    } on ApiError catch (e) {
      if (mounted) showMessage(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final sections = _sections;
    // Still to come first, soonest at the top; the rest as they happened.
    final upcoming = _booked.where((b) => b.status == 'UPCOMING').toList()
      ..sort((a, b) {
        final d = a.date.compareTo(b.date);
        return d != 0 ? d : slots.indexOf(a.timeSlot).compareTo(slots.indexOf(b.timeSlot));
      });
    final past = _booked.where((b) => b.status != 'UPCOMING').toList();
    final blocked = _report != null && !_report!.ok;
    final ready = !_busy && !blocked && !_checking && _date != null && _room != null && _section != null;

    return Scaffold(
      appBar: AppBar(title: const Text('Book an extra class')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        children: [
          Text(
            'Take an empty room for one of your sections. It is booked at once, with no approval, and '
            "staff check it like any class. Held, it counts towards the course's classes; if you do not "
            'come, it is recorded as missed.',
            style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.45),
          ),
          const SizedBox(height: 18),
          if (_error != null) ...[Notice.error(_error!), const SizedBox(height: 14)],
          if (sections == null)
            const Loading(label: 'Loading your sections…')
          else if (sections.isEmpty)
            const Panel(
              child: EmptyState(
                icon: Icons.class_outlined,
                title: 'No sections to book for',
                body: 'You have no classes on the routine in force.',
              ),
            )
          else
            Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const FieldLabel('Section'),
                  DropdownButtonFormField<String>(
                    initialValue: _picked,
                    isExpanded: true,
                    borderRadius: BorderRadius.circular(14),
                    items: [
                      for (final s in sections)
                        DropdownMenuItem(
                          value: s.key,
                          child: Text(
                            '${s.courseCode} · ${s.section}${s.courseTitle.isNotEmpty ? ' — ${s.courseTitle}' : ''}',
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontWeight: FontWeight.w600, fontSize: 16, color: p.ink),
                          ),
                        ),
                    ],
                    onChanged: (v) {
                      setState(() => _picked = v);
                      _validate();
                    },
                  ),
                  const SizedBox(height: 20),
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
                  const SizedBox(height: 20),
                  const FieldLabel('Time', hint: 'Classes run on fixed 90-minute slots.'),
                  SlotGrid(
                    selected: _slot,
                    onPick: (s) {
                      setState(() => _slot = s);
                      _cellChanged();
                    },
                  ),
                  const SizedBox(height: 20),
                  RoomPicker(
                    hasCell: _date != null,
                    loader: _rooms,
                    room: _room,
                    roomType: _section?.roomType,
                    onPick: (r) {
                      setState(() => _room = r);
                      _validate();
                    },
                  ),
                  const SizedBox(height: 16),
                  ConflictNotes(checking: _checking, report: _report),
                  if (_formError != null) ...[const SizedBox(height: 12), Notice.error(_formError!)],
                  if (_notice != null) ...[
                    const SizedBox(height: 12),
                    Notice(_notice!, tone: Tone.ok, icon: Icons.check_circle_rounded, title: 'Booked'),
                  ],
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: ready ? _book : null,
                    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
                    child: _busy
                        ? const ButtonSpinner()
                        : Text(
                            blocked
                                ? 'Resolve the conflict first'
                                : _date == null
                                ? 'Pick a date'
                                : _room == null
                                ? 'Pick an empty room'
                                : 'Book $_room',
                          ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 26),
          SectionHeader('Your extra classes', subtitle: '${upcoming.length} coming'),
          Panel(
            padding: EdgeInsets.zero,
            child: _booked.isEmpty
                ? const EmptyState(icon: Icons.event_available_outlined, title: 'None booked yet')
                : Column(
                    children: [
                      for (final (i, b) in [...upcoming, ...past].indexed) ...[
                        if (i > 0) Divider(indent: 16, endIndent: 16, color: p.line),
                        _BookedRow(inst: b, onCancel: () => _cancel(b)),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _BookedRow extends StatelessWidget {
  const _BookedRow({required this.inst, required this.onCancel});
  final ClassInstance inst;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 8, 10),
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
                      '${inst.courseCode} · ${inst.section}',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: p.ink),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${shortDay(inst.date)} · ${slotLabel(inst.timeSlot)} · ${inst.room}',
                      style: TextStyle(fontSize: 14.5, color: p.inkSoft, fontFeatures: tabular),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: StatusBadge(inst.status, lateMinutes: inst.check?.lateMinutes),
              ),
            ],
          ),
          if (inst.status == 'UPCOMING')
            TextButton.icon(
              onPressed: onCancel,
              style: TextButton.styleFrom(foregroundColor: p.bad, padding: EdgeInsets.zero),
              icon: const Icon(Icons.close_rounded, size: 18),
              label: const Text('Cancel this class'),
            ),
        ],
      ),
    );
  }
}
