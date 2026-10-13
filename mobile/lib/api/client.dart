import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import 'models.dart';

/// Where the API lives. Build with
/// `--dart-define=API_BASE=http://10.0.2.2:8000/api/v1` to use a local backend
/// from the Android emulator.
const apiBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: 'https://class.bitstreamhq.com/api/v1',
);

/// The website the API belongs to, for links out of the app.
String get siteUrl => apiBase.replaceFirst(RegExp(r'/api/v1/?$'), '');

/// An error carrying the backend's `{detail, code}` shape, or a network failure.
class ApiError implements Exception {
  const ApiError(this.message, {this.status = 0, this.code = 'error'});

  final String message;
  final int status;
  final String code;

  bool get offline => code == 'offline';

  @override
  String toString() => message;
}

/// The ClassTrack API, signed in with a bearer token.
///
/// The backend sets its session as a cookie for the browser and accepts the
/// same token as `Authorization: Bearer`, so the app reads it off the sign-in
/// response and sends it as a header.
class Api {
  Api({this.baseUrl = apiBase});

  final String baseUrl;
  final http.Client _http = http.Client();

  String? token;

  /// Called when a signed-in request comes back 401: the session ended.
  void Function()? onUnauthorized;

  Uri _uri(String path, [Map<String, Object?>? query]) {
    final q = <String, String>{};
    query?.forEach((k, v) {
      if (v != null && v != '') q[k] = '$v';
    });
    final uri = Uri.parse('$baseUrl$path');
    return q.isEmpty ? uri : uri.replace(queryParameters: q);
  }

  Future<http.Response> _send(String method, String path, {Object? body, Map<String, Object?>? query}) async {
    final req = http.Request(method, _uri(path, query));
    req.headers['Accept'] = 'application/json';
    if (token != null) req.headers['Authorization'] = 'Bearer $token';
    if (body != null) {
      req.headers['Content-Type'] = 'application/json';
      req.body = jsonEncode(body);
    }
    try {
      return await http.Response.fromStream(await _http.send(req).timeout(const Duration(seconds: 20)));
    } on SocketException {
      throw const ApiError('No connection. Check your internet and try again.', code: 'offline');
    } on TimeoutException {
      throw const ApiError('The server took too long to answer. Try again.', code: 'offline');
    } on http.ClientException {
      throw const ApiError('No connection. Check your internet and try again.', code: 'offline');
    }
  }

  dynamic _decode(http.Response res) {
    final text = utf8.decode(res.bodyBytes);
    dynamic body;
    try {
      body = text.isEmpty ? null : jsonDecode(text);
    } on FormatException {
      body = null;
    }
    if (res.statusCode >= 200 && res.statusCode < 300) return body;

    final signedIn = token != null;
    if (res.statusCode == 401 && signedIn) onUnauthorized?.call();
    throw ApiError(
      _detail(body) ?? 'Request failed (${res.statusCode}).',
      status: res.statusCode,
      code: (body is Map ? body['code'] as String? : null) ?? 'error',
    );
  }

  /// FastAPI says what went wrong as a string, or as a list of field errors.
  static String? _detail(dynamic body) {
    if (body is! Map) return null;
    final d = body['detail'];
    if (d is String) return d;
    if (d is List && d.isNotEmpty) {
      return d.map((e) => e is Map ? (e['msg'] ?? '').toString().replaceFirst('Value error, ', '') : '$e').join('\n');
    }
    return null;
  }

  Future<dynamic> _get(String path, [Map<String, Object?>? query]) async =>
      _decode(await _send('GET', path, query: query));
  Future<dynamic> _post(String path, [Object? body]) async => _decode(await _send('POST', path, body: body ?? {}));
  Future<dynamic> _patch(String path, Object body) async => _decode(await _send('PATCH', path, body: body));

  List<T> _list<T>(dynamic raw, T Function(Json) of) => (raw as List).map((e) => of(e as Json)).toList();

  // --- auth -------------------------------------------------------------------

  /// `username` is an email address, a teacher's initial, or an employee ID.
  /// Returns the user and the session token.
  Future<(User, String)> login(String username, String password) async {
    final res = await _send('POST', '/auth/login', body: {'username': username, 'password': password});
    final user = User.fromJson(_decode(res) as Json);
    final cookie = res.headers['set-cookie'] ?? '';
    // "classtrack_session=<jwt>; HttpOnly; Max-Age=…": the first value is the token.
    final match = RegExp(r'^\s*[^=;,\s]+=([^;]+)').firstMatch(cookie);
    if (match == null) {
      throw const ApiError('Signed in, but the server sent no session. Try again.');
    }
    return (user, match.group(1)!);
  }

  Future<User> me() async => User.fromJson(await _get('/auth/me') as Json);
  Future<Profile> profile() async => Profile.fromJson(await _get('/auth/profile') as Json);
  Future<Profile> updateContactEmail(String email) async =>
      Profile.fromJson(await _patch('/auth/profile', {'contact_email': email}) as Json);
  Future<void> changePassword(String current, String next) async =>
      _post('/auth/password', {'current_password': current, 'new_password': next});

  // --- staff checking -----------------------------------------------------------

  Future<CheckingScreen> checkingRooms({String? date, String? slot}) async =>
      CheckingScreen.fromJson(await _get('/checking/rooms', {'date': date, 'slot': slot}) as Json);

  Future<CheckResponse> submitCheck(
    int instanceId, {
    required String outcome,
    String? arrivalTime,
    String? remark,
    String? reason,
  }) async =>
      CheckResponse.fromJson(await _post('/checking/$instanceId', {
        'outcome': outcome,
        'arrival_time': arrivalTime,
        'remark': remark,
        'reason': reason,
      }) as Json);

  /// A teacher's classes over a range, newest first: to find one to correct.
  Future<List<RoomRow>> searchChecking(String teacher, String from, String to) async =>
      _list(await _get('/checking/search', {'teacher': teacher, 'from': from, 'to': to}), RoomRow.fromJson);

  // --- a teacher's own classes ----------------------------------------------------

  Future<List<ClassInstance>> instances({String? date, bool? needsReschedule, int? limit}) async => _list(
        await _get('/instances', {'date': date, 'needs_reschedule': needsReschedule, 'limit': limit}),
        ClassInstance.fromJson,
      );

  Future<ClassInstance> instance(int id) async => ClassInstance.fromJson(await _get('/instances/$id') as Json);

  Future<TeacherReport> teacherReport(String teacher) async =>
      TeacherReport.fromJson(await _get('/reports/teacher', {'teacher': teacher, 'term': 'FULL'}) as Json);

  // --- reschedules and extra classes ----------------------------------------------

  Future<List<Makeup>> makeups() async => _list(await _get('/makeup'), Makeup.fromJson);

  Future<Makeup> completeMakeup(int id, {String? driveLink}) async =>
      Makeup.fromJson(await _post('/makeup/$id/complete', driveLink == null ? null : {'drive_link': driveLink}) as Json);

  Future<ConflictReport> checkConflict({
    required String date,
    String? timeSlot,
    String? startTime,
    String? room,
    String? section,
    String? courseCode,
  }) async =>
      ConflictReport.fromJson(await _post('/makeup/check-conflict', {
        'date': date,
        'time_slot': timeSlot,
        'start_time': startTime,
        'room': room,
        'section': section,
        'course_code': courseCode,
      }) as Json);

  Future<List<FreeRoom>> freeRooms(String date, String slot) async =>
      _list(await _get('/makeup/free-rooms', {'date': date, 'time_slot': slot}), FreeRoom.fromJson);

  Future<Makeup> createMakeup({
    required int originalInstanceId,
    required String mode,
    required String date,
    String? timeSlot,
    String? startTime,
    String? room,
    String? reason,
    String? driveLink,
  }) async =>
      Makeup.fromJson(await _post('/makeup', {
        'original_instance_id': originalInstanceId,
        'mode': mode,
        'date': date,
        'time_slot': timeSlot,
        'start_time': startTime,
        'room': room,
        'reason': reason,
        'drive_link': driveLink,
      }) as Json);

  Future<List<ExtraSection>> extraSections() async =>
      _list(await _get('/extra-classes/sections'), ExtraSection.fromJson);
  Future<List<ClassInstance>> extraClasses() async => _list(await _get('/extra-classes'), ClassInstance.fromJson);

  Future<ClassInstance> bookExtraClass({
    required String courseCode,
    required String section,
    required String date,
    required String timeSlot,
    required String room,
  }) async =>
      ClassInstance.fromJson(await _post('/extra-classes', {
        'course_code': courseCode,
        'section': section,
        'date': date,
        'time_slot': timeSlot,
        'room': room,
      }) as Json);

  Future<void> cancelExtraClass(int id) async => _post('/extra-classes/$id/cancel');

  // --- notifications ------------------------------------------------------------

  Future<List<AppNotification>> notifications({bool unread = false}) async =>
      _list(await _get('/notifications', {'unread': unread ? 'true' : null}), AppNotification.fromJson);
  Future<void> markRead(int id) async => _post('/notifications/$id/read');
  Future<void> markAllRead() async => _post('/notifications/read-all');
}
