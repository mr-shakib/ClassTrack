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

  test('avatar initials prefer the teacher initial, then skip titles', () {
    expect(Avatar.initialsOf('Dr. Sheak Rashed Haider Noori', 'SRH'), 'SRH');
    expect(Avatar.initialsOf('Dr. Sheak Rashed Haider Noori', null), 'SN');
    expect(Avatar.initialsOf('Staff One', null), 'SO');
  });
}
