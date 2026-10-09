// Mirrors backend/docs/API.md. Keep in sync with classtrack/schemas/*.

/** Everything the API can permit. Mirrors `Permission` in models/access.py. */
export type Permission =
  | "checking.submit"
  | "checking.correct"
  | "dashboard.view"
  | "classes.cancel"
  | "reschedules.decide"
  | "reschedules.any_teacher"
  | "reschedules.request"
  | "extra_classes.book"
  | "reports.department"
  | "routine.manage"
  | "semesters.manage"
  | "calendar.manage"
  | "settings.manage"
  | "staff.manage"
  | "teachers.manage"
  | "accounts.manage"
  | "roles.manage"
  | "audit.view"
  | "alerts.receive";

/** What a role makes a person: a teacher, floor staff, or neither. */
export type RoleKind = "TEACHER" | "STAFF" | "OFFICE";

export interface RoleRef {
  key: string;
  name: string;
  kind: RoleKind;
}

/** Stored, terminal statuses plus the two the backend derives from the clock. */
export type ClassStatus =
  | "UPCOMING"
  | "ONGOING"
  | "RUNNING"
  | "LATE"
  | "MISSED"
  | "NOT_CHECKED"
  | "MAKEUP_REQUESTED"
  | "MAKEUP_SCHEDULED"
  | "MAKEUP_COMPLETED"
  | "ONLINE_PENDING"
  | "ONLINE_APPROVED"
  | "ONLINE_REJECTED"
  | "CANCELLED";

export type CheckOutcome = "RUNNING" | "LATE" | "TEACHER_NOT_FOUND";
export type MakeupMode = "PHYSICAL" | "ONLINE";
export type MakeupStatus =
  | "SCHEDULED"
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "COMPLETED";
export type TeacherResponseValue = "CONFIRMED" | "DISPUTED";

export interface User {
  id: number;
  email: string;
  full_name: string;
  roles: RoleRef[];
  /** Everything any of the roles permits. Screens show and hide by it; the API
   *  checks again on every request. */
  permissions: Permission[];
  /** A teacher: their own classes, reports and reschedules. */
  is_teacher: boolean;
  /** Floor staff: their floors come first on the checking screen. */
  is_staff: boolean;
  teacher_initial: string | null;
  /** A teacher's faculty photo, when the directory has one. */
  photo_url?: string | null;
}

export interface CheckRecord {
  outcome: CheckOutcome;
  arrival_time: string | null;
  late_minutes: number | null;
  remark: string | null;
  checked_at: string;
  checked_by: string | null;
}

export interface Zone {
  key: string;
  building: string;
  floor: number | null;
  label: string;
  short_label: string;
  room_count: number;
  rooms: string[];
}

/** An account as the Accounts screen lists it. */
export interface Account {
  id: number;
  email: string;
  full_name: string;
  roles: (RoleRef & { id: number })[];
  teacher_initial: string | null;
  is_active: boolean;
}

/** A role and what it permits, for the Roles screen. */
export interface RoleInfo {
  id: number;
  key: string;
  name: string;
  description: string;
  kind: RoleKind;
  is_builtin: boolean;
  /** Super admin: every permission, always. */
  is_locked: boolean;
  permissions: Permission[];
  /** How many accounts hold it. */
  holders: number;
}

export interface PermissionInfo {
  key: Permission;
  group: string;
  label: string;
  description: string;
}

/** The signed-in user's own profile. */
export interface Profile {
  full_name: string;
  /** The names of the roles held. */
  roles: string[];
  is_teacher: boolean;
  /** What they type to sign in: a teacher's initial, else the email or ID. */
  sign_in: string;
  teacher_initial: string | null;
  designation: string | null;
  department: string | null;
  /** Where a teacher's absence reports are mailed. Null for anyone else. */
  contact_email: string | null;
  /** A teacher's faculty photo, when the directory has one. */
  photo_url: string | null;
}

export interface StaffMember {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  zones: string[];
}

/** The other end of a reschedule. */
export interface SlotRef {
  date: string;
  time_slot: string;
  room: string | null;
  instance_id: number | null;
  mode: MakeupMode | null;
  /** The makeup's progress; set on `rescheduled_to` only. */
  status: MakeupStatus | null;
}

export interface RoomRow {
  instance_id: number;
  date: string | null;
  time_slot: string | null;
  /** This class's own reporting state -- the teacher search mixes slots and days. */
  slot_state: "UPCOMING" | "ONGOING" | "CLOSED" | null;
  room: string;
  room_type: string;
  course_code: string;
  course_title: string | null;
  section: string;
  teacher_initial: string;
  teacher_name: string | null;
  scheduled_start: string;
  scheduled_end: string;
  is_makeup: boolean;
  /** Booked by the teacher on top of the routine: checked and counted, never owed. */
  is_extra: boolean;
  /** Set on a makeup: the missed class it recovers, on another day. */
  rescheduled_from: SlotRef | null;
  zone: string | null;
  /** "KT-3", "UNZONED" -- matches FloorSummary.key. */
  zone_key: string | null;
  status: ClassStatus | null;
  check: CheckRecord | null;
}

/** One floor card on the checking screen. */
export interface FloorSummary {
  key: string;
  /** "KT · Floor 3", "G1 · Ground floor", "Other rooms". */
  label: string;
  short_label: string;
  total: number;
  checked: number;
  /** One of the caller's assigned floors: listed first, never a restriction. */
  is_mine: boolean;
}

export interface CheckingScreen {
  date: string;
  time_slot: string;
  slot_state: "UPCOMING" | "ONGOING" | "CLOSED";
  window_closes_at: string;
  /** The caller's assigned floors (staff only). They order the list, not filter it. */
  zones: string[];
  floors: FloorSummary[];
  rooms: RoomRow[];
}

export interface CheckResponse {
  instance_id: number;
  status: ClassStatus | null;
  late_minutes: number | null;
  checked_by: string;
  checked_at: string;
  /** True when an admin or the committee corrected the record after its day. */
  outside_window: boolean;
}

export interface ClassInstance {
  id: number;
  date: string;
  day: string;
  time_slot: string;
  room: string;
  room_type: string;
  course_code: string;
  course_title: string | null;
  section: string;
  batch: string;
  teacher_initial: string;
  is_makeup: boolean;
  /** Booked by the teacher on top of the routine: checked and counted, never owed. */
  is_extra: boolean;
  status: ClassStatus | null;
  rescheduled_from: SlotRef | null;
  rescheduled_to: SlotRef | null;
  teacher_response: TeacherResponseValue | null;
  response_note: string | null;
  check: CheckRecord | null;
}

export interface DashboardSummary {
  scheduled_now: number;
  running: number;
  late: number;
  missed: number;
  not_checked: number;
  makeup_physical: number;
  online_approved: number;
}

export interface AttentionCounts {
  missed_today: number;
  not_checked_today: number;
  pending_online: number;
  pending_makeup: number;
  disputes: number;
}

export interface DashboardRow {
  instance_id: number;
  room: string;
  teacher_initial: string;
  teacher_name: string | null;
  course_code: string;
  section: string;
  time_slot: string;
  status: ClassStatus | null;
  late_minutes: number | null;
  checked_by: string | null;
  checked_at: string | null;
  is_makeup: boolean;
  /** Booked by the teacher on top of the routine: checked and counted, never owed. */
  is_extra: boolean;
  rescheduled_from: SlotRef | null;
}

/** The report bucket every class falls in -- exactly one. */
export type Outcome =
  | "CONDUCTED"
  | "LATE"
  | "MISSED"
  | "NOT_CHECKED"
  | "RESCHEDULED"
  | "CANCELLED"
  | "PENDING";

export interface DayRow extends DashboardRow {
  date: string;
  start: string;
  end: string;
  zone: string;
  zone_key: string;
  course_title: string | null;
  outcome: Outcome;
  remark: string | null;
  rescheduled_to: SlotRef | null;
}

export interface DayStatus {
  date: string;
  as_of: string;
  current_slot: string | null;
  rows: DayRow[];
}

export interface Dashboard {
  as_of: string;
  current_slot: string | null;
  summary: DashboardSummary;
  rows: DashboardRow[];
  attention: AttentionCounts;
}

export interface Conflict {
  type: "TEACHER" | "ROOM" | "SECTION" | "HOLIDAY" | "EXAM" | "SLOT";
  message: string;
  instance_id: number | null;
}

export interface ConflictReport {
  ok: boolean;
  overridable: boolean;
  conflicts: Conflict[];
}

export interface Makeup {
  id: number;
  original_instance_id: number;
  teacher_initial: string;
  mode: MakeupMode;
  date: string;
  time_slot: string;
  room: string | null;
  reason: string | null;
  status: MakeupStatus;
  decision_note: string | null;
  decided_at: string | null;
  created_instance_id: number | null;
  /** ONLINE only: submitted by the teacher when marking the class done. */
  drive_link: string | null;
  completed_at: string | null;
  /** When the rescheduled class ends; it can be marked done from then on. */
  ends_at: string | null;
  original_course_code: string | null;
  original_section: string | null;
  original_date: string | null;
  original_time_slot: string | null;
  original_room: string | null;
  teacher_name: string | null;
}

/** An empty room offered for a physical reschedule. */
export interface FreeRoom {
  room: string;
  room_type: string;
  zone: string;
}

/** A faculty member's details, as an admin adds or corrects them. */
export interface TeacherDetails {
  /** As the routine writes it; their sign-in once they have an account. */
  initial: string;
  name: string;
  designation: string | null;
  /** Where absence reports are mailed. */
  email: string | null;
  office_room: string | null;
  photo_url: string | null;
}

/** A faculty member, and whether an admin has given them a sign-in yet. */
export interface TeacherAccount extends TeacherDetails {
  id: number;
  has_account: boolean;
  account_active: boolean | null;
  /** For changing the account's roles; null without one. */
  account_id: number | null;
  roles: Account["roles"];
}

/** Counts per outcome. Every class falls in exactly one bucket. */
export interface Tally {
  total: number;
  /** Routine classes, excluding makeups. */
  scheduled: number;
  /** On time + late: the class happened. */
  held: number;
  conducted: number;
  late: number;
  missed: number;
  not_checked: number;
  rescheduled: number;
  cancelled: number;
  pending: number;
  makeup_held: number;
  /** Extra classes held, on top of the routine; also counted in `held`. */
  extra_held: number;
  /** Held ÷ (held + missed). Not-checked classes are left out. */
  conduct_rate: number;
  avg_late_minutes: number;
}

export interface FloorTally extends Tally {
  key: string;
  label: string;
  short_label: string;
}

export interface SlotTally extends Tally {
  time_slot: string;
}

export interface TrendPoint extends Tally {
  date: string;
}

export interface TeacherTally extends Tally {
  teacher_initial: string;
  teacher_name: string | null;
  courses: number;
  courses_below_minimum: number;
  min_course_held: number;
  /** At least one course is below the minimum so far. */
  flagged: boolean;
}

export interface CourseTally extends Tally {
  teacher_initial: string;
  teacher_name: string | null;
  course_code: string;
  course_title: string | null;
  section: string;
  below_minimum: boolean;
}

export interface ClassRow {
  instance_id: number;
  date: string;
  day: string;
  time_slot: string;
  room: string;
  zone: string;
  course_code: string;
  course_title: string | null;
  section: string;
  teacher_initial: string;
  teacher_name: string | null;
  status: ClassStatus | null;
  outcome: Outcome;
  late_minutes: number | null;
  remark: string | null;
  is_makeup: boolean;
  /** Booked by the teacher on top of the routine: checked and counted, never owed. */
  is_extra: boolean;
  rescheduled_from: SlotRef | null;
  rescheduled_to: SlotRef | null;
}

export interface ReportFilters {
  teacher?: string;
  floor?: string;
  course?: string;
  section?: string;
  slot?: string;
}

/** A stretch of a semester reported on by itself. */
export type Term = "MID" | "FINAL" | "FULL";

/**
 * What a period report covers: two dates, or a term of a semester. A term
 * also decides the minimum number of classes, so it is sent as itself.
 */
export type ReportPeriod =
  | { from: string; to: string }
  /** No semester named means the current one. */
  | { semester?: number; term: Term };

export interface Overview {
  range: { from: string; to: string };
  /** "Fall 2026 · Till mid-term" for a term; null for plain dates. */
  label: string | null;
  term: Term | null;
  filters: Record<string, string | null>;
  min_conducted: number;
  totals: Tally;
  granularity: "day" | "week" | "month";
  trend: TrendPoint[];
  by_floor: FloorTally[];
  by_slot: SlotTally[];
  by_teacher: TeacherTally[];
  by_course: CourseTally[];
}

export interface DailyReport {
  date: string;
  total_scheduled: number;
  total_checked: number;
  running: number;
  late: number;
  missed: number;
  not_checked: number;
  makeup: number;
  online_approved: number;
  unresolved: number;
  totals: Tally;
  by_floor: FloorTally[];
  by_slot: SlotTally[];
  /** Makeups held on this day for a class missed on another. */
  rescheduled_in: ClassRow[];
}

export interface TeacherReport {
  teacher_initial: string;
  teacher_name: string | null;
  range: { from: string; to: string };
  label: string | null;
  term: Term | null;
  min_conducted: number;
  total_scheduled: number;
  conducted: number;
  on_time: number;
  late: number;
  missed: number;
  not_checked: number;
  rescheduled: number;
  cancelled: number;
  makeup_scheduled: number;
  makeup_completed: number;
  makeup_pending: number;
  online_approved: number;
  unresolved: number;
  conduct_rate: number;
  avg_late_minutes: number;
  flagged: boolean;
  courses: CourseTally[];
  classes: ClassRow[];
}

export interface StaffReport {
  range: { from: string; to: string };
  label: string | null;
  assigned: number;
  checked: number;
  not_checked: number;
  completion_rate: number;
  rows: {
    user_id: number;
    name: string;
    assigned: number;
    checked: number;
    completion_rate: number;
  }[];
}

export interface Notification {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  actor_id: number | null;
  actor_name: string | null;
  entity_type: string;
  entity_id: number;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string | null;
  created_at: string;
}

export interface Routine {
  id: number;
  department: string;
  version: string;
  semester: string | null;
  source_filename: string | null;
  is_active: boolean;
  session_count: number;
  published_at: string | null;
}

export interface IngestionReport {
  department: string;
  version: string;
  routine_id: number | null;
  cells_read: number;
  sessions_created: number;
  days_covered: Record<string, number>;
  reserved: number;
  skipped: number;
  skipped_sample: {
    page: number;
    day: string;
    time_slot: string;
    room: string;
    text: string;
  }[];
}

export interface RoutineReview {
  routine: Routine;
  conflicts: {
    type: string;
    message: string;
    day?: string;
    time_slot?: string;
  }[];
  sessions: {
    day: string;
    time_slot: string;
    room: string;
    course_code: string;
    section: string;
    teacher: string;
    is_lab: boolean;
  }[];
  total_sessions: number;
}

export interface Holiday {
  id: number;
  semester_id: number;
  date: string;
  title: string;
  kind: "HOLIDAY" | "EXAM" | "CLOSED" | "SPECIAL";
}

export interface Semester {
  id: number;
  name: string;
  department: string;
  routine_id: number | null;
  start_date: string;
  end_date: string;
  /** The mid-term exam period, inclusive. Null until announced. */
  mid_exam_start: string | null;
  mid_exam_end: string | null;
  /** First day of the final exams; teaching ends the day before. */
  final_exam_start: string | null;
  /** The semester the department is running now. */
  is_active: boolean;
}

export interface SemesterDates {
  name: string;
  start_date: string;
  end_date: string;
  mid_exam_start: string | null;
  mid_exam_end: string | null;
  final_exam_start: string | null;
}

export interface TermSpan {
  term: Term;
  label: string;
  /** Null while the exam dates the term needs are unset. */
  from: string | null;
  to: string | null;
  /** False until the dates are set and the term has begun. */
  available: boolean;
}

/** A semester as the report period picker sees it -- teachers included. */
export interface ReportSemester {
  id: number;
  name: string;
  is_active: boolean;
  start_date: string;
  end_date: string;
  terms: TermSpan[];
}


export interface UnreportedClass {
  instance_id: number;
  date: string;
  time_slot: string;
  room: string;
  zone: string;
  course_code: string;
  section: string;
  teacher_initial: string;
  hours_since: number;
}

export type Urgency = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface StaffMisses {
  user_id: number;
  name: string;
  email: string;
  zones: string[];
  total: number;
  today: number;
  this_week: number;
  urgency: Urgency;
  classes: UnreportedClass[];
}

export interface UnreportedReport {
  as_of: string;
  range: { from: string; to: string };
  summary: {
    total: number;
    today: number;
    this_week: number;
    staff_with_misses: number;
    unassigned: number;
  };
  by_staff: StaffMisses[];
  /** Classes on floors nobody covers — an admin gap, not a staff failure. */
  unassigned: UnreportedClass[];
}

/** A course-section a teacher may book an extra class for. */
export interface ExtraSection {
  course_code: string;
  course_title: string;
  section: string;
  /** The kind of room it usually meets in, offered first. */
  room_type: string;
}
