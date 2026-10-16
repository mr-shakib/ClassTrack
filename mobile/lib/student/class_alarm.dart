import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/painting.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../api/models.dart';

/// Class Alarm on the phone: a reminder before each of a student's classes,
/// set on the phone itself so it rings with no signal.
///
/// Android only rings an alarm at its minute when the person lets the app set
/// exact alarms (Alarms & reminders, in the app's settings); without that it
/// could ring hours late. So it is used only when allowed, and the server's
/// push reminds otherwise (`Student.sync`).
class ClassAlarm {
  final _plugin = FlutterLocalNotificationsPlugin();
  final _opened = StreamController<String?>.broadcast();
  bool _ready = false;
  String? _launched;
  late tz.Location _dhaka;

  /// How far ahead alarms are set: they are set again each time the routine loads.
  static const _days = 7;

  /// A tapped reminder, with the day of its class.
  Stream<String?> get opened => _opened.stream;

  /// The reminder that opened the app, given out once.
  String? takeLaunched() {
    final d = _launched;
    _launched = null;
    return d;
  }

  AndroidFlutterLocalNotificationsPlugin? get _android =>
      _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();

  Future<void> start() async {
    if (!Platform.isAndroid) return;
    try {
      tzdata.initializeTimeZones();
      _dhaka = tz.getLocation('Asia/Dhaka');
      await _plugin.initialize(
        settings: const InitializationSettings(android: AndroidInitializationSettings('@drawable/ic_stat_notify')),
        onDidReceiveNotificationResponse: (r) => _opened.add(r.payload),
      );
      final launch = await _plugin.getNotificationAppLaunchDetails();
      if (launch?.didNotificationLaunchApp ?? false) _launched = launch!.notificationResponse?.payload;
      _ready = true;
    } catch (e) {
      debugPrint('Class Alarm off: $e');
    }
  }

  /// Whether the phone lets the app ring at the minute.
  Future<bool> exactAllowed() async {
    if (!_ready) return false;
    try {
      return await _android?.canScheduleExactNotifications() ?? false;
    } catch (_) {
      return false;
    }
  }

  /// Opens the phone's setting for it. Whether it is allowed afterwards.
  Future<bool> askExact() async {
    if (!_ready) return false;
    try {
      await _android?.requestExactAlarmsPermission();
    } catch (_) {
      // An older Android, where exact alarms need no permission.
    }
    return exactAllowed();
  }

  /// Sets an alarm `lead` minutes before each class still on, for the coming
  /// week, in place of those set before: a moved or cancelled class rings no more.
  Future<void> schedule(List<StudentClass> classes, int lead) async {
    if (!_ready || lead <= 0) return;
    await clear();
    final now = tz.TZDateTime.now(_dhaka);
    final until = now.add(const Duration(days: _days));
    for (final c in classes) {
      if (!c.on) continue;
      final day = DateTime.parse(c.date);
      final start = tz.TZDateTime(_dhaka, day.year, day.month, day.day, c.start ~/ 60, c.start % 60);
      final at = start.subtract(Duration(minutes: lead));
      if (!at.isAfter(now) || at.isAfter(until)) continue;
      final kind = c.isExtra
          ? 'Extra class'
          : c.isMakeup
          ? 'Makeup class'
          : null;
      final where = c.online ? 'Online · open ClassTrack to join' : 'Room ${c.room}';
      try {
        await _plugin.zonedSchedule(
          id: c.id,
          scheduledDate: at,
          title: '${c.courseCode} starts in $lead minute${lead == 1 ? '' : 's'}',
          body: [?kind, where, _times(c)].join(' · '),
          payload: c.date,
          androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
          notificationDetails: const NotificationDetails(
            android: AndroidNotificationDetails(
              // The channel the server's reminders use too (MainActivity.kt).
              'classes',
              'Class reminders',
              channelDescription: 'Shortly before each of your classes',
              importance: Importance.high,
              priority: Priority.high,
              icon: '@drawable/ic_stat_notify',
              color: Color(0xFF1D4ED8),
            ),
          ),
        );
      } catch (e) {
        // Exact alarms withdrawn since: the server's push takes over at the next sync.
        debugPrint('Could not set the alarm for ${c.courseCode}: $e');
        return;
      }
    }
  }

  static String _times(StudentClass c) {
    String clock(int m) => '${(m ~/ 60).toString().padLeft(2, '0')}:${(m % 60).toString().padLeft(2, '0')}';
    return '${clock(c.start)}–${clock(c.end)}';
  }

  /// Takes every alarm off: Class Alarm turned off, or left to the server.
  Future<void> clear() async {
    if (!_ready) return;
    try {
      // Only those still to ring: never what is already in the tray.
      await _plugin.cancelAllPendingNotifications();
    } catch (_) {}
  }
}
