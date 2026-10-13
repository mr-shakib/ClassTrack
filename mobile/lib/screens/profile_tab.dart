import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// Who is signed in, their absence-email address, their password, and the
/// way out. Mirrors web/src/app/profile/page.tsx.
class ProfileTab extends StatefulWidget {
  const ProfileTab({super.key});

  @override
  State<ProfileTab> createState() => _ProfileTabState();
}

class _ProfileTabState extends State<ProfileTab> {
  Profile? _profile;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final profile = await context.api.profile();
      if (mounted) {
        setState(() {
          _profile = profile;
          _error = null;
        });
      }
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _editEmail() async {
    final saved = await showModalBottomSheet<Profile>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _EmailSheet(current: _profile?.contactEmail),
    );
    if (saved != null && mounted) {
      setState(() => _profile = saved);
      showMessage(context, 'Saved. Absence emails go to ${saved.contactEmail}.');
    }
  }

  Future<void> _signOut() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text('You will need your password to sign in again.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Stay')),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(minimumSize: const Size(64, 44)),
            child: const Text('Sign out'),
          ),
        ],
      ),
    );
    if (yes == true && mounted) await SessionScope.read(context).signOut();
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final user = SessionScope.of(context).user!;
    final profile = _profile;

    // The brand band runs under the status bar: light icons on it.
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: Scaffold(
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            _Hero(user: user, profile: profile),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_error != null && profile == null) ...[Notice.error(_error!), const SizedBox(height: 16)],
                  if (user.isTeacher) ...[
                    const _GroupLabel('Absence emails'),
                    Panel(
                      padding: EdgeInsets.zero,
                      child: Column(
                        children: [
                          Padding(
                            padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
                            child: Text('When staff report you absent from a class, ClassTrack emails you.',
                                style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4)),
                          ),
                          ListTile(
                            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
                            leading: Icon(Icons.mail_outline_rounded, color: p.info),
                            title: Text(
                              profile == null ? '…' : (profile.contactEmail ?? 'No address on file'),
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                color: profile?.contactEmail == null ? p.warn : p.ink,
                              ),
                            ),
                            subtitle: profile?.contactEmail == null && profile != null
                                ? const Text('You are not emailed when reported absent. Add one.')
                                : null,
                            trailing: Text(profile?.contactEmail == null ? 'Add' : 'Change',
                                style: TextStyle(color: p.brand, fontWeight: FontWeight.w700, fontSize: 15)),
                            onTap: profile == null ? null : _editEmail,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 22),
                  ],
                  const _GroupLabel('Account'),
                  Panel(
                    padding: EdgeInsets.zero,
                    child: Column(
                      children: [
                        ListTile(
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                          leading: Icon(Icons.lock_outline_rounded, color: p.brand),
                          title: const Text('Change password'),
                          subtitle: const Text('Replace a default password with one only you know'),
                          trailing: Icon(Icons.chevron_right_rounded, color: p.inkFaint),
                          onTap: () => Navigator.of(context)
                              .push(MaterialPageRoute(builder: (_) => const ChangePasswordScreen())),
                        ),
                        Divider(indent: 16, endIndent: 16, color: p.line),
                        ListTile(
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                          leading: Icon(Icons.language_rounded, color: p.brand),
                          title: const Text('Open ClassTrack on the web'),
                          subtitle: Text(Uri.parse(siteUrl).host),
                          trailing: Icon(Icons.open_in_new_rounded, color: p.inkFaint, size: 20),
                          onTap: () => openLink(context, siteUrl),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 22),
                  OutlinedButton.icon(
                    onPressed: _signOut,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: p.bad,
                      side: BorderSide(color: p.bad.withValues(alpha: 0.35), width: 1.5),
                      minimumSize: const Size.fromHeight(54),
                    ),
                    icon: const Icon(Icons.logout_rounded),
                    label: const Text('Sign out'),
                  ),
                  const SizedBox(height: 26),
                  Center(
                    child: InkWell(
                      onTap: () => openLink(context, 'https://shakibhowlader.online'),
                      borderRadius: BorderRadius.circular(8),
                      child: Padding(
                        padding: const EdgeInsets.all(8),
                        child: Text.rich(
                          TextSpan(children: [
                            const TextSpan(text: 'ClassTrack 1.0  ·  Developed by '),
                            TextSpan(text: 'Shakib Howlader', style: TextStyle(color: p.inkSoft, fontWeight: FontWeight.w600)),
                          ]),
                          style: TextStyle(fontSize: 13, color: p.inkFaint),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
    );
  }
}

class _GroupLabel extends StatelessWidget {
  const _GroupLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(left: 4, bottom: 8),
        child: Text(text.toUpperCase(),
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.8,
              color: context.palette.inkFaint,
            )),
      );
}

/// The person: photo or initials on a brand band, and what identifies them here.
class _Hero extends StatelessWidget {
  const _Hero({required this.user, required this.profile});
  final User user;
  final Profile? profile;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final top = MediaQuery.of(context).padding.top;
    final facts = <(IconData, String, String)>[
      (Icons.badge_outlined, 'Signs in with', profile?.signIn ?? user.teacherInitial ?? user.email),
      (Icons.verified_user_outlined, user.roles.length == 1 ? 'Role' : 'Roles', user.roleNames),
      if (profile?.department != null) (Icons.apartment_rounded, 'Department', profile!.department!.toUpperCase()),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              width: double.infinity,
              height: 118 + top,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [p.brandSolid, Color.lerp(p.brandSolid, p.infoSolid, 0.7)!],
                ),
              ),
              padding: EdgeInsets.fromLTRB(20, top + 14, 20, 0),
              child: const Text('Profile',
                  style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800)),
            ),
            Positioned(
              left: 20,
              bottom: -44,
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(color: p.canvas, shape: BoxShape.circle),
                child: Avatar(
                  name: user.fullName,
                  initial: user.teacherInitial,
                  photo: profile?.photoUrl ?? user.photoUrl,
                  size: 88,
                ),
              ),
            ),
          ],
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 54, 20, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(user.fullName,
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.5)),
              if (profile?.designation != null)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(profile!.designation!, style: TextStyle(fontSize: 15.5, color: p.inkSoft)),
                ),
              const SizedBox(height: 16),
              for (final f in facts)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Row(
                    children: [
                      Container(
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(11)),
                        child: Icon(f.$1, color: p.brand, size: 20),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(f.$2.toUpperCase(),
                                style: TextStyle(
                                    fontSize: 11.5, fontWeight: FontWeight.w700, letterSpacing: 0.6, color: p.inkFaint)),
                            Text(f.$3, style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: p.ink)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              Text(
                user.teacherInitial != null
                    ? 'Your name and designation come from the faculty list. Ask the department office to correct them.'
                    : 'Your name and role are set by an administrator.',
                style: TextStyle(fontSize: 13, color: p.inkFaint, height: 1.4),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Change the address absence reports are mailed to.
class _EmailSheet extends StatefulWidget {
  const _EmailSheet({required this.current});
  final String? current;

  @override
  State<_EmailSheet> createState() => _EmailSheetState();
}

class _EmailSheetState extends State<_EmailSheet> {
  late final _email = TextEditingController(text: widget.current ?? '');
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final profile = await context.api.updateContactEmail(_email.text.trim());
      if (mounted) Navigator.of(context).pop(profile);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final unchanged = _email.text.trim() == (widget.current ?? '') || _email.text.trim().isEmpty;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Absence emails', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: p.ink)),
          const SizedBox(height: 4),
          Text('When staff report you absent from a class, ClassTrack emails this address.',
              style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4)),
          const SizedBox(height: 16),
          TextField(
            controller: _email,
            autofocus: true,
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.email],
            onChanged: (_) => setState(() {}),
            onSubmitted: (_) => unchanged ? null : _save(),
            decoration: const InputDecoration(hintText: 'name@diu.edu.bd', prefixIcon: Icon(Icons.mail_outline_rounded)),
          ),
          if (_error != null) ...[const SizedBox(height: 12), Notice.error(_error!)],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy || unchanged ? null : _save,
            child: _busy ? const ButtonSpinner() : const Text('Save email'),
          ),
        ],
      ),
    );
  }
}

/// Change the password, with the server's rules shown as they are met.
class ChangePasswordScreen extends StatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  State<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends State<ChangePasswordScreen> {
  static const _minLength = 6;
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  bool _shown = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  List<(bool, String)> get _rules => [
        (_next.text.length >= _minLength, 'At least $_minLength characters'),
        (_next.text.isNotEmpty && _next.text != _current.text, 'Different from your current password'),
        (_confirm.text.isNotEmpty && _confirm.text == _next.text, 'Both new passwords match'),
      ];

  bool get _ready => _current.text.isNotEmpty && _rules.every((r) => r.$1);

  Future<void> _submit() async {
    if (!_ready) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.api.changePassword(_current.text, _next.text);
      if (!mounted) return;
      showMessage(context, 'Password changed. Use the new one next time you sign in.');
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
    Widget field(String label, TextEditingController c, List<String> hints) => Padding(
          padding: const EdgeInsets.only(bottom: 14),
          child: TextField(
            controller: c,
            obscureText: !_shown,
            autofillHints: hints,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(labelText: label),
          ),
        );

    return Scaffold(
      appBar: AppBar(title: const Text('Change password')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
        children: [
          Text('If the department gave you a default password, replace it with one only you know.',
              style: TextStyle(fontSize: 15, color: p.inkSoft, height: 1.4)),
          const SizedBox(height: 18),
          AutofillGroup(
            child: Column(
              children: [
                field('Current password', _current, const [AutofillHints.password]),
                field('New password', _next, const [AutofillHints.newPassword]),
                field('New password again', _confirm, const [AutofillHints.newPassword]),
              ],
            ),
          ),
          SwitchListTile(
            value: _shown,
            onChanged: (v) => setState(() => _shown = v),
            contentPadding: const EdgeInsets.symmetric(horizontal: 4),
            title: const Text('Show passwords'),
          ),
          const SizedBox(height: 6),
          Panel(
            color: p.canvas,
            padding: const EdgeInsets.all(14),
            child: Column(
              children: [
                for (final (met, label) in _rules)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      children: [
                        Icon(met ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                            size: 20, color: met ? p.ok : p.inkFaint),
                        const SizedBox(width: 10),
                        Text(label,
                            style: TextStyle(
                              fontSize: 14.5,
                              color: met ? p.ok : p.inkSoft,
                              fontWeight: met ? FontWeight.w700 : FontWeight.w500,
                            )),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          if (_error != null) ...[const SizedBox(height: 14), Notice.error(_error!)],
          const SizedBox(height: 18),
          FilledButton(
            onPressed: _busy || !_ready ? null : _submit,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
            child: _busy ? const ButtonSpinner() : const Text('Update password'),
          ),
        ],
      ),
    );
  }
}
