import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';
import 'room_card.dart';

/// Find a teacher's classes by initial, to correct a past record without
/// walking back through each day, slot and floor. Each card locks by its own
/// day: staff can still change today's, admins and the committee any day's.
/// Mirrors web/src/components/TeacherSearch.tsx.
class TeacherSearch extends StatefulWidget {
  const TeacherSearch({super.key, required this.canOverride});
  final bool canOverride;

  @override
  State<TeacherSearch> createState() => _TeacherSearchState();
}

class _TeacherSearchState extends State<TeacherSearch> {
  final _initial = TextEditingController();
  late String _from = isoDate(dhakaNow().subtract(const Duration(days: 14)));
  String _to = todayIso();
  List<RoomRow>? _rows;
  String _searched = '';
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _initial.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final q = _initial.text.trim().toUpperCase();
    if (q.isEmpty) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final rows = await context.api.searchChecking(q, _from, _to);
      setState(() {
        _rows = rows;
        _searched = q;
      });
    } on ApiError catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pick(bool from) async {
    final picked = await showDatePicker(
      context: context,
      initialDate: parseDay(from ? _from : _to),
      firstDate: from ? DateTime(2024) : parseDay(_from),
      lastDate: from ? parseDay(_to) : DateTime(2035),
    );
    if (picked == null) return;
    setState(() => from ? _from = isoDate(picked) : _to = isoDate(picked));
  }

  void _patch(RoomRow next) => setState(() {
    _rows = [for (final r in _rows!) r.instanceId == next.instanceId ? next : r];
  });

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final byDay = <String, List<RoomRow>>{};
    for (final r in _rows ?? const <RoomRow>[]) {
      byDay.putIfAbsent(r.date ?? '', () => []).add(r);
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      children: [
        Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Teacher initial',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: p.ink),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _initial,
                textCapitalization: TextCapitalization.characters,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _search(),
                onChanged: (_) => setState(() {}),
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: 1.5),
                decoration: const InputDecoration(hintText: 'e.g. SRH', prefixIcon: Icon(Icons.person_search_rounded)),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _DateField(label: 'From', value: _from, onTap: () => _pick(true)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _DateField(label: 'To', value: _to, onTap: () => _pick(false)),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: _loading || _initial.text.trim().isEmpty ? null : _search,
                icon: _loading ? const ButtonSpinner() : const Icon(Icons.search_rounded),
                label: Text(_loading ? 'Searching…' : 'Find classes'),
              ),
              if (!widget.canOverride) ...[
                const SizedBox(height: 10),
                Text(
                  "You can change today's classes. Older ones are shown for reference.",
                  style: TextStyle(fontSize: 14, color: p.inkSoft),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (_error != null) Notice.error(_error!),
        if (_rows != null && !_loading)
          if (_rows!.isEmpty)
            Panel(
              child: EmptyState(
                icon: Icons.search_off_rounded,
                title: 'No classes for $_searched',
                body: 'Check the initial, or widen the dates.',
              ),
            )
          else ...[
            Text.rich(
              TextSpan(
                children: [
                  TextSpan(
                    text: '${_rows!.length}',
                    style: TextStyle(fontWeight: FontWeight.w800, color: p.ink),
                  ),
                  const TextSpan(text: ' classes for '),
                  TextSpan(
                    text: _searched,
                    style: TextStyle(fontWeight: FontWeight.w800, color: p.ink),
                  ),
                  if (_rows!.first.teacherName != null) TextSpan(text: ' · ${_rows!.first.teacherName}'),
                  const TextSpan(text: ', newest first'),
                ],
              ),
              style: TextStyle(fontSize: 15, color: p.inkSoft),
            ),
            const SizedBox(height: 14),
            for (final entry in byDay.entries) ...[
              SectionHeader(entry.key.isEmpty ? '—' : formatDay(entry.key)),
              for (final row in entry.value)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: RoomCard(
                    key: ValueKey(row.instanceId),
                    row: row,
                    showWhen: true,
                    locked: row.slotState != 'ONGOING',
                    canOverride: widget.canOverride,
                    onChanged: _patch,
                  ),
                ),
              const SizedBox(height: 6),
            ],
          ],
      ],
    );
  }
}

class _DateField extends StatelessWidget {
  const _DateField({required this.label, required this.value, required this.onTap});
  final String label, value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Material(
      color: p.surface,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: p.line, width: 1.5),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: p.inkSoft),
              ),
              const SizedBox(height: 2),
              Text(
                shortDay(value),
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: p.ink),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
