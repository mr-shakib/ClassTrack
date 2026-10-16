# Releasing the app on Google Play

What is ready in the repo, and what has to be done in Play Console by the account owner.

## What is ready

| Item | Where |
|---|---|
| Signed app bundle | `cd mobile && flutter build appbundle --release` → `build/app/outputs/bundle/release/app-release.aab` |
| Upload key | `~/.classtrack-keys/upload-keystore.p12` and `key.properties` beside it (linked from `mobile/android/key.properties`). Never in git |
| Everything for the listing and the policy forms | [`mobile/store/listing.md`](../mobile/store/listing.md) |
| Icon, feature graphic, 8 captioned screenshots | [`mobile/store/`](../mobile/store) |
| Privacy policy | https://class.bitstreamhq.com/privacy, linked from the app's Profile and More |
| Package name | `com.bitstreamhq.classtrack`: permanent once published |
| Version | `mobile/pubspec.yaml`: `1.3.0+4`. Raise the `+N` build number for every upload |
| Target API | 36 (Flutter's default), above Play's minimum |

**Back up the upload key now.** Copy both files in `~/.classtrack-keys/` somewhere safe
(a password manager, or an encrypted drive). The password is in `key.properties`. With Play
App Signing a lost upload key can be reset through Play support, but it takes days.

## Before you start

- **A developer account.** A personal account costs a one-time $25. New personal accounts
  must run a **closed test with at least 12 testers for 14 days** before they can publish to
  production; check the current numbers in Play Console. An **organization** account (it
  needs a D-U-N-S number for the university or the company) skips that test.
- **Permission to use the university's name and logo.** The app shows the DIU logo and
  names the department. Play removes apps that appear to impersonate an organization, so
  get written permission from the department (the HoD) before submitting, and keep it to
  hand in case Play asks. Publishing under an account in the department's name avoids the
  question.

## In Play Console

1. **Create the app.** App name *ClassTrack: DIU CSE Classes*, default language English,
   App, Free.
2. **App signing.** Keep the default: *Google manages the app signing key*. The upload key
   above only proves the uploads are yours.
3. **Upload the bundle** to *Testing → Internal testing* first, install it from the test
   link, and try it on a real phone (see *Test on a phone* below). Then *Closed testing*
   with your 12 testers if the account needs it, then *Production*.
4. **Store listing, store settings, countries, and every *App content* form:** paste and
   upload from [`mobile/store/listing.md`](../mobile/store/listing.md), section by section.
   It has the answers for data safety, content rating, target audience and app access.

### App access, and why not a real account

Play reviewers expect a test sign-in for the restricted part. **Do not give them a real
staff account**: a reviewer tapping *Teacher absent* would record it against a real class
and email a real teacher. The listing sheet has instructions to paste that point reviewers
to student mode. If Play still asks for credentials, ask for a demo account that only sees
sample data, which needs a small server change.

## Test on a phone

Before production, on a real Android phone from the internal-testing link:

- Student mode: pick a section, check My Routine, allow alarms in More, and see Class Alarm
  ring with the internet off.
- Staff: open Checking with a signal, switch to flight mode, mark a few rooms, switch back,
  and see them sent.
- Notifications arrive, and tapping one opens the right screen.

## Moving people from the website APK to Play

The APKs offered on `/app` so far are signed with the debug key; Play installs are signed
by Google's key. Android will not update one over the other, so:

1. Stop publishing APKs on the website once the Play version is out.
2. Set `CLASSTRACK_ANDROID_PLAY_URL=https://play.google.com/store/apps/details?id=com.bitstreamhq.classtrack`
   in `/srv/classtrack/.env` and recreate the API container: `/app` then sends everyone to
   Play.
3. Ask people who installed from the website to uninstall it once and install from Play.
   Teachers and staff sign in again; students pick their section again.

## Each later release

1. Raise `version` in `mobile/pubspec.yaml`, the build number included (`1.3.1+5`).
2. `cd mobile && flutter build appbundle --release`.
3. Upload to a testing track, check it, promote to production, with release notes.
