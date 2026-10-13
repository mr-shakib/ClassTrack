import 'package:classtrack/util/time.dart';
import 'package:classtrack/widgets/common.dart';
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
}
