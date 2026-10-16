import 'package:flutter/material.dart';

import '../api/models.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';

/// What is unusual about a class, if anything.
Widget? classBadge(BuildContext context, StudentClass c, {bool large = false}) {
  final p = context.palette;
  if (c.state == 'CANCELLED') {
    return Pill('Cancelled', color: p.bad, background: p.badSoft, icon: Icons.event_busy_rounded, large: large);
  }
  if (c.state == 'MOVED') {
    final to = c.movedTo;
    return Pill(
      to == null ? 'Moved' : 'Moved to ${shortDay(to.date)}',
      color: p.info,
      background: p.infoSoft,
      icon: Icons.sync_rounded,
      large: large,
    );
  }
  if (c.isMakeup) {
    return Pill(
      c.online ? 'Online makeup' : 'Makeup',
      color: p.info,
      background: p.infoSoft,
      icon: c.online ? Icons.videocam_rounded : Icons.sync_rounded,
      large: large,
    );
  }
  if (c.isExtra) {
    return Pill('Extra class', color: p.brand, background: p.brandSoft, icon: Icons.add_rounded, large: large);
  }
  return null;
}

String _times(StudentClass c) => '${clock(c.start)}–${clock(c.end)}';

/// One class in a list: when, what, where, and who teaches it.
class StudentClassTile extends StatelessWidget {
  const StudentClassTile({super.key, required this.c, this.showDay = false});
  final StudentClass c;
  final bool showDay;

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final off = !c.on;
    final badge = classBadge(context, c);
    return InkWell(
      onTap: () => showStudentClass(context, c),
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 58,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (showDay)
                    Text(
                      shortDay(c.date).toUpperCase(),
                      style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: p.inkFaint),
                    ),
                  Text(
                    clock(c.start),
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: off ? p.inkFaint : p.ink,
                      decoration: off ? TextDecoration.lineThrough : null,
                      fontFeatures: tabular,
                    ),
                  ),
                  Text(
                    clock(c.end),
                    style: TextStyle(fontSize: 12.5, color: p.inkFaint, fontFeatures: tabular),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          c.courseCode,
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: off ? p.inkSoft : p.ink),
                        ),
                      ),
                      if (c.noteBody != null) ...[
                        const SizedBox(width: 6),
                        Icon(Icons.chat_bubble_outline_rounded, size: 16, color: p.brand),
                      ],
                    ],
                  ),
                  if (c.courseTitle != null && c.courseTitle!.isNotEmpty)
                    Text(
                      c.courseTitle!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 14, color: p.inkSoft),
                    ),
                  const SizedBox(height: 3),
                  Wrap(
                    spacing: 12,
                    runSpacing: 2,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            c.online ? Icons.videocam_outlined : Icons.meeting_room_outlined,
                            size: 15,
                            color: p.inkSoft,
                          ),
                          const SizedBox(width: 4),
                          Text(c.online ? 'Online' : c.room ?? '', style: TextStyle(fontSize: 14, color: p.inkSoft)),
                        ],
                      ),
                      Text(c.teacher.display, style: TextStyle(fontSize: 14, color: p.inkSoft)),
                    ],
                  ),
                  if (badge != null) Padding(padding: const EdgeInsets.only(top: 6), child: badge),
                ],
              ),
            ),
            Icon(Icons.chevron_right_rounded, color: p.inkFaint),
          ],
        ),
      ),
    );
  }
}

/// One class in full: the Teacher Card, a note from the teacher, where it
/// moved, and how to join it online.
void showStudentClass(BuildContext context, StudentClass c) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (sheet) {
      final p = sheet.palette;
      final badge = classBadge(sheet, c, large: true);
      final t = c.teacher;

      Widget fact(IconData icon, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(
          children: [
            Icon(icon, size: 20, color: p.inkSoft),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                text,
                style: TextStyle(fontSize: 15.5, color: p.ink, fontWeight: FontWeight.w600, fontFeatures: tabular),
              ),
            ),
          ],
        ),
      );

      return SafeArea(
        top: false,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: MediaQuery.of(sheet).size.height * 0.88),
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  c.courseCode,
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: p.ink, letterSpacing: -0.4),
                ),
                if (c.courseTitle != null && c.courseTitle!.isNotEmpty)
                  Text(c.courseTitle!, style: TextStyle(fontSize: 15.5, color: p.inkSoft)),
                Text('Section ${c.section}', style: TextStyle(fontSize: 14, color: p.inkFaint)),
                if (badge != null) Padding(padding: const EdgeInsets.only(top: 10), child: badge),
                const SizedBox(height: 18),
                fact(Icons.event_rounded, formatDay(c.date)),
                fact(Icons.schedule_rounded, _times(c)),
                fact(
                  c.online ? Icons.videocam_rounded : Icons.meeting_room_rounded,
                  c.online ? 'Online' : 'Room ${c.room}${c.roomType.isNotEmpty ? ' · ${c.roomType}' : ''}',
                ),
                if (c.state == 'MOVED' && c.movedTo != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Notice(
                      'Moved to ${formatDay(c.movedTo!.date)}, ${slot24(c.movedTo!.timeSlot)}'
                      '${c.movedOnline ? ', online' : (c.movedTo!.room != null ? ', room ${c.movedTo!.room}' : '')}.',
                      tone: Tone.info,
                      icon: Icons.sync_rounded,
                    ),
                  ),
                if (c.state == 'CANCELLED')
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Notice('This class will not be held.', tone: Tone.bad, icon: Icons.event_busy_rounded),
                  ),
                if (c.isMakeup && c.makeupFor != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Notice(
                      'Makes up the class of ${formatDay(c.makeupFor!.date)}, ${slot24(c.makeupFor!.timeSlot)}.',
                      tone: Tone.info,
                      icon: Icons.history_rounded,
                    ),
                  ),
                if (c.online)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: c.joinLink != null
                        ? SizedBox(
                            width: double.infinity,
                            child: FilledButton.icon(
                              onPressed: () => openLink(sheet, c.joinLink!),
                              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                              icon: const Icon(Icons.videocam_rounded),
                              label: const Text('Join the class'),
                            ),
                          )
                        : const Notice(
                            'Your teacher has not added a join link yet. It shows here when they do.',
                            tone: Tone.neutral,
                            icon: Icons.link_off_rounded,
                          ),
                  ),
                if (c.noteBody != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Notice(
                      c.noteBody!,
                      title: 'Note from your teacher${c.noteAt != null ? ' · ${relativeTime(c.noteAt!)}' : ''}',
                      tone: Tone.info,
                      icon: Icons.chat_bubble_outline_rounded,
                    ),
                  ),
                const SizedBox(height: 6),
                Panel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'TEACHER CARD',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                          color: p.inkFaint,
                          letterSpacing: 0.8,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Avatar(name: t.display, initial: t.initial, photo: t.photoUrl, size: 56),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  t.display,
                                  style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: p.ink),
                                ),
                                Text(
                                  [t.designation, t.initial].whereType<String>().where((s) => s.isNotEmpty).join(' · '),
                                  style: TextStyle(fontSize: 14, color: p.inkSoft),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      if (t.officeRoom != null && t.officeRoom!.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Icon(Icons.door_front_door_outlined, size: 18, color: p.inkSoft),
                            const SizedBox(width: 8),
                            Text('Office ', style: TextStyle(color: p.inkSoft)),
                            Text(
                              t.officeRoom!,
                              style: TextStyle(fontWeight: FontWeight.w800, color: p.ink),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    },
  );
}
