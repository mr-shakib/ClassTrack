import 'package:flutter/material.dart';

import '../api/client.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets/common.dart';

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

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final notice = SessionScope.of(context).notice;
    final dark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(
                      child: Container(
                        width: 76,
                        height: 76,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(22),
                          gradient: LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [p.brandSolid, Color.lerp(p.brandSolid, p.infoSolid, 0.6)!],
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: p.brandSolid.withValues(alpha: 0.3),
                              blurRadius: 18,
                              offset: const Offset(0, 8),
                            ),
                          ],
                        ),
                        child: const Icon(Icons.event_available_rounded, color: Colors.white, size: 40),
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      'ClassTrack',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.8),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Class monitoring & makeup management',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 15, color: p.inkSoft),
                    ),
                    const SizedBox(height: 28),
                    if (notice != null) ...[
                      Notice(notice, tone: Tone.info, icon: Icons.info_outline_rounded),
                      const SizedBox(height: 14),
                    ],
                    Panel(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Sign in',
                            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: p.ink),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Teachers use their initial, e.g. SRH. Staff may use their employee ID.',
                            style: TextStyle(fontSize: 14, color: p.inkSoft, height: 1.4),
                          ),
                          const SizedBox(height: 18),
                          TextField(
                            controller: _username,
                            autofillHints: const [AutofillHints.username],
                            autocorrect: false,
                            enableSuggestions: false,
                            textInputAction: TextInputAction.next,
                            onSubmitted: (_) => _passwordFocus.requestFocus(),
                            decoration: const InputDecoration(
                              labelText: 'Email, initial or employee ID',
                              prefixIcon: Icon(Icons.person_outline_rounded),
                            ),
                          ),
                          const SizedBox(height: 14),
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
                            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
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
                    const SizedBox(height: 28),
                    Center(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        decoration: BoxDecoration(
                          color: dark ? Colors.white : Colors.transparent,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Image.asset('assets/images/diu-logo.png', height: 40),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Department of CSE',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 13, color: p.inkFaint),
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
