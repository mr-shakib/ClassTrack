// Mirrors web/src/lib/types.ts, for the screens this app has. Keep in sync
// with backend/src/classtrack/schemas/*.

typedef Json = Map<String, dynamic>;

List<T> _list<T>(Object? raw, T Function(Json) of) => (raw as List? ?? const []).map((e) => of(e as Json)).toList();

int _int(Object? v) => (v as num?)?.toInt() ?? 0;
double _double(Object? v) => (v as num?)?.toDouble() ?? 0;

class RoleRef {
  RoleRef.fromJson(Json j) : key = j['key'] as String, name = j['name'] as String, kind = j['kind'] as String;
  final String key, name, kind;
}

class User {
  User.fromJson(Json j)
    : id = _int(j['id']),
      email = j['email'] as String? ?? '',
      fullName = j['full_name'] as String? ?? '',
      roles = _list(j['roles'], RoleRef.fromJson),
      permissions = {...(j['permissions'] as List? ?? const []).cast<String>()},
      isTeacher = j['is_teacher'] as bool? ?? false,
      isStaff = j['is_staff'] as bool? ?? false,
      teacherInitial = j['teacher_initial'] as String?,
      photoUrl = j['photo_url'] as String?,
      raw = j;

  final int id;
  final String email, fullName;
  final List<RoleRef> roles;
  final Set<String> permissions;
  final bool isTeacher, isStaff;
  final String? teacherInitial, photoUrl;

  /// Kept to cache the user between launches.
  final Json raw;

  bool can(String permission) => permissions.contains(permission);

  /// The checking screen. Mirrors `mayCheck` in web/src/lib/auth.tsx.
  bool get mayCheck => can('checking.submit') || can('checking.correct');

  /// Change a record after its day: admins and the committee.
  bool get mayCorrect => can('checking.correct');

  bool get mayReschedule => isTeacher && can('reschedules.request');

  /// Write to the students of their own sections.
  bool get mayMessageStudents => isTeacher && can('students.message');
  bool get mayBookExtra => isTeacher && can('extra_classes.book');

  String get roleNames => roles.map((r) => r.name).join(' · ');
}

class Profile {
  Profile.fromJson(Json j)
    : fullName = j['full_name'] as String? ?? '',
      roles = (j['roles'] as List? ?? const []).cast<String>(),
      isTeacher = j['is_teacher'] as bool? ?? false,
      signIn = j['sign_in'] as String? ?? '',
      teacherInitial = j['teacher_initial'] as String?,
      designation = j['designation'] as String?,
      department = j['department'] as String?,
      officeRoom = j['office_room'] as String?,
      contactEmail = j['contact_email'] as String?,
      photoUrl = j['photo_url'] as String?;

  final String fullName, signIn;
  final List<String> roles;
  final bool isTeacher;
  final String? teacherInitial, designation, department, officeRoom, contactEmail, photoUrl;
}

class CheckRecord {
  const CheckRecord({
    required this.outcome,
    this.arrivalTime,
    this.lateMinutes,
    this.remark,
    required this.checkedAt,
    this.checkedBy,
  });

  CheckRecord.fromJson(Json j)
    : outcome = j['outcome'] as String,
      arrivalTime = j['arrival_time'] as String?,
      lateMinutes = (j['late_minutes'] as num?)?.toInt(),
      remark = j['remark'] as String?,
      checkedAt = j['checked_at'] as String? ?? '',
      checkedBy = j['checked_by'] as String?;

  /// RUNNING, LATE or TEACHER_NOT_FOUND.
  final String outcome;
  final String? arrivalTime;
  final int? lateMinutes;
  final String? remark;
  final String checkedAt;
  final String? checkedBy;
}

/// The other end of a reschedule.
class SlotRef {
  SlotRef.fromJson(Json j)
    : date = j['date'] as String,
      timeSlot = j['time_slot'] as String,
      room = j['room'] as String?,
      instanceId = (j['instance_id'] as num?)?.toInt(),
      mode = j['mode'] as String?,
      status = j['status'] as String?;

  static SlotRef? maybe(Object? j) => j == null ? null : SlotRef.fromJson(j as Json);

  final String date, timeSlot;
  final String? room, mode, status;
  final int? instanceId;
}

/// One class on the checking screen.
class RoomRow {
  RoomRow.fromJson(Json j)
    : instanceId = _int(j['instance_id']),
      date = j['date'] as String?,
      timeSlot = j['time_slot'] as String?,
      slotState = j['slot_state'] as String?,
      room = j['room'] as String? ?? '',
      roomType = j['room_type'] as String? ?? '',
      courseCode = j['course_code'] as String? ?? '',
      courseTitle = j['course_title'] as String?,
      section = j['section'] as String? ?? '',
      teacherInitial = j['teacher_initial'] as String? ?? '',
      teacherName = j['teacher_name'] as String?,
      scheduledStart = j['scheduled_start'] as String? ?? '',
      scheduledEnd = j['scheduled_end'] as String? ?? '',
      isMakeup = j['is_makeup'] as bool? ?? false,
      isExtra = j['is_extra'] as bool? ?? false,
      rescheduledFrom = SlotRef.maybe(j['rescheduled_from']),
      zoneKey = j['zone_key'] as String?,
      status = j['status'] as String?,
      check = j['check'] == null ? null : CheckRecord.fromJson(j['check'] as Json);

  RoomRow._copy(RoomRow r, {required this.status, required this.check})
    : instanceId = r.instanceId,
      date = r.date,
      timeSlot = r.timeSlot,
      slotState = r.slotState,
      room = r.room,
      roomType = r.roomType,
      courseCode = r.courseCode,
      courseTitle = r.courseTitle,
      section = r.section,
      teacherInitial = r.teacherInitial,
      teacherName = r.teacherName,
      scheduledStart = r.scheduledStart,
      scheduledEnd = r.scheduledEnd,
      isMakeup = r.isMakeup,
      isExtra = r.isExtra,
      rescheduledFrom = r.rescheduledFrom,
      zoneKey = r.zoneKey;

  /// The same class with a new check, or none.
  RoomRow withCheck(CheckRecord? check, String? status) => RoomRow._copy(this, status: status, check: check);

  final int instanceId;
  final String? date, timeSlot;

  /// This class's own reporting state: UPCOMING, ONGOING or CLOSED.
  final String? slotState;
  final String room, roomType, courseCode, section, teacherInitial;
  final String? courseTitle, teacherName;
  final String scheduledStart, scheduledEnd;
  final bool isMakeup, isExtra;
  final SlotRef? rescheduledFrom;
  final String? zoneKey;
  final String? status;
  final CheckRecord? check;
}

/// One floor on the checking screen.
class FloorSummary {
  FloorSummary.fromJson(Json j)
    : key = j['key'] as String,
      label = j['label'] as String,
      shortLabel = j['short_label'] as String? ?? '',
      isMine = j['is_mine'] as bool? ?? false;

  final String key, label, shortLabel;

  /// One of the caller's assigned floors: listed first, never a restriction.
  final bool isMine;
}

class CheckingScreen {
  CheckingScreen.fromJson(Json j)
    : date = j['date'] as String,
      timeSlot = j['time_slot'] as String,
      slotState = j['slot_state'] as String,
      zones = (j['zones'] as List? ?? const []).cast<String>(),
      floors = _list(j['floors'], FloorSummary.fromJson),
      rooms = _list(j['rooms'], RoomRow.fromJson);

  final String date, timeSlot;

  /// UPCOMING, ONGOING or CLOSED.
  final String slotState;

  /// The caller's assigned floors (staff only). They order the list, not filter it.
  final List<String> zones;
  final List<FloorSummary> floors;
  List<RoomRow> rooms;
}

class CheckResponse {
  CheckResponse.fromJson(Json j)
    : status = j['status'] as String?,
      lateMinutes = (j['late_minutes'] as num?)?.toInt(),
      checkedBy = j['checked_by'] as String? ?? '',
      checkedAt = j['checked_at'] as String? ?? '';

  final String? status;
  final int? lateMinutes;
  final String checkedBy, checkedAt;
}

class ClassInstance {
  ClassInstance.fromJson(Json j)
    : id = _int(j['id']),
      date = j['date'] as String,
      timeSlot = j['time_slot'] as String,
      room = j['room'] as String? ?? '',
      roomType = j['room_type'] as String? ?? '',
      courseCode = j['course_code'] as String? ?? '',
      courseTitle = j['course_title'] as String?,
      section = j['section'] as String? ?? '',
      teacherInitial = j['teacher_initial'] as String? ?? '',
      isMakeup = j['is_makeup'] as bool? ?? false,
      isExtra = j['is_extra'] as bool? ?? false,
      status = j['status'] as String?,
      rescheduledFrom = SlotRef.maybe(j['rescheduled_from']),
      rescheduledTo = SlotRef.maybe(j['rescheduled_to']),
      check = j['check'] == null ? null : CheckRecord.fromJson(j['check'] as Json);

  final int id;
  final String date, timeSlot, room, roomType, courseCode, section, teacherInitial;
  final String? courseTitle;
  final bool isMakeup, isExtra;
  final String? status;
  final SlotRef? rescheduledFrom, rescheduledTo;
  final CheckRecord? check;
}

class Makeup {
  Makeup.fromJson(Json j)
    : id = _int(j['id']),
      originalInstanceId = _int(j['original_instance_id']),
      mode = j['mode'] as String,
      date = j['date'] as String,
      timeSlot = j['time_slot'] as String,
      room = j['room'] as String?,
      reason = j['reason'] as String?,
      status = j['status'] as String,
      decisionNote = j['decision_note'] as String?,
      driveLink = j['drive_link'] as String?,
      meetingLink = j['meeting_link'] as String?,
      endsAt = j['ends_at'] as String?,
      originalCourseCode = j['original_course_code'] as String?,
      originalSection = j['original_section'] as String?,
      originalDate = j['original_date'] as String?,
      originalTimeSlot = j['original_time_slot'] as String?,
      originalRoom = j['original_room'] as String?;

  final int id, originalInstanceId;

  /// PHYSICAL or ONLINE.
  final String mode;
  final String date, timeSlot;
  final String? room, reason;

  /// SCHEDULED, PENDING, APPROVED, REJECTED or COMPLETED.
  final String status;
  final String? decisionNote, driveLink, endsAt;

  /// ONLINE only: where students join the class.
  final String? meetingLink;
  final String? originalCourseCode, originalSection, originalDate, originalTimeSlot, originalRoom;

  bool get online => mode == 'ONLINE';

  /// Still to see through: undecided, or booked/approved and not done.
  bool get isOpen => status == 'PENDING' || status == 'SCHEDULED' || status == 'APPROVED';
}

class Conflict {
  Conflict.fromJson(Json j) : type = j['type'] as String? ?? '', message = j['message'] as String? ?? '';
  final String type, message;
}

class ConflictReport {
  ConflictReport.fromJson(Json j)
    : ok = j['ok'] as bool? ?? true,
      conflicts = _list(j['conflicts'], Conflict.fromJson),
      warnings = (j['warnings'] as List? ?? const []).cast<String>();

  final bool ok;
  final List<Conflict> conflicts;

  /// What could not be checked, such as a retake's students. Never blocks.
  final List<String> warnings;
}

/// An empty room offered for a booking.
class FreeRoom {
  FreeRoom.fromJson(Json j)
    : room = j['room'] as String,
      roomType = j['room_type'] as String? ?? '',
      zone = j['zone'] as String? ?? '';
  final String room, roomType, zone;
}

/// A course-section a teacher may book an extra class for.
class ExtraSection {
  ExtraSection.fromJson(Json j)
    : courseCode = j['course_code'] as String,
      courseTitle = j['course_title'] as String? ?? '',
      section = j['section'] as String,
      roomType = j['room_type'] as String? ?? '';
  final String courseCode, courseTitle, section, roomType;
  String get key => '$courseCode|$section';
}

class CourseTally {
  CourseTally.fromJson(Json j)
    : courseCode = j['course_code'] as String? ?? '',
      courseTitle = j['course_title'] as String?,
      section = j['section'] as String? ?? '',
      scheduled = _int(j['scheduled']),
      held = _int(j['held']),
      missed = _int(j['missed']),
      belowMinimum = j['below_minimum'] as bool? ?? false;

  final String courseCode, section;
  final String? courseTitle;
  final int scheduled, held, missed;
  final bool belowMinimum;
}

class TeacherReport {
  TeacherReport.fromJson(Json j)
    : label = j['label'] as String?,
      from = (j['range'] as Json?)?['from'] as String? ?? '',
      to = (j['range'] as Json?)?['to'] as String? ?? '',
      minConducted = _int(j['min_conducted']),
      totalScheduled = _int(j['total_scheduled']),
      conducted = _int(j['conducted']),
      late = _int(j['late']),
      missed = _int(j['missed']),
      notChecked = _int(j['not_checked']),
      makeupCompleted = _int(j['makeup_completed']),
      makeupPending = _int(j['makeup_pending']),
      onTime = _int(j['on_time']),
      rescheduled = _int(j['rescheduled']),
      avgLateMinutes = _double(j['avg_late_minutes']),
      conductRate = _double(j['conduct_rate']),
      courses = _list(j['courses'], CourseTally.fromJson);

  final String? label;
  final String from, to;
  final int minConducted, totalScheduled, conducted, late, missed, notChecked;
  final int makeupCompleted, makeupPending, onTime, rescheduled;
  final double avgLateMinutes;

  /// Held ÷ (held + missed), as a percentage. Not-checked classes are left out.
  final double conductRate;
  final List<CourseTally> courses;
}

class AppNotification {
  AppNotification.fromJson(Json j)
    : id = _int(j['id']),
      kind = j['kind'] as String? ?? '',
      title = j['title'] as String? ?? '',
      body = j['body'] as String? ?? '',
      link = j['link'] as String?,
      readAt = j['read_at'] as String?,
      createdAt = j['created_at'] as String? ?? '';

  final int id;
  final String kind, title, body, createdAt;
  final String? link, readAt;
  bool get unread => readAt == null;
}

// --- students -------------------------------------------------------------------
// Mirrors backend/src/classtrack/schemas/student.py. Students have no account:
// they pick their groups, and every read is public.

class StudentSection {
  StudentSection.fromJson(Json j)
    : section = j['section'] as String,
      intake = j['intake'] as String? ?? '',
      labGroups = (j['lab_groups'] as List? ?? const []).cast<String>();
  final String section, intake;
  final List<String> labGroups;
}

class RetakeGroup {
  RetakeGroup.fromJson(Json j)
    : token = j['token'] as String,
      section = j['section'] as String,
      labGroups = _list(j['lab_groups'], (l) => (l['token'] as String, l['section'] as String));
  final String token, section;
  final List<(String, String)> labGroups;
}

class RetakeCourse {
  RetakeCourse.fromJson(Json j)
    : courseCode = j['course_code'] as String,
      courseTitle = j['course_title'] as String?,
      groups = _list(j['groups'], RetakeGroup.fromJson);
  final String courseCode;
  final String? courseTitle;
  final List<RetakeGroup> groups;
}

class StudentDirectory {
  StudentDirectory.fromJson(Json j)
    : department = j['department'] as String? ?? 'CSE',
      semester = j['semester'] as String?,
      sections = _list(j['sections'], StudentSection.fromJson),
      retakes = _list(j['retakes'], RetakeCourse.fromJson);
  final String department;
  final String? semester;
  final List<StudentSection> sections;
  final List<RetakeCourse> retakes;
}

class TeacherCard {
  TeacherCard.fromJson(Json j)
    : initial = j['initial'] as String? ?? '',
      name = j['name'] as String?,
      designation = j['designation'] as String?,
      officeRoom = j['office_room'] as String?,
      photoUrl = j['photo_url'] as String?;
  final String initial;
  final String? name, designation, officeRoom, photoUrl;

  String get display => name ?? initial;
}

/// A class as students see it: where and when, and whether it is on. Nothing
/// about whether the teacher came: that never leaves the server.
class StudentClass {
  StudentClass.fromJson(Json j)
    : id = _int(j['id']),
      date = j['date'] as String,
      timeSlot = j['time_slot'] as String,
      start = _int(j['start_min']),
      end = _int(j['end_min']),
      room = j['room'] as String?,
      roomType = j['room_type'] as String? ?? '',
      online = j['online'] as bool? ?? false,
      courseCode = j['course_code'] as String,
      courseTitle = j['course_title'] as String?,
      section = j['section'] as String,
      kind = j['kind'] as String? ?? 'CLASS',
      state = j['state'] as String? ?? 'SCHEDULED',
      movedTo = j['moved_to'] == null ? null : SlotRef.fromJson(j['moved_to'] as Json),
      movedOnline = (j['moved_to'] as Json?)?['online'] == true,
      makeupFor = j['makeup_for'] == null ? null : SlotRef.fromJson(j['makeup_for'] as Json),
      joinLink = j['join_link'] as String?,
      teacher = TeacherCard.fromJson(j['teacher'] as Json? ?? const {}),
      noteBody = (j['note'] as Json?)?['body'] as String?,
      noteAt = (j['note'] as Json?)?['created_at'] as String?;

  final int id, start, end;
  final String date, timeSlot, roomType, courseCode, section;

  /// Null when it is held online.
  final String? room, courseTitle, joinLink;
  final bool online;

  /// CLASS, MAKEUP or EXTRA.
  final String kind;

  /// SCHEDULED, CANCELLED, or MOVED to [movedTo].
  final String state;
  final SlotRef? movedTo, makeupFor;
  final bool movedOnline;
  final TeacherCard teacher;

  /// The latest note the teacher wrote about this class.
  final String? noteBody, noteAt;

  bool get on => state == 'SCHEDULED';
  bool get isMakeup => kind == 'MAKEUP';
  bool get isExtra => kind == 'EXTRA';
}

class StudentNotice {
  StudentNotice.fromJson(Json j)
    : id = _int(j['id']),
      kind = j['kind'] as String,
      title = j['title'] as String,
      body = j['body'] as String,
      author = j['author'] as String? ?? '',
      createdAt = j['created_at'] as String,
      about = j['about'] == null ? null : StudentClass.fromJson(j['about'] as Json);

  final int id;

  /// ANNOUNCEMENT, TEACHER or CHANGE.
  final String kind;
  final String title, body, author, createdAt;
  final StudentClass? about;
}

class StudentTopics {
  StudentTopics.fromJson(Json j)
    : alerts = (j['alerts'] as List? ?? const []).cast<String>(),
      reminders = (j['reminders'] as List? ?? const []).cast<String>();
  final List<String> alerts, reminders;
}

class FreeSlot {
  FreeSlot.fromJson(Json j) : timeSlot = j['time_slot'] as String, rooms = _list(j['rooms'], FreeRoom.fromJson);
  final String timeSlot;
  final List<FreeRoom> rooms;
}

class StudentCalendar {
  StudentCalendar.fromJson(Json j)
    : name = j['name'] as String,
      startDate = j['start_date'] as String,
      endDate = j['end_date'] as String,
      exams = _list(j['exams'], (e) => (e['name'] as String, e['start'] as String, e['end'] as String)),
      holidays = _list(j['holidays'], (h) => (h['date'] as String, h['title'] as String, h['kind'] as String));
  final String name, startDate, endDate;
  final List<(String, String, String)> exams;

  /// Date, title and kind: HOLIDAY, EXAM, CLOSED or SPECIAL.
  final List<(String, String, String)> holidays;
}

/// A section a teacher may write to.
class TeacherGroup {
  TeacherGroup.fromJson(Json j)
    : token = j['token'] as String,
      courseCode = j['course_code'] as String,
      section = j['section'] as String;
  final String token, courseCode, section;
}
