import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../util/time.dart';
import 'outbox.dart';

/// A floor with its counts taken from the rooms, so a check saved on this
/// phone moves the count straight away.
class FloorTally {
  FloorTally(this.floor, this.total, this.checked);
  final FloorSummary floor;
  final int total, checked;
  int get left => total - checked;
}

/// One day and slot of the checking screen, shared by the floor list and each
/// floor's page, refreshed every 30 seconds while it is on screen so a second
/// staff member's checks show up.
///
/// With no signal it shows the list kept from the last time there was one --
/// every slot of today is fetched ahead for that -- and checks made then wait in
/// the [Outbox], shown on their rooms until they are sent.
class CheckingController extends ChangeNotifier {
  CheckingController(this.api, this.outbox) {
    outbox.addListener(_onOutbox);
  }

  final Api api;
  final Outbox outbox;

  /// When the list on screen was saved, if it is a kept one; null when fresh.
  DateTime? savedAt;
  DateTime? _prefetched;

  String date = todayIso();

  /// Null until the first load adopts the slot the backend says is current.
  String? slot;

  /// The slot running now, as the backend picks it for today.
  String? liveSlot;
  CheckingScreen? screen;
  bool loading = true;
  String? error;

  Timer? _timer;
  int _request = 0;
  bool _disposed = false;

  bool get isToday => date == todayIso();

  /// UPCOMING, ONGOING or CLOSED.
  String? get slotState => screen?.slotState;
  bool get locked => screen != null && screen!.slotState != 'ONGOING';
  bool get closed => screen?.slotState == 'CLOSED';

  Future<void> load({bool spinner = false}) async {
    final request = ++_request;
    if (spinner) {
      loading = true;
      _notify();
    }
    final asked = slot;
    try {
      final data = await api.checkingRooms(date: date, slot: asked);
      if (request != _request) return;
      savedAt = api.offline.value;
      if (savedAt != null) {
        // Kept from earlier: the slot running then may not be the one running now.
        final now = _slotNow();
        if (asked == null && date == todayIso() && now != data.timeSlot) {
          slot = liveSlot = now;
          return load();
        }
        data.slotState = _stateNow(data.date, data.timeSlot);
      }
      screen = data;
      if (asked == null && date == todayIso()) liveSlot = data.timeSlot;
      slot ??= data.timeSlot;
      error = null;
      _overlay();
      if (savedAt == null) unawaited(_prefetch());
    } on ApiError catch (e) {
      if (request != _request) return;
      error = e.message;
    }
    loading = false;
    _notify();
  }

  /// The slot on now, or the next one today; after the last, the last.
  static String _slotNow() {
    final now = dhakaMinutesNow();
    return slots.firstWhere((s) => slotBounds(s).$2 > now, orElse: () => slots.last);
  }

  /// What the backend would say of a slot now: reporting opens at its start
  /// and closes at the end of its day.
  static String _stateNow(String day, String slot) {
    final today = todayIso();
    if (day.compareTo(today) < 0) return 'CLOSED';
    if (day.compareTo(today) > 0) return 'UPCOMING';
    return dhakaMinutesNow() < slotBounds(slot).$1 ? 'UPCOMING' : 'ONGOING';
  }

  /// Every other slot of today, so they are on the phone if the signal goes.
  /// At most every ten minutes.
  Future<void> _prefetch() async {
    if (!isToday) return;
    final last = _prefetched;
    if (last != null && DateTime.now().difference(last) < const Duration(minutes: 10)) return;
    _prefetched = DateTime.now();
    for (final s in slots) {
      if (s == screen?.timeSlot) continue;
      try {
        await api.checkingRooms(date: date, slot: s);
      } on ApiError {
        return;
      }
    }
  }

  /// Checks still on the phone show on their rooms, over what the server said.
  void _overlay() {
    final s = screen;
    if (s == null) return;
    s.rooms = [
      for (final r in s.rooms)
        switch (outbox.waitingFor(r.instanceId)) {
          null => r,
          final q => r.withCheck(q.record, q.outcome == 'TEACHER_NOT_FOUND' ? null : q.outcome),
        },
    ];
  }

  /// A waiting check was sent, or refused: the rooms catch up with the server.
  void _onOutbox() => load();

  void setDate(String next) {
    if (next == date) return;
    date = next;
    load(spinner: true);
  }

  void setSlot(String next) {
    if (next == slot) return;
    slot = next;
    load(spinner: true);
  }

  /// Back to now: today, and whichever slot is running.
  void resetToNow() {
    date = todayIso();
    slot = null;
    load(spinner: true);
  }

  void patch(RoomRow next) {
    final s = screen;
    if (s == null) return;
    s.rooms = [for (final r in s.rooms) r.instanceId == next.instanceId ? next : r];
    _notify();
  }

  List<FloorTally> get floors {
    final s = screen;
    if (s == null) return const [];
    return [
      for (final f in s.floors)
        FloorTally(
          f,
          s.rooms.where((r) => r.zoneKey == f.key).length,
          s.rooms.where((r) => r.zoneKey == f.key && r.check != null).length,
        ),
    ];
  }

  List<RoomRow> roomsOn(String? floorKey) {
    final all = screen?.rooms ?? const <RoomRow>[];
    return floorKey == null ? all : all.where((r) => r.zoneKey == floorKey).toList();
  }

  void startPolling() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => load());
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
    outbox.removeListener(_onOutbox);
    stopPolling();
    super.dispose();
  }
}
