# Google Play listing: everything to paste and upload

Everything Play Console asks for, in the order it asks. Files are beside this one.
The process around it (account, testing tracks, signing) is in
[docs/PLAY_STORE.md](../../docs/PLAY_STORE.md).

## 1. Create app

| Field | Value |
|---|---|
| App name | ClassTrack: DIU CSE Classes |
| Default language | English (United States) – en-US |
| App or game | App |
| Free or paid | Free |

## 2. Main store listing (*Grow users → Store presence → Main store listing*)

| Field | Value |
|---|---|
| App name (≤ 30) | `ClassTrack: DIU CSE Classes` (27) |
| Short description (≤ 80) | `Class routine, makeups and alerts for DIU CSE students, teachers and staff.` (75) |
| Full description (≤ 4000) | Below (2,224) |
| App icon | `icon-512.png`: 512 × 512, 32-bit PNG |
| Feature graphic | `feature-graphic.png`: 1024 × 500 |
| Phone screenshots (2–8) | `screenshots/1-routine.png` … `8-sign-in.png`: 1080 × 1920, in that order |
| Tablet screenshots | None: optional, and the app is designed for phones |
| Video | None: optional |

The screenshots are the real app screens, with made-up teacher names, under one caption each:

| File | Caption |
|---|---|
| 1-routine | Your whole week, one tap away |
| 2-class | Every class: room, teacher and notes |
| 3-radar | Makeups and extra classes, ahead of time |
| 4-updates | Know the moment a class moves |
| 5-rooms | Find an empty room to study |
| 6-calendar | Holidays and exams, counted down |
| 7-checking | Staff check each room in one tap |
| 8-sign-in | Made for DIU CSE. Students need no sign-in |

### Full description

```
ClassTrack keeps the classes of the Department of Computer Science and Engineering, Daffodil International University, on track: students always know where their next class is and when one moves, teachers see their week and reschedule missed classes, and office staff check every room in a tap.

FOR STUDENTS · NO SIGN-IN
Pick your batch, section and lab group once. That's it.
• My Routine: today's classes and the whole week, with the class on now or next at the top: room, time and teacher.
• Class Alarm: a reminder a few minutes before every class, makeups and extra classes included. It can ring from your phone with no internet.
• Change Alerts: know the moment a class of yours is cancelled, moved, or gets a makeup or extra class.
• Makeup Radar: every makeup and extra class for your section over the next four weeks, with the room or the link to join online.
• Section Notices: notes from your teachers and the department, for your section.
• Free Room Finder: empty rooms now and later today, for group study.
• Teacher Card: tap a class for its teacher's designation and office room.
• Semester Calendar: holidays, and the days left until the mid-term and final exams.
• Works offline: your routine opens with no signal.

FOR TEACHERS
• Pocket Timetable: the class on now, today as a timeline, and any week at a glance.
• Class Alarm before each of your classes, and alerts as soon as anything changes.
• Reschedule Anywhere: find an empty room for a missed class and book it from your phone, or ask to hold it online.
• Heads-up: tell a section about one class, a quiz or laptops, and it shows on the class for them.
• Semester Scorecard: classes held, late and missed, and each course against its minimum.

FOR OFFICE STAFF
• Tap-to-Check: walk your floors and report each room in a single tap: running, late or absent.
• Keep checking with no signal: checks wait on the phone and are sent, with the time you made them, as soon as you are back online.

Students never see whether a teacher was late or absent: only when a class is on, moved or cancelled.

Teachers and staff sign in with the account the department gives them. ClassTrack was built for the Department of CSE, Daffodil International University.
```

## 3. Store settings (*Store presence → Store settings*)

| Field | Value |
|---|---|
| App category | Education |
| Tags | Education, Productivity, Schedule (pick the closest Play offers) |
| Email | contactshakibhere@gmail.com |
| Website | https://class.bitstreamhq.com |
| Phone | Leave empty (optional) |
| External marketing | On |

## 4. Countries and pricing (*Monetize → Pricing* and *Release → Production → Countries*)

| Field | Value |
|---|---|
| Price | Free |
| Countries | Bangladesh. Add others only if the department wants students abroad to find it |
| In-app purchases, ads | None |

## 5. App content (*Policy → App content*)

| Section | Answer |
|---|---|
| Privacy policy | https://class.bitstreamhq.com/privacy |
| Ads | No, my app does not contain ads |
| App access | All or some functionality is restricted: see *App access* below |
| Content rating | See *Content rating* below |
| Target audience | 18 and over |
| Appeal to children | No |
| News app | No |
| COVID-19 apps | Not a COVID-19 app |
| Data safety | See *Data safety* below |
| Government app | No |
| Financial features | My app doesn't provide any financial features |
| Health apps | My app doesn't have any health features |
| Advertising ID | No (the app uses no ads or analytics SDK) |

### App access: instructions to paste

```
Students use the app without an account: on the first screen tap "I'm a student", pick any batch and section (for example 72, then B), and tap "Show my routine". This shows the routine, Makeup Radar, Updates, Free Room Finder and Semester Calendar.

Signing in is only for teachers and office staff of the Department of CSE, Daffodil International University, with accounts the department issues. Staff accounts record real class reports, and an absence report emails the teacher, so we cannot give a public test account for that part.
```

If Play asks for credentials anyway, ask for a demo account that only sees sample data:
never give a real staff account (see the release guide).

### Content rating (IARC questionnaire)

| Question | Answer |
|---|---|
| Category | All other app types (Utility, Productivity, Communication or Other) |
| Violence, fear, sexuality, language, controlled substances, gambling | No to every one |
| Do users interact or exchange content? | Yes: teachers and the department send notices to sections. No open chat, no strangers |
| Does the app share the user's current location with other users? | No |
| Does the app allow purchases of digital goods? | No |
| Is the app a web browser or search engine? | No |

Expected rating: Everyone / 3+ (IARC), which is fine for an 18+ audience.

### Data safety

| Question | Answer |
|---|---|
| Does your app collect or share any of the required user data types? | Yes |
| Is all of the user data collected by your app encrypted in transit? | Yes |
| Do you provide a way for users to request that their data is deleted? | Yes: by email, as the privacy policy says. Accounts are created by the department, not in the app, so no in-app deletion link is required |
| Shared with third parties | None (Firebase and the email service process it on our behalf, which Play does not count as sharing) |

Data collected, none of it shared, none processed ephemerally, all required for those who
sign in (students give none of it):

| Data type | Purpose | What it is |
|---|---|---|
| Personal info → Name | App functionality, Account management | Teachers' and staff names |
| Personal info → Email address | App functionality, Account management | Sign-in, and a teacher's address for absence reports |
| Personal info → User IDs | App functionality, Account management | Teacher initial or employee ID |
| App activity → Other actions | App functionality | Class checks staff make; reschedules |
| App activity → Other user-generated content | App functionality | Remarks on checks; notes teachers send to students |
| Device or other IDs | App functionality | The Firebase push token, to deliver notifications (students too) |

Not collected: location, contacts, photos, videos, audio, files, messages, calendar, health,
fitness, financial info, web browsing, crash logs, diagnostics, analytics.

## 6. Release (*Testing → Internal testing*, then *Production*)

| Field | Value |
|---|---|
| App bundle | `mobile/build/app/outputs/bundle/release/app-release.aab` (`flutter build appbundle --release`) |
| Version | 1.3.0 (build 4) |
| Release name | 1.3.0 |
| App signing | Let Google manage the app signing key (the default) |

### Release notes (≤ 500)

```
<en-US>
• Works offline: your routine opens with no signal, and staff can keep checking rooms; checks are sent when you are back online.
• Class Alarm can ring from your phone with no internet.
• Students: My Routine, Makeup Radar, Section Notices, Free Room Finder and the Semester Calendar, with no sign-in.
• Teachers: send a heads-up about a class, and add a join link to an online makeup.
</en-US>
```
