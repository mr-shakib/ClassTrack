import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api/client.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'session.dart';
import 'theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  final session = Session(Api())..restore();
  runApp(ClassTrackApp(session: session));
}

class ClassTrackApp extends StatefulWidget {
  const ClassTrackApp({super.key, required this.session});
  final Session session;

  @override
  State<ClassTrackApp> createState() => _ClassTrackAppState();
}

class _ClassTrackAppState extends State<ClassTrackApp> {
  final _navigator = GlobalKey<NavigatorState>();
  int? _signedInAs;

  @override
  void initState() {
    super.initState();
    widget.session.addListener(_onSession);
  }

  @override
  void dispose() {
    widget.session.removeListener(_onSession);
    super.dispose();
  }

  /// Signing out, or a new person signing in, closes whatever was open on top.
  void _onSession() {
    final id = widget.session.user?.id;
    if (id != _signedInAs) {
      _signedInAs = id;
      _navigator.currentState?.popUntil((route) => route.isFirst);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SessionScope(
      session: widget.session,
      child: MaterialApp(
        title: 'ClassTrack',
        debugShowCheckedModeBanner: false,
        navigatorKey: _navigator,
        theme: buildTheme(Brightness.light),
        darkTheme: buildTheme(Brightness.dark),
        builder: (context, child) {
          final dark = Theme.of(context).brightness == Brightness.dark;
          return AnnotatedRegion<SystemUiOverlayStyle>(
            value: (dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark).copyWith(
              statusBarColor: Colors.transparent,
              systemNavigationBarColor: Colors.transparent,
            ),
            child: child!,
          );
        },
        home: const _Gate(),
      ),
    );
  }
}

/// The splash while the keystore is read, then sign-in or the app.
class _Gate extends StatelessWidget {
  const _Gate();

  @override
  Widget build(BuildContext context) {
    final session = SessionScope.of(context);
    if (session.restoring) {
      final p = context.palette;
      return Scaffold(
        body: Center(
          child: Container(
            width: 76,
            height: 76,
            decoration: BoxDecoration(color: p.brandSolid, borderRadius: BorderRadius.circular(22)),
            child: const Icon(Icons.event_available_rounded, color: Colors.white, size: 40),
          ),
        ),
      );
    }
    final user = session.user;
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 250),
      child: user == null ? const LoginScreen() : HomeShell(key: ValueKey(user.id)),
    );
  }
}
