# ClassTrack mobile

The ClassTrack app for the people who use it on their feet: **students** following their
section's routine with no account, **office staff** checking classes room by room, and
**teachers** seeing their classes and rescheduling missed ones. Admin work (dashboards,
reports, approvals, routines) stays on the website.

**Stack:** Flutter (Android + iOS) · talks to the same FastAPI backend as `web/`

## What it does

| Who | Tab | Mirrors on the web |
|---|---|---|
| Students (no sign-in) | **Routine**: the class on now or next, and the week a day at a time; tap a class for its Teacher Card, a note from the teacher, where it moved, or the join link of an online makeup | `/students` |
| Students | **Makeups** (Makeup Radar): makeups, extra classes and cancellations for their groups, four weeks ahead | `/students` → Makeup Radar |
| Students | **Updates**: Change Alerts when a class moves, Section Notices from teachers and the department | `/students` → Updates |
| Students | **Rooms** (Free Room Finder): empty rooms today or tomorrow, by slot | `/students` → Free rooms |
| Students | **More**: Class Alarm on or off, change section, Semester Calendar, appearance, and *Staff or teacher? Sign in* | `/students` → Calendar |
| Office staff, committee, admins who check | **Checking**: pick a floor, then one tap per room (running / late / absent); *Find by teacher* to correct a past record | `/staff` |
| Teachers | **Home**: the class on now (or next), what is waiting on them, today as a timeline, and the week as a timetable (days across, slots down, any week back or forward; tap a class for its details) | — |
| Teachers | **Reschedule**: *Reschedule required*, makeups under way with mark-done and Drive link, extra classes, past reschedules | `/teacher`, `/teacher/makeup`, `/teacher/extra` |
| Everyone | **Alerts**: tapping one opens what it is about. Each is also pushed to the phone, as are notifications admins write; teachers are reminded before each class | the bell |
| Everyone | **Profile**, as cards: who they are; for a teacher the semester (share held, conducted, late, missed, not checked) and each course against the minimum; for staff their floors; then details and settings (appearance, password, sign out) | `/profile` |

A teacher who also checks classes gets Home, Reschedule and Checking. An account with neither is pointed to the website.
A teacher writes to their students from Home (*Message your students*), sends a heads-up
about one class from its details in the week, and adds an online makeup's join link on its card.

**Students** tap *I'm a student* on the sign-in screen and pick their batch, section, lab
group and any retake groups (`lib/student/`). The choice is kept on the phone; nothing is
signed in. The phone follows the Firebase topics the API names for those groups
(`/students/topics`): every notice to them, and, while Class Alarm is on, the reminder before
each class. It follows them again on each launch, since a new token follows none.

Home reads the teacher's classes from today to three weeks ahead (`/instances?from=&to=`). A server
older than that filter sends every class instead, and the app keeps only the window.

## Run

```bash
cd mobile
flutter pub get

# Against production (the default API_BASE)
flutter run

# Against a local backend from the Android emulator (10.0.2.2 is the host machine)
flutter run --dart-define=API_BASE=http://10.0.2.2:8000/api/v1
```

Debug builds may use plain `http` for a local backend; release builds cannot.

## Build

```bash
flutter build apk --release            # android: build/app/outputs/flutter-apk/app-release.apk
flutter build ipa                      # iOS, on a Mac with Xcode
```

Until the app is on the Play Store, people get it from the website's **/app** page, which
offers the universal `app-release.apk` (every Android phone, ~56 MB); publishing it is
copying it to the server ([deploy/README.md](../deploy/README.md#the-android-app)). Raise
`version` in `pubspec.yaml` for every release, the build number included: Android only
installs an APK over the old one when its build number is higher.

The release build is still signed with the debug key (`android/app/build.gradle.kts`).
Set up an upload key before publishing to Play.

## How it signs in

The backend sets its session as a cookie for the browser and also accepts the same token
as `Authorization: Bearer` ([`api/deps.py`](../backend/src/classtrack/api/deps.py)). The app
reads the token off the sign-in response's `Set-Cookie`, keeps it in the platform keystore
(`flutter_secure_storage`), and sends it as a header. The backend needs no change for the app.

The user is cached beside the token, so the app opens straight onto its tabs and refreshes
the user in the background. A 401 signs out with a notice on the sign-in screen.

## Layout

| Path | Holds |
|---|---|
| `lib/api/` | `client.dart` (every endpoint the app calls), `models.dart` (mirrors `web/src/lib/types.ts`) |
| `lib/session.dart` | Sign-in, the stored token, the cached user |
| `lib/push.dart` | Push notifications: registering the phone, and the pushes tapped or received while open |
| `lib/staff/` | Checking: floors, a floor's rooms, the room card, find by teacher |
| `lib/teacher/` | Home, Reschedule, the reschedule and extra-class screens, and `teacher_data.dart`, which loads what all three teacher tabs show |
| `lib/screens/` | Sign-in, the tab shell, alerts, profile |
| `lib/theme.dart` | The palette from `web/src/app/globals.css`, and a layered charcoal dark built from the same tokens |
| `lib/settings.dart` | The appearance choice: light by default, dark, or match the phone; kept through sign-out |
| `lib/util/time.dart` | The six slots, and dates on Dhaka's clock |

## Push notifications

Every notification the Alerts tab shows is pushed to the phone too, through Firebase
Cloud Messaging, and a teacher is reminded before each class they hold — routine, makeup
or extra — as long before as an admin sets (**Admin → Rules** on the website; 10 minutes
unless changed). Reminders are pushed only; they never fill up Alerts.

- **The phone is registered** on each sign-in and launch (`POST /notifications/devices`),
  asking for notification permission the first time on Android 13+ and iOS (older Android
  allows notifications from install, so it never asks), and **let go on sign-out**. A
  session that merely expired keeps its pushes, so reminders do not stop when it lapses;
  they move to whoever signs in on the phone next.
- **Tapping a push** opens what it is about, as tapping it in Alerts does; a reminder
  opens Home. One that arrives while the app is open shows as a bar with *Open*.
- **Android channels**: *Class reminders* and *Alerts* (`MainActivity.kt`), so either
  can be silenced in the phone's settings.

The Firebase project is **classtrack-diu**. `lib/firebase_options.dart`,
`android/app/google-services.json` and `firebase.json` hold its app IDs and are meant to
be committed (they are not secrets; every build carries them). `flutterfire configure`
rewrites them. If Firebase cannot start, the app runs as before, without push. The
backend needs the same project's service account
([deploy/README.md](../deploy/README.md#push-notifications)).

**iOS** is registered in the project but needs a Mac to finish: in Xcode, *Signing &
Capabilities* → add **Push Notifications**, and in the Firebase console → Project
settings → Cloud Messaging, upload an APNs key (Apple Developer → Keys). The deployment
target is iOS 15, which Firebase requires.

## Rules kept from the web app

- **Missed and Not checked never share a colour**: red is a teacher-side problem, purple a
  staff-side one ([`theme.dart`](lib/theme.dart)).
- **Running is one tap, late is two**: the arrival time is prefilled with now.
- **Days are Dhaka's**, whatever zone the phone is set to.

## Test

```bash
flutter analyze
flutter test
```
