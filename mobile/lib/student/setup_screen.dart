import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Who a student is, as the routine knows them: a batch, a section of it, a lab
/// group of that, and any retake groups. No sign-in: the phone remembers it.
/// Pops with the groups picked. Mirrors SectionPicker.tsx.
class StudentSetupScreen extends StatefulWidget {
  const StudentSetupScreen({super.key, this.initial = const []});
  final List<String> initial;

  @override
  State<StudentSetupScreen> createState() => _StudentSetupScreenState();
}

class _StudentSetupScreenState extends State<StudentSetupScreen> {
  StudentDirectory? _dir;
  String? _error;
  String? _intake, _section, _lab;
  late final List<String> _retakes = widget.initial.where((g) => g.contains(':')).toList();
  final _query = TextEditingController();

  static final _labRe = RegExp(r'^(\d+_[A-Z])\d+$');

  @override
  void initState() {
    super.initState();
    for (final g in widget.initial.where((g) => !g.contains(':'))) {
      final lab = _labRe.firstMatch(g);
      if (lab != null) {
        _lab = g;
        _section = lab.group(1);
      } else {
        _section = g;
      }
    }
    _intake = _section?.split('_').first;
    _query.addListener(() => setState(() {}));
    _load();
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final dir = await context.api.studentDirectory();
      if (!mounted) return;
      setState(() {
        _dir = dir;
        _error = null;
      });
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  List<String> get _groups => [if (_section != null) _lab ?? _section!, ..._retakes];

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final dir = _dir;

    return Scaffold(
      appBar: AppBar(title: const Text('Find your routine')),
      body: dir == null
          ? (_error != null
                ? LoadError(message: _error!, onRetry: _load)
                : const Loading(label: 'Loading the routine…'))
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              children: [
                Text(
                  '${dir.department} · ${dir.semester ?? 'No semester running'}. No sign-in: pick your section once '
                  'and ClassTrack remembers it.',
                  style: TextStyle(fontSize: 15, color: p.inkSoft, height: 1.4),
                ),
                const SizedBox(height: 20),
                ..._steps(context, dir),
              ],
            ),
      bottomNavigationBar: dir == null
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: FilledButton(
                  onPressed: _groups.isEmpty ? null : () => Navigator.of(context).pop(_groups),
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
                  child: const Text('Show my routine'),
                ),
              ),
            ),
    );
  }

  List<Widget> _steps(BuildContext context, StudentDirectory dir) {
    final intakes = {for (final s in dir.sections) s.intake}.where((i) => i.isNotEmpty).toList();
    final sections = dir.sections.where((s) => s.intake == _intake).toList();
    final chosen = dir.sections.where((s) => s.section == _section).firstOrNull;
    final hasLabs = chosen != null && chosen.labGroups.isNotEmpty;

    return [
      _Step(
        n: 1,
        title: 'Your batch',
        child: _Chips(
          options: [for (final i in intakes) (i, i)],
          selected: _intake,
          onPick: (i) => setState(() {
            _intake = i;
            _section = null;
            _lab = null;
          }),
        ),
      ),
      if (_intake != null)
        _Step(
          n: 2,
          title: 'Your section',
          child: _Chips(
            options: [for (final s in sections) (s.section, s.section.split('_').last)],
            selected: _section,
            onPick: (s) => setState(() {
              _section = s;
              _lab = null;
            }),
          ),
        ),
      if (hasLabs)
        _Step(
          n: 3,
          title: 'Your lab group',
          hint: 'For your lab classes. Theory classes are the whole section\'s.',
          child: _Chips(
            options: [for (final g in chosen.labGroups) (g, g), ('', 'Not sure')],
            selected: _lab ?? '',
            onPick: (g) => setState(() => _lab = g.isEmpty ? null : g),
          ),
        ),
      if (_section != null)
        _Step(
          n: hasLabs ? 4 : 3,
          title: 'Retake courses (optional)',
          hint: 'Taking a course again with another batch? Add its retake group.',
          child: _retakePicker(context, dir),
        ),
    ];
  }

  Widget _retakePicker(BuildContext context, StudentDirectory dir) {
    final p = context.palette;
    final q = _query.text.trim().toLowerCase();
    final matches = q.isEmpty
        ? const <RetakeCourse>[]
        : dir.retakes
              .where((r) => r.courseCode.toLowerCase().contains(q) || (r.courseTitle ?? '').toLowerCase().contains(q))
              .take(8)
              .toList();

    void toggle(String token) =>
        setState(() => _retakes.contains(token) ? _retakes.remove(token) : _retakes.add(token));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_retakes.isNotEmpty) ...[
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final t in _retakes) InputChip(label: Text(t.replaceFirst(':', ' · ')), onDeleted: () => toggle(t)),
            ],
          ),
          const SizedBox(height: 10),
        ],
        TextField(
          controller: _query,
          textCapitalization: TextCapitalization.characters,
          decoration: const InputDecoration(
            labelText: 'Course code, e.g. CSE447',
            prefixIcon: Icon(Icons.search_rounded),
          ),
        ),
        for (final r in matches)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Panel(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    r.courseTitle == null ? r.courseCode : '${r.courseCode} · ${r.courseTitle}',
                    style: TextStyle(fontWeight: FontWeight.w700, color: p.ink),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final (token, section) in [
                        for (final g in r.groups) ...[(g.token, g.section), ...g.labGroups],
                      ])
                        FilterChip(
                          label: Text(section),
                          selected: _retakes.contains(token),
                          onSelected: (_) => toggle(token),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        if (q.isNotEmpty && matches.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('No retake course matches.', style: TextStyle(color: p.inkFaint)),
          ),
      ],
    );
  }
}

class _Step extends StatelessWidget {
  const _Step({required this.n, required this.title, required this.child, this.hint});
  final int n;
  final String title;
  final String? hint;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: const EdgeInsets.only(bottom: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(color: p.brandSolid, shape: BoxShape.circle),
                child: Text(
                  '$n',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 14),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                title,
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: p.ink),
              ),
            ],
          ),
          if (hint != null)
            Padding(
              padding: const EdgeInsets.only(left: 38, top: 2),
              child: Text(hint!, style: TextStyle(fontSize: 14, color: p.inkSoft)),
            ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

/// A row of large choices, one of which may be picked.
class _Chips extends StatelessWidget {
  const _Chips({required this.options, required this.selected, required this.onPick});
  final List<(String, String)> options;
  final String? selected;
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final (value, label) in options)
          Material(
            color: value == selected ? p.brandSolid : p.surface,
            borderRadius: BorderRadius.circular(14),
            child: InkWell(
              borderRadius: BorderRadius.circular(14),
              onTap: () => onPick(value),
              child: Container(
                constraints: const BoxConstraints(minWidth: 52, minHeight: 48),
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: value == selected ? p.brandSolid : p.line, width: 1.2),
                ),
                // A row as wide as its label: an aligned child would stretch the chip across the screen.
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: value == selected ? Colors.white : p.ink,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}
