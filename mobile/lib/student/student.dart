import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../push.dart';
import '../util/time.dart';

/// A student on this phone. Students have no account: they pick the groups
/// they sit in -- a section, its lab group, any retake groups, as tokens like
/// `63_A1` or `CSE447:RE_A` -- and the phone follows those groups' push topics.
/// Everything is kept on the phone and survives restarts.
class Student extends ChangeNotifier {
  Student(this.api, this.push);

  final Api api;
  final Push push;
  final _store = const FlutterSecureStorage();

  static const _groupsKey = 'student.groups';
  static const _alarmKey = 'student.alarm';
  static const _topicsKey = 'student.topics';
  static const _seenKey = 'student.seen';

  List<String> groups = [];

  /// Class Alarm: a push before each class. Change Alerts are always on.
  bool alarm = true;

  /// The newest notice read, so Updates can mark the rest new.
  int seen = 0;
  Set<String> _followed = {};

  bool get active => groups.isNotEmpty;

  Future<void> load() async {
    try {
      groups = ((jsonDecode(await _store.read(key: _groupsKey) ?? '[]') as List?) ?? const []).cast<String>();
      alarm = (await _store.read(key: _alarmKey)) != 'off';
      _followed = {...((jsonDecode(await _store.read(key: _topicsKey) ?? '[]') as List?) ?? const []).cast<String>()};
      seen = int.tryParse(await _store.read(key: _seenKey) ?? '') ?? 0;
    } catch (_) {
      // A keystore that cannot be read is a phone with no student on it.
      groups = [];
    }
  }

  Future<void> setGroups(List<String> picked) async {
    groups = picked;
    notifyListeners();
    await _write(_groupsKey, jsonEncode(groups));
    unawaited(sync());
  }

  Future<void> setAlarm(bool on) async {
    alarm = on;
    notifyListeners();
    await _write(_alarmKey, on ? 'on' : 'off');
    await sync();
  }

  Future<void> markSeen(int id) async {
    if (id <= seen) return;
    seen = id;
    notifyListeners();
    await _write(_seenKey, '$id');
  }

  /// Leaves student mode: the phone stops following every topic.
  Future<void> leave() async {
    groups = [];
    notifyListeners();
    await _store.delete(key: _groupsKey);
    await sync();
  }

  /// Follows the topics of the groups picked, and leaves the rest. On each
  /// launch too, since a new Firebase token starts following nothing.
  Future<void> sync() async {
    var wanted = <String>{};
    if (active) {
      await push.askPermission();
      try {
        final topics = await api.studentTopics(groups);
        wanted = {...topics.alerts, if (alarm) ...topics.reminders};
      } on ApiError {
        // Offline: keep what is followed, and try on the next launch.
        return;
      }
    }
    _followed = await push.follow(wanted: wanted, followed: _followed);
    await _write(_topicsKey, jsonEncode(_followed.toList()));
  }

  Future<void> _write(String key, String value) async {
    try {
      await _store.write(key: key, value: value);
    } catch (_) {
      // Unsaved, it still holds until the app closes.
    }
  }
}

class StudentScope extends InheritedNotifier<Student> {
  const StudentScope({super.key, required Student student, required super.child}) : super(notifier: student);

  static Student of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<StudentScope>()!.notifier!;

  /// Without listening: for callbacks.
  static Student read(BuildContext context) => context.getInheritedWidgetOfExactType<StudentScope>()!.notifier!;
}

/// What the student's tabs show, loaded together: the classes from today for
/// four weeks, and what was written to their groups.
class StudentFeed extends ChangeNotifier {
  StudentFeed(this.api, this.groups);

  final Api api;
  final List<String> groups;

  static const horizonDays = 27;

  List<StudentClass> upcoming = [];
  List<StudentNotice> notices = [];
  bool loading = true;
  String? error;
  Timer? _timer;
  bool _disposed = false;

  Future<void> load() async {
    final from = todayIso();
    final to = isoDate(parseDay(from).add(const Duration(days: horizonDays)));
    try {
      final results = await Future.wait<Object>([api.studentClasses(groups, from, to), api.studentNotices(groups)]);
      upcoming = results[0] as List<StudentClass>;
      notices = results[1] as List<StudentNotice>;
      error = null;
    } on ApiError catch (e) {
      error = e.message;
    } finally {
      loading = false;
      if (!_disposed) notifyListeners();
    }
  }

  void startPolling() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(minutes: 2), (_) => load());
  }

  void stopPolling() => _timer?.cancel();

  /// The class on now, or the next one still to come; a moved or cancelled one never.
  (StudentClass, bool)? get nowOrNext {
    final today = todayIso();
    final now = dhakaMinutesNow();
    final on = upcoming.where((c) => c.on);
    final current = on.where((c) => c.date == today && c.start <= now && now < c.end).firstOrNull;
    if (current != null) return (current, true);
    final next = on.where((c) => c.date.compareTo(today) > 0 || (c.date == today && c.start > now)).firstOrNull;
    return next == null ? null : (next, false);
  }

  /// Makeups, extra classes and cancellations still to come.
  List<StudentClass> get radar {
    final today = todayIso();
    final now = dhakaMinutesNow();
    return upcoming.where((c) => (!c.on || c.kind != 'CLASS') && (c.date.compareTo(today) > 0 || c.end > now)).toList();
  }

  @override
  void dispose() {
    _disposed = true;
    _timer?.cancel();
    super.dispose();
  }
}

/// How a group reads to a person: "Section 63_A", "Lab group 63_A1", "CSE447 retake RE_A".
String groupLabel(String token) {
  final parts = token.split(':');
  if (parts.length == 2) return '${parts[0]} retake ${parts[1]}';
  return RegExp(r'_[A-Z]\d+$').hasMatch(token) ? 'Lab group $token' : 'Section $token';
}
