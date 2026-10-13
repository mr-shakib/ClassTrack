# ClassTrack mobile

The ClassTrack app for the two groups who use it on their feet: **office staff** checking
classes room by room, and **teachers** seeing their classes and rescheduling missed ones.
Admin work (dashboards, reports, approvals, routines) stays on the website.

**Stack:** Flutter (Android + iOS) · talks to the same FastAPI backend as `web/`

## What it does

| Who | Tab | Mirrors on the web |
|---|---|---|
| Office staff, committee, admins who check | **Checking**: pick a floor, then one tap per room (running / late / absent); *Find by teacher* to correct a past record | `/staff` |
| Teachers | **My classes**: semester figures, *Reschedule required*, open reschedules with mark-done and Drive link, today, courses against the minimum, past reschedules | `/teacher` |
| Teachers | Reschedule a missed class (in a room, or online at any time) and book extra classes | `/teacher/makeup`, `/teacher/extra` |
| Everyone | **Alerts** (tapping one opens what it is about) and **Profile** (absence email, password, sign out) | the bell, `/profile` |

A teacher who also checks classes gets both tabs. An account with neither is pointed to the website.

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
| `lib/staff/` | Checking: floors, a floor's rooms, the room card, find by teacher |
| `lib/teacher/` | My classes, reschedule, extra class, and the booking pieces they share |
| `lib/screens/` | Sign-in, the tab shell, alerts, profile |
| `lib/theme.dart` | The palette from `web/src/app/globals.css`, light and dark |
| `lib/util/time.dart` | The six slots, and dates on Dhaka's clock |

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
