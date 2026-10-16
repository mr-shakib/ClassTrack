import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/client.dart';
import '../session.dart';
import '../student/setup_screen.dart';
import '../student/student.dart';
import '../theme.dart';
import '../widgets/common.dart';

/// The way in. Most people opening the app are students, who need no account,
/// so their door comes first; teachers and staff sign in below it.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  late final _username = TextEditingController(text: SessionScope.read(context).lastUsername);
  final _password = TextEditingController();
  final _passwordFocus = FocusNode();
  bool _shown = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_username.text.trim().isEmpty || _password.text.isEmpty) {
      setState(() => _error = 'Enter your sign-in and password.');
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await SessionScope.read(context).signIn(_username.text, _password.text);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// No sign-in for a student: they pick their section, and the app opens on it.
  Future<void> _student() async {
    final picked = await Navigator.of(
      context,
    ).push<List<String>>(MaterialPageRoute(builder: (_) => const StudentSetupScreen()));
    if (picked != null && picked.isNotEmpty && mounted) await StudentScope.read(context).setGroups(picked);
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final notice = SessionScope.of(context).notice;

    return Scaffold(
      body: SingleChildScrollView(
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        child: Column(
          children: [
            const _Header(),
            // The cards ride up over the header's lower edge.
            Transform.translate(
              offset: const Offset(0, -34),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 440),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _StudentDoor(onTap: _busy ? null : _student),
                      const SizedBox(height: 26),
                      Row(
                        children: [
                          Expanded(child: Divider(color: p.line)),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: Text(
                              'TEACHERS AND STAFF',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0.9,
                                color: p.inkFaint,
                              ),
                            ),
                          ),
                          Expanded(child: Divider(color: p.line)),
                        ],
                      ),
                      const SizedBox(height: 16),
                      if (notice != null) ...[
                        Notice(notice, tone: Tone.info, icon: Icons.info_outline_rounded),
                        const SizedBox(height: 12),
                      ],
                      _form(context),
                      const SizedBox(height: 18),
                      Center(
                        child: TextButton(
                          onPressed: () => openLink(context, '$siteUrl/privacy'),
                          style: TextButton.styleFrom(foregroundColor: p.inkFaint),
                          child: const Text('Privacy policy'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _form(BuildContext context) {
    final p = context.palette;
    return Panel(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      child: AutofillGroup(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Sign in',
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.3),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _username,
              autofillHints: const [AutofillHints.username],
              autocorrect: false,
              enableSuggestions: false,
              textInputAction: TextInputAction.next,
              onSubmitted: (_) => _passwordFocus.requestFocus(),
              decoration: const InputDecoration(
                labelText: 'Initial, email or employee ID',
                helperText: 'Teachers use their initial, e.g. SRH.',
                prefixIcon: Icon(Icons.person_outline_rounded),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _password,
              focusNode: _passwordFocus,
              obscureText: !_shown,
              autofillHints: const [AutofillHints.password],
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
              decoration: InputDecoration(
                labelText: 'Password',
                prefixIcon: const Icon(Icons.lock_outline_rounded),
                suffixIcon: IconButton(
                  tooltip: _shown ? 'Hide password' : 'Show password',
                  icon: Icon(_shown ? Icons.visibility_off_outlined : Icons.visibility_outlined),
                  onPressed: () => setState(() => _shown = !_shown),
                ),
              ),
            ),
            if (_error != null) ...[const SizedBox(height: 14), Notice.error(_error!)],
            const SizedBox(height: 18),
            FilledButton(
              onPressed: _busy ? null : _submit,
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(54)),
              child: _busy
                  ? const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [ButtonSpinner(), SizedBox(width: 10), Text('Signing in…')],
                    )
                  : const Text('Sign in'),
            ),
          ],
        ),
      ),
    );
  }
}

/// The university, then the app: on the logo's own blue, edge to edge.
class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) {
    // White status-bar icons over the blue.
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light.copyWith(statusBarColor: Colors.transparent),
      child: _blue(),
    );
  }

  Widget _blue() {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: logoGradient,
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(36)),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 20, 24, 64),
          child: Column(
            children: [
              // The university's logo is drawn for white, so it gets a white card.
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: [
                    BoxShadow(color: Colors.black.withValues(alpha: 0.12), blurRadius: 14, offset: const Offset(0, 4)),
                  ],
                ),
                child: Image.asset('assets/images/diu-logo.png', height: 36),
              ),
              const SizedBox(height: 30),
              Image.asset('assets/images/logo-mark.png', width: 76, height: 76),
              const SizedBox(height: 12),
              const Text(
                'ClassTrack',
                style: TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.w800, letterSpacing: -0.8),
              ),
              const SizedBox(height: 4),
              Text(
                'Department of CSE',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.82),
                  fontSize: 15.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Students' way in: no account, just their section.
class _StudentDoor extends StatelessWidget {
  const _StudentDoor({required this.onTap});
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    return DecoratedBox(
      // A soft lift off the page; a Material elevation draws a hard ring on light.
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        boxShadow: p.isDark
            ? null
            : [
                BoxShadow(
                  color: const Color(0xFF0B1F4D).withValues(alpha: 0.14),
                  blurRadius: 28,
                  offset: const Offset(0, 12),
                ),
              ],
      ),
      child: Material(
        color: p.surface,
        borderRadius: BorderRadius.circular(22),
        child: InkWell(
          borderRadius: BorderRadius.circular(22),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.fromLTRB(16, 16, 14, 16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: p.isDark ? p.line : Colors.transparent, width: 1.2),
            ),
            child: Row(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(color: p.brandSoft, borderRadius: BorderRadius.circular(16)),
                  child: Icon(Icons.school_rounded, color: p.brand, size: 28),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        "I'm a student",
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.2),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Your routine, makeups and alerts. No sign-in.',
                        style: TextStyle(fontSize: 14, color: p.inkSoft, height: 1.3),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(color: p.brandSolid, shape: BoxShape.circle),
                  child: const Icon(Icons.arrow_forward_rounded, color: Colors.white, size: 21),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
