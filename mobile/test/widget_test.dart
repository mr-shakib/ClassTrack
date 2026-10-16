import 'package:classtrack/api/models.dart';
import 'package:classtrack/push.dart';
import 'package:classtrack/student/student.dart';
import 'package:classtrack/util/time.dart';
import 'package:classtrack/widgets/common.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('a naive server timestamp is read as UTC', () {
    expect(parseServerTime('2026-10-04T12:41:05'), DateTime.utc(2026, 10, 4, 12, 41, 5));
    expect(parseServerTime('2026-10-14T00:00:00+06:00'), DateTime.utc(2026, 10, 13, 18));
    expect(dhakaHhmm('2026-10-04T12:41:05'), '18:41');
  });

  test('an online class runs 90 minutes from its start', () {
    expect(endsLabel('19:30'), '19:30–21:00');
    expect(endsLabel('22:30'), '22:30–00:00');
  });

  test('routine slots read the afternoon on a 12-hour clock; online times are 24-hour', () {
    expect(slotBounds('08:30-10:00'), (510, 600));
    expect(slotBounds('11:30-01:00'), (690, 780));
    expect(slotBounds('04:00-05:30'), (960, 1050));
    expect(slot24('01:00-02:30'), '13:00–14:30');
    expect(slotBounds('07:00-08:30'), (420, 510));
    expect(slotBounds('20:00-21:30'), (1200, 1290));
  });

  test('avatar initials prefer the teacher initial, then skip titles', () {
    expect(Avatar.initialsOf('Dr. Sheak Rashed Haider Noori', 'SRH'), 'SRH');
    expect(Avatar.initialsOf('Dr. Sheak Rashed Haider Noori', null), 'SN');
    expect(Avatar.initialsOf('Staff One', null), 'SO');
  });

  test('a push carries its kind and link as data; an empty link is none', () {
    final missed = PushMessage.from(
      const RemoteMessage(
        data: {'kind': 'CLASS_REPORTED', 'link': '/teacher/makeup?instance=7'},
        notification: RemoteNotification(title: 'Class missed', body: 'CSE311 has been marked as missed.'),
      ),
    );
    expect(missed.link, '/teacher/makeup?instance=7');
    expect(missed.title, 'Class missed');
    expect(missed.isReminder, isFalse);

    final reminder = PushMessage.from(const RemoteMessage(data: {'kind': 'CLASS_REMINDER', 'link': ''}));
    expect(reminder.isReminder, isTrue);
    expect(reminder.link, isNull);
    expect(reminder.title, isNull);
  });

  test('a group reads as a section, a lab group or a retake group', () {
    expect(groupLabel('63_A'), 'Section 63_A');
    expect(groupLabel('63_A1'), 'Lab group 63_A1');
    expect(groupLabel('CSE447:RE_A'), 'CSE447 retake RE_A');
  });

  test('a student class reads where it moved, and nothing else about it', () {
    final c = StudentClass.fromJson({
      'id': 7,
      'date': '2026-10-18',
      'time_slot': '10:00-11:30',
      'start_min': 600,
      'end_min': 690,
      'room': 'KT-305',
      'room_type': 'Theory',
      'online': false,
      'course_code': 'CSE311',
      'section': '70_A',
      'kind': 'CLASS',
      'state': 'MOVED',
      'moved_to': {'date': '2026-10-20', 'time_slot': '04:00-05:30', 'room': null, 'online': true},
      'teacher': {'initial': 'TCA', 'name': 'Teacher A'},
      'note': {'body': 'Quiz', 'author': 'Teacher A (TCA)', 'created_at': '2026-10-16T08:00:00'},
    });
    expect(c.on, isFalse);
    expect(c.movedTo!.date, '2026-10-20');
    expect(c.movedOnline, isTrue);
    expect(c.teacher.display, 'Teacher A');
    expect(c.noteBody, 'Quiz');
  });
}
