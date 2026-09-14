// Mirrors backend/docs/API.md. Keep in sync with classtrack/schemas/*.

export type Role =
  | "SUPER_ADMIN"
  | "HOD"
  | "ASSOCIATE_HEAD"
  | "COMMITTEE"
  | "STAFF"
  | "TEACHER";

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
  role: Role;
  teacher_initial: string | null;
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

export interface StaffMember {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  zones: string[];
}

export interface RoomRow {
  instance_id: number;
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
  status: ClassStatus | null;
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
}

export interface Dashboard {
  as_of: string;
  current_slot: string | null;
  summary: DashboardSummary;
  rows: DashboardRow[];
  attention: AttentionCounts;
}

export interface Conflict {
  type: "TEACHER" | "ROOM" | "SECTION" | "HOLIDAY" | "SLOT";
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

/** A faculty member, and whether an admin has given them a sign-in yet. */
export interface TeacherAccount {
  initial: string;
  name: string;
  designation: string | null;
  has_account: boolean;
  account_active: boolean | null;
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
}

export interface TeacherReport {
  teacher_initial: string;
  teacher_name: string | null;
  range: { from: string; to: string };
  total_scheduled: number;
  conducted: number;
  late: number;
  missed: number;
  not_checked: number;
  makeup_scheduled: number;
  makeup_completed: number;
  makeup_pending: number;
  online_approved: number;
  unresolved: number;
}

export interface StaffReport {
  range: { from: string; to: string };
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
  is_active: boolean;
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
