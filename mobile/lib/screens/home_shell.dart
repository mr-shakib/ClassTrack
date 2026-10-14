import 'dart:async';

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../push.dart';
import '../session.dart';
import '../staff/checking_tab.dart';
import '../teacher/home_tab.dart';
import '../teacher/reschedule_screen.dart';
import '../teacher/reschedule_tab.dart';
import '../teacher/teacher_data.dart';
import '../theme.dart';
import '../widgets/common.dart';
import 'alerts_tab.dart';
import 'profile_tab.dart';

enum _Tab { home, reschedule, checking, alerts, profile }

/// The signed-in app. A teacher gets Home (today and the week ahead) and
/// Reschedule (missed classes and makeups); staff get Checking; a teacher who
/// also checks gets all three. Everyone gets Alerts and Profile.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {
  int _index = 0;
  int _unread = 0;
  Timer? _timer;
  TeacherData? _teacher;
  final _pushes = <StreamSubscription<PushMessage>>[];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final session = SessionScope.read(context);
    final user = session.user!;
    final initial = user.teacherInitial;
    if (user.isTeacher && initial != null) {
      _teacher = TeacherData(context.api, initial)
        ..load()
        ..startPolling();
    }
    _pollUnread();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _pollUnread());

    final push = session.push;
    _pushes
      ..add(push.opened.listen(_onPushOpened))
      ..add(push.received.listen(_onPushReceived));
    // A tap that launched the app, perhaps onto the sign-in screen first.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final pending = push.takePending();
      if (pending != null) _onPushOpened(pending);
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    for (final s in _pushes) {
      s.cancel();
    }
    _teacher?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _pollUnread();
      SessionScope.read(context).refreshUser();
      _teacher
        ?..load()
        ..startPolling();
    } else if (state == AppLifecycleState.paused) {
      _teacher?.stopPolling();
    }
  }

  Future<void> _pollUnread() async {
    try {
      final unread = await context.api.notifications(unread: true);
      if (mounted) setState(() => _unread = unread.length);
    } on ApiError {
      // Offline, or signed out: the badge is not worth an error.
    }
  }

  /// Something changed on the server: the badge and the teacher's classes catch up.
  void _refresh() {
    _pollUnread();
    _teacher?.load();
  }

  /// A push tapped in the tray: open what it is about, over whatever was open.
  void _onPushOpened(PushMessage m) {
    if (!mounted) return;
    _refresh();
    Navigator.of(context).popUntil((route) => route.isFirst);
    final tabs = _tabs;
    final link = m.link;
    if (m.isReminder) {
      _go(tabs, _Tab.home);
    } else if (link != null) {
      _openLink(tabs, link);
    } else {
      _go(tabs, _Tab.alerts);
    }
  }

  /// The phone shows nothing for a push while the app is open, so the app does.
  void _onPushReceived(PushMessage m) {
    if (!mounted) return;
    _refresh();
    final title = m.title;
    if (title == null) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text.rich(
            TextSpan(
              children: [
                TextSpan(text: title, style: const TextStyle(fontWeight: FontWeight.w700)),
                if (m.body != null) TextSpan(text: '\n${m.body}'),
              ],
            ),
          ),
          duration: const Duration(seconds: 6),
          // A bar with an action stays until dismissed unless told otherwise.
          persist: false,
          action: SnackBarAction(label: 'Open', onPressed: () => _onPushOpened(m)),
        ),
      );
  }

  List<_Tab> get _tabs {
    final user = SessionScope.read(context).user!;
    final teacher = _teacher != null;
    return _tabsFor(teacher, user.mayCheck, user.isStaff || !teacher);
  }

  List<_Tab> _tabsFor(bool teacher, bool checks, bool staffFirst) => [
    if (staffFirst && checks) _Tab.checking,
    if (teacher) ...[_Tab.home, _Tab.reschedule],
    if (!staffFirst && checks) _Tab.checking,
    _Tab.alerts,
    _Tab.profile,
  ];

  void _go(List<_Tab> tabs, _Tab tab) {
    if (tabs.contains(tab)) setState(() => _index = tabs.indexOf(tab));
  }

  /// Opens what a notification is about. Links are the web app's paths.
  void _openLink(List<_Tab> tabs, String link) {
    final uri = Uri.parse(link);
    final user = SessionScope.read(context).user!;
    if (uri.path == '/teacher/makeup' && user.mayReschedule) {
      final id = int.tryParse(uri.queryParameters['instance'] ?? '');
      if (id != null) {
        Navigator.of(context)
            .push<bool>(MaterialPageRoute(builder: (_) => RescheduleScreen(instanceId: id)))
            .then((booked) => booked == true ? _teacher?.load() : null);
        return;
      }
    }
    // A missed class or a makeup: the teacher deals with it on Reschedule.
    final tab = uri.path.startsWith('/teacher')
        ? _Tab.reschedule
        : uri.path.startsWith('/staff')
        ? _Tab.checking
        : null;
    if (tab != null && tabs.contains(tab)) {
      _go(tabs, tab);
    } else {
      // An admin screen: only the website has it.
      openLink(context, '$siteUrl$link');
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = SessionScope.of(context).user!;
    final teacher = _teacher;
    final tabs = _tabsFor(teacher != null, user.mayCheck, user.isStaff || teacher == null);

    if (!tabs.contains(_Tab.home) && !tabs.contains(_Tab.checking)) {
      return const _NoWorkHere();
    }
    final index = _index.clamp(0, tabs.length - 1);

    Widget page(_Tab t, bool active) => switch (t) {
      _Tab.home => HomeTab(data: teacher!, onOpenReschedule: () => _go(tabs, _Tab.reschedule)),
      _Tab.reschedule => RescheduleTab(data: teacher!),
      _Tab.checking => CheckingTab(active: active),
      _Tab.alerts => AlertsTab(
        active: active,
        onOpen: (link) => _openLink(tabs, link),
        onUnreadChanged: (n) => setState(() => _unread = n),
      ),
      _Tab.profile => ProfileTab(teacher: teacher),
    };

    return Scaffold(
      body: IndexedStack(index: index, children: [for (var i = 0; i < tabs.length; i++) page(tabs[i], i == index)]),
      bottomNavigationBar: teacher == null
          ? _NavBar(tabs: tabs, index: index, unread: _unread, actions: 0, onTap: (i) => setState(() => _index = i))
          : ListenableBuilder(
              listenable: teacher,
              builder: (context, _) => _NavBar(
                tabs: tabs,
                index: index,
                unread: _unread,
                actions: teacher.actionCount,
                onTap: (i) => setState(() => _index = i),
              ),
            ),
    );
  }
}

class _NavBar extends StatelessWidget {
  const _NavBar({
    required this.tabs,
    required this.index,
    required this.unread,
    required this.actions,
    required this.onTap,
  });

  final List<_Tab> tabs;
  final int index, unread, actions;
  final ValueChanged<int> onTap;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;

    Widget badged(IconData icon, int count) => Badge(
      isLabelVisible: count > 0,
      label: Text(count > 9 ? '9+' : '$count'),
      backgroundColor: p.badSolid,
      child: Icon(icon),
    );

    NavigationDestination dest(_Tab t) => switch (t) {
      _Tab.home => const NavigationDestination(
        icon: Icon(Icons.home_outlined),
        selectedIcon: Icon(Icons.home_rounded),
        label: 'Home',
      ),
      _Tab.reschedule => NavigationDestination(
        icon: badged(Icons.event_repeat_outlined, actions),
        selectedIcon: badged(Icons.event_repeat_rounded, actions),
        label: 'Reschedule',
      ),
      _Tab.checking => const NavigationDestination(
        icon: Icon(Icons.fact_check_outlined),
        selectedIcon: Icon(Icons.fact_check_rounded),
        label: 'Checking',
      ),
      _Tab.alerts => NavigationDestination(
        icon: badged(Icons.notifications_outlined, unread),
        selectedIcon: badged(Icons.notifications_rounded, unread),
        label: 'Alerts',
      ),
      _Tab.profile => const NavigationDestination(
        icon: Icon(Icons.person_outline_rounded),
        selectedIcon: Icon(Icons.person_rounded),
        label: 'Profile',
      ),
    };

    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: p.line)),
      ),
      child: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: onTap,
        destinations: [for (final t in tabs) dest(t)],
      ),
    );
  }
}

/// Signed in, but with nothing this app does: an admin or office account.
class _NoWorkHere extends StatelessWidget {
  const _NoWorkHere();

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final user = SessionScope.of(context).user!;
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const Spacer(),
              EmptyState(
                icon: Icons.desktop_windows_outlined,
                title: 'Use ClassTrack on the web',
                body:
                    'This app is for teachers and the staff who check classes. '
                    '${user.fullName}, your work (${user.roleNames}) is on the website.',
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: () => openLink(context, siteUrl),
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(54)),
                icon: const Icon(Icons.open_in_new_rounded),
                label: const Text('Open the website'),
              ),
              const SizedBox(height: 10),
              TextButton(
                onPressed: () => SessionScope.read(context).signOut(),
                style: TextButton.styleFrom(foregroundColor: p.inkSoft),
                child: const Text('Sign out'),
              ),
              const Spacer(),
            ],
          ),
        ),
      ),
    );
  }
}
