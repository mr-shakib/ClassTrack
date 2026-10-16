import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../util/time.dart';

/// A check made on this phone that is waiting to reach the server.
class PendingCheck {
  PendingCheck({
    required this.instanceId,
    required this.outcome,
    required this.observedAt,
    required this.date,
    required this.room,
    required this.label,
    required this.account,
    this.arrivalTime,
    this.remark,
    this.reason,
    this.failure,
  });

  PendingCheck.fromJson(Map<String, dynamic> j)
    : instanceId = j['instance_id'] as int,
      outcome = j['outcome'] as String,
      observedAt = j['observed_at'] as String,
      date = j['date'] as String,
      room = j['room'] as String,
      label = j['label'] as String? ?? '',
      account = j['account'] as String? ?? '',
      arrivalTime = j['arrival_time'] as String?,
      remark = j['remark'] as String?,
      reason = j['reason'] as String?,
      failure = j['failure'] as String?;

  final int instanceId;
  final String outcome;

  /// When it was made, on Dhaka's clock with its offset: the server keeps this
  /// time, not the time it arrives.
  final String observedAt;

  /// The class's day: reporting for it closes at the end of that day.
  final String date;
  final String room, label;

  /// Who made it: only their session may send it.
  final String account;
  final String? arrivalTime, remark, reason;

  /// Why the server refused it, once it has; then it is no longer sent.
  String? failure;

  Map<String, dynamic> toJson() => {
    'instance_id': instanceId,
    'outcome': outcome,
    'observed_at': observedAt,
    'date': date,
    'room': room,
    'label': label,
    'account': account,
    'arrival_time': arrivalTime,
    'remark': remark,
    'reason': reason,
    'failure': failure,
  };

  CheckRecord get record =>
      CheckRecord(outcome: outcome, arrivalTime: arrivalTime, remark: remark, checkedAt: CheckRecord.queued);
}

/// Checks made with no signal. Each is kept on the phone, in the order made,
/// and sent as soon as the server can be reached: on a timer while any wait, on
/// returning to the app, and the moment any request gets through.
///
/// Reporting for a class closes at the end of its day, so one still here near
/// midnight is a check about to be lost: the checking screen says so.
class Outbox extends ChangeNotifier {
  Outbox(this.api) {
    api.offline.addListener(_onSignal);
  }

  final Api api;
  final _items = <PendingCheck>[];
  Timer? _timer;
  bool _sending = false;
  File? _file;

  /// Waiting to be sent, oldest first.
  List<PendingCheck> get waiting => _items.where((c) => c.failure == null).toList();

  /// Refused by the server: shown until dismissed, so nobody thinks they were sent.
  List<PendingCheck> get failed => _items.where((c) => c.failure != null).toList();

  PendingCheck? waitingFor(int instanceId) =>
      _items.where((c) => c.instanceId == instanceId && c.failure == null).lastOrNull;

  Future<File> _store() async => _file ??= File('${(await getApplicationSupportDirectory()).path}/outbox.json');

  Future<void> load() async {
    try {
      final file = await _store();
      if (!file.existsSync()) return;
      final raw = jsonDecode(await file.readAsString()) as List;
      _items
        ..clear()
        ..addAll(raw.map((e) => PendingCheck.fromJson(e as Map<String, dynamic>)));
      notifyListeners();
      _schedule();
    } catch (e) {
      debugPrint('Could not read the outbox: $e');
    }
  }

  Future<void> _save() async {
    try {
      await (await _store()).writeAsString(jsonEncode([for (final c in _items) c.toJson()]));
    } catch (e) {
      debugPrint('Could not keep the outbox: $e');
    }
  }

  /// Sends a check now, or keeps it for later when there is no signal.
  /// Returns the server's answer, or null when it was kept. Any refusal other
  /// than no signal is thrown, as before.
  Future<CheckResponse?> send(PendingCheck check) async {
    try {
      final res = await _post(check);
      // A newer check for the same class supersedes one still waiting.
      final before = _items.length;
      _items.removeWhere((c) => c.instanceId == check.instanceId && c.failure == null);
      if (_items.length != before) {
        await _save();
        notifyListeners();
      }
      unawaited(flush());
      return res;
    } on ApiError catch (e) {
      if (!e.offline) rethrow;
      _items
        ..removeWhere((c) => c.instanceId == check.instanceId && c.failure == null)
        ..add(check);
      await _save();
      notifyListeners();
      _schedule();
      return null;
    }
  }

  Future<CheckResponse> _post(PendingCheck c) => api.submitCheck(
    c.instanceId,
    outcome: c.outcome,
    arrivalTime: c.arrivalTime,
    remark: c.remark,
    reason: c.reason,
    observedAt: c.observedAt,
  );

  /// Sends every waiting check, oldest first, until one finds no signal.
  Future<void> flush() async {
    if (_sending || waiting.isEmpty) return;
    _sending = true;
    var changed = false;
    try {
      for (final c in waiting) {
        try {
          await _post(c);
          _items.remove(c);
          changed = true;
        } on ApiError catch (e) {
          // No signal, or the session ended: keep it for the next try or sign-in.
          if (e.offline || e.status == 401) break;
          // Refused: the day closed before it got through, or the class changed.
          c.failure = e.message;
          changed = true;
        }
      }
    } finally {
      _sending = false;
      if (changed) {
        await _save();
        notifyListeners();
      }
      _schedule();
    }
  }

  void dismiss(PendingCheck c) {
    _items.remove(c);
    _save();
    notifyListeners();
  }

  /// At sign-in: checks another account made cannot be sent by this one.
  Future<void> adopt(String account) async {
    final before = _items.length;
    _items.removeWhere((c) => c.account != account);
    if (_items.length != before) {
      await _save();
      notifyListeners();
    }
    unawaited(flush());
  }

  /// Forgets everything: at sign-out, after the person agreed to.
  Future<void> clear() async {
    _items.clear();
    _timer?.cancel();
    await _save();
    notifyListeners();
  }

  void _schedule() {
    _timer?.cancel();
    if (waiting.isEmpty) return;
    _timer = Timer(const Duration(seconds: 20), flush);
  }

  /// A request got through: try the waiting ones now rather than on the timer.
  void _onSignal() {
    if (api.offline.value == null && waiting.isNotEmpty) flush();
  }

  /// Waiting checks whose day ends within two hours: about to be lost.
  bool get closingSoon {
    final today = todayIso();
    return waiting.any((c) => c.date == today) && dhakaNow().hour >= 22;
  }

  @override
  void dispose() {
    api.offline.removeListener(_onSignal);
    _timer?.cancel();
    super.dispose();
  }
}

/// Now on Dhaka's clock, with its offset, as the server reads a time.
String observedNow() {
  final d = dhakaNow();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${d.year}-${two(d.month)}-${two(d.day)}T${two(d.hour)}:${two(d.minute)}:${two(d.second)}+06:00';
}
