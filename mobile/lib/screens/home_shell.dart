import 'dart:async';

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../session.dart';
import '../staff/checking_tab.dart';
import '../teacher/reschedule_screen.dart';
import '../teacher/teacher_tab.dart';
import '../theme.dart';
import '../widgets/common.dart';
import 'alerts_tab.dart';
import 'profile_tab.dart';

enum _Tab { teacher, checking, alerts, profile }

/// The signed-in app: a teacher's classes and/or the checking screen, then
/// alerts and the profile. A teacher who also checks gets both.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {
  int _index = 0;
  int _unread = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _pollUnread();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _pollUnread());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _pollUnread();
      SessionScope.read(context).refreshUser();
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

  List<_Tab> _tabsFor(bool teacher, bool checks, bool staffFirst) => [
        if (staffFirst && checks) _Tab.checking,
        if (teacher) _Tab.teacher,
        if (!staffFirst && checks) _Tab.checking,
        _Tab.alerts,
        _Tab.profile,
      ];

  /// Opens what a notification is about. Links are the web app's paths.
  void _openLink(List<_Tab> tabs, String link) {
    final uri = Uri.parse(link);
    final user = SessionScope.read(context).user!;
    if (uri.path == '/teacher/makeup' && user.mayReschedule) {
      final id = int.tryParse(uri.queryParameters['instance'] ?? '');
      if (id != null) {
        Navigator.of(context).push(MaterialPageRoute(builder: (_) => RescheduleScreen(instanceId: id)));
        return;
      }
    }
    final tab = uri.path.startsWith('/teacher')
        ? _Tab.teacher
        : uri.path.startsWith('/staff')
            ? _Tab.checking
            : null;
    if (tab != null && tabs.contains(tab)) {
      setState(() => _index = tabs.indexOf(tab));
    } else {
      // An admin screen: only the website has it.
      openLink(context, '$siteUrl$link');
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final user = SessionScope.of(context).user!;
    final tabs = _tabsFor(user.isTeacher, user.mayCheck, user.isStaff || !user.isTeacher);

    if (!tabs.contains(_Tab.teacher) && !tabs.contains(_Tab.checking)) {
      return const _NoWorkHere();
    }
    final index = _index.clamp(0, tabs.length - 1);

    Widget page(_Tab t, bool active) => switch (t) {
          _Tab.teacher => TeacherTab(active: active),
          _Tab.checking => CheckingTab(active: active),
          _Tab.alerts => AlertsTab(
              active: active,
              onOpen: (link) => _openLink(tabs, link),
              onUnreadChanged: (n) => setState(() => _unread = n),
            ),
          _Tab.profile => const ProfileTab(),
        };

    NavigationDestination dest(_Tab t) => switch (t) {
          _Tab.teacher => const NavigationDestination(
              icon: Icon(Icons.school_outlined),
              selectedIcon: Icon(Icons.school_rounded),
              label: 'My classes',
            ),
          _Tab.checking => const NavigationDestination(
              icon: Icon(Icons.fact_check_outlined),
              selectedIcon: Icon(Icons.fact_check_rounded),
              label: 'Checking',
            ),
          _Tab.alerts => NavigationDestination(
              icon: Badge(
                isLabelVisible: _unread > 0,
                label: Text(_unread > 9 ? '9+' : '$_unread'),
                backgroundColor: p.badSolid,
                child: const Icon(Icons.notifications_outlined),
              ),
              selectedIcon: Badge(
                isLabelVisible: _unread > 0,
                label: Text(_unread > 9 ? '9+' : '$_unread'),
                backgroundColor: p.badSolid,
                child: const Icon(Icons.notifications_rounded),
              ),
              label: 'Alerts',
            ),
          _Tab.profile => const NavigationDestination(
              icon: Icon(Icons.person_outline_rounded),
              selectedIcon: Icon(Icons.person_rounded),
              label: 'Profile',
            ),
        };

    return Scaffold(
      body: IndexedStack(
        index: index,
        children: [for (var i = 0; i < tabs.length; i++) page(tabs[i], i == index)],
      ),
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(border: Border(top: BorderSide(color: p.line))),
        child: NavigationBar(
          selectedIndex: index,
          onDestinationSelected: (i) => setState(() => _index = i),
          destinations: [for (final t in tabs) dest(t)],
        ),
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
                body: 'This app is for teachers and the staff who check classes. '
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
