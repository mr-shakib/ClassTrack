import 'dart:async';

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';

/// A form field's label, set large: teachers use these screens on a phone.
class FieldLabel extends StatelessWidget {
  const FieldLabel(this.text, {super.key, this.hint});
  final String text;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            text,
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: p.ink),
          ),
          if (hint != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(hint!, style: TextStyle(fontSize: 14, color: p.inkSoft)),
            ),
        ],
      ),
    );
  }
}

/// A tappable field that opens a picker: a date, a time.
class PickerField extends StatelessWidget {
  const PickerField({
    super.key,
    required this.icon,
    required this.value,
    required this.placeholder,
    required this.onTap,
  });

  final IconData icon;
  final String? value;
  final String placeholder;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final empty = value == null;
    return Material(
      color: p.surface,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Container(
          height: 58,
          padding: const EdgeInsets.symmetric(horizontal: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: empty ? p.line : p.brand.withValues(alpha: 0.5), width: 1.5),
          ),
          child: Row(
            children: [
              Icon(icon, color: empty ? p.inkFaint : p.brand, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  value ?? placeholder,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 16.5,
                    fontWeight: empty ? FontWeight.w500 : FontWeight.w700,
                    color: empty ? p.inkFaint : p.ink,
                    fontFeatures: tabular,
                  ),
                ),
              ),
              Icon(Icons.expand_more_rounded, color: p.inkSoft),
            ],
          ),
        ),
      ),
    );
  }
}

/// Opens a date picker that starts today, for a class still to come.
Future<String?> pickFutureDate(BuildContext context, String? current) async {
  final today = parseDay(todayIso());
  final picked = await showDatePicker(
    context: context,
    initialDate: current == null ? today : parseDay(current),
    firstDate: today,
    lastDate: today.add(const Duration(days: 180)),
  );
  return picked == null ? null : isoDate(picked);
}

/// The six routine slots as a 3 × 2 grid of large buttons.
class SlotGrid extends StatelessWidget {
  const SlotGrid({super.key, required this.selected, required this.onPick});
  final String? selected;
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return LayoutBuilder(
      builder: (context, box) {
        final w = (box.maxWidth - 16) / 3;
        return Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final s in slots)
              SizedBox(
                width: w,
                child: _Tile(
                  selected: selected == s,
                  onTap: () => onPick(s),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        slotStart(s),
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w800,
                          color: selected == s ? Colors.white : p.ink,
                          fontFeatures: tabular,
                        ),
                      ),
                      Text(
                        'to ${s.split('-').last}',
                        style: TextStyle(
                          fontSize: 12.5,
                          color: selected == s ? Colors.white70 : p.inkSoft,
                          fontFeatures: tabular,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

/// A selectable tile: brand-filled when picked.
class _Tile extends StatelessWidget {
  const _Tile({required this.selected, required this.onTap, required this.child, this.height = 62});
  final bool selected;
  final VoidCallback onTap;
  final Widget child;
  final double height;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Material(
      color: selected ? p.brandSolid : p.surface,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Container(
          height: height,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: selected ? p.brandSolid : p.line, width: 1.5),
          ),
          child: child,
        ),
      ),
    );
  }
}

/// Two big choices side by side, such as "In a room" and "Online".
class ChoicePair<T> extends StatelessWidget {
  const ChoicePair({super.key, required this.value, required this.options, required this.onChanged});
  final T value;
  final List<(T, String, IconData)> options;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Row(
      children: [
        for (var i = 0; i < options.length; i++) ...[
          if (i > 0) const SizedBox(width: 10),
          Expanded(
            child: _Tile(
              selected: value == options[i].$1,
              onTap: () => onChanged(options[i].$1),
              height: 64,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(options[i].$3, color: value == options[i].$1 ? Colors.white : p.inkSoft),
                  const SizedBox(width: 8),
                  Text(
                    options[i].$2,
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: value == options[i].$1 ? Colors.white : p.ink,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}

/// The empty rooms of one cell, reloaded whenever the cell changes.
class FreeRoomsLoader {
  FreeRoomsLoader(this.api, this.onChange);

  final Api api;
  final VoidCallback onChange;

  List<FreeRoom>? rooms;
  bool loading = false;
  String? error;
  int _request = 0;

  Future<void> load(String? date, String? slot) async {
    final request = ++_request;
    if (date == null || slot == null) {
      rooms = null;
      loading = false;
      onChange();
      return;
    }
    loading = true;
    error = null;
    onChange();
    try {
      final r = await api.freeRooms(date, slot);
      if (request != _request) return;
      rooms = r;
    } on ApiError catch (e) {
      if (request != _request) return;
      rooms = [];
      error = e.message;
    }
    loading = false;
    onChange();
  }
}

/// Pick one empty room, offered as large tiles. `roomType` narrows the list
/// to rooms like the class usually meets in, with a switch to show them all.
class RoomPicker extends StatefulWidget {
  const RoomPicker({
    super.key,
    required this.hasCell,
    required this.loader,
    required this.room,
    required this.onPick,
    this.roomType,
  });

  final bool hasCell;
  final FreeRoomsLoader loader;
  final String? room;
  final ValueChanged<String?> onPick;
  final String? roomType;

  @override
  State<RoomPicker> createState() => _RoomPickerState();
}

class _RoomPickerState extends State<RoomPicker> {
  bool _sameType = true;
  bool _all = false;

  static const _first = 12;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final l = widget.loader;
    final type = widget.roomType;
    final narrowed = _sameType && type != null && type.isNotEmpty;
    final shown = (l.rooms ?? const <FreeRoom>[]).where((r) => !narrowed || r.roomType == type).toList();
    final visible = _all ? shown : shown.take(_first).toList();
    final typeLabel = (type ?? '').toLowerCase();

    Widget body;
    if (l.error != null) {
      body = Notice.error(l.error!);
    } else if (!widget.hasCell) {
      body = const Notice(
        'Pick a date and time to see which rooms are empty.',
        tone: Tone.neutral,
        icon: Icons.info_outline_rounded,
      );
    } else if (l.loading) {
      body = Row(
        children: [
          const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2.5)),
          const SizedBox(width: 10),
          Text('Finding empty rooms…', style: TextStyle(color: p.inkSoft, fontSize: 15)),
        ],
      );
    } else if (shown.isEmpty) {
      body = Notice(
        'No empty ${narrowed ? '$typeLabel ' : ''}rooms at this time. Try another time'
        '${narrowed ? ' or include every room type' : ''}.',
        tone: Tone.neutral,
        icon: Icons.meeting_room_outlined,
      );
    } else {
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          LayoutBuilder(
            builder: (context, box) {
              final cols = box.maxWidth > 520 ? 4 : 2;
              final w = (box.maxWidth - 8 * (cols - 1)) / cols;
              return Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final r in visible)
                    SizedBox(
                      width: w,
                      child: _Tile(
                        selected: widget.room == r.room,
                        onTap: () => widget.onPick(r.room),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    r.room,
                                    style: TextStyle(
                                      fontSize: 17,
                                      fontWeight: FontWeight.w800,
                                      color: widget.room == r.room ? Colors.white : p.ink,
                                    ),
                                  ),
                                  Text(
                                    narrowed ? r.zone : '${r.zone} · ${r.roomType}',
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontSize: 12.5,
                                      color: widget.room == r.room ? Colors.white70 : p.inkSoft,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            if (widget.room == r.room)
                              const Icon(Icons.check_circle_rounded, color: Colors.white, size: 20),
                          ],
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
          if (shown.length > _first && !_all)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: TextButton(
                onPressed: () => setState(() => _all = true),
                child: Text('Show all ${shown.length} empty rooms'),
              ),
            ),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                widget.room == null ? 'Empty room' : 'Empty room · ${widget.room}',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: p.ink),
              ),
            ),
            if (type != null && type.isNotEmpty) ...[
              Text('Only $typeLabel', style: TextStyle(fontSize: 13.5, color: p.inkSoft)),
              const SizedBox(width: 4),
              Switch(value: _sameType, onChanged: (v) => setState(() => _sameType = v)),
            ],
          ],
        ),
        const SizedBox(height: 8),
        body,
      ],
    );
  }
}

/// What stands in the way of a proposed time, and what could not be checked.
class ConflictNotes extends StatelessWidget {
  const ConflictNotes({super.key, required this.checking, required this.report});
  final bool checking;
  final ConflictReport? report;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    if (checking) {
      return Row(
        children: [
          const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
          const SizedBox(width: 10),
          Text('Checking availability…', style: TextStyle(color: p.inkSoft, fontSize: 15)),
        ],
      );
    }
    final r = report;
    if (r == null) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!r.ok)
          Notice(
            r.conflicts.map((c) => '${_typeLabel(c.type)}: ${c.message}').join('\n'),
            title: '${r.conflicts.length} conflict${r.conflicts.length == 1 ? '' : 's'}',
            tone: Tone.bad,
            icon: Icons.block_rounded,
          )
        else
          const Notice('This time is free.', tone: Tone.ok, icon: Icons.check_circle_outline_rounded),
        if (r.warnings.isNotEmpty) ...[
          const SizedBox(height: 10),
          Notice(
            r.warnings.join('\n'),
            title: 'Check before you book',
            tone: Tone.warn,
            icon: Icons.warning_amber_rounded,
          ),
        ],
      ],
    );
  }

  static String _typeLabel(String type) => switch (type) {
    'TEACHER' => 'Teacher',
    'ROOM' => 'Room',
    'SECTION' => 'Section',
    'HOLIDAY' => 'Holiday',
    'EXAM' => 'Exams',
    'SLOT' => 'Time',
    _ => type,
  };
}

/// Runs `action` once input has paused for a moment.
class Debouncer {
  Timer? _timer;
  void call(VoidCallback action) {
    _timer?.cancel();
    _timer = Timer(const Duration(milliseconds: 350), action);
  }

  void dispose() => _timer?.cancel();
}
