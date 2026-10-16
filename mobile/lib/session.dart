import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api/client.dart';
import 'api/models.dart';
import 'offline/cache.dart';
import 'push.dart';
import 'staff/outbox.dart';

/// Who is signed in. The token lives in the platform keystore; the user is
/// cached beside it, so the app opens straight onto its screens and refreshes
/// the user in the background.
class Session extends ChangeNotifier {
  Session(this.api, this.push) {
    api.onUnauthorized = () => signOut(notice: 'Your session ended. Sign in again.', expired: true);
    api.cache = cache;
  }

  final Api api;
  final Push push;

  /// What was last read, for screens to show with no signal.
  final cache = OfflineCache();

  /// Checks made with no signal, waiting to be sent.
  late final outbox = Outbox(api);
  final _store = const FlutterSecureStorage();

  static const _tokenKey = 'token';
  static const _userKey = 'user';
  static const _usernameKey = 'username';

  User? user;
  bool restoring = true;

  /// What they last signed in with, to prefill the form.
  String lastUsername = '';

  /// Why they were signed out, shown once on the sign-in screen.
  String? notice;

  Future<void> restore() async {
    try {
      lastUsername = await _store.read(key: _usernameKey) ?? '';
      final token = await _store.read(key: _tokenKey);
      final cached = await _store.read(key: _userKey);
      if (token != null && cached != null) {
        api.token = token;
        user = User.fromJson(jsonDecode(cached) as Json);
        api.cacheScope = '${user!.id}';
      }
    } catch (_) {
      // A keystore that cannot be read is the same as being signed out.
      user = null;
    }
    await outbox.load();
    restoring = false;
    notifyListeners();
    if (user != null) {
      unawaited(outbox.adopt(api.cacheScope));
      await refreshUser();
      // A launch re-registers, so the server always has the phone's current token.
      if (user != null) unawaited(push.register(api));
    }
  }

  /// Picks up role changes made on the website since the last launch.
  Future<void> refreshUser() async {
    try {
      final fresh = await api.me();
      user = fresh;
      await _store.write(key: _userKey, value: jsonEncode(fresh.raw));
      notifyListeners();
    } on ApiError {
      // Offline keeps the cached user; a 401 has already signed them out.
    }
  }

  Future<void> signIn(String username, String password) async {
    final (signedIn, token) = await api.login(username.trim(), password);
    // Another account's reads and waiting checks are not this one's to see or send.
    await cache.clearAccount();
    api.cacheScope = '${signedIn.id}';
    await outbox.adopt(api.cacheScope);
    api.token = token;
    user = signedIn;
    notice = null;
    lastUsername = username.trim();
    await _store.write(key: _tokenKey, value: token);
    await _store.write(key: _userKey, value: jsonEncode(signedIn.raw));
    await _store.write(key: _usernameKey, value: lastUsername);
    notifyListeners();
    unawaited(push.register(api));
    // The sign-in response leaves out the faculty photo; /me has it.
    await refreshUser();
  }

  /// `expired`: the server ended the session, rather than the person signing out.
  /// The phone keeps its pushes then -- it is still theirs, and reminders should
  /// not stop because a session lapsed -- until someone signs in on it again. It
  /// keeps their waiting checks and what they read, too, to send and show once
  /// they sign in again.
  Future<void> signOut({String? notice, bool expired = false}) async {
    if (user == null && api.token == null) return;
    if (!expired) {
      await push.unregister(api);
      await outbox.clear();
      await cache.clearAccount();
    }
    api.token = null;
    user = null;
    this.notice = notice;
    await _store.delete(key: _tokenKey);
    await _store.delete(key: _userKey);
    notifyListeners();
  }
}

/// Puts the session within reach of every screen.
class SessionScope extends InheritedNotifier<Session> {
  const SessionScope({super.key, required Session session, required super.child}) : super(notifier: session);

  static Session of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<SessionScope>()!.notifier!;

  /// Without listening: for callbacks.
  static Session read(BuildContext context) => context.getInheritedWidgetOfExactType<SessionScope>()!.notifier!;
}

extension SessionOf on BuildContext {
  Api get api => SessionScope.read(this).api;
}
