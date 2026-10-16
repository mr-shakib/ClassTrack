import 'package:package_info_plus/package_info_plus.dart';

/// The installed app's version, "1.3.0", read once: support asks for it first.
final Future<String> appVersion = PackageInfo.fromPlatform().then((i) => i.version, onError: (Object _) => '');
