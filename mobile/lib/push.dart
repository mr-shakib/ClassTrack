import 'dart:async';
import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import 'api/client.dart';
import 'firebase_options.dart';

/// A push the person tapped, or one that arrived while the app was open.
class PushMessage {
  const PushMessage({required this.kind, this.link, this.title, this.body});

  factory PushMessage.from(RemoteMessage m) {
    final link = m.data['link'] as String?;
    return PushMessage(
      kind: m.data['kind'] as String? ?? '',
      link: link == null || link.isEmpty ? null : link,
      title: m.notification?.title,
      body: m.notification?.body,
    );
  }

  /// A notification's kind, or `CLASS_REMINDER`: a class of theirs is about to start.
  final String kind;

  /// The web path it is about, as on the notification.
  final String? link;
  final String? title, body;

  bool get isReminder => kind == 'CLASS_REMINDER' || kind == 'STUDENT_REMINDER';
}

/// Push notifications, through Firebase Cloud Messaging.
///
/// The backend pushes every notification it keeps for the bell, and reminds a
/// teacher before each of their classes. The app registers the phone on each
/// sign-in and launch, and lets it go on sign-out. The Firebase project is in
/// `firebase_options.dart` (`flutterfire configure` writes it); if Firebase
/// cannot start, the app runs as before, without push.
class Push {
  bool _ready = false;
  StreamSubscription<String>? _refresh;

  /// The token being deleted at sign-out. Signing in again waits for it, or
  /// would register the old token just before it dies.
  Future<void>? _deleting;
  PushMessage? _pending;
  final _opened = StreamController<PushMessage>.broadcast();
  final _received = StreamController<PushMessage>.broadcast();

  static const _wait = Duration(seconds: 3);

  /// Tapped in the tray while the app was in the background.
  Stream<PushMessage> get opened => _opened.stream;

  /// Arrived while the app was open. The phone shows nothing then, so the app does.
  Stream<PushMessage> get received => _received.stream;

  /// The tap that launched the app, given out once: to the signed-in screens when
  /// they first build, which may be only after signing in.
  PushMessage? takePending() {
    final p = _pending;
    _pending = null;
    return p;
  }

  Future<void> start() async {
    try {
      await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
    } catch (e) {
      debugPrint('Push off: $e');
      return;
    }
    _ready = true;
    FirebaseMessaging.onMessage.listen((m) => _received.add(PushMessage.from(m)));
    FirebaseMessaging.onMessageOpenedApp.listen((m) => _opened.add(PushMessage.from(m)));
    try {
      final initial = await FirebaseMessaging.instance.getInitialMessage();
      if (initial != null) _pending = PushMessage.from(initial);
    } catch (_) {
      // Opened from the launcher, as far as the app can tell.
    }
  }

  static String get _platform => Platform.isIOS ? 'ios' : 'android';

  /// Sends this account's notifications to this phone. Asks for permission the
  /// first time; once refused, the phone is not registered.
  Future<void> register(Api api) async {
    if (!_ready) return;
    final messaging = FirebaseMessaging.instance;
    try {
      await _deleting;
      final allowed = await messaging.requestPermission();
      if (allowed.authorizationStatus == AuthorizationStatus.denied) return;
      // iOS hands out a Firebase token only once Apple has given its own.
      if (Platform.isIOS && await messaging.getAPNSToken() == null) return;
      final token = await messaging.getToken();
      if (token == null) return;
      await api.registerDevice(token, _platform);
      _refresh ??= messaging.onTokenRefresh.listen(
        (fresh) => api.registerDevice(fresh, _platform).catchError((Object _) {}),
      );
    } catch (e) {
      // Offline, or Play services missing: the next launch tries again.
      debugPrint('Push registration failed: $e');
    }
  }

  /// Asks to show notifications, the first time. Whether they are allowed.
  Future<bool> askPermission() async {
    if (!_ready) return false;
    try {
      final allowed = await FirebaseMessaging.instance.requestPermission();
      return allowed.authorizationStatus != AuthorizationStatus.denied;
    } catch (_) {
      return false;
    }
  }

  /// Follows and leaves push topics: how a student, who has no account, gets
  /// the pushes for their sections. Firebase keeps the topics with the phone's
  /// token, so they survive restarts; following one twice changes nothing.
  /// Returns the topics now followed, which on a failure keeps what was.
  Future<Set<String>> follow({required Set<String> wanted, required Set<String> followed}) async {
    if (!_ready) return followed;
    final messaging = FirebaseMessaging.instance;
    final now = {...followed};
    await _deleting;
    for (final t in followed.difference(wanted)) {
      try {
        await messaging.unsubscribeFromTopic(t);
        now.remove(t);
      } catch (e) {
        debugPrint('Could not leave topic $t: $e');
      }
    }
    // Every wanted topic again, not only the new ones: a reinstall or a new
    // token starts with none.
    for (final t in wanted) {
      try {
        await messaging.subscribeToTopic(t);
        now.add(t);
      } catch (e) {
        debugPrint('Could not follow topic $t: $e');
      }
    }
    return now;
  }

  /// Stops this phone receiving the account's notifications. Offline, the token
  /// is still deleted, so Firebase refuses it and the server forgets it.
  Future<void> unregister(Api api) async {
    if (!_ready) return;
    await _refresh?.cancel();
    _refresh = null;
    final messaging = FirebaseMessaging.instance;
    try {
      final token = await messaging.getToken().timeout(_wait);
      if (token != null) await api.removeDevice(token).timeout(_wait);
    } catch (_) {
      // The token is deleted below either way.
    }
    // Not awaited, so signing out is not held up; the next sign-in waits instead.
    _deleting = messaging.deleteToken().timeout(const Duration(seconds: 10)).catchError((Object _) {});
  }
}
