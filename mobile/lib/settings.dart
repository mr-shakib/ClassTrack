import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// The person's own choices about the app, kept on the phone. Signing out
/// keeps them: they belong to the phone's owner, not the session.
class AppSettings extends ChangeNotifier {
  static const _themeKey = 'theme';
  final _store = const FlutterSecureStorage();

  /// Light unless the person picks otherwise.
  ThemeMode themeMode = ThemeMode.light;

  /// Read before the first frame, so the app never flashes the wrong theme.
  Future<void> load() async {
    try {
      themeMode = switch (await _store.read(key: _themeKey)) {
        'dark' => ThemeMode.dark,
        'system' => ThemeMode.system,
        _ => ThemeMode.light,
      };
    } catch (_) {
      themeMode = ThemeMode.light;
    }
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    if (mode == themeMode) return;
    themeMode = mode;
    notifyListeners();
    try {
      await _store.write(key: _themeKey, value: mode.name);
    } catch (_) {
      // Unsaved, it still applies until the app closes.
    }
  }
}

class SettingsScope extends InheritedNotifier<AppSettings> {
  const SettingsScope({super.key, required AppSettings settings, required super.child}) : super(notifier: settings);

  static AppSettings of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<SettingsScope>()!.notifier!;
}
