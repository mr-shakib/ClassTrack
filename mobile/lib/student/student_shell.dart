import 'dart:async';

import 'package:flutter/material.dart';

import '../offline/offline_bar.dart';
import '../push.dart';
import '../session.dart';
import '../theme.dart';
import 'more_tab.dart';
import 'routine_tab.dart';
import 'student.dart';
import 'tabs.dart';

enum _Tab { routine, radar, updates, rooms, more }

/// The app for a student, who needs no account: My Routine, Makeup Radar,
/// Updates, the Free Room Finder, and More.
class StudentShell extends StatefulWidget {
  const StudentShell({super.key});

  @override
  State<StudentShell> createState() => _StudentShellState();
}

class _StudentShellState extends State<StudentShell> with WidgetsBindingObserver {
  late final StudentFeed _feed;
  _Tab _tab = _Tab.routine;
  String? _focusDate;
  final _pushes = <StreamSubscription<PushMessage>>[];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final student = StudentScope.read(context);
    _feed = StudentFeed(context.api, student.groups)
      ..addListener(_onFeed)
      ..load()
      ..startPolling();
    final push = SessionScope.read(context).push;
    _pushes
      ..add(push.opened.listen(_onPushOpened))
      ..add(push.received.listen(_onPushReceived));
    _alarms = student.clock.opened.listen(_onAlarmOpened);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final pending = push.takePending();
      if (pending != null) _onPushOpened(pending);
      final rang = student.clock.takeLaunched();
      if (rang != null) _onAlarmOpened(rang);
    });
  }

  StreamSubscription<String?>? _alarms;

  /// The routine loaded, fresh or saved: Class Alarm is set for it on the phone.
  void _onFeed() {
    if (!_feed.loading) StudentScope.read(context).ring(_feed.upcoming);
  }

  /// A Class Alarm tapped: the day of its class.
  void _onAlarmOpened(String? date) {
    if (!mounted) return;
    Navigator.of(context).popUntil((route) => route.isFirst);
    setState(() {
      _tab = _Tab.routine;
      _focusDate = date;
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    for (final s in _pushes) {
      s.cancel();
    }
    _alarms?.cancel();
    _feed
      ..removeListener(_onFeed)
      ..dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      // Back from the phone's settings, perhaps with alarms now allowed.
      StudentScope.read(context).sync();
      _feed
        ..load()
        ..startPolling();
    } else if (state == AppLifecycleState.paused) {
      _feed.stopPolling();
    }
  }

  /// A push tapped in the tray: a reminder opens the day's classes, anything else Updates.
  void _onPushOpened(PushMessage m) {
    if (!mounted) return;
    _feed.load();
    Navigator.of(context).popUntil((route) => route.isFirst);
    final date = Uri.tryParse(m.link ?? '')?.queryParameters['date'];
    setState(() {
      if (m.isReminder) {
        _tab = _Tab.routine;
        _focusDate = date;
      } else {
        _tab = _Tab.updates;
      }
    });
  }

  void _onPushReceived(PushMessage m) {
    if (!mounted) return;
    _feed.load();
    final title = m.title;
    if (title == null) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: title,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                if (m.body != null) TextSpan(text: '\n${m.body}'),
              ],
            ),
          ),
          duration: const Duration(seconds: 6),
          persist: false,
          action: SnackBarAction(label: 'Open', onPressed: () => _onPushOpened(m)),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final student = StudentScope.of(context);
    final tabs = _Tab.values;
    final index = tabs.indexOf(_tab);

    Widget page(_Tab t) => switch (t) {
      _Tab.routine => StudentRoutineTab(feed: _feed, focusDate: _focusDate),
      _Tab.radar => StudentRadarTab(feed: _feed),
      _Tab.updates => StudentUpdatesTab(feed: _feed, active: _tab == _Tab.updates),
      _Tab.rooms => StudentRoomsTab(active: _tab == _Tab.rooms),
      _Tab.more => const StudentMoreTab(),
    };

    return Scaffold(
      body: IndexedStack(index: index, children: [for (final t in tabs) page(t)]),
      bottomNavigationBar: ListenableBuilder(
        listenable: _feed,
        builder: (context, _) {
          final unread = _feed.notices.where((n) => n.id > student.seen).length;
          final radar = _feed.radar.length;
          Widget badged(IconData icon, int count, Color color) => Badge(
            isLabelVisible: count > 0,
            label: Text(count > 9 ? '9+' : '$count'),
            backgroundColor: color,
            child: Icon(icon),
          );
          final bar = DecoratedBox(
            decoration: BoxDecoration(
              border: Border(top: BorderSide(color: p.line)),
            ),
            child: NavigationBar(
              selectedIndex: index,
              onDestinationSelected: (i) => setState(() => _tab = tabs[i]),
              destinations: [
                const NavigationDestination(
                  icon: Icon(Icons.calendar_view_week_outlined),
                  selectedIcon: Icon(Icons.calendar_view_week_rounded),
                  label: 'Routine',
                ),
                NavigationDestination(
                  icon: badged(Icons.radar_outlined, radar, p.infoSolid),
                  selectedIcon: badged(Icons.radar_rounded, radar, p.infoSolid),
                  label: 'Makeups',
                ),
                NavigationDestination(
                  icon: badged(Icons.notifications_outlined, unread, p.badSolid),
                  selectedIcon: badged(Icons.notifications_rounded, unread, p.badSolid),
                  label: 'Updates',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.meeting_room_outlined),
                  selectedIcon: Icon(Icons.meeting_room_rounded),
                  label: 'Rooms',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.more_horiz_rounded),
                  selectedIcon: Icon(Icons.more_horiz_rounded),
                  label: 'More',
                ),
              ],
            ),
          );
          return Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              OfflineBar(api: context.api),
              bar,
            ],
          );
        },
      ),
    );
  }
}
