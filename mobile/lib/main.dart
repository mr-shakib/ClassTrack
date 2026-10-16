import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api/client.dart';
import 'push.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'session.dart';
import 'settings.dart';
import 'student/class_alarm.dart';
import 'student/student.dart';
import 'student/student_shell.dart';
import 'theme.dart';
import 'widgets/common.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  final settings = AppSettings();
  await settings.load();
  final push = Push();
  await push.start();
  final session = Session(Api(), push)..restore();
  final clock = ClassAlarm();
  await clock.start();
  final student = Student(session.api, push, clock);
  await student.load();
  // A new Firebase token follows nothing: follow the student's topics again.
  if (student.active) unawaited(student.sync());
  runApp(ClassTrackApp(session: session, settings: settings, student: student));
}

final _light = buildTheme(Brightness.light);
final _dark = buildTheme(Brightness.dark);

class ClassTrackApp extends StatefulWidget {
  const ClassTrackApp({super.key, required this.session, required this.settings, required this.student});
  final Session session;
  final AppSettings settings;
  final Student student;

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
    return SettingsScope(
      settings: widget.settings,
      child: SessionScope(
        session: widget.session,
        child: StudentScope(
          student: widget.student,
          child: ListenableBuilder(
            listenable: widget.settings,
            builder: (context, _) => MaterialApp(
              title: 'ClassTrack',
              debugShowCheckedModeBanner: false,
              navigatorKey: _navigator,
              theme: _light,
              darkTheme: _dark,
              themeMode: widget.settings.themeMode,
              // A short cross-fade when the theme changes, rather than a snap.
              themeAnimationDuration: const Duration(milliseconds: 220),
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
          ),
        ),
      ),
    );
  }
}

/// The splash while the keystore is read, then sign-in, the app, or -- with no
/// one signed in and a section picked -- the student's app.
class _Gate extends StatelessWidget {
  const _Gate();

  @override
  Widget build(BuildContext context) {
    final session = SessionScope.of(context);
    if (session.restoring) {
      return Scaffold(
        body: Center(
          child: Container(
            width: 76,
            height: 76,
            decoration: BoxDecoration(gradient: logoGradient, borderRadius: BorderRadius.circular(22)),
            alignment: Alignment.center,
            child: Image.asset('assets/images/logo-mark.png', width: 52, height: 52),
          ),
        ),
      );
    }
    final user = session.user;
    final student = StudentScope.of(context);
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 250),
      child: user != null
          ? HomeShell(key: ValueKey(user.id))
          : student.active
          // A new section starts the student's tabs afresh.
          ? StudentShell(key: ValueKey(student.groups.join(',')))
          : const LoginScreen(),
    );
  }
}
