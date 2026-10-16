import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

/// What the app last read from the server, kept in files, so a screen still
/// shows something with no signal. Each answer is kept with when it arrived.
///
/// Two shelves: `public`, the student routine anyone may read, and `account`,
/// what the signed-in person read, which goes when they sign out.
class OfflineCache {
  Directory? _root;
  final _memory = <String, (dynamic, DateTime)>{};

  Future<Directory> _dir(bool public) async {
    _root ??= Directory('${(await getApplicationSupportDirectory()).path}/offline');
    final dir = Directory('${_root!.path}/${public ? 'public' : 'account'}');
    if (!dir.existsSync()) dir.createSync(recursive: true);
    return dir;
  }

  /// A file name for any key: a request's path and query can be long, and hold
  /// characters no file system wants.
  static String _name(String key) {
    // FNV-1a, 64-bit: no collisions to speak of among a few hundred keys.
    var hash = 0xcbf29ce484222325;
    for (final unit in utf8.encode(key)) {
      hash = (hash ^ unit) * 0x100000001b3;
    }
    return '${hash.toUnsigned(64).toRadixString(16)}.json';
  }

  Future<void> write(String key, dynamic data, {required bool public}) async {
    final now = DateTime.now().toUtc();
    _memory[key] = (data, now);
    try {
      final file = File('${(await _dir(public)).path}/${_name(key)}');
      await file.writeAsString(jsonEncode({'key': key, 'saved_at': now.toIso8601String(), 'data': data}));
    } catch (e) {
      // A full or read-only disk: the screen still has the answer, it is only not kept.
      debugPrint('Could not keep $key: $e');
    }
  }

  /// The answer kept for `key`, and when it arrived; null when none was.
  Future<(dynamic, DateTime)?> read(String key, {required bool public}) async {
    final held = _memory[key];
    if (held != null) return held;
    try {
      final file = File('${(await _dir(public)).path}/${_name(key)}');
      if (!file.existsSync()) return null;
      final json = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
      if (json['key'] != key) return null;
      final kept = (json['data'], DateTime.parse(json['saved_at'] as String));
      _memory[key] = kept;
      return kept;
    } catch (_) {
      return null;
    }
  }

  /// Forgets what the signed-in person read: at sign-in and sign-out.
  Future<void> clearAccount() async {
    _memory.removeWhere((key, _) => !key.startsWith('/students/'));
    try {
      final dir = await _dir(false);
      if (dir.existsSync()) await dir.delete(recursive: true);
    } catch (_) {
      // Rare. Keys carry the account, so nobody else is ever shown what is left;
      // the next sign-in tries again.
    }
  }
}
