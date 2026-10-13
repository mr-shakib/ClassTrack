import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../util/time.dart';

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
class CheckingController extends ChangeNotifier {
  CheckingController(this.api);

  final Api api;

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
      screen = data;
      if (asked == null && date == todayIso()) liveSlot = data.timeSlot;
      slot ??= data.timeSlot;
      error = null;
    } on ApiError catch (e) {
      if (request != _request) return;
      error = e.message;
    }
    loading = false;
    _notify();
  }

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
    stopPolling();
    super.dispose();
  }
}
