import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../util/time.dart';

/// A class the teacher is to hold: one from the routine, a makeup, or an
/// extra class. An approved online makeup comes back as a class too, in the
/// room "ONLINE" at its own time.
class UpcomingClass {
  UpcomingClass(ClassInstance i)
    : date = i.date,
      timeSlot = i.timeSlot,
      courseCode = i.courseCode,
      section = i.section,
      room = _online(i) ? null : i.room,
      isMakeup = i.isMakeup,
      isExtra = i.isExtra,
      online = _online(i),
      status = i.status,
      check = i.check,
      rescheduledFrom = i.rescheduledFrom,
      bounds = slotBounds(i.timeSlot);

  static bool _online(ClassInstance i) => i.room == 'ONLINE' || (i.status ?? '').startsWith('ONLINE');

  final String date, timeSlot, courseCode, section;

  /// Null for an online class.
  final String? room;
  final bool isMakeup, isExtra, online;
  final String? status;
  final CheckRecord? check;
  final SlotRef? rescheduledFrom;

  /// Minutes since midnight.
  final (int, int) bounds;
  int get start => bounds.$1;
  int get end => bounds.$2;

  String get times => '${clock(start)}–${clock(end)}';
}

/// One weekly class of the routine.
class RoutineEntry {
  RoutineEntry(this.day, this.timeSlot, this.courseCode, this.section, this.room);
  final String day, timeSlot, courseCode, section, room;
}

const weekdays = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

/// Everything the teacher's tabs show, loaded together and shared: Home reads
/// the coming classes, Reschedule the missed ones and makeups, Profile the
/// semester's figures and the routine.
class TeacherData extends ChangeNotifier {
  TeacherData(this.api, this.initial);

  final Api api;
  final String initial;

  /// How far ahead Home looks, and the routine is read from.
  static const horizonDays = 21;

  List<UpcomingClass> upcoming = [];
  List<ClassInstance> needsAction = [];
  List<Makeup> makeups = [];
  TeacherReport? report;
  bool loading = true;
  String? error;

  Timer? _timer;
  bool _disposed = false;
  int _request = 0;

  Future<void> load() async {
    final request = ++_request;
    final from = todayIso();
    final to = isoDate(parseDay(from).add(const Duration(days: horizonDays)));
    try {
      final results = await Future.wait<Object?>([
        api.instances(from: from, to: to, limit: 1000),
        api.instances(needsReschedule: true, limit: 50),
        api.makeups(),
        // The current semester so far. None yet, or not begun: no figures.
        api.teacherReport(initial).then<TeacherReport?>((r) => r).catchError((Object _) => null),
      ]);
      if (request != _request) return;
      final instances = (results[0] as List<ClassInstance>)
          // An older server ignores from/to: keep the window here too.
          .where((i) => i.date.compareTo(from) >= 0 && i.date.compareTo(to) <= 0 && i.status != 'CANCELLED');
      makeups = results[2] as List<Makeup>;
      upcoming = instances.map(UpcomingClass.new).toList()
        ..sort((a, b) {
          final d = a.date.compareTo(b.date);
          return d != 0 ? d : a.start.compareTo(b.start);
        });
      needsAction = results[1] as List<ClassInstance>;
      report = results[3] as TeacherReport?;
      error = null;
    } on ApiError catch (e) {
      if (request != _request) return;
      error = e.message;
    }
    loading = false;
    _notify();
  }

  // --- what the tabs ask ----------------------------------------------------------

  List<UpcomingClass> get today => upcoming.where((c) => c.date == todayIso()).toList();

  /// Soonest first, so the next class to hold is at the top.
  List<Makeup> get openMakeups => makeups.where((m) => m.isOpen).toList()..sort((a, b) => a.date.compareTo(b.date));
  List<Makeup> get pastMakeups => makeups.where((m) => !m.isOpen).toList();

  /// Held already, waiting for the teacher to say so.
  List<Makeup> get toMarkDone => openMakeups
      .where(
        (m) => m.status != 'PENDING' && m.endsAt != null && !parseServerTime(m.endsAt!).isAfter(DateTime.now().toUtc()),
      )
      .toList();

  List<Makeup> get awaitingApproval => makeups.where((m) => m.status == 'PENDING').toList();

  /// What needs the teacher on the Reschedule tab: its badge.
  int get actionCount => needsAction.length + toMarkDone.length;

  /// The weekly routine, read off the coming weeks; from the semester so far
  /// when nothing is coming, as in the exams.
  List<RoutineEntry> get routine {
    final seen = <String>{};
    final entries = <RoutineEntry>[];
    void add(String day, String slot, String course, String section, String room) {
      if (seen.add('$day|$slot|$course|$section')) entries.add(RoutineEntry(day, slot, course, section, room));
    }

    for (final c in upcoming.where((c) => !c.isMakeup && !c.isExtra)) {
      add(weekdays[(parseDay(c.date).weekday + 1) % 7], c.timeSlot, c.courseCode, c.section, c.room ?? '');
    }
    if (entries.isEmpty) {
      for (final c in report?.classes ?? const <ReportClass>[]) {
        if (!c.isMakeup && !c.isExtra) add(c.day, c.timeSlot, c.courseCode, c.section, c.room);
      }
    }
    entries.sort((a, b) {
      final d = weekdays.indexOf(a.day).compareTo(weekdays.indexOf(b.day));
      return d != 0 ? d : slotBounds(a.timeSlot).$1.compareTo(slotBounds(b.timeSlot).$1);
    });
    return entries;
  }

  void startPolling() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => load());
  }

  void stopPolling() {
    _timer?.cancel();
    _timer = null;
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    stopPolling();
    super.dispose();
  }
}
