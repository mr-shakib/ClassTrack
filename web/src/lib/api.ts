import type {
  Account,
  AuditEntry,
  CheckOutcome,
  CheckResponse,
  CheckingScreen,
  ClassInstance,
  ConflictReport,
  Dashboard,
  DailyReport,
  DayStatus,
  FreeRoom,
  Holiday,
  IngestionReport,
  Makeup,
  MakeupMode,
  Notification,
  Overview,
  Profile,
  ReportFilters,
  ReportPeriod,
  ReportSemester,
  Role,
  RoomRow,
  Routine,
  RoutineReview,
  Semester,
  SemesterDates,
  StaffMember,
  StaffReport,
  TeacherAccount,
  TeacherReport,
  TeacherResponseValue,
  UnreportedReport,
  User,
  Zone,
} from "./types";

/** An error carrying the backend's `{detail, code, context}` shape. */
export class ApiError extends Error {
  code: string;
  status: number;
  context?: unknown;

  constructor(message: string, status: number, code = "error", context?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.context = context;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    // Same-origin via the Next.js rewrite, so the session cookie just works.
    credentials: "include",
    headers:
      init.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json", ...(init.headers ?? {}) },
    cache: "no-store",
    ...init,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const body = text ? JSON.parse(text) : null;

  if (!res.ok) {
    throw new ApiError(
      body?.detail ?? `Request failed (${res.status})`,
      res.status,
      body?.code ?? "error",
      body?.context,
    );
  }
  return body as T;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined });
const del = <T>(path: string) => request<T>(path, { method: "DELETE" });

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const s = search.toString();
  return s ? `?${s}` : "";
};

export const api = {
  // --- auth ---------------------------------------------------------------
  /** `username` is an email address, or a teacher's initial. */
  login: (username: string, password: string) =>
    post<User>("/auth/login", { username, password }),
  logout: () => post<{ detail: string }>("/auth/logout"),
  me: () => get<User>("/auth/me"),
  profile: () => get<Profile>("/auth/profile"),
  /** A teacher's address for absence reports. */
  updateProfile: (contact_email: string) =>
    request<Profile>("/auth/profile", {
      method: "PATCH",
      body: JSON.stringify({ contact_email }),
    }),
  changePassword: (current_password: string, new_password: string) =>
    post<{ detail: string }>("/auth/password", { current_password, new_password }),

  // --- staff checking -----------------------------------------------------
  checkingRooms: (date?: string, slot?: string) =>
    get<CheckingScreen>(`/checking/rooms${qs({ date, slot })}`),
  submitCheck: (
    instanceId: number,
    payload: {
      outcome: CheckOutcome;
      arrival_time?: string | null;
      remark?: string | null;
      /** Optional note when an admin or the committee corrects a record after its day. */
      reason?: string | null;
    },
  ) => post<CheckResponse>(`/checking/${instanceId}`, payload),
  /** A teacher's classes over a range, newest first -- to find one to correct. */
  searchChecking: (teacher: string, from?: string, to?: string) =>
    get<RoomRow[]>(`/checking/search${qs({ teacher, from, to })}`),

  // --- dashboard ----------------------------------------------------------
  dashboard: () => get<Dashboard>("/dashboard/live"),
  dayStatus: (date?: string) => get<DayStatus>(`/dashboard/day${qs({ date })}`),
  slots: () => get<{ days: string[]; slots: string[] }>("/meta/slots"),

  // --- instances ----------------------------------------------------------
  instances: (params: {
    date?: string;
    teacher?: string;
    room?: string;
    section?: string;
    status?: string;
    /** Missed, or reported absent and not yet settled by the sweep. */
    needs_reschedule?: boolean;
    limit?: number;
  }) => get<ClassInstance[]>(`/instances${qs(params)}`),
  instance: (id: number) => get<ClassInstance>(`/instances/${id}`),
  respond: (id: number, response: TeacherResponseValue, note?: string) =>
    post<ClassInstance>(`/instances/${id}/respond`, { response, note }),
  cancelInstance: (id: number, reason: string) =>
    post<ClassInstance>(`/instances/${id}/cancel`, { reason }),

  // --- makeup -------------------------------------------------------------
  checkConflict: (payload: {
    date: string;
    /** A routine slot, or `start_time` — exactly one of the two. */
    time_slot?: string | null;
    start_time?: string | null;
    teacher_initial?: string | null;
    room?: string | null;
    section?: string | null;
  }) => post<ConflictReport>("/makeup/check-conflict", payload),
  freeRooms: (date: string, slot: string) =>
    get<FreeRoom[]>(`/makeup/free-rooms${qs({ date, time_slot: slot })}`),
  createMakeup: (payload: {
    original_instance_id: number;
    mode: MakeupMode;
    date: string;
    /** A routine slot, or `start_time` — exactly one of the two. */
    time_slot?: string | null;
    /** ONLINE only: a 24-hour `HH:MM` off the clock; the class runs 90 minutes. */
    start_time?: string | null;
    room?: string | null;
    reason?: string | null;
    /** ONLINE only, optional: for the HoD or Associate Head to open while deciding. */
    drive_link?: string | null;
  }) => post<Makeup>("/makeup", payload),
  makeups: (status?: string) => get<Makeup[]>(`/makeup${qs({ status })}`),
  completeMakeup: (id: number, driveLink?: string) =>
    post<Makeup>(
      `/makeup/${id}/complete`,
      driveLink ? { drive_link: driveLink } : undefined,
    ),

  // --- approvals ----------------------------------------------------------
  pendingApprovals: () => get<Makeup[]>("/approvals/pending"),
  decide: (id: number, decision: "APPROVE" | "REJECT", note?: string) =>
    post<Makeup>(`/approvals/${id}/decide`, { decision, note }),

  // --- reports ------------------------------------------------------------
  dailyReport: (date?: string) => get<DailyReport>(`/reports/daily${qs({ date })}`),
  /** Semesters and their terms -- open to teachers, for their own report. */
  reportSemesters: () => get<ReportSemester[]>("/reports/semesters"),
  teacherReport: (teacher: string, period: ReportPeriod) =>
    get<TeacherReport>(`/reports/teacher${qs({ teacher, ...period })}`),
  overview: (period: ReportPeriod, filters: ReportFilters = {}) =>
    get<Overview>(`/reports/overview${qs({ ...period, ...filters })}`),
  staffReport: (period: ReportPeriod) =>
    get<StaffReport>(`/reports/staff${qs({ ...period })}`),
  unreported: (from?: string, to?: string) =>
    get<UnreportedReport>(`/reports/unreported${qs({ from, to })}`),

  // --- notifications ------------------------------------------------------
  notifications: (unread = false) =>
    get<Notification[]>(`/notifications${qs({ unread })}`),
  markRead: (id: number) => post<{ detail: string }>(`/notifications/${id}/read`),
  markAllRead: () => post<{ detail: string }>("/notifications/read-all"),

  // --- admin --------------------------------------------------------------
  ingestRoutine: (form: FormData) =>
    request<IngestionReport>("/admin/routine/ingest", { method: "POST", body: form }),
  routines: () => get<Routine[]>("/admin/routines"),
  routineReview: (id: number) => get<RoutineReview>(`/admin/routine/${id}/review`),
  activateRoutine: (id: number, semesterId?: number) =>
    post<Record<string, unknown>>(`/admin/routine/${id}/activate`, {
      semester_id: semesterId ?? null,
    }),
  generateInstances: () => post<Record<string, unknown>>("/admin/instances/generate"),
  semesters: () => get<Semester[]>("/admin/semesters"),
  createSemester: (payload: SemesterDates & { make_current: boolean }) =>
    post<Semester>("/admin/semesters", payload),
  /** Every date is replaced; the semester's classes follow at once. */
  updateSemester: (id: number, payload: SemesterDates) =>
    put<{ semester: Semester; generation: Record<string, unknown> | null }>(
      `/admin/semesters/${id}`,
      payload,
    ),
  activateSemester: (id: number) => post<Semester>(`/admin/semesters/${id}/activate`),
  holidays: (semesterId?: number) =>
    get<Holiday[]>(`/admin/holidays${qs({ semester_id: semesterId })}`),
  addHoliday: (payload: { date: string; title: string; kind?: string; semester_id?: number }) =>
    post<Holiday>("/admin/holidays", payload),
  removeHoliday: (id: number) => del<{ detail: string }>(`/admin/holidays/${id}`),
  settings: () => get<Record<string, string>>("/admin/settings"),
  updateSettings: (payload: {
    missed_threshold_minutes?: number;
    min_conducted_classes?: number;
    min_conducted_before_mid?: number;
  }) => put<Record<string, string>>("/admin/settings", payload),
  audit: (params: { entity_type?: string; entity_id?: number; limit?: number }) =>
    get<AuditEntry[]>(`/admin/audit${qs(params)}`),
  teachers: (q?: string) => get<TeacherAccount[]>(`/admin/teachers${qs({ q })}`),
  createTeacherAccount: (initial: string, password: string) =>
    post<TeacherAccount>(`/admin/teachers/${encodeURIComponent(initial)}/account`, {
      password,
    }),
  createAllTeacherAccounts: (password: string) =>
    post<{ created: number }>("/admin/teachers/accounts", { password }),
  resetTeacherPassword: (initial: string, password: string) =>
    put<{ detail: string }>(`/admin/teachers/${encodeURIComponent(initial)}/password`, {
      password,
    }),
  users: () => get<Account[]>("/admin/users"),
  createUser: (payload: {
    email: string;
    full_name: string;
    role: Role;
    password: string;
  }) => post<Account>("/admin/users", payload),
  updateUser: (
    id: number,
    payload: { full_name?: string; role?: Role; is_active?: boolean; password?: string },
  ) => request<Account>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  zones: () => get<Zone[]>("/admin/zones"),
  staff: () => get<StaffMember[]>("/admin/staff"),
  createStaff: (payload: {
    full_name: string;
    email: string;
    password: string;
    zones: string[];
  }) => post<StaffMember>("/admin/staff", payload),
  assignZones: (userId: number, zones: string[]) =>
    put<StaffMember>(`/admin/staff/${userId}/zones`, { zones }),
};

/** Where a report PDF downloads from. Same-origin, so the session cookie goes along. */
export const pdfUrl = {
  teacher: (teacher: string, period: ReportPeriod) =>
    `/api/v1/reports/teacher/pdf${qs({ teacher, ...period })}`,
  overview: (period: ReportPeriod, filters: ReportFilters = {}) =>
    `/api/v1/reports/overview/pdf${qs({ ...period, ...filters })}`,
};

/** The routine lattice. Fixed, so the UI need not fetch it to render a picker. */
export const SLOTS = [
  "08:30-10:00",
  "10:00-11:30",
  "11:30-01:00",
  "01:00-02:30",
  "02:30-04:00",
  "04:00-05:30",
] as const;

export const DAYS = [
  "Saturday",
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
] as const;

export const todayISO = () => {
  // The department works in Asia/Dhaka; use it rather than the browser zone so
  // a device set to another timezone does not show the wrong day's classes.
  const now = new Date();
  const dhaka = new Date(now.getTime() + (6 * 60 + now.getTimezoneOffset()) * 60_000);
  return dhaka.toISOString().slice(0, 10);
};
