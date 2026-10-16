import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Things a teacher often tells a section before a class.
const _quick = [
  'Please bring your laptops.',
  'We will have a quiz in this class.',
  'Please read the shared material before the class.',
];

const _bodyMax = 500;

/// Heads-up: a note to a class's students about that one class. It shows on
/// the class for them, and reaches their phones.
Future<void> showHeadsUpSheet(BuildContext context, {required int instanceId, required String label}) async {
  final sent = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _HeadsUp(instanceId: instanceId, label: label),
  );
  if (sent == true && context.mounted) showMessage(context, 'Sent to your students.');
}

class _HeadsUp extends StatefulWidget {
  const _HeadsUp({required this.instanceId, required this.label});
  final int instanceId;
  final String label;

  @override
  State<_HeadsUp> createState() => _HeadsUpState();
}

class _HeadsUpState extends State<_HeadsUp> {
  final _body = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _body.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.api.writeToMyStudents(body: _body.text.trim(), instanceId: widget.instanceId);
      if (mounted) Navigator.of(context).pop(true);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Heads-up to your students',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: p.ink),
          ),
          Text(widget.label, style: TextStyle(fontSize: 14.5, color: p.inkSoft)),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [for (final q in _quick) ActionChip(label: Text(q), onPressed: () => _body.text = q)],
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _body,
            maxLength: _bodyMax,
            minLines: 2,
            maxLines: 5,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(labelText: 'Your note'),
          ),
          if (_error != null) ...[const SizedBox(height: 8), Notice.error(_error!)],
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: _busy || _body.text.trim().isEmpty ? null : _send,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            icon: _busy ? const ButtonSpinner() : const Icon(Icons.send_rounded),
            label: const Text('Send'),
          ),
        ],
      ),
    );
  }
}

/// Section Notices, from the teacher: a note to any of their sections.
class MessageStudentsScreen extends StatefulWidget {
  const MessageStudentsScreen({super.key});

  @override
  State<MessageStudentsScreen> createState() => _MessageStudentsScreenState();
}

class _MessageStudentsScreenState extends State<MessageStudentsScreen> {
  List<TeacherGroup>? _groups;
  final _chosen = <String>{};
  final _body = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _body.addListener(() => setState(() {}));
    _load();
  }

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final groups = await context.api.myStudentGroups();
      if (mounted) setState(() => _groups = groups);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _send() async {
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.api.writeToMyStudents(body: _body.text.trim(), targets: _chosen.toList());
      if (!mounted) return;
      showMessage(context, 'Sent. Your students see it in ClassTrack.');
      Navigator.of(context).pop();
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final groups = _groups;
    return Scaffold(
      appBar: AppBar(title: const Text('Message your students')),
      body: groups == null
          ? (_error != null ? LoadError(message: _error!, onRetry: _load) : const Loading())
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
              children: [
                Text(
                  'They see it in ClassTrack, and on their phone if they have the app.',
                  style: TextStyle(fontSize: 14.5, color: p.inkSoft),
                ),
                const SizedBox(height: 16),
                Text(
                  'To',
                  style: TextStyle(fontWeight: FontWeight.w700, color: p.ink),
                ),
                const SizedBox(height: 8),
                if (groups.isEmpty)
                  const Notice('You have no sections on the routine in force.', tone: Tone.neutral)
                else
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final g in groups)
                        FilterChip(
                          label: Text('${g.courseCode} · ${g.section}'),
                          selected: _chosen.contains(g.token),
                          onSelected: (on) => setState(() => on ? _chosen.add(g.token) : _chosen.remove(g.token)),
                        ),
                    ],
                  ),
                const SizedBox(height: 16),
                TextField(
                  controller: _body,
                  maxLength: _bodyMax,
                  minLines: 3,
                  maxLines: 8,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: const InputDecoration(
                    labelText: 'Your note',
                    hintText: 'e.g. Assignment 2 is due Sunday.',
                  ),
                ),
                if (_error != null) ...[const SizedBox(height: 8), Notice.error(_error!)],
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _busy || _chosen.isEmpty || _body.text.trim().isEmpty ? null : _send,
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(54)),
                  icon: _busy ? const ButtonSpinner() : const Icon(Icons.send_rounded),
                  label: Text(
                    _chosen.isEmpty
                        ? 'Choose a section'
                        : 'Send to ${_chosen.length} section${_chosen.length == 1 ? '' : 's'}',
                  ),
                ),
              ],
            ),
    );
  }
}

/// Where the students of an online class join it: on its card, until it ends.
class JoinLinkEditor extends StatefulWidget {
  const JoinLinkEditor({super.key, required this.makeup, required this.onChanged});
  final Makeup makeup;
  final VoidCallback onChanged;

  @override
  State<JoinLinkEditor> createState() => _JoinLinkEditorState();
}

class _JoinLinkEditorState extends State<JoinLinkEditor> {
  late final _link = TextEditingController(text: widget.makeup.meetingLink ?? '');
  bool _editing = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _link.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.api.setMeetingLink(widget.makeup.id, _link.text.trim());
      if (!mounted) return;
      setState(() => _editing = false);
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
    final m = widget.makeup;
    if (!_editing) {
      return Panel(
        padding: const EdgeInsets.fromLTRB(14, 10, 8, 10),
        child: Row(
          children: [
            Icon(Icons.videocam_outlined, color: p.info),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Join link for students',
                    style: TextStyle(fontWeight: FontWeight.w700, color: p.ink),
                  ),
                  Text(
                    m.meetingLink ?? 'Not added yet',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 13.5, color: p.inkSoft),
                  ),
                ],
              ),
            ),
            TextButton(
              onPressed: () => setState(() => _editing = true),
              child: Text(m.meetingLink == null ? 'Add' : 'Change'),
            ),
          ],
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: _link,
          keyboardType: TextInputType.url,
          autocorrect: false,
          decoration: const InputDecoration(labelText: 'Join link for students', hintText: 'https://meet.google.com/…'),
        ),
        const SizedBox(height: 6),
        Text(
          m.status == 'APPROVED'
              ? 'Students of the section see it on the class, and are told it is there.'
              : 'Students see it on the class once it is approved.',
          style: TextStyle(fontSize: 13, color: p.inkSoft),
        ),
        if (_error != null) ...[const SizedBox(height: 8), Notice.error(_error!)],
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: FilledButton(
                onPressed: _busy ? null : _save,
                child: _busy ? const ButtonSpinner() : const Text('Save link'),
              ),
            ),
            const SizedBox(width: 8),
            TextButton(onPressed: _busy ? null : () => setState(() => _editing = false), child: const Text('Cancel')),
          ],
        ),
      ],
    );
  }
}
