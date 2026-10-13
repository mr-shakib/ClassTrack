import 'package:intl/intl.dart';

/// The routine lattice: six 90-minute slots. Fixed, so it is not fetched.
const slots = [
  '08:30-10:00',
  '10:00-11:30',
  '11:30-01:00',
  '01:00-02:30',
  '02:30-04:00',
  '04:00-05:30',
];

/// "08:30-10:00" → "08:30–10:00", with a proper dash.
String slotLabel(String slot) => slot.replaceAll('-', '–');

/// "08:30-10:00" → "08:30".
String slotStart(String slot) => slot.split('-').first;

/// The department works in Asia/Dhaka (UTC+6, no daylight saving). Use it
/// rather than the phone's zone, so a phone set to another zone does not show
/// the wrong day's classes.
const _dhaka = Duration(hours: 6);

/// Dhaka's wall clock, as a UTC DateTime whose fields read as Dhaka time.
DateTime dhakaNow() => DateTime.now().toUtc().add(_dhaka);

String isoDate(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

String todayIso() => isoDate(dhakaNow());

/// "16:05", Dhaka time, for prefilling a late arrival.
String nowHhmm() => DateFormat('HH:mm').format(dhakaNow());

DateTime parseDay(String iso) => DateTime.parse(iso);

/// "Sunday, 20 September 2026": spelled out, so nobody misreads a date.
String formatDay(String iso) => DateFormat('EEEE, d MMMM y').format(parseDay(iso));

/// "Sun 13 Sep": short enough for a chip.
String shortDay(String iso) => DateFormat('EEE d MMM').format(parseDay(iso));

/// "Tuesday, 13 Oct".
String mediumDay(String iso) => DateFormat('EEEE, d MMM').format(parseDay(iso));

/// A timestamp from the API. Stored ones come back as naive UTC
/// ("2026-10-04T12:41:05"); computed ones carry their offset.
DateTime parseServerTime(String s) {
  final hasZone = s.endsWith('Z') || RegExp(r'[+-]\d\d:\d\d$').hasMatch(s);
  return DateTime.parse(hasZone ? s : '${s}Z').toUtc();
}

/// A server timestamp on Dhaka's clock: "16:05".
String dhakaHhmm(String serverTime) =>
    DateFormat('HH:mm').format(parseServerTime(serverTime).add(_dhaka));

/// "Just now", "12 min ago", "3 h ago", "Yesterday", "4 Oct".
String relativeTime(String serverTime) {
  final t = parseServerTime(serverTime);
  final diff = DateTime.now().toUtc().difference(t);
  if (diff.inMinutes < 1) return 'Just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes} min ago';
  if (diff.inHours < 24) return '${diff.inHours} h ago';
  if (diff.inDays < 2) return 'Yesterday';
  if (diff.inDays < 7) return '${diff.inDays} days ago';
  return DateFormat('d MMM').format(t.add(_dhaka));
}

/// "19:30" → "19:30–21:00": a class runs 90 minutes.
String endsLabel(String start) {
  final parts = start.split(':').map(int.parse).toList();
  final end = parts[0] * 60 + parts[1] + 90;
  String two(int n) => n.toString().padLeft(2, '0');
  return '$start–${two((end ~/ 60) % 24)}:${two(end % 60)}';
}

/// "Good morning" by Dhaka's clock.
String greeting() {
  final h = dhakaNow().hour;
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}
