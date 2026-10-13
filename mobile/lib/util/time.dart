import 'package:intl/intl.dart';

/// The routine lattice: six 90-minute slots. Fixed, so it is not fetched.
const slots = ['08:30-10:00', '10:00-11:30', '11:30-01:00', '01:00-02:30', '02:30-04:00', '04:00-05:30'];

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
String dhakaHhmm(String serverTime) => DateFormat('HH:mm').format(parseServerTime(serverTime).add(_dhaka));

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

/// Minutes since midnight of a routine label's "HH:MM". The routine writes
/// the afternoon on a 12-hour clock ("01:00" is 13:00); no class starts
/// before 08:00, so an hour below 8 is afternoon. Online classes use 24-hour
/// labels ("20:00"), which this leaves alone.
int labelMinutes(String hhmm) {
  final parts = hhmm.trim().split(':');
  var h = int.parse(parts[0]);
  final m = int.parse(parts[1]);
  if (h < 8) h += 12;
  return h * 60 + m;
}

/// A time label's start and end, in minutes since midnight: one of the six
/// routine slots, or an online class's own 24-hour period ("07:00-08:30").
(int, int) slotBounds(String slot) {
  final parts = slot.split('-');
  if (!slots.contains(slot)) {
    int m(String s) => int.parse(s.split(':')[0]) * 60 + int.parse(s.split(':')[1]);
    return (m(parts.first), m(parts.last));
  }
  final start = labelMinutes(parts.first);
  var end = labelMinutes(parts.last);
  if (end <= start) end += 12 * 60;
  return (start, end);
}

/// "16:00", from minutes since midnight.
String clock(int minutes) =>
    '${(minutes ~/ 60 % 24).toString().padLeft(2, '0')}:${(minutes % 60).toString().padLeft(2, '0')}';

/// A slot on the 24-hour clock: "04:00-05:30" → "16:00–17:30".
String slot24(String slot) {
  final (start, end) = slotBounds(slot);
  return '${clock(start)}–${clock(end)}';
}

/// Minutes since midnight on Dhaka's clock.
int dhakaMinutesNow() {
  final now = dhakaNow();
  return now.hour * 60 + now.minute;
}

/// "45 min", "1 h 20 min", "3 h".
String spanLabel(int minutes) {
  if (minutes < 60) return '$minutes min';
  final h = minutes ~/ 60, m = minutes % 60;
  return m == 0 ? '$h h' : '$h h $m min';
}

/// "Today", "Tomorrow", or "Wednesday, 14 Oct".
String dayLabel(String iso) {
  final today = parseDay(todayIso());
  final day = parseDay(iso);
  final diff = day.difference(today).inDays;
  if (diff == 0) return 'Today';
  if (diff == 1) return 'Tomorrow';
  return mediumDay(iso);
}

/// "Good morning" by Dhaka's clock.
String greeting() {
  final h = dhakaNow().hour;
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}
